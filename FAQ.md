# FAQ

## What is QUANTUM Inspector?

A Python desktop GUI for inspecting Android UI snapshots (UIAutomator dumps + screenshots) and generating robust locators.

## Who is this for?

QA engineers working with Android-based systems and in-lab test racks who need fast UI inspection and locator creation.

## Do I need ADB?

Only for live mirror and capture. Offline inspection works without ADB.

## Does it replace UI Automator Viewer and scrcpy?

Yes. It consolidates UI tree inspection, live view, and snapshot review into one workflow.

## What snapshot format is expected?

A folder containing `screenshot.png` and `dump.uix` (optional `meta.json` and `logcat.txt`).

## Can I use it without a device connected?

Yes. Offline snapshots are fully supported.

## What locator formats are generated?

XPath (generic), Appium Java, and Appium Python.

## Are snapshots uploaded anywhere?

No. Everything runs locally by default.

## Why are bounds all zeros?

The dump is malformed or missing bounds. Re-capture the dump.

## Does it support multiple viewports?

It supports any screenshot size; use Fit Screen for large viewports.

## Is this production-ready?

This is a PoC (work in progress). Stability and features will evolve.
