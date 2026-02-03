# Implementation log (how everything was done)

This document captures the major engineering decisions, implementation milestones, and the “why” behind the current architecture. It exists so we never lose context.

## 1) Core goal

Build a QA utility that can:
- capture Android UI snapshots (image + UI hierarchy + logs),
- align the XML bounds perfectly on the image,
- and provide automation‑ready selectors.

## 2) Foundational architecture

**Desktop app:** PySide6/Qt
- Split into clear modules:
  - `gui.py` — the UI and interaction layer
  - `adb_manager.py` — device and ADB utilities
  - `uix_parser.py` — parses XML and cleans invalid bounds
  - `locator_suggester.py` — generates robust locators
  - `live_mirror.py` — live stream + logcat + focus monitoring

**Snapshot format:**
- `screenshot.png` — what the user saw
- `dump.uix` — UIAutomator XML dump
- `logcat.txt` — logs around the capture
- `meta.json` — device + timestamp metadata

## 3) UI tree alignment

- The XML bounds are mapped onto the current screenshot.
- Scaling is calculated based on dump bounds vs rendered frame size.
- Hover/click picks the smallest bounding rectangle under the cursor.

## 4) Live mirror evolution

### 4.1 ADB polling (baseline)
- We originally used `adb exec-out screencap` in a tight loop.
- It works everywhere, but it’s slower and less smooth.

### 4.2 scrcpy integration (current “golden state”)

We adopted scrcpy for live video streaming because it’s significantly faster and more stable than ADB polling.

Key requirements that drove the solution:
- **Don’t reparent** the scrcpy window (causes rendering glitches).
- **Don’t use `--no-window`** (prevents rendering entirely).
- Hide the window **off‑screen** while keeping it rendering.

Implementation summary:
1. Start scrcpy as a subprocess with a custom window title.
2. Locate the HWND via `FindWindowW`.
3. Move it off‑screen using `SetWindowPos(-32000, -32000, ...)`.
4. Capture its pixels using `PrintWindow(PW_RENDERFULLCONTENT)`.
5. Convert the bitmap to `QImage` and render in Qt.

### 4.3 Snapshot alignment fix

To avoid timing mismatch between UI dumps and screenshots:
- We save the **last rendered frame** from the live mirror directly to disk.
- Then we capture the XML dump immediately afterward.

This guarantees the screenshot matches the XML state the user saw.

## 5) Logging and diagnostics

- scrcpy stdout/stderr is streamed into the System Log.
- Logcat has its own tab for device logs.
- The System Log speaks in plain English for QA clarity.

## 6) Performance notes

- PrintWindow capture is stable but may cap FPS on some systems.
- Raw H.264 decoding with PyAV provides higher FPS when available.
- Resolution presets allow quick performance tuning.

## 7) Remote device farm support

- ADB server host/port can be configured to point to a remote device farm.
- All ADB commands are routed through `adb -H <host> -P <port>`.
- This enables integration with remote labs or cloud emulator pools.

## 8) Future ideas

- Optional hardware‑accelerated decoding (DXVA) for PyAV.
- Auto‑detect display focus changes to trigger UI tree refresh.
- Session recorder (video + XML timeline).
