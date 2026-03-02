# Rack Signoff Evidence (2026-03-02)

## Environment
- Execution date: 2026-03-02
- Host session: RDP (`RDP-Tcp#1`)
- Connected rack serial: `8f94fbac4ec2dab5066bf053900061c?`
- Model: `BMW IDCEvo`

## Executed checks
1. Device connectivity:
   - `adb devices -l` returned connected rack device with model metadata.
2. Real XML capture:
   - `adb shell uiautomator dump` succeeded.
   - Pulled XML from `/storage/emulated/0/ui.xml` to local capture.
3. Real frame capture:
   - `screencap -d 0` returned protected-display error (`Status: -2`) on this rack.
   - `exec-out screencap -p` produced prefixed warning text due multi-display; PNG payload was recovered and decoded to seed a real profiling session.
4. Session recorder seed:
   - Created session: `C:\Users\DavidErikGarciaArena\.qa_snapshot_tool\sessions\20260302_145354_8f94fbac4ec2dab5066bf053900061c`
   - Wrote frame + XML + log + event into `session.db`.
5. Strict hotspot gate:
   - `scripts/profile_hotspots.py --targets balanced --enforce-targets` passed on seeded rack session.
   - `scripts/release_gate.ps1 -Strict` passed.
6. Forced-crash preservation contract:
   - `scripts/verify_forced_crash_signoff.py` passed.
   - Report schema: `quantum_forced_crash_check.v1`.
   - Verified `session_dir_exists`, `frame_preserved`, `xml_preserved`, `crash_file_present`, and `db_has_crash_event` were all `true`.
7. G70 multi-device endpoint precheck:
   - `scripts/rack_multidevice_signoff.ps1 -SkipScrcpy` executed with HU/CDE/RSE defaults.
   - Expected fail in current environment because the three G70 endpoints were not connected/reachable.

## Results
- Pass: rack connectivity
- Pass: XML dump retrieval
- Pass: strict hotspot acceptance on real rack-derived session
- Pass: forced-crash recorder preservation contract
- Partial: direct `screencap -d <id>` path fails on protected/multi-display surfaces (`Status: -2`)

## Remaining rack blocking items (not completed in this run)
- 30-minute 1-device stability run
- 20-minute 2-device concurrent run
- 10-minute 3-device concurrent run
- Forced crash during active full live workflow (manual GUI run, beyond recorder-level contract)

## Notes
- A real recorder bug was found and fixed during this run: session directory generation now sanitizes invalid serial characters (for example `?`) in `SessionRecorder.start_session()`.
