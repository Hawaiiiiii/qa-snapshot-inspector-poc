# QUANTUM Inspector (QA Snapshot Inspector)

A professional-grade Python desktop GUI to inspect Android UI snapshots (UIAutomator dumps + screenshots), review live device state, and generate robust locators for QA automation.

Project owner and technical authority: David Erik García Arenas (QA, Paradox Cat).

![QUANTUM Inspector UI - V1 PoC](docs/v1-poc.png)

V1 PoC (current build).

## What it does

- Live mirror via ADB (optional) to inspect the current UI in real time.
- Offline snapshot inspection from saved folders.
- UI tree navigation with hover/selection overlay on the screenshot.
- Inspector panel with node properties (text, bounds, resource-id, etc.).
- Locator suggestions (XPath + Appium Java/Python formats).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Usage guide](docs/USAGE_GUIDE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [FAQ](FAQ.md)
- [Draft article (Spanish)](docs/QUANTUM_Article_Final.pdf)

## How it works

1. Load a snapshot folder or start a live mirror session over ADB.
2. The UIAutomator XML is parsed into a node tree with bounds and attributes.
3. The screenshot is rendered with hover/selection overlays tied to the node tree.
4. Selecting a node shows its properties and locator suggestions for automation.

## Architecture at a glance

- **GUI layer (`gui.py`)**: PySide6 window, overlays, tree navigation, inspector panels.
- **XML parser (`uix_parser.py`)**: converts UIAutomator XML into `UiNode` objects with bounds validation.
- **Locator engine (`locator_suggester.py`)**: generates scoped, ID, text, and content-desc locators.
- **ADB integration (`adb_manager.py`, `adb_capture.py`)**: device discovery, snapshot capture, input events.
- **Live mirror (`live_mirror.py`)**: background threads for video, hierarchy, logcat, and focus updates.
- **Theme (`theme.py`)**: palette and styling rules.

## Additional visuals

![QUANTUM Inspector UI - Example](docs/ui-example.png)

UI_Example: guidance screenshot to explain what each section shows when you open a screen.

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

## Workflow (GitFlow)

This repo follows GitFlow conventions:

- main: stable releases
- develop: active integration
- feature/*: new features
- hotfix/*: urgent fixes on main
- release/*: pre-release stabilization

## Project files

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [FAQ.md](FAQ.md)
- [CHANGELOG.md](CHANGELOG.md)
- [LICENSE](LICENSE)

<img src="docs/bernard-tennis.gif" width="120" alt="Bernard tennis easter egg" />
