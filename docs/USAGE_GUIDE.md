# Usage Guide

## Run the app

```bash
python src/qa_snapshot_tool/main.py
```

## Offline inspection

1. Click **Load Offline Dump...**
2. Select a snapshot folder containing `screenshot.png` and `dump.uix`.
3. Hover the image to highlight nodes.
4. Click to lock selection and inspect properties.
5. Use **Smart Locators** to copy suggested XPath/Appium selectors.

## Live mirror (optional)

1. Connect the target device via ADB.
2. Click **LIVE MODE**.
3. Interact with the live mirror and observe UI updates.
4. Use **Capture Snapshot** to store the current state.

## Snapshot capture format

Snapshots are stored as:

```
snap_<timestamp>/
  screenshot.png
  dump.uix
  meta.json
  logcat.txt
```

## Tips

- Use **Fit Screen** for large or unusual aspect ratios.
- Use the UI tree panel to navigate dense hierarchies quickly.
- Prefer resource-id + class selectors when available.
