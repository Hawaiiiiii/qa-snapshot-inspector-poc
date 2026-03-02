"""Validate Maestro handoff evidence package and workspace links.

Usage:
  .venv\\Scripts\\python.exe scripts\\maestro_signoff_check.py --workspace C:\\path\\to\\radio-maestro-regression
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]


def _latest_manifest(workspace: Path) -> Path | None:
    root = workspace / "artifacts" / "runs" / "quantum"
    if not root.exists():
        return None
    manifests = [p for p in root.glob("*/quantum_handoff.json") if p.is_file()]
    if not manifests:
        return None
    manifests.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return manifests[0]


def _collect_artifact_paths(manifest: Dict[str, object]) -> List[str]:
    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return []
    output: List[str] = []
    for key in ("core_files", "frame_files", "xml_dumps", "xml_compressed", "crash_files"):
        values = artifacts.get(key, [])
        if isinstance(values, list):
            output.extend(str(v) for v in values)
    for key in ("latest_frame", "latest_xml_dump", "latest_log"):
        val = artifacts.get(key, "")
        if val:
            output.append(str(val))
    bookmarks = artifacts.get("bookmarks", [])
    if isinstance(bookmarks, list):
        for item in bookmarks:
            if not isinstance(item, dict):
                continue
            for key in ("screenshot", "dump", "logcat", "meta"):
                val = item.get(key, "")
                if val:
                    output.append(str(val))
    return sorted(set(output))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Maestro handoff package compatibility.")
    parser.add_argument("--workspace", required=True, help="Path to Maestro workspace repository.")
    parser.add_argument("--manifest", default="", help="Optional explicit quantum_handoff.json path.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional output report path. Defaults under docs/evidence/maestro.",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    manifest_path = Path(args.manifest).resolve() if args.manifest else _latest_manifest(workspace)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    output_path = (
        Path(args.output).resolve()
        if args.output
        else REPO_ROOT / "docs" / "evidence" / "maestro" / f"maestro_signoff_check_{stamp}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    checks = {
        "workspace_exists": workspace.exists(),
        "flows_dir_exists": (workspace / "flows").exists(),
        "manifest_exists": bool(manifest_path and manifest_path.exists()),
        "schema_ok": False,
        "schema_version_ok": False,
        "artifact_paths_resolve": False,
    }
    missing_artifacts: List[str] = []
    manifest_data: Dict[str, object] = {}

    if checks["manifest_exists"] and manifest_path:
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = {}
        checks["schema_ok"] = manifest_data.get("schema") == "quantum_handoff.v1"
        checks["schema_version_ok"] = int(manifest_data.get("schema_version", 0)) == 1

        artifacts = _collect_artifact_paths(manifest_data)
        export_root = manifest_path.parent
        for rel in artifacts:
            if not (export_root / rel).exists():
                missing_artifacts.append(rel)
        checks["artifact_paths_resolve"] = len(missing_artifacts) == 0

    passed = all(checks.values())
    report = {
        "schema": "quantum_maestro_signoff_check.v1",
        "generated_at_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workspace": str(workspace),
        "manifest_path": str(manifest_path) if manifest_path else "",
        "checks": checks,
        "missing_artifacts": missing_artifacts,
        "passed": passed,
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

