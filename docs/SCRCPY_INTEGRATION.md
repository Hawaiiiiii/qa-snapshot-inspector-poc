# scrcpy integration (implementation notes)

This document preserves the current “golden state” for live mirroring so we don’t lose the working recipe.

## Goals

- Achieve high‑FPS live mirroring with scrcpy.
- Keep the UI responsive and stable.
- Guarantee snapshot alignment between image and UI dump.

## Architecture summary

1. **scrcpy runs as a subprocess**
   - We invoke scrcpy with a custom window title.
   - We do **not** embed or reparent the window.
   - We do **not** use `--no-window` (it prevents GPU/renderer output).

2. **Window management (critical)**
   - We find the scrcpy window handle (HWND) using `FindWindowW` with the custom title.
   - We move it off‑screen via `SetWindowPos(..., -32000, -32000, ...)`.
   - This keeps rendering active while the window stays hidden to the user.

3. **Frame capture**
   - Standard Qt grabs return black frames when the window is off‑screen.
   - We use Win32 `PrintWindow` with `PW_RENDERFULLCONTENT (0x00000002)` to copy pixels.
   - Fallback to `BitBlt` when `PrintWindow` fails.
   - The bitmap is converted into `QImage` and emitted into the UI.

4. **Snapshot alignment**
   - We do not use `adb shell screencap` for live snapshots.
   - The last rendered `QImage` is saved directly to disk as `screenshot.png`.
   - The UI dump is captured immediately after, ensuring alignment.

5. **Logging**
   - scrcpy stdout/stderr is streamed into the System Log.
   - This mirrors scrcpy’s own console messages (device, renderer, texture size, etc.).

## Key files

- `src/qa_snapshot_tool/live_mirror.py`
  - `ScrcpyVideoSource` manages the subprocess and Win32 capture.
  - `_capture_window_image()` implements `PrintWindow`.
  - `_move_window_offscreen()` hides the window without disabling rendering.

- `src/qa_snapshot_tool/gui.py`
  - `MainWindow` wires the live source into the UI.
  - Snapshot capture writes cached live frame.
  - System Log receives scrcpy output.

## Known limitations

- FPS depends on device, GPU driver, and Windows composition. The UI may not reach >30 FPS on some systems.
- If the scrcpy window isn’t found, we log a warning and the stream may stall.
- Raw H.264 mode requires PyAV (optional). Window capture is the default safe path.

## Why this approach

- Avoids input latency and ADB polling bottlenecks.
- Works even when the scrcpy window is off‑screen.
- Keeps UI and dump perfectly in sync for QA snapshots.
