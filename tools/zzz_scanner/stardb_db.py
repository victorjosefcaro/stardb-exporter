import os
import re
import json
import urllib.request
from difflib import SequenceMatcher
from typing import Optional, Dict, List, Any

API_URL = "https://stardb.gg/api/zzz/achievements"
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stardb_zzz_achievements.json")

def normalize_text(text: str) -> str:
    """Normalize text by converting to lowercase and stripping punctuation/extra spaces."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return " ".join(cleaned.split())

class StarDB:
    def __init__(self):
        self.achievements: List[Dict[str, Any]] = []
        self.id_map: Dict[int, Dict[str, Any]] = {}
        self.normalized_map: Dict[str, Dict[str, Any]] = {}
        self.load_database()

    def load_database(self):
        """Load achievements from local JSON cache, or download from StarDB API."""
        if not os.path.exists(DB_FILE):
            print(f"[StarDB] Cache not found. Downloading live ZZZ achievements from {API_URL}...")
            try:
                req = urllib.request.Request(API_URL, headers={"User-Agent": "stardb-exporter/2.20"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw_data = resp.read().decode("utf-8")
                    data = json.loads(raw_data)
                    with open(DB_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    print(f"[StarDB] Successfully downloaded and cached {len(data)} achievements.")
            except Exception as e:
                print(f"[StarDB] Warning: Failed to fetch online data: {e}")

        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                self.achievements = json.load(f)
            
            for item in self.achievements:
                aid = item.get("id")
                name = item.get("name", "")
                norm_name = normalize_text(name)
                
                self.id_map[aid] = item
                self.normalized_map[norm_name] = item

            print(f"[StarDB] Loaded {len(self.achievements)} achievements into memory.")
        else:
            raise FileNotFoundError("Could not load StarDB achievement database.")

    def match_title(self, ocr_text: str, min_confidence: float = 0.82) -> Optional[Dict[str, Any]]:
        """Match an OCR-detected line of text against known StarDB achievement titles."""
        norm_ocr = normalize_text(ocr_text)
        if len(norm_ocr) < 3:
            return None

        # Exact normalized match
        if norm_ocr in self.normalized_map:
            return self.normalized_map[norm_ocr]

        # Check substring containment
        for norm_title, item in self.normalized_map.items():
            if len(norm_title) > 6 and (norm_title in norm_ocr or norm_ocr in norm_title):
                return item

        # Fuzzy match using SequenceMatcher
        best_match = None
        best_ratio = 0.0

        for norm_title, item in self.normalized_map.items():
            ratio = SequenceMatcher(None, norm_ocr, norm_title).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = item

        if best_ratio >= min_confidence:
            return best_match

        return None

if __name__ == "__main__":
    db = StarDB()
    test_title = "Movie Lovers Cant be Bad Guys"
    match = db.match_title(test_title)
    if match:
        print(f"Matched '{test_title}' -> ID {match['id']} ('{match['name']}') in '{match['series_name']}'")
    else:
        print("No match found.")
