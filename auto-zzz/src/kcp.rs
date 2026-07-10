use std::time::SystemTime;

use kcp::{get_conv, Kcp, KCP_OVERHEAD};
use tracing::{error, info, instrument, span, trace, warn, Level};

use crate::bytes_as_hex;

pub(crate) struct KcpSniffer {
    conv_id: u32,
    kcp: Kcp<Vec<u8>>,
    time_start: SystemTime,
}

impl KcpSniffer {
    #[instrument(skip(segment))]
    pub fn try_new(segment: &[u8]) -> Option<Self> {
        validate_kcp_segment(segment).map(Self::new).or_else(|| {
            error!("could not create new kcp instance");
            None
        })
    }

    #[instrument]
    fn new(conv_id: u32) -> Self {
        info!("new connection, created new kcp instance");

        KcpSniffer {
            conv_id,
            kcp: new_kcp(conv_id),
            time_start: SystemTime::now(),
        }
    }

    #[instrument(skip_all, fields(conv_id = self.conv_id, len = segments.len()))]
    pub fn receive_segments(&mut self, segments: &[u8]) -> Vec<Vec<u8>> {
        let Some(conv_id) = validate_kcp_segment(segments) else {
            return Vec::new();
        };

        trace!("message data: {}", bytes_as_hex(segments));

        if conv_id != self.conv_id {
            warn!(
                expected = self.conv_id,
                "packet did not belong to conversation"
            );
            return Vec::new();
        }

        // ZZZ KCP uses the standard 28-byte header layout — no extra bytes to strip.
        // Confirmed from remielle/gamesv/src/kcp/Header.zig: size=28, standard layout.
        match self.kcp.input(segments) {
            Ok(size) => trace!(size, "input successful"),
            Err(e) => warn!("could not input to kcp: {e}"),
        }

        let mut recv = Vec::new();
        while let Ok(size) = self.kcp.peeksize() {
            let span = span!(Level::TRACE, "receiving", size);
            let _enter = span.enter();

            let mut bytes = vec![0; size];

            match self.kcp.recv(&mut bytes) {
                Ok(_size) => {
                    recv.push(bytes);
                }
                Err(e) => {
                    warn!(%e, "could not receive kcp bytes");
                }
            }
        }

        if let Err(e) = self.kcp.update(self.clock()) {
            warn!(%e, "could not update kcp state");
        }

        recv
    }

    #[inline]
    fn clock(&self) -> u32 {
        SystemTime::now()
            .duration_since(self.time_start)
            .expect("time went backwards")
            .as_millis() as u32
    }
}

#[inline]
fn new_kcp(conv_id: u32) -> Kcp<Vec<u8>> {
    let mut kcp = Kcp::new(conv_id, Vec::new());
    kcp.set_wndsize(1024, 1024);
    kcp
}

fn validate_kcp_segment(payload: &[u8]) -> Option<u32> {
    if payload.len() <= KCP_OVERHEAD {
        warn!(
            len = payload.len(),
            data = bytes_as_hex(payload),
            "kcp header was too short"
        );
        return None;
    }
    Some(get_conv(payload))
}
