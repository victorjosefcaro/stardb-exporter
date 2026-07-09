#[derive(Default)]
pub struct Achievement {
    pub id: u32,
    pub status: u32,
    pub finish_timestamp: Option<u32>,
}

pub fn matches_achievement_all_data_notify(_data: Vec<u8>) -> Option<Vec<Achievement>> {
    // Mock parsing for now
    Some(vec![
        Achievement { id: 100101, status: 3, finish_timestamp: Some(1720051200) },
        Achievement { id: 100102, status: 3, finish_timestamp: Some(1720051200) },
    ])
}
