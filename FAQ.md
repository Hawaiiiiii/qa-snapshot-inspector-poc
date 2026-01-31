# FAQ

## What is QUANTUM Inspector?

A Python desktop GUI for inspecting Android UI snapshots (UIAutomator dumps + screenshots) and generating automation-ready locators.

## Do I need ADB?

Only for live mirror and capture. Offline inspection works without ADB.

## What snapshot format is expected?

A folder containing `screenshot.png` and `dump.uix` (optional `meta.json` and `logcat.txt`).

## Is this production-ready?

This is a PoC (work in progress). Stability and features will evolve.

## How is this different from legacy tools?

It keeps snapshot inspection, hierarchy navigation, and locator generation in a single offline-first desktop app, reducing manual copy/paste and context switching.

## Can I use it without a connected device?

Yes. Offline mode only needs a snapshot folder.

## Which platforms are supported?

The app targets Windows 11 but can run on macOS and Linux with Python 3.11+ and PySide6.

## What does “scoped locator” mean?

A scoped locator anchors the target inside a stable parent node, improving stability compared with global XPath.

## Do you generate Appium locators?

Yes. The locator panel includes Appium-friendly XPath outputs.

## Can I inspect dynamic or animated screens?

Yes, but live mirror performance depends on device and ADB throughput.

## Why are some nodes marked NAF?

Nodes without text, resource-id, or content-desc are flagged as not accessibility-friendly (NAF).

## What if my XML has zero bounds?

Re-capture the snapshot. Some UIAutomator dumps fail to include bounds if the capture is incomplete.

## Can I capture logcat?

Yes. If logcat capture is enabled, `logcat.txt` is saved with the snapshot.

## Does the tool modify the device state?

Only if you use input controls (tap/scroll) during live mirror. Offline inspection is read-only.

## Where should I store snapshots?

Use per-run folders with date or build identifiers to keep sessions reproducible.

## Is data sent to external services?

No. The tool is local-only and does not upload snapshots.

## Where can I learn the architecture?

See the [Architecture](docs/ARCHITECTURE.md) document for component and data flow details.
