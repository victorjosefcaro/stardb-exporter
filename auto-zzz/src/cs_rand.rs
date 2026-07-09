const N: usize = 312;
const M: usize = 156;
const R: u64 = 31;
const A: u64 = 0xB5026F5AA96619E9;
const U: u64 = 29;
const D: u64 = 0x5555555555555555;
const S: u64 = 17;
const B: u64 = 0x71D67FFFEDA60000;
const T: u64 = 37;
const C: u64 = 0xFFF7EEE000000000;
const L: u64 = 43;
const F: u64 = 6364136223846793005;

pub struct Csprng {
    array: [u64; N],
    index: usize,
}

impl Csprng {
    pub fn new(seed: u64) -> Self {
        let mut mt = Self {
            array: [0; N],
            index: N,
        };

        let mut prev_value = seed;
        mt.array[0] = prev_value;
        for i in 1..N {
            prev_value = (i as u64).wrapping_add(
                F.wrapping_mul(prev_value ^ (prev_value >> 62))
            );
            mt.array[i] = prev_value;
        }
        mt
    }

    pub fn next(&mut self) -> u64 {
        let mag01 = [0, A];
        let lm = (1 << R) - 1;
        let um = !lm;

        if self.index >= N {
            let mut i = 0;

            while i < N - M {
                let x = (self.array[i] & um) | (self.array[i + 1] & lm);
                self.array[i] = self.array[i + M] ^ (x >> 1) ^ mag01[(x & 1) as usize];
                i += 1;
            }

            while i < N - 1 {
                let x = (self.array[i] & um) | (self.array[i + 1] & lm);
                self.array[i] = self.array[i + M - N] ^ (x >> 1) ^ mag01[(x & 1) as usize];
                i += 1;
            }
            
            let x = (self.array[i] & um) | (self.array[0] & lm);
            self.array[i] = self.array[M - 1] ^ (x >> 1) ^ mag01[(x & 1) as usize];

            self.index = 0;
        }

        let mut x = self.array[self.index];
        self.index += 1;

        x ^= (x >> U) & D;
        x ^= (x << S) & B;
        x ^= (x << T) & C;
        x ^= x >> L;

        x
    }
}
