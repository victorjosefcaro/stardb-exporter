import os
import re
import sys
import time
import json
import winsound
from typing import Set, Dict, Any, List, Optional, Tuple
from PIL import Image
import pyperclip

from stardb_db import StarDB
from ocr_engine import WindowsOcr
from capture import WindowCapture
from automation import InputController, WindowController

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DATE_PATTERN = re.compile(
    r"\b(?:202\d|2\d)\s*[\/.\-]\s*\d{1,2}\s*[\/.\-]\s*\d{1,2}\b|"
    r"\b\d{1,2}\s*[\/.\-]\s*\d{1,2}\s*[\/.\-]\s*(?:202\d|2\d)\b"
)
OUTPUT_FILE = os.path.join(APP_DIR, "zzz_achievements.json")

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
        self.skipped_incomplete: Set[int] = set()
        self.require_completion_date = True

    def process_image(self, img: Image.Image) -> Tuple[List[Dict[str, Any]], Set[str]]:
        """
        Processes a single image, recognizes achievement cards, and records completions.
        Returns:
            newly_found: list of newly discovered achievements
            visible_titles: set of all achievement titles recognized on this frame
        """
        lines = self.ocr.recognize(img)
        if not lines:
            return [], set()

        # Find all dates on this image with bounding boxes
        date_entries = []
        for l in lines:
            m = DATE_PATTERN.search(l["text"])
            if m:
                date_entries.append((m.group(0), l["bbox"]))

        has_any_dates = len(date_entries) > 0
        newly_found = []
        visible_titles: Set[str] = set()

        # Dynamically scale vertical card height tolerance based on image height (e.g. 1080p, 1440p, 4K)
        card_vertical_range = max(110, int(img.height * 0.14))

        for l in lines:
            text = l["text"]
            # Ignore pure dates or very short lines
            if DATE_PATTERN.fullmatch(text.strip()) or len(text.strip()) < 3:
                continue

            match = self.stardb.match_title(text)
            if match:
                aid = match["id"]
                title = match["name"]
                visible_titles.add(title)

                card_y_mid = (l["bbox"][1] + l["bbox"][3]) / 2.0
                card_x_min = l["bbox"][0]

                # Match completion date vertically aligned with the card
                matched_date = None
                if has_any_dates:
                    for d_str, d_box in date_entries:
                        date_y_mid = (d_box[1] + d_box[3]) / 2.0
                        if abs(date_y_mid - card_y_mid) <= card_vertical_range and d_box[0] >= card_x_min - 60:
                            matched_date = d_str
                            break

                is_completed = (matched_date is not None) if self.require_completion_date else True

                if is_completed:
                    if aid not in self.scanned_achievements:
                        self.scanned_achievements[aid] = match
                        newly_found.append(match)

                        try:
                            winsound.MessageBeep(winsound.MB_OK)
                        except Exception:
                            pass

                        date_info = f" [Date: {matched_date}]" if matched_date else ""
                        print(f" [+] Found (Completed): {title} (ID: {aid}) - [{match['series_name']}]{date_info}")
                else:
                    if aid not in self.scanned_achievements and aid not in self.skipped_incomplete:
                        self.skipped_incomplete.add(aid)
                        print(f" [-] Incomplete / Locked: {title} (No completion date on card)")

        return newly_found, visible_titles

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

        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

    def get_game_window(self) -> Optional[Tuple[int, str, Tuple[int, int, int, int]]]:
        """Detects ZZZ window and returns (hwnd, title, geometry)."""
        win_info = WindowCapture.find_zzz_window()
        if not win_info:
            print("\n[!] Could not find Zenless Zone Zero game window.")
            print("    Please ensure the game is running in Windowed or Borderless Windowed mode.")
            return None

        hwnd, title = win_info
        geom = WindowController.get_client_geometry(hwnd)
        if not geom:
            print(f"\n[!] Failed to get client geometry for window: {title}")
            return None

        return hwnd, title, geom

    def scan_category_cards(self, hwnd: int, geom: Tuple[int, int, int, int], max_scrolls: int = 50) -> int:
        """
        Auto-scrolls the achievement cards list downwards until reaching the bottom.
        Returns the number of newly discovered achievements.
        """
        left, top, width, height = geom
        # Position cursor over center of achievement cards pane
        cards_x = left + int(width * 0.62)
        cards_y = top + int(height * 0.50)
        InputController.move_to(cards_x, cards_y)
        time.sleep(0.15)

        prev_frame = None
        prev_visible_titles: Set[str] = set()
        consecutive_static_frames = 0
        newly_found_count = 0

        for scroll_idx in range(max_scrolls):
            if InputController.is_escape_pressed():
                print("\n[!] ESC pressed! Stopping scan...")
                return newly_found_count

            frame = WindowCapture.capture_window(hwnd)
            if not frame:
                time.sleep(0.2)
                continue

            found, visible_titles = self.process_image(frame)
            newly_found_count += len(found)

            # Check if list reached the bottom
            if prev_frame is not None:
                is_static_pixels = InputController.is_frame_identical(prev_frame, frame, threshold=2.5)
                is_same_titles = (visible_titles == prev_visible_titles and len(visible_titles) > 0)

                if is_static_pixels or is_same_titles:
                    consecutive_static_frames += 1
                    if consecutive_static_frames >= 2:
                        # Bottom reached!
                        break
                else:
                    consecutive_static_frames = 0

            prev_frame = frame
            prev_visible_titles = visible_titles

            # Scroll down smoothly
            InputController.scroll(-3)
            time.sleep(0.38) # wait for game scroll animation

        return newly_found_count

    def run_hands_free_auto_scan(self, all_categories: bool = True):
        """
        Fully automated hands-free scanner.
        Takes control of scrolling, navigates categories, and automatically copies results.
        """
        target = self.get_game_window()
        if not target:
            return

        hwnd, title, geom = target
        left, top, width, height = geom

        print(f"\n[+] Hooked into game window: '{title}' ({width}x{height})")
        print("\n" + "=" * 60)
        print("          STARTING HANDS-FREE AUTOMATED SCAN")
        print("=" * 60)
        print("Instructions:")
        print("  1. Switch hands off your keyboard and mouse.")
        print("  2. The scanner will automatically focus ZZZ and scroll.")
        print("  3. Press [ESC] at any time for an immediate emergency stop.")
        print("=" * 60 + "\n")

        for sec in range(3, 0, -1):
            print(f"Starting in {sec}... (Hands off!)", end="\r", flush=True)
            time.sleep(1.0)
        print("Starting NOW!                                      \n")

        # Focus game window
        WindowController.focus_window(hwnd)
        time.sleep(0.5)

        if not all_categories:
            # Just auto-scroll the current view
            print("[*] Auto-scrolling current achievement category to bottom...")
            self.scan_category_cards(hwnd, geom)
        else:
            # Full scan: navigate categories on the left sidebar
            print("[*] Auto-scanning all categories via left navigation sidebar...")
            visited_categories: Set[str] = set()
            sidebar_bottom_attempts = 0

            # First, ensure sidebar is scrolled to top
            sidebar_x = left + int(width * 0.15)
            sidebar_y = top + int(height * 0.40)
            InputController.move_to(sidebar_x, sidebar_y)
            InputController.scroll(6)
            time.sleep(0.3)

            for step in range(30):
                if InputController.is_escape_pressed():
                    print("\n[!] ESC pressed! Stopping scan...")
                    break

                # Capture window and inspect sidebar
                frame = WindowCapture.capture_window(hwnd)
                if not frame:
                    time.sleep(0.3)
                    continue

                # Crop sidebar area (left 30% of window)
                sidebar_crop = frame.crop((0, 0, int(width * 0.30), height))
                sidebar_lines = self.ocr.recognize(sidebar_crop)

                # Find unvisited category buttons visible on the sidebar
                unvisited_found = []
                for s_line in sidebar_lines:
                    series = self.stardb.match_series(s_line["text"])
                    if series and series not in visited_categories:
                        unvisited_found.append((series, s_line["bbox"]))

                if unvisited_found:
                    # Click each visible unvisited category and scan its cards
                    for series_name, bbox in unvisited_found:
                        if InputController.is_escape_pressed():
                            break

                        print(f"\n[Category] Scanning: {series_name}...")
                        click_x = left + (bbox[0] + bbox[2]) // 2
                        click_y = top + (bbox[1] + bbox[3]) // 2

                        InputController.click(click_x, click_y)
                        visited_categories.add(series_name)
                        sidebar_bottom_attempts = 0
                        time.sleep(0.6) # wait for category cards to load

                        # Scroll cards in this category to bottom
                        self.scan_category_cards(hwnd, geom)
                        time.sleep(0.2)
                else:
                    # No unvisited categories currently visible; scroll the sidebar down
                    InputController.move_to(sidebar_x, sidebar_y)
                    InputController.scroll(-4)
                    sidebar_bottom_attempts += 1
                    time.sleep(0.4)

                    if sidebar_bottom_attempts >= 3:
                        # Sidebar reached the bottom and all visible categories scanned
                        print("\n[*] Reached end of categories sidebar.")
                        break

        self.export_results()

    def run_live_assisted_scan(self):
        """
        Real-time assisted scanner: The user simply scrolls the game window,
        while the scanner continuously reads the screen, recognizes achievements,
        and beeps on each discovery. 100% anti-cheat safe and reliable!
        """
        target = self.get_game_window()
        if not target:
            return

        hwnd, title, geom = target
        left, top, width, height = geom

        print(f"\n[+] Hooked into game window: '{title}' ({width}x{height})")
        print("\n" + "=" * 60)
        print("           STARTING LIVE ASSISTED SCANNER")
        print("=" * 60)
        print("Instructions:")
        print("  1. Switch to Zenless Zone Zero (Achievements menu).")
        print("  2. Scroll down your achievements list with your mouse wheel")
        print("     or drag the in-game scrollbar.")
        print("  3. Click into ANY other categories on the left sidebar and scroll")
        print("     those as well! (The scanner stays active across all categories).")
        print("  4. You will hear a beep every time newly discovered achievements appear.")
        print("  5. When you have scrolled through all categories you want:")
        print("     Press [F10] in-game or [Enter] in this console window.")
        print("=" * 60 + "\n")

        # Try to bring game window to front
        WindowController.focus_window(hwnd)

        print("[*] LIVE SCANNER ACTIVE (Switch to ZZZ, click & scroll through categories now!)\n")

        self.skipped_incomplete.clear()
        last_scan_time = 0
        scan_interval = 0.15 # ~7 scans per second for high-speed responsiveness
        last_reported_count = 0

        try:
            import msvcrt
            while True:
                # Check for keyboard inputs to finish (F10 in-game or Enter in console)
                if InputController.is_f10_pressed():
                    print("\n[*] [F10] detected! Finishing scan session...")
                    break

                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key in (b"\r", b"\n", b"q", b"Q", b" "):
                        print("\n[*] Key press detected! Finishing scan session...")
                        break

                now = time.time()
                if now - last_scan_time >= scan_interval:
                    last_scan_time = now
                    frame = WindowCapture.capture_window(hwnd)
                    if frame:
                        found, _ = self.process_image(frame)
                        current_total = len(self.scanned_achievements)
                        if current_total > last_reported_count and current_total % 5 == 0:
                            last_reported_count = current_total
                            print(f"[*] Total recorded so far: {current_total} achievements...")

                time.sleep(0.02)

        except KeyboardInterrupt:
            pass

        self.export_results()

    def run_clipboard_scan(self):
        """Scans a screenshot from the system clipboard."""
        print("\n[*] Reading screenshot from clipboard...")
        img = WindowCapture.capture_clipboard()
        if not img:
            print("[!] No image found on clipboard.")
            print("    Tip: Use [Windows Key + Shift + S] to take a screenshot of your achievements list first!")
            return

        print(f"[+] Found clipboard image ({img.size[0]}x{img.size[1]}). Scanning...")
        found, _ = self.process_image(img)
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
            found, _ = self.process_image(img)
            print(f"[+] Recognized {len(found)} achievements.")
            self.export_results()
        except Exception as e:
            print(f"[!] Error reading image: {e}")

