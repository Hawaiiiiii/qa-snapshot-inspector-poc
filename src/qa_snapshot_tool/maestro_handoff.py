"""Maestro evidence handoff exporter for QUANTUM sessions."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _read_meta(meta_path: Path) -> Dict[str, Any]:
    if not meta_path.exists():
        return {}
    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _iso_utc(unix_ts: Optional[float]) -> str:
    if not unix_ts:
        return ""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(unix_ts)))


def _copy_file_if_exists(
    session_dir: Path,
    export_dir: Path,
    source_path: Path,
    kind: str,
    copied: List[Dict[str, str]],
) -> Optional[str]:
    if not source_path.exists() or not source_path.is_file():
        return None
    try:
        source_rel = source_path.relative_to(session_dir).as_posix()
    except ValueError:
        source_rel = source_path.name
    destination = export_dir / source_rel
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)
    export_rel = destination.relative_to(export_dir).as_posix()
    copied.append(
        {
            "kind": kind,
            "source_relpath": source_rel,
            "export_relpath": export_rel,
        }
    )
    return export_rel


def _copy_recent_files(
    session_dir: Path,
    export_dir: Path,
    source_root: Path,
    pattern: str,
    kind: str,
    copied: List[Dict[str, str]],
    limit: int = 20,
) -> List[str]:
    if not source_root.exists():
        return []
    files = [p for p in source_root.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    exported: List[str] = []
    for path in files[: max(1, int(limit))]:
        rel = _copy_file_if_exists(session_dir, export_dir, path, kind, copied)
        if rel:
            exported.append(rel)
    exported.sort()
    return exported


def _build_bookmark_entries(bookmarks_root: Path) -> List[Dict[str, str]]:
    if not bookmarks_root.exists():
        return []
    entries: List[Dict[str, str]] = []
    for folder in sorted([p for p in bookmarks_root.iterdir() if p.is_dir()], key=lambda p: p.name):
        payload: Dict[str, str] = {"bookmark_id": folder.name}
        for filename, key in (
            ("screenshot.png", "screenshot"),
            ("dump.uix", "dump"),
            ("logcat.txt", "logcat"),
            ("meta.json", "meta"),
        ):
            path = folder / filename
            if path.exists():
                payload[key] = path.relative_to(bookmarks_root.parent).as_posix()
        entries.append(payload)
    return entries


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
    if export_dir.exists():
        shutil.rmtree(export_dir, ignore_errors=True)
    export_dir.mkdir(parents=True, exist_ok=True)

    copied_entries: List[Dict[str, str]] = []
    core_files: List[str] = []
    for relative, kind in (
        ("meta.json", "core_meta"),
        ("session.db", "core_session_db"),
        ("logcat_live.txt", "core_log"),
    ):
        rel = _copy_file_if_exists(session_dir, export_dir, session_dir / relative, kind, copied_entries)
        if rel:
            core_files.append(rel)
    core_files.sort()

    snapshots_src = session_dir / "bookmarks"
    snapshots_dst = export_dir / "bookmarks"
    if snapshots_src.exists():
        shutil.copytree(snapshots_src, snapshots_dst)
        copied_entries.append(
            {
                "kind": "bookmarks",
                "source_relpath": "bookmarks/",
                "export_relpath": "bookmarks/",
            }
        )

    frames = _copy_recent_files(
        session_dir=session_dir,
        export_dir=export_dir,
        source_root=session_dir / "frames",
        pattern="*.png",
        kind="frame",
        copied=copied_entries,
        limit=30,
    )
    xml_dumps = _copy_recent_files(
        session_dir=session_dir,
        export_dir=export_dir,
        source_root=session_dir / "xml",
        pattern="*.uix",
        kind="xml",
        copied=copied_entries,
        limit=30,
    )
    xml_compressed = _copy_recent_files(
        session_dir=session_dir,
        export_dir=export_dir,
        source_root=session_dir / "xml",
        pattern="*.uix.z",
        kind="xml_compressed",
        copied=copied_entries,
        limit=30,
    )
    crash_files = _copy_recent_files(
        session_dir=session_dir,
        export_dir=export_dir,
        source_root=session_dir,
        pattern="crash_*.txt",
        kind="crash",
        copied=copied_entries,
        limit=20,
    )

    meta = _read_meta(session_dir / "meta.json")
    now = time.time()
    bookmarks = _build_bookmark_entries(snapshots_dst)
    copied_entries.sort(key=lambda item: item["export_relpath"])

    latest_frame = frames[-1] if frames else ""
    latest_xml_dump = xml_dumps[-1] if xml_dumps else ""
    latest_log = "logcat_live.txt" if (export_dir / "logcat_live.txt").exists() else ""
    display_id = meta.get("display_id")
    if display_id is None:
        display_id = ""

    manifest = {
        "schema": "quantum_handoff.v1",
        "schema_version": 1,
        "generated_at": {
            "unix": int(now),
            "iso": _iso_utc(now),
        },
        "session": {
            "id": session_id,
            "source_session_dir": str(session_dir),
            "source_session_db": str(session_dir / "session.db"),
            "maestro_export_dir": str(export_dir),
            "start_ts": meta.get("start_ts"),
            "start_iso": str(meta.get("start_iso") or _iso_utc(meta.get("start_ts"))),
            "end_ts": meta.get("end_ts"),
            "end_iso": str(meta.get("end_iso") or _iso_utc(meta.get("end_ts"))),
            "status": str(meta.get("status") or "unknown"),
        },
        "device": {
            "serial": str(meta.get("serial") or ""),
            "model": str(meta.get("model") or "Unknown"),
            "environment_type": str(meta.get("environment_type") or "rack"),
            "profile": str(meta.get("profile") or "rack_aaos"),
        },
        "display_context": {
            "display_id": str(display_id),
            "source_preferred_display_id": str(meta.get("preferred_display_id") or ""),
            "focus": str(meta.get("focus") or ""),
        },
        "artifacts": {
            "core_files": core_files,
            "latest_frame": latest_frame,
            "latest_xml_dump": latest_xml_dump,
            "latest_log": latest_log,
            "frame_files": frames,
            "xml_dumps": xml_dumps,
            "xml_compressed": xml_compressed,
            "crash_files": crash_files,
            "bookmarks": bookmarks,
            "copied_entries": copied_entries,
        },
        "locator_bundle": {
            "count": len(locator_suggestions),
            "suggestions": locator_suggestions,
        },
        # Backward-compatible aliases consumed by existing callers.
        "session_id": session_id,
        "source_session_dir": str(session_dir),
        "maestro_export_dir": str(export_dir),
        "copied_files": [entry["export_relpath"] for entry in copied_entries],
        "locator_suggestions": locator_suggestions,
    }

    manifest_path = export_dir / "quantum_handoff.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return {
        "export_dir": export_dir,
        "manifest_path": manifest_path,
    }
