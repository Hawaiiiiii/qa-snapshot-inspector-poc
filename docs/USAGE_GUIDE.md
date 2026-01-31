# Usage guide

This guide covers the core workflows: offline snapshot inspection, live mirror usage, and locator export for automation.

## Quick start (offline)

1. Launch the app:

```bash
python src/qa_snapshot_tool/main.py
```

2. Click **Load Offline Dump...** and select a snapshot folder.
3. Use the tree to navigate the hierarchy or click directly on the screenshot overlay.
4. Review node attributes and locator suggestions in the inspector panel.

## Snapshot capture (online)

1. Connect a device with ADB available in your PATH.
2. Click **Refresh List**, then select the device.
3. Use **Capture Snapshot** to save a folder containing `dump.uix` and `screenshot.png`.

Captured snapshots can be re-opened later in offline mode.

## Live mirror inspection

1. Connect a device and select it from the **Target Device** list.
2. Click **START LIVE STREAM**.
3. Use the overlay to inspect the current screen.
4. Toggle **Fit Screen** or **1:1 Pixel** from the toolbar for precision.

## Locator generation workflow

1. Select a node in the tree or screenshot.
2. Inspect locator suggestions (scoped, ID, text, content-desc).
3. Copy the most stable locator into your automation framework.

## Working with Appium

The locator panel includes Appium-ready XPath formats. For example:

```xpath
//*[@resource-id='com.example:id/login']//*[@text='Sign in']
```

Use these locators in Appium Java or Python clients as needed.

## Recommended folder hygiene

- Keep snapshots grouped by test run or device model.
- Store `meta.json` when possible to help trace device/OS state.
- Use consistent naming for reproducibility (date, build number, feature).
