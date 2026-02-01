# Troubleshooting

## Parse Error: junk after document element

The UI dump contains extra content after the XML root. Re-capture the dump or use the built‑in XML sanitizing.

## No overlay highlights

- Ensure `dump.uix` exists in the snapshot folder.
- Verify bounds are valid (not all `[0,0][0,0]`).

## Live mirror not updating

- Confirm the device appears in the dropdown.
- Check ADB connectivity: `adb devices`.
- Restart live mode.

## Screenshot loads, tree empty

The XML dump is missing or malformed. Re-capture the snapshot.

## ADB permissions denied

- Reconnect the device and accept the authorization prompt.
- Run `adb kill-server` and `adb start-server`.

## Performance issues

- Use offline mode for large snapshots.
- Close unused apps to reduce UI dump size.
