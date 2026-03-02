# QUANTUM 2.0 Release Checklist

Use this checklist before publishing installer assets to GitHub Releases.

## 1) Branch and version consistency

- [ ] Branch is `release/2.0.0-rc1` (or final release branch).
- [ ] `pyproject.toml` version is correct for target release.
- [ ] `CHANGELOG.md` includes the release entry and date.
- [ ] `README.md` and docs reflect current runtime behavior.

## 2) Automated gates (local)

Run:

```powershell
.\scripts\release_gate.ps1
```

Expected:

- [ ] `pytest` passes.
- [ ] `compileall` passes for `src/qa_snapshot_tool`, `src/qa_snapshot_native`, and `scripts`.

Optional strict performance check (requires recorded session):

```powershell
.\scripts\release_gate.ps1 -Strict
```

Optional executable build:

```powershell
.\scripts\release_gate.ps1 -BuildExe
```

## 3) CI gates

- [ ] CI workflow (`.github/workflows/ci.yml`) passes.
- [ ] Release build workflow (`.github/workflows/release-build.yml`) passes on Windows Python 3.11.
- [ ] Artifact `QuantumInspector-windows-exe` is produced.

## 4) Functional acceptance (manual)

### Core runtime

- [ ] App starts from source with `.venv\Scripts\python.exe src/qa_snapshot_tool/main.py`.
- [ ] Live start/stop works with recorder auto-session.
- [ ] Timeline tab shows events and opens event/session files.
- [ ] Crash marker appears in active session if forced crash occurs.

### Multi-device (rack)

- [ ] 2-device concurrent live run stable for at least 10 minutes.
- [ ] 3-device concurrent live run stable for at least 10 minutes.
- [ ] Active/background scheduling behaves as expected (active stays responsive).
- [ ] No cross-device leakage in tree, overlays, or logs.

### Capability gating

- [ ] Emulator beta OFF blocks unsupported emulator actions with clear message.
- [ ] Emulator beta ON allows emulator runtime paths.
- [ ] Unsupported actions are disabled in UI where required.

### Maestro handoff

- [ ] Export succeeds to `<workspace>/artifacts/runs/quantum/<session_id>/`.
- [ ] `quantum_handoff.json` exists and references real files.
- [ ] "Open folder", "Copy manifest path", and "Open Maestro flows" actions work.

### Performance and stability

- [ ] `scripts/profile_hotspots.py --targets balanced --enforce-targets` passes on representative machine/session.
- [ ] No sustained runaway memory growth in long live session.

## 5) Packaging and publishing

- [ ] Build `dist/QuantumInspector.exe` on Python 3.11.
- [ ] Smoke-run executable on clean test machine profile.
- [ ] Create GitHub Release notes with known limitations and validation summary.
- [ ] Upload executable artifact and checksums.
