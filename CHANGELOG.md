# Changelog

## [Unreleased]

- Ongoing PoC improvements
- Added release automation workflow for Windows packaging and executable artifact upload.
- Added `scripts/release_gate.ps1` and `docs/RELEASE_CHECKLIST_2_0.md` for reproducible 2.0 signoff.
- Added signoff runbook and evidence helpers for A/B perf capture and emulator smoke validation.
- Updated release gates/docs to support Python >=3.11 (including 3.14) with optional 3.11-only packaging baseline enforcement.
- Expanded CI/release workflows to validate test+compile on Python 3.11 and 3.14 while keeping Windows packaging pinned to 3.11.
- Added forced-crash signoff validator and Maestro handoff validation helper scripts.
- Added rack multi-device (HU/CDE/RSE) endpoint signoff helper script for G70 workflows.
- Added GUI deep-link tests for timeline and Maestro open-folder actions.

## [2.0.0-rc2] - 2026-03-02

- Finalized `quantum_handoff.v1` contract with full session/device/display/artifact metadata and deterministic export paths.
- Enforced capability-driven runtime gating across live start, snapshot capture, input injection, display switching, and UI tree refresh.
- Extended multi-device scheduler policy to throttle background XML/focus/log pipelines in addition to video FPS.
- Added adaptive event-triggered recorder captures for tap, swipe, focus, dump-error, and display-change transitions.
- Added performance acceptance profiles and enforcement flags to hotspot profiling (`--targets`, `--enforce-targets`).
- Added focused runtime tests for recorder reliability/pruning/crash handling, capability behavior, scheduler bounds, and workspace isolation.
- Normalized runtime docs to `.venv\\Scripts\\python.exe` command usage and documented QUANTUM 2.0 runtime model.

## [2.0.0-rc1] - 2026-03-02

- Added multi-device tabbed workspaces (up to 3 concurrent sessions).
- Added continuous live session recorder with SQLite timeline indexing.
- Added timeline browser and session evidence inspection inside the Inspector dock.
- Added rack-first capability profiles with explicit emulator beta support toggle.
- Added Maestro handoff export with deterministic `quantum_handoff.json` manifests.
- Added crash marker propagation into active recorder sessions.
- Added hotspot performance telemetry, profiling script, and Python/native hotspot facade.
- Added adaptive recorder optimization for large XML dumps (compressed sidecar output).
- Updated runtime baseline to Python 3.11+.

## [0.1.0] - 2026-01-31

- Initial public PoC state
- README updates and multilingual documentation
- Added draft article PDF and screenshots
