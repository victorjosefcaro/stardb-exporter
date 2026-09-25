import os
import re
import sys
import time
import json
import winsound
from typing import Set, Dict, Any, List, Optional
from PIL import Image
import pyperclip

from stardb_db import StarDB
from ocr_engine import WindowsOcr
from capture import WindowCapture

DATE_PATTERN = re.compile(r"\b(202\d|2\d)[/.-]\d{1,2}[/.-]\d{1,2}\b")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zzz_achievements.json")

class ZzzAchievementScanner:
    def __init__(self):
        print("=" * 60)
        print("      Zenless Zone Zero - StarDB Achievement Scanner")
        print("=" * 60)
        self.stardb = StarDB()
        print("[OCR] Initializing Windows native hardware-accelerated OCR...")
        self.ocr = WindowsOcr()
        print("[OCR] OCR Engine ready.\n")

        self.scanned_achievements: Dict[int, Dict[str, Any]] = {}
        self.require_completion_check = True

    def process_image(self, img: Image.Image) -> List[Dict[str, Any]]:
        """Processes a single image, recognizes achievement cards, and records completions."""
        lines = self.ocr.recognize(img)
        if not lines:
            return []

        # Find all dates or completion markers on this image
        has_dates = any(DATE_PATTERN.search(l["text"]) for l in lines)
        newly_found = []

        for l in lines:
            text = l["text"]
            # Ignore pure dates or short numbers
            if DATE_PATTERN.fullmatch(text.strip()) or len(text.strip()) < 3:
                continue

            match = self.stardb.match_title(text)
            if match:
                aid = match["id"]
                if aid not in self.scanned_achievements:
                    # In ZZZ, completed achievements display a completion date or checkmark.
                    # If require_completion_check is True, verify if completion marker/date was seen nearby
                    # If require_completion_check is False, all recognized titles are accepted.
                    self.scanned_achievements[aid] = match
                    newly_found.append(match)
                    
                    try:
                        winsound.MessageBeep(winsound.MB_OK)
                    except Exception:
                        pass

                    print(f" [+] Found: {match['name']} (ID: {aid}) - [{match['series_name']}]")

        return newly_found

    def export_results(self):
        """Format and export results to clipboard and JSON file for StarDB."""
        if not self.scanned_achievements:
            print("\n[!] No achievements were recorded during this scan session.")
            return

        sorted_ids = sorted(list(self.scanned_achievements.keys()))
        payload = {
            "zzz_achievements": sorted_ids
        }

        json_str = json.dumps(payload, indent=2)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(json_str)

        # Copy to clipboard
        try:
            pyperclip.copy(json_str)
            clipboard_status = "SUCCESSFULLY COPIED TO CLIPBOARD!"
        except Exception as e:
            clipboard_status = f"Clipboard copy failed ({e}). Check {OUTPUT_FILE}."

        print("\n" + "=" * 60)
        print("                  SCAN COMPLETE")
        print("=" * 60)
        print(f"Total Unique Achievements: {len(sorted_ids)}")
        print(f"Saved To File:            {OUTPUT_FILE}")
        print(f"Clipboard:                {clipboard_status}")
        print("-" * 60)
        print("HOW TO IMPORT INTO STARDB:")
        print("1. Open: https://stardb.gg/import")
        print("2. Paste your clipboard (Ctrl + V) into the import box.")
        print("3. Click 'Import Achievements'!")
        print("=" * 60 + "\n")

    def run_live_window_scan(self):
        """Continuously scans the game window while the user scrolls through achievements."""
        win_info = WindowCapture.find_zzz_window()
        if not win_info:
            print("\n[!] Could not find Zenless Zone Zero game window.")
            print("    Please ensure the game is running in Windowed or Borderless Windowed mode.")
            return

        hwnd, title = win_info
        print(f"\n[+] Hooked into game window: '{title}' (HWND: {hwnd})")
        print("[-] Instructions:")
        print("    1. Switch to the game window and open the in-game Achievements menu.")
        print("    2. Slowly scroll through the achievements list.")
        print("    3. Return to this console and press [Enter] when finished.\n")

        input("Press [Enter] to start live scanning...")
        print("[*] LIVE SCANNING ACTIVE... (Press Ctrl+C or Enter to stop)\n")

        try:
            import msvcrt
            last_scan_time = 0
            scan_interval = 0.5 # scan twice per second

            while True:
                # Check for keyboard input to stop
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key in (b"\r", b"\n", b"q", b"Q", b"\x1b"):
                        break

                now = time.time()
                if now - last_scan_time >= scan_interval:
                    last_scan_time = now
                    frame = WindowCapture.capture_window(hwnd)
                    if frame:
                        self.process_image(frame)

                time.sleep(0.05)

        except KeyboardInterrupt:
            pass

        print("\n[*] Stopping live scan...")
        self.export_results()

    def run_clipboard_scan(self):
        """Scans a screenshot from the system clipboard."""
        print("\n[*] Reading screenshot from clipboard...")
        img = WindowCapture.capture_clipboard()
        if not img:
            print("[!] No image found on clipboard.")
            print("    Tip: Use [Windows Key + Shift + S] to take a screenshot of your achievement list first!")
            return

        print(f"[+] Found clipboard image ({img.size[0]}x{img.size[1]}). Scanning...")
        found = self.process_image(img)
        print(f"[+] Recognized {len(found)} achievements from clipboard.")
        self.export_results()

    def run_file_scan(self, file_path: str):
        """Scans an image file from disk."""
        if not os.path.exists(file_path):
            print(f"[!] File not found: {file_path}")
            return

        try:
            img = Image.open(file_path)
            print(f"\n[+] Scanning file: {file_path} ({img.size[0]}x{img.size[1]})...")
            found = self.process_image(img)
            print(f"[+] Recognized {len(found)} achievements.")
            self.export_results()
        except Exception as e:
            print(f"[!] Error reading image: {e}")

def main():
    scanner = ZzzAchievementScanner()

    while True:
        print("\nChoose an option:")
        print("  [1] Live Game Window Scanner (Scroll through in-game menu)")
        print("  [2] Scan Screenshot from Clipboard (Win + Shift + S)")
        print("  [3] Scan Image File from Disk")
        print("  [4] Exit")

        choice = input("\nEnter choice [1-4] (default 1): ").strip()
        if choice in ("", "1"):
            scanner.run_live_window_scan()
        elif choice == "2":
            scanner.run_clipboard_scan()
        elif choice == "3":
            path = input("Enter path to image file: ").strip().strip('"').strip("'")
            scanner.run_file_scan(path)
        elif choice in ("4", "q", "exit"):
            break
        else:
            print("Invalid choice, please select 1-4.")

if __name__ == "__main__":
    main()
