use std::collections::HashMap;

use protobuf::Message;
use protobuf::UnknownValueRef::*;
use tracing::info;

use crate::crypto::decrypt_client_rand_key;
use crate::gen::protos::Unk;

#[derive(Default)]
pub struct Achievement {
    pub id: u32,
    pub status: u32,
    pub finish_timestamp: Option<u32>,
}

pub fn matches_achievement_all_data_notify(data: Vec<u8>) -> Option<Vec<Achievement>> {
    if data.len() < 1000 {
        return None;
    }
    let d_msg = Unk::parse_from_bytes(&data);
    match d_msg {
        Ok(d_msg) => {
            let mut achievement_list: Vec<HashMap<u32, u64>> = vec![];
            let mut list_tag: Option<u32> = None;
            let unknown_fields = d_msg.unknown_fields();
            for (field_number, field_data) in unknown_fields.iter() {
                match field_data {
                    LengthDelimited(bytes) => {
                        let d_msg_inside = Unk::parse_from_bytes(bytes);
                        let unknown_fields_inside;
                        match d_msg_inside {
                            Ok(d_msg_inside) => {
                                unknown_fields_inside = d_msg_inside.unknown_fields().clone();
                                if unknown_fields_inside.clone().iter().count() <= 1 {
                                    continue; // Only one field inside -> not Achievement
                                }
                            }
                            _ => continue,
                        }
                        let mut achievement_map: HashMap<u32, u64> = HashMap::new();
                        for (field_number_inside, field_data_inside) in
                            unknown_fields_inside.iter()
                        {
                            match field_data_inside {
                                Varint(value) => {
                                    let _ = achievement_map.insert(field_number_inside, value);
                                }
                                _ => {
                                    return None; // Not an achievement packet
                                }
                            }
                        }
                        achievement_list.push(achievement_map);
                        match list_tag {
                            Some(x) => {
                                if field_number != x {
                                    return None; // Multiple tags — not expected
                                }
                            }
                            None => list_tag = Some(field_number),
                        }
                    }
                    _ => (),
                }
            }
            if achievement_list.is_empty() {
                return None;
            }
            info!("Collected some possible achievements, trying to find field tags...");

            let mut tag_finish_timestamp = None;
            let mut tag_id = None;
            let mut possible_tag_status: Vec<u32> =
                achievement_list[0].clone().into_keys().collect();
            for achievement_map in &achievement_list {
                for (&tag, &value) in achievement_map.iter() {
                    if value > 1_420_066_800 {
                        // Wed Dec 31 2014 23:00:00 GMT+0000 — likely a unix timestamp
                        tag_finish_timestamp = match tag_finish_timestamp {
                            Some(t) => {
                                if t != tag {
                                    return None;
                                } else {
                                    tag_finish_timestamp
                                }
                            }
                            _ => Some(tag),
                        }
                    }
                    // TODO: Replace 0 with a real common ZZZ achievement ID once known (e.g. from Hakush.in)
                    // The anchor is used to identify which protobuf field contains achievement IDs.
                    if value == 0 {
                        tag_id = Some(tag)
                    }
                    if possible_tag_status.contains(&tag) {
                        if value > 3 {
                            possible_tag_status.retain(|&x| x != tag)
                        }
                    }
                }
            }

            if tag_finish_timestamp.is_none() || tag_id.is_none() || possible_tag_status.is_empty()
            {
                return None;
            }

            let tag_status = possible_tag_status[0];
            let mut achievements: Vec<Achievement> = vec![];
            for achievement_map in &achievement_list {
                let mut achievement = Achievement {
                    ..Default::default()
                };
                for (&tag, &value) in achievement_map.iter() {
                    if tag_finish_timestamp.unwrap() == tag {
                        achievement.finish_timestamp = Some(value as u32);
                    }
                    if tag_id.unwrap() == tag {
                        achievement.id = value as u32;
                    }
                    if tag_status == tag {
                        achievement.status = value as u32;
                    }
                }
                achievements.push(achievement)
            }
            assert!(!achievements.is_empty());
            Some(achievements)
        }
        _ => None,
    }
}

/// Try to extract client_rand_key from a PlayerGetTokenCsReq body.
///
/// Scans all LengthDelimited unknown fields for 128-byte RSA ciphertext encoded as base64,
/// then decrypts using the server private key embedded in crypto.rs.
pub fn matches_player_get_token_cs_req(data: &[u8]) -> Option<u64> {
    let d_msg = Unk::parse_from_bytes(data).ok()?;
    for (_field_number, field_data) in d_msg.unknown_fields().iter() {
        if let LengthDelimited(bytes) = field_data {
            // The field is raw bytes — try base64-decoding them as a string
            if let Ok(s) = std::str::from_utf8(bytes) {
                if let Some(key) = decrypt_client_rand_key(s) {
                    return Some(key);
                }
            }
        }
    }
    None
}

/// Try to extract server_rand_key from a PlayerGetTokenScRsp body.
///
/// TODO: This requires the client private key which is not present in the repository.
/// Until it is available, this always returns None.
pub fn matches_player_get_token_sc_rsp(_data: &[u8]) -> Option<u64> {
    // TODO: Decrypt server_rand_key using the client private key (not in repo).
    // The server_rand_key is RSA-encrypted with the client public key,
    // base64-encoded, and found in a LengthDelimited unknown field.
    // Once the client private key is available, follow the same pattern as
    // matches_player_get_token_cs_req but decrypt with the client key.
    None
}
