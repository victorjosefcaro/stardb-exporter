use crate::cs_rand::Csprng;

pub const INITIAL_XORPAD: &[u8; 4096] =
    include_bytes!("../../remielle/gamesv/initial_xorpad.bytes");

pub struct Xorpad {
    pub bytes: [u8; 4096],
    pub offset: usize,
}

impl Xorpad {
    /// Creates a Xorpad using the embedded dispatch-phase initial xorpad bytes.
    pub fn initial() -> Self {
        Self {
            bytes: *INITIAL_XORPAD,
            offset: 0,
        }
    }

    /// Creates a Xorpad by seeding MT19937-64 with `seed`, generating 512 u64 values,
    /// and writing each as big-endian u64 bytes into the 4096-byte buffer.
    pub fn seeded(seed: u64) -> Self {
        let mut rng = Csprng::new(seed);
        let mut bytes = [0u8; 4096];
        for i in 0..512 {
            let val = rng.next();
            let be = val.to_be_bytes();
            bytes[i * 8..(i + 1) * 8].copy_from_slice(&be);
        }
        Self { bytes, offset: 0 }
    }

    /// XORs each byte in `data` with the pad at the current offset, then advances the offset.
    /// The offset wraps around at 4096 (stateful across calls).
    pub fn apply(&mut self, data: &mut [u8]) {
        for (i, byte) in data.iter_mut().enumerate() {
            *byte ^= self.bytes[(self.offset + i) % 4096];
        }
        self.offset = (self.offset + data.len()) % 4096;
    }
}
