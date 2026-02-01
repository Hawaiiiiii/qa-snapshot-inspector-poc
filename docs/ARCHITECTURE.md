# Architecture

QUANTUM Inspector is a PySide6 desktop application that combines ADB‑driven capture with offline snapshot inspection and locator generation.

## High-level flow

1. **Capture or load** a snapshot (screenshot + UIAutomator XML).
2. **Parse** XML into a UI tree of nodes with bounds.
3. **Render** screenshot and overlay UI elements for selection.
4. **Inspect** node properties and generate locator suggestions.

## Modules

- **main.py**: App entry point, theme setup, window bootstrap.
- **gui.py**: Main window, docks, graphics view, and UI event routing.
- **adb_manager.py**: ADB device discovery, screencap, UI dump, logcat, and snapshot packaging.
- **live_mirror.py**: Live capture loop (optional) and frame delivery.
- **uix_parser.py**: XML parsing into `UiNode` objects + bounds validation.
- **locator_suggester.py**: Generates XPath/Appium locator suggestions.
- **theme.py**: UI theme tokens and stylesheet.

## Snapshot format

Each snapshot directory may contain:

- `screenshot.png` — ADB screencap
- `dump.uix` — UIAutomator XML dump
- `meta.json` — device info, focused activity, timestamps
- `logcat.txt` — optional logs

## Data model

- **UiNode** (from `uix_parser.py`):
  - attributes: class, resource-id, text, content-desc, package
  - bounds: `x`, `y`, `w`, `h`
  - flags: clickable, enabled, focused, selected, etc.

## Locator strategy

Locator suggestions are produced from a node’s attributes and its position in the hierarchy, targeting:

- XPath (generic)
- Appium Java
- Appium Python

The goal is stable, scoped selectors with minimal false positives.
