# QA Snapshot Inspector & Locator Assistant

A Python desktop GUI for QA engineers to inspect Android UI snapshots offline, debug locator issues, and generate robust/scoped Page Object locators.

## Prerequisites

- Python 3.11+
- Windows 11 (designed for, but works on macOS/Linux)
- ADB (optional, for online capture)

## Snapshot Format

Each snapshot folder can include:

- screenshot.png (ADB screencap)
- dump.uix (UIAutomator XML dump)
- meta.json (device info, focused activity, timestamps)
- logcat.txt (optional)

Missing files are handled gracefully with warnings.

## Installation

1) Create a virtual environment:

```bash
python -m venv venv
venv\Scripts\activate
```

2) Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the tool:

```bash
python src/qa_snapshot_tool/main.py
```

## Notes

- Offline mode: Select a snapshot folder or a parent directory to browse snapshots.
- Online mode (optional): Connect a device and capture a snapshot via ADB.
