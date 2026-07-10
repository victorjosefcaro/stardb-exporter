//! Parse network packets transmitted between ZZZ game client and server.
//!
//! # Protocol Stack
//! 1. **Ethernet/IP/UDP** — parsed with [`etherparse`]
//! 2. **KCP** — standard 28-byte header (no extra prefix bytes in ZZZ)
//! 3. **Game command** — `[magic(4)][cmd_id(2)][head_len(2)][body_len(4)][head][body][tail(4)]`
//! 4. **XOR** — stateful 4096-byte pad, offset advances across all packets
//! 5. **Protobuf** — body decoded with generated types in [`gen::protos`]

use std::fmt;
use std::fmt::Write;

use base64::prelude::BASE64_STANDARD;
use base64::Engine;
use tracing::{error, info, info_span, trace, warn};

use crate::connection::{parse_udp, validate_ports};
use crate::kcp::KcpSniffer;
use crate::unk_util::{
    matches_achievement_all_data_notify, matches_player_get_token_cs_req,
    matches_player_get_token_sc_rsp, Achievement,
};
use crate::xorpad::Xorpad;

fn bytes_as_hex(bytes: &[u8]) -> String {
    bytes.iter().fold(String::new(), |mut output, b| {
        let _ = write!(output, "{b:02x}");
        output
    })
}

pub mod gen;
pub mod xorpad;

mod connection;
mod crypto;
mod cs_rand;
mod kcp;
mod unk_util;

// ZZZ uses UDP — exact port range unknown; use wide net for now.
// TODO: Replace with real ZZZ port range once confirmed via Wireshark.
const PORTS: [u16; 0] = [];

/// Top-level packet type.
pub enum GamePacket {
    Connection(ConnectionPacket),
    Commands(Vec<GameCommand>),
}

/// Connection-layer events.
pub enum ConnectionPacket {
    HandshakeRequested,
    Disconnected,
    HandshakeEstablished,
    SegmentData(PacketDirection, Vec<u8>),
}

/// A decrypted game command extracted from the KCP stream.
///
/// ## Wire layout (after XOR decryption of body)
/// | Bytes            | Field       |
/// |------------------|-------------|
/// | 0..4             | header magic `0x01234567` |
/// | 4..6             | `cmd_id`    |
/// | 6..8             | `head_len`  |
/// | 8..12            | `body_len`  |
/// | 12..12+head_len  | proto_header (plaintext) |
/// | 12+head_len..+body_len | proto_data (was XOR'd on wire) |
/// | end..end+4       | tail magic `0x89ABCDEF` |
#[derive(Clone)]
pub struct GameCommand {
    pub command_id: u16,
    #[allow(unused)]
    pub header_len: u16,
    #[allow(unused)]
    pub data_len: u32,
    #[allow(unused)]
    pub proto_header: Vec<u8>,
    pub proto_data: Vec<u8>,
}

impl GameCommand {
    const HEADER_LEN: usize = 12;
    const TAIL_LEN: usize = 4;
    const HEADER_MAGIC: [u8; 4] = [0x01, 0x23, 0x45, 0x67];
    const TAIL_MAGIC: u32 = 0x89AB_CDEF;

    pub fn try_new(bytes: Vec<u8>) -> Option<Self> {
        let header_overhead = Self::HEADER_LEN + Self::TAIL_LEN;
        if bytes.len() < header_overhead {
            warn!(len = bytes.len(), "game command header incomplete");
            return None;
        }

        if bytes[0..4] != Self::HEADER_MAGIC {
            error!("Header magic mismatch");
            return None;
        }

        let command_id = u16::from_be_bytes(bytes[4..6].try_into().unwrap());
        let header_len = u16::from_be_bytes(bytes[6..8].try_into().unwrap());
        let data_len = u32::from_be_bytes(bytes[8..12].try_into().unwrap());

        let data_start = 12 + header_len as usize;
        let data_end = data_start + data_len as usize;

        if data_end + Self::TAIL_LEN > bytes.len() {
            warn!(len = bytes.len(), "game command buffer too short");
            return None;
        }

        let tail = u32::from_be_bytes(bytes[data_end..data_end + 4].try_into().unwrap());
        if tail != Self::TAIL_MAGIC {
            error!(tail, "Tail magic mismatch");
            return None;
        }

        let proto_header = bytes[12..data_start].to_vec();
        let proto_data = bytes[data_start..data_end].to_vec();

        Some(GameCommand {
            command_id,
            header_len,
            data_len,
            proto_header,
            proto_data,
        })
    }

    pub fn parse_proto<T: protobuf::Message>(&self) -> protobuf::Result<T> {
        T::parse_from_bytes(&self.proto_data)
    }
}

impl fmt::Debug for GameCommand {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("GameCommand")
            .field("command_id", &self.command_id)
            .field("header_len", &self.header_len)
            .field("data_len", &self.data_len)
            .finish()
    }
}

/// Which direction a packet is travelling.
#[derive(Debug, Clone, Copy, Hash, PartialEq, Eq)]
pub enum PacketDirection {
    Sent,
    Received,
}

/// Which XOR key phase we are in.
pub enum Key {
    /// Uses the embedded dispatch-phase initial xorpad.
    Dispatch,
    /// Uses the session xorpad derived from `client_rand_key XOR server_rand_key`.
    Session,
}

