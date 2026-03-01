# Exifor — ExifTool Manager

A clean, privacy-first metadata manager for **iSH (iOS)** and any Unix terminal.
Beautiful interactive menu on top of the system `exiftool`.

**No logs. No traces. No complex commands.**

---

## Install

```sh
git clone https://github.com/tooter9/exifor.git
cd exifor
```

Install ExifTool for your system:

| Platform | Command |
|---|---|
| iSH / Alpine Linux | `apk add exiftool` |
| macOS (Homebrew) | `brew install exiftool` |
| Debian / Ubuntu | `apt install libimage-exiftool-perl` |
| Fedora / RHEL | `dnf install perl-Image-ExifTool` |

Install Python dependencies:

```sh
pip3 install -r requirements.txt
```

If you get an error on newer Python:

```sh
pip3 install -r requirements.txt --break-system-packages
```

---

## Run

```sh
python3 exifor.py
```

The interactive menu opens — navigate with numbers. Press **0** at any step to go back.

---

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | View metadata | All tags grouped by category |
| 2 | **Strip metadata** | Remove all / GPS only / one tag — choose output location |
| 3 | **ZIP Cleaner** | Strip metadata from every file inside a ZIP archive |
| 4 | GPS | View coordinates (+ Google Maps link), edit, or remove |
| 5 | Edit tags | Choose from popular tags or enter custom tag names |
| 6 | Folder batch | Process an entire directory at once |
| 7 | Export | Save metadata to JSON or CSV |
| 8 | Copy tags | Transfer metadata from one file to another |

---

## What's improved in this version

- **Full English interface** — all menus, prompts and messages in English
- **Clear result panel** — every operation shows: status (success/fail), input file path, output file path, backup path
- **Output location choice** — for single-file strip you choose: overwrite in-place OR save as a new copy (original untouched)
- **Backup location shown** — when you keep a backup, the tool shows exactly where it was saved (`filename.ext_original`)
- **0 = back at every step** — press 0 at any prompt to return to the main menu immediately
- **Simplified flow** — cleaner step-by-step sequence for every operation
- **Fixed folder navigation** — no double `cd` needed; everything is at the repo root

---

## ZIP Cleaner

Processes a whole ZIP archive:

1. You pick a ZIP file
2. Files are extracted to a hidden temp folder
3. ExifTool strips all metadata
4. Files are repacked into a clean new ZIP
5. Temp folder is deleted immediately — no traces

The original ZIP is **never modified**. You choose where the clean ZIP is saved.
Also includes an **Inspect** mode that shows exactly which files inside the ZIP contain metadata.

---

## Privacy

- No history or log files ever written
- Temp folders deleted immediately after use
- Uses the **system ExifTool binary** — no custom parser vulnerabilities
- All processing is local — no internet connection required

---

## Requirements

- Python 3.8+
- ExifTool (system package — see install instructions above)
- rich 13.0+ (only Python dependency — installed via pip)

---

## Supported Formats

All formats supported by ExifTool:
JPEG, PNG, HEIC, TIFF, GIF, WebP, RAW (CR2/CR3/NEF/ARW/DNG),
MP4, MOV, AVI, MKV, MP3, FLAC, M4A, WAV, AAC,
PDF, DOCX, XLSX, PPTX, ZIP and many more.
