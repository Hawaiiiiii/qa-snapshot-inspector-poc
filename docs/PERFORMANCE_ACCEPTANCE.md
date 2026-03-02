# Performance acceptance (QUANTUM 2.0)

This document defines measurable hotspot acceptance criteria for 2.0 release gating.

## Scope

Hotspot profiling targets:

- `frame_sha1`
- `xml_parse`
- `smallest_hit`

Profiler script:

```bash
.venv\Scripts\python.exe scripts\profile_hotspots.py --targets balanced --enforce-targets
```

## Threshold profiles

### balanced (release default)

- `frame_sha1`: `avg <= 8.0 ms`, `p95 <= 16.0 ms`
- `xml_parse`: `avg <= 30.0 ms`, `p95 <= 60.0 ms`
- `smallest_hit`: `avg <= 4.0 ms`, `p95 <= 8.0 ms`

### strict (stretch target)

- `frame_sha1`: `avg <= 5.0 ms`, `p95 <= 10.0 ms`
- `xml_parse`: `avg <= 20.0 ms`, `p95 <= 45.0 ms`
- `smallest_hit`: `avg <= 2.5 ms`, `p95 <= 5.0 ms`

## Policy

- `balanced` profile must pass for release candidates.
- `strict` profile is tracked as an optimization objective.
- Use `--enforce-targets` in CI/local release checks to fail on regressions.

## Notes

- Results depend on local hardware; compare regressions on the same machine class where possible.
- If `balanced` fails consistently, prioritize optimization in Python paths first, then native hotspot backend.
