# Architecture

QUANTUM Inspector is a local, offline-first desktop application for analyzing Android UIAutomator snapshots with optional live device mirroring over ADB. The architecture prioritizes deterministic locator generation and fast visual inspection without requiring a backend service.

## System overview

- **Input**: UIAutomator XML + screenshot folders (offline) or live ADB streams (online).
- **Processing**: XML parsing to structured nodes, locator inference, UI overlays.
- **Output**: Visual inspection UI, node properties, locator suggestions, and Appium-ready snippets.

## Core components

1. **GUI layer (`gui.py`)**
   - `MainWindow` orchestrates panels and dock widgets.
   - `SmartGraphicsView` renders the screenshot and selection overlays.
   - Inspector panels show node properties and locator options.

2. **UIAutomator parser (`uix_parser.py`)**
   - Converts XML into `UiNode` objects.
   - Validates bounds, detects non-accessible (`NAF`) nodes, and fingerprints nodes for re-selection.

3. **Locator engine (`locator_suggester.py`)**
   - Prioritizes scoped locators based on stable parent anchors.
   - Falls back to resource-id, text match, or content-desc.
   - Generates Appium-friendly XPath variants.

4. **ADB integration (`adb_manager.py`, `adb_capture.py`)**
   - Device discovery, snapshot capture, and input events.
   - Handles optional live capture workflows.

5. **Live mirror (`live_mirror.py`)**
   - Background threads keep video, hierarchy, logcat, and focus states updated.
   - Designed to decouple UI refresh from device I/O.

6. **Theme (`theme.py`)**
   - Central styling palette and UI consistency.

## Data flow

### Offline inspection
1. User selects a snapshot folder.
2. `uix_parser.py` builds a node tree from `dump.uix`.
3. `gui.py` renders the screenshot with selectable overlays.
4. `locator_suggester.py` creates candidate locators for the selected node.

### Live mirror + capture
1. User selects an ADB device and starts live mirror.
2. `live_mirror.py` streams the current screen and hierarchy.
3. The GUI keeps node selection synchronized with the updated tree.
4. Optional snapshot capture writes `dump.uix` and `screenshot.png`.

## Snapshot folder format

```
snapshot/
  screenshot.png
  dump.uix
  meta.json    # device + activity metadata (optional)
  logcat.txt   # optional logs
```

Missing `meta.json` or `logcat.txt` is tolerated; `dump.uix` and `screenshot.png` are required for full inspection.

## Key data structures

- **`UiNode`**: parsed XML node with text, resource-id, class, content-desc, bounds, and `NAF` attributes.
- **Fingerprinting**: stable hash of identifying attributes for re-selection after refresh.

## Security & privacy

QUANTUM Inspector runs locally and does not transmit device data to external services. Files remain on disk where snapshots are saved.

## Reference material

The PDF in `docs/QUANTUM_Article_Final.pdf` contains broader context and earlier drafts (Spanish).
