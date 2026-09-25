# Zenless Zone Zero (ZZZ) Achievement Scanner for StarDB

A fast, lightweight, and 100% ToS-compliant visual scanner for Zenless Zone Zero achievements. It reads your in-game achievement screen using Windows' native hardware-accelerated OCR (`Windows.Media.Ocr`) and automatically exports a payload ready for [StarDB](https://stardb.gg/import).

---

## Features
- **100% Account Safe & ToS Compliant**: Never touches game memory, never injects into processes, and never touches network packets.
- **Hands-Free Automation**: Automatically brings the game into focus, auto-scrolls down lists, navigates categories on the sidebar, and copies the export straight to your clipboard when finished.
- **Hardware-Accelerated OCR**: Powered by Microsoft's built-in Windows OCR engine (~10–20ms per screen).
- **Exact StarDB Mapping**: Uses the official live StarDB achievement database (with fuzzy matching) to map recognized titles to their exact IDs.
- **Emergency Stop**: Press `ESC` at any time to instantly stop scanning and export whatever has been collected.
- **Instant Clipboard Export**: Automatically formats and copies the required JSON directly to your clipboard:
  ```json
  {
    "zzz_achievements": [
      1004001,
      1005001,
      ...
    ]
  }
  ```

---

## How to Use (Zero Manual Input)

1. Launch **Zenless Zone Zero** (in Windowed or Borderless Windowed mode) and open the **Achievements** menu.
2. Double-click **`run_scanner.bat`** (or run `python tools/zzz_scanner/scanner.py`).
3. Press <kbd>Enter</kbd> to start **Hands-Free Full Auto-Scan**.
4. Take your hands off your mouse and keyboard! The scanner will:
   - Bring Zenless Zone Zero into focus.
   - Smoothly scroll through your achievements.
   - Click through categories on the left sidebar.
   - Detect when each list reaches the bottom.
   - Play a chime when complete and copy the JSON straight to your clipboard.
5. Open **[stardb.gg/import](https://stardb.gg/import)**, press <kbd>Ctrl</kbd> + <kbd>V</kbd>, and click **Import Achievements**!

---

## Scanning Modes

- **[1] Hands-Free Full Auto-Scan (All Categories) [Default]**:
  Navigates through categories and auto-scrolls every list to the bottom.
- **[2] Hands-Free Auto-Scan (Current Category Only)**:
  Auto-scrolls only the currently open category/list to the bottom.
- **[3] Manual Live Scroll**:
  You scroll the list manually at your own pace; the scanner detects and beeps in real time.
- **[4] Scan Clipboard Screenshot**:
  Snip an achievement view using `Win + Shift + S` and parse it from your clipboard.
- **[5] Scan Image File**:
  Parse an image file saved on disk.
