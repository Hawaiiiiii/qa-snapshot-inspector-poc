# QUANTUM Inspector (QA Snapshot Inspector)

A Python desktop GUI to inspect Android UI snapshots (UIAutomator dumps + screenshots), review live device state, and generate robust locators for QA automation.

![QUANTUM Inspector UI](docs/screenshot.png)

## What it does

- Live mirror via ADB (optional) to inspect the current UI in real time.
- Offline snapshot inspection from saved folders.
- UI tree navigation with hover/selection overlay on the screenshot.
- Inspector panel with node properties (text, bounds, resource-id, etc.).
- Locator suggestions (XPath + Appium Java/Python formats).

## Prerequisites

- Python 3.11+
- Windows 11 (designed for, but works on macOS/Linux)
- ADB (optional, for live mirror + capture)

## Snapshot format

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

- Offline mode: Open any snapshot folder with a dump and screenshot.
- Online mode (optional): Connect a device and capture snapshots via ADB.

## Screenshot

Place the provided UI screenshot at docs/screenshot.png to render the image in this README.
