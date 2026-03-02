# Signoff Runbook (QUANTUM 2.0)

This runbook executes the final signoff plan with reproducible commands and evidence output paths.

## 1) Local release gates

```powershell
.\scripts\release_gate.ps1
.\scripts\release_gate.ps1 -BuildExe
```

Optional strict hotspot gate (requires session with frames+xml):

```powershell
.\scripts\release_gate.ps1 -Strict
```

Optional deterministic packaging baseline (exact Python 3.11):

```powershell
.\scripts\release_gate.ps1 -RequirePackagingBaseline311
.\scripts\release_gate.ps1 -BuildExe -RequirePackagingBaseline311
```

## 2) Performance A/B evidence

Use the same canonical session path for both environments whenever possible.

```powershell
# Local baseline
.\scripts\perf_ab_capture.ps1 -Env local -Runs 3 -Session "C:\path\to\session" -RequireAllPass

# RDP baseline
.\scripts\perf_ab_capture.ps1 -Env rdp -Runs 3 -Session "C:\path\to\session"
```

`perf_ab_capture.ps1` enforces acceptance targets by default. Use `-SkipEnforceTargets` only for diagnostics.

Output folders:

- `docs/evidence/perf/local_YYYYMMDD_HHMMSS/`
- `docs/evidence/perf/rdp_YYYYMMDD_HHMMSS/`

Each folder contains:

- run logs (`*.log`)
- parsed run JSON (`*.json`)
- summary JSON + Markdown

## 3) Emulator beta smoke evidence

```powershell
# Beta OFF/ON scenarios should be run separately in the app settings.
.\scripts\emulator_smoke.ps1 -Serial "emulator-5554"
```

Output folder:

- `docs/evidence/emulator/smoke_<serial>_<timestamp>/`

Contains command artifacts and `emulator_smoke_report.json`.

## 4) Rack + Maestro blocking signoff

Follow checklist and store notes in your signoff evidence folder:

- `docs/RELEASE_CHECKLIST_2_0.md`
- `docs/evidence/rack/`
- `docs/evidence/maestro/`

Recommended evidence files:

- `rack_signoff_<date>.md`
- `maestro_signoff_<date>.md`
- critical exported manifests (`quantum_handoff.json`)

## 5) Final release promotion

After blocking signoff passes:

1. Update changelog for final `2.0.0` entry.
2. Ensure release workflow is green.
3. Tag and publish:
   - `v2.0.0`
   - `QuantumInspector.exe`
   - checksums
   - validation summary + known limitations
