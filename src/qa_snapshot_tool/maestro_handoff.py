"""Maestro evidence handoff exporter for QUANTUM sessions."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List


def export_session_handoff(
    session_dir: Path,
    maestro_workspace: Path,
    locator_suggestions: List[Dict[str, Any]],
) -> Dict[str, Path]:
    session_dir = session_dir.resolve()
    maestro_workspace = maestro_workspace.resolve()
    run_root = maestro_workspace / "artifacts" / "runs" / "quantum"
    run_root.mkdir(parents=True, exist_ok=True)

    session_id = session_dir.name
    export_dir = run_root / session_id
    export_dir.mkdir(parents=True, exist_ok=True)

    copied_files: List[str] = []
    for relative in ("meta.json", "logcat_live.txt", "session.db"):
        src = session_dir / relative
        if src.exists():
            shutil.copy2(src, export_dir / src.name)
            copied_files.append(src.name)

    snapshots_src = session_dir / "bookmarks"
    snapshots_dst = export_dir / "bookmarks"
    if snapshots_src.exists():
        if snapshots_dst.exists():
            shutil.rmtree(snapshots_dst, ignore_errors=True)
        shutil.copytree(snapshots_src, snapshots_dst)
        copied_files.append("bookmarks/")

    manifest = {
        "schema": "quantum_handoff.v1",
        "generated_at": int(time.time()),
        "session_id": session_id,
        "source_session_dir": str(session_dir),
        "maestro_export_dir": str(export_dir),
        "copied_files": copied_files,
        "locator_suggestions": locator_suggestions,
    }

    manifest_path = export_dir / "quantum_handoff.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return {
        "export_dir": export_dir,
        "manifest_path": manifest_path,
    }
