use std::{
    fs::File,
    io::{BufRead, BufReader},
    path::PathBuf,
};

pub fn game_path() -> anyhow::Result<PathBuf> {
    let mut log_path = PathBuf::from(&std::env::var("APPDATA")?);
    log_path.pop();
    log_path.push("LocalLow");
    log_path.push("miHoYo");

    let mut log_path_cn = log_path.clone();

    log_path.push("ZenlessZoneZero");
    log_path_cn.push("绝区零");

    log_path.push("Player.log");
    log_path_cn.push("Player.log");

    let log_path = match (log_path.exists(), log_path_cn.exists()) {
        (true, _) => log_path,
        (_, true) => log_path_cn,
        _ => return Err(anyhow::anyhow!("Can't find log file")),
    };

    for line in BufReader::new(File::open(log_path)?).lines() {
        let Ok(line) = line else {
            break;
        };

        if let Some(line) = line.strip_prefix("[Subsystems] Discovering subsystems at path ") {
            let mut path = PathBuf::from(line);

            path.pop();

            return Ok(path);
        }
    }

    Err(anyhow::anyhow!("Couldn't find game path"))
}

use auto_zzz::{GameSniffer, matches_achievement_packet};
use std::sync::mpsc;
use std::time::{Duration, Instant};

pub fn sniff(
    achievement_ids: &[u32],
    device_rx: &mpsc::Receiver<Vec<u8>>,
) -> anyhow::Result<Vec<u32>> {
    let mut sniffer = GameSniffer::new();
    let mut achievements = Vec::new();
    let timeout = Duration::from_secs(300); // 5 minutes timeout
    let start_time = Instant::now();

    while start_time.elapsed() < timeout {
        if let Ok(packet) = device_rx.recv_timeout(Duration::from_millis(100)) {
            if let Some(decrypted) = sniffer.receive_packet(packet) {
                if let Some(read_achievements) = matches_achievement_packet(&decrypted) {
                    tracing::info!("Found achievement packet");
                    
                    if !achievements.is_empty() {
                        achievements.clear();
                    }

                    for achievement in read_achievements {
                        if achievement_ids.contains(&achievement.id)
                            && (achievement.status == 2 || achievement.status == 3)
                        {
                            achievements.push(achievement.id);
                        }
                    }

                    if !achievements.is_empty() {
                        break;
                    }
                }
            }
        }
    }

    if achievements.is_empty() {
        return Err(anyhow::anyhow!("No achievements found"));
    }

    Ok(achievements)
}