def main():
    scanner = ZzzAchievementScanner()

    while True:
        filter_status = "ONLY COMPLETED (Must have date)" if scanner.require_completion_date else "ALL VISIBLE (Record everything seen)"
        print("\n" + "-" * 60)
        print(f"Current Filter: [{filter_status}]")
        print("Choose an option:")
        print("  [1] Live Assisted Scanner (Recommended) [Default - Press Enter]")
        print("      (You scroll the list in-game; scanner auto-reads at 15ms and beeps)")
        print("  [2] Experimental Hands-Free Auto-Scan (All Categories)")
        print("      (Attempts simulated mouse scrolling; may be blocked by game anti-cheat)")
        print("  [3] Experimental Hands-Free Auto-Scan (Current Category Only)")
        print("  [4] Scan Clipboard Screenshot (Win + Shift + S)")
        print("  [5] Scan Image File from Disk")
        print("  [C] Toggle Completion Filter (Completed-Only vs All-Visible)")
        print("  [6] Exit")

        choice = input("\nEnter choice [1-6, C] (Press Enter for Option 1): ").strip()
        if choice in ("", "1"):
            scanner.run_live_assisted_scan()
        elif choice.lower() == "c":
            scanner.require_completion_date = not scanner.require_completion_date
            new_status = "ONLY COMPLETED (Must have date)" if scanner.require_completion_date else "ALL VISIBLE (Record everything seen)"
            print(f"\n[+] Filter updated to: [{new_status}]")
        elif choice == "2":
            scanner.run_hands_free_auto_scan(all_categories=True)
        elif choice == "3":
            scanner.run_hands_free_auto_scan(all_categories=False)
        elif choice == "4":
            scanner.run_clipboard_scan()
        elif choice == "5":
            path = input("Enter path to image file: ").strip().strip('"').strip("'")
            scanner.run_file_scan(path)
        elif choice in ("6", "q", "exit"):
            break
        else:
            print("Invalid choice, please select 1-6 or C.")

if __name__ == "__main__":
    main()
