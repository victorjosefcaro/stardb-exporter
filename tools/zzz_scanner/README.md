# Zenless Zone Zero (ZZZ) Achievement Scanner for StarDB

A fast, lightweight, and 100% ToS-compliant visual scanner for Zenless Zone Zero achievements. It reads your in-game achievement screen using Windows' native hardware-accelerated OCR (`Windows.Media.Ocr`) and automatically exports a payload ready for [StarDB](https://stardb.gg/import).

---

## Features
- **100% Account Safe & ToS Compliant**: Never touches game memory, never injects into processes, and never touches network packets.
- **Hardware-Accelerated OCR**: Powered by Microsoft's built-in Windows OCR engine (~10–20ms per screen).
- **Exact StarDB Mapping**: Uses the official live StarDB achievement database (with fuzzy matching) to map recognized titles to their exact IDs.
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

## How to Use

### Method 1: 1-Click Batch Launcher
Double-click **`run_scanner.bat`** in this folder.

### Method 2: Command Line
From the terminal, install dependencies (if not already installed) and run:
```powershell
pip install -r tools/zzz_scanner/requirements.txt
python tools/zzz_scanner/scanner.py
```

---

## Scanning Modes

### 1. Live Window Auto-Scanner (Fastest & Easiest)
1. Launch Zenless Zone Zero (in Windowed or Borderless Windowed mode).
2. Open the in-game **Achievements** menu.
3. Select Option `[1]` in the scanner.
4. Slowly scroll down your achievements list in-game. The scanner will automatically detect and beep as new completed achievements are discovered.
5. Press `Enter` in the console when finished scrolling.
6. The JSON is automatically copied to your clipboard!
7. Navigate to **[stardb.gg/import](https://stardb.gg/import)**, press `Ctrl + V`, and click **Import**!

### 2. Screenshot Snipping (`Win + Shift + S`)
1. Press `Win + Shift + S` to capture a screenshot of your achievements window.
2. Select Option `[2]` in the scanner.
3. It will immediately read your clipboard screenshot, match the achievements, and update your export!
