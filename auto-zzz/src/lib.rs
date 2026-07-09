pub mod crypto;
pub mod cs_rand;
pub mod unk_util;

pub struct GameSniffer;

impl GameSniffer {
    pub fn new() -> Self {
        Self
    }

    pub fn receive_packet(&mut self, _bytes: Vec<u8>) -> Option<Vec<u8>> {
        None
    }
}

pub fn matches_achievement_packet(_bytes: &[u8]) -> Option<Vec<unk_util::Achievement>> {
    // Mock parsing for now
    Some(vec![
        unk_util::Achievement { id: 100101, status: 3, finish_timestamp: Some(1720051200) },
        unk_util::Achievement { id: 100102, status: 3, finish_timestamp: Some(1720051200) },
    ])
}
