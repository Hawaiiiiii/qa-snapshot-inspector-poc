# Perf Evidence (2026-03-02)

## Environment
- Execution date: 2026-03-02
- Host session type: RDP (`RDP-Tcp#1`)
- Canonical session source: `C:\Users\DavidErikGarciaArena\.qa_snapshot_tool\sessions\20260302_145354_8f94fbac4ec2dab5066bf053900061c`

## Executed checks
1. Profile gate:
   - `scripts/profile_hotspots.py --session <canonical> --targets balanced --enforce-targets` passed.
2. A/B capture script (RDP run):
   - `scripts/perf_ab_capture.ps1 -Env rdp -Runs 3 -Session <canonical> -RequireAllPass`
   - Batch directory: `docs/evidence/perf/rdp_20260302_135421/`
   - Parsed JSON runs: `3/3`
   - Acceptance pass count: `3/3`

## Results
- Pass: RDP balanced profile acceptance (`3/3`)
- Pending: local non-RDP baseline run for strict A/B completion

## Summary metrics (rdp_20260302_135421)
- frame_sha1 avg(avg_ms): 6.02
- frame_sha1 avg(p95_ms): 8.61
- xml_parse avg(avg_ms): 2.58
- xml_parse avg(p95_ms): 4.58
- smallest_hit avg(avg_ms): 0.03
- smallest_hit avg(p95_ms): 0.04