#[derive(Default)]
enum KeyState {
    #[default]
    Uninitialized,
    Dispatch,
    Session,
}

/// Sniffs ZZZ UDP traffic and reassembles + decrypts game commands.
#[derive(Default)]
pub struct GameSniffer {
    sent_kcp: Option<KcpSniffer>,
    recv_kcp: Option<KcpSniffer>,
    xorpad: Option<Xorpad>,
    key_state: KeyState,
    client_rand_key: Option<u64>,
}

impl GameSniffer {
    /// Creates a new sniffer, pre-loaded with the dispatch-phase XOR pad.
    pub fn new() -> Self {
        Self {
            xorpad: Some(Xorpad::initial()),
            key_state: KeyState::Dispatch,
            ..Default::default()
        }
    }

    /// Process a raw ethernet frame.
    ///
    /// Returns `Some(proto_data)` for the first command that passes the achievement
    /// heuristic, or for every decrypted command body when the anchor ID is unknown.
    /// Returns `None` if the packet is not ZZZ game data.
    pub fn receive_packet(&mut self, bytes: Vec<u8>) -> Option<Vec<u8>> {
        // Parse UDP layer (ZZZ ports unknown — accept all UDP)
        let (udp, payload) = parse_udp(bytes)?;

        // Classify as connection event or data segment.
        // Since PORTS is empty, validate_ports always returns None.
        // For ZZZ we treat every UDP payload as potential KCP segment data.
        let direction = if PORTS.is_empty() {
            // Heuristic: payload from server → Received; from client → Sent.
            // We can't know for sure without ports, so treat all as Received.
            PacketDirection::Received
        } else {
            validate_ports(&PORTS, udp)?
        };

        // Short payloads are connection handshake frames, not KCP data.
        if payload.len() <= 20 {
            return None;
        }

        // Pass through KCP reassembly.
        let kcp = match direction {
            PacketDirection::Sent => &mut self.sent_kcp,
            PacketDirection::Received => &mut self.recv_kcp,
        };

        if kcp.is_none() {
            let new_kcp = KcpSniffer::try_new(&payload)?;
            *kcp = Some(new_kcp);
        }

        if let Some(kcp) = kcp {
            for data in kcp.receive_segments(&payload) {
                if let Some(command) = self.receive_command(data) {
                    trace!(
                        data = BASE64_STANDARD.encode(&command.proto_data),
                        "command proto_data"
                    );
                    // Return the proto_data so the caller can run matches_achievement_packet.
                    return Some(command.proto_data);
                }
            }
        }

        None
    }

    /// Decrypt one KCP payload into a [`GameCommand`], updating the XOR pad state.
    ///
    /// Only the body portion (`[12+head_len .. 12+head_len+body_len]`) was XOR'd on the wire;
    /// the fixed header and head bytes are plaintext.
    fn receive_command(&mut self, kcp_bytes: Vec<u8>) -> Option<GameCommand> {
        if kcp_bytes.len() < GameCommand::HEADER_LEN + GameCommand::TAIL_LEN {
            return None;
        }

        if kcp_bytes[0..4] != GameCommand::HEADER_MAGIC {
            return None;
        }

        let header_len =
            u16::from_be_bytes(kcp_bytes[6..8].try_into().ok()?) as usize;
        let body_len =
            u32::from_be_bytes(kcp_bytes[8..12].try_into().ok()?) as usize;
        let body_start = 12 + header_len;
        let body_end = body_start + body_len;

        if body_end + 4 > kcp_bytes.len() {
            return None;
        }

        let mut bytes = kcp_bytes;

        // XOR only the body (head and magic are plaintext).
        if let Some(xorpad) = &mut self.xorpad {
            xorpad.apply(&mut bytes[body_start..body_end]);
        }

        let command = GameCommand::try_new(bytes)?;
        let span = info_span!("command", ?command);
        let _enter = span.enter();
        info!("received");

        // --- Session key negotiation ---

        // Try to extract client_rand_key from PlayerGetTokenCsReq.
        if matches!(self.key_state, KeyState::Dispatch) {
            if let Some(client_rand_key) =
                matches_player_get_token_cs_req(&command.proto_data)
            {
                self.client_rand_key = Some(client_rand_key);
                info!(client_rand_key, "found client_rand_key from PlayerGetTokenCsReq");
            }
        }

        // Try to extract server_rand_key from PlayerGetTokenScRsp.
        // TODO: requires client private key (not in repo) — currently always None.
        if matches!(self.key_state, KeyState::Dispatch) {
            if let Some(server_rand_key) =
                matches_player_get_token_sc_rsp(&command.proto_data)
            {
                if let Some(client_rand_key) = self.client_rand_key {
                    let seed = client_rand_key ^ server_rand_key;
                    info!(seed, "derived session seed, switching to session xorpad");
                    self.xorpad = Some(Xorpad::seeded(seed));
                    self.key_state = KeyState::Session;
                }
            }
        }

        Some(command)
    }
}

/// Run the heuristic achievement parser on raw proto body bytes.
///
/// # Note
/// The anchor achievement ID in ZZZ is currently a TODO placeholder — see
/// `unk_util::matches_achievement_all_data_notify` for details.
pub fn matches_achievement_packet(bytes: &[u8]) -> Option<Vec<Achievement>> {
    matches_achievement_all_data_notify(bytes.to_vec())
}
