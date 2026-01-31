# Troubleshooting

## ADB not detected

**Symptoms**
- Device list is empty
- Live mirror controls are disabled

**Fix**
- Confirm `adb` is available in your PATH.
- Run `adb devices` from a terminal and verify the device is authorized.
- Restart the ADB server: `adb kill-server && adb start-server`.

## Snapshot loads but no overlays appear

**Symptoms**
- Screenshot renders but nodes do not highlight

**Fix**
- Confirm `dump.uix` exists and is not empty.
- Ensure the XML is a UIAutomator dump and not a custom format.
- Check that node bounds are non-zero.

## XML parsing errors

**Symptoms**
- “XML Parse Error” in console
- Tree view is empty

**Fix**
- Verify that `dump.uix` is valid XML.
- Re-capture the snapshot via ADB.
- Avoid saving dumps that are truncated by shell timeouts.

## Live mirror feels slow

**Symptoms**
- Low FPS
- Stale hierarchy updates

**Fix**
- Reduce active background apps on the device.
- Prefer a USB connection over Wi-Fi.
- Disable other ADB-heavy tools while mirroring.

## Locator suggestions look unstable

**Symptoms**
- XPath changes between runs

**Fix**
- Prefer scoped locators anchored by a stable resource-id.
- Avoid text-only locators for dynamic content.
- Review node attributes in the inspector for better anchors.
