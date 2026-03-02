"""Verify forced-crash preservation for QUANTUM recorder sessions.

Usage:
  .venv\\Scripts\\python.exe scripts\\verify_forced_crash_signoff.py
  .venv\\Scripts\\python.exe scripts\\verify_forced_crash_signoff.py --output docs/evidence/rack/forced_crash_check.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtGui import QColor, QImage

from qa_snapshot_tool.session_recorder import SessionRecorder, SessionRecorderRegistry


def _count_events(db_path: Path) -> Dict[str, int]:
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute("SELECT kind, COUNT(*) FROM events GROUP BY kind")
        rows = cur.fetchall()
        return {str(kind): int(count) for kind, count in rows}
    finally:
        con.close()


def _default_output() -> Path:
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d_%H%M%S")
    return REPO_ROOT / "docs" / "evidence" / "rack" / f"forced_crash_check_{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate forced-crash artifact preservation.")
    parser.add_argument(
        "--session-root",
        default=str(Path.home() / ".qa_snapshot_tool" / "sessions"),
        help="Session storage root used for the synthetic crash check.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output JSON report path. Defaults under docs/evidence/rack.",
    )
    parser.add_argument(
        "--serial",
        default="SIGNOFF:?*CRASH",
        help="Serial token used for session creation (invalid chars are intentional).",
    )
    args = parser.parse_args()

    session_root = Path(args.session_root).resolve()
    output_path = Path(args.output).resolve() if args.output else _default_output()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    recorder = SessionRecorder.start_session(
        session_root=session_root,
        serial=str(args.serial),
        model="SIGNOFF_MODEL",
        environment_type="rack",
        profile="rack_aaos",
        display_id="0",
        session_max_bytes=15 * 1024 * 1024 * 1024,
    )

    image = QImage(32, 32, QImage.Format_ARGB32)
    image.fill(QColor("#224466"))
    frame_path = recorder.record_frame(image, reason="event_pre_crash")
    xml_path = recorder.record_xml_dump(
        '<hierarchy><node class="android.widget.TextView" bounds="[0,0][10,10]"/></hierarchy>',
        reason="event_pre_crash",
    )
    recorder.record_log_line("forced crash preservation check")

    SessionRecorderRegistry.record_global_crash("forced crash signoff check")
    recorder.finish_session("crashed")

    crash_files: List[Path] = sorted(recorder.session_dir.glob("crash_*.txt"))
    event_counts = _count_events(recorder.db_path)
    checks = {
        "session_dir_exists": recorder.session_dir.exists(),
        "frame_preserved": bool(frame_path and frame_path.exists()),
        "xml_preserved": bool(xml_path and xml_path.exists()),
        "crash_file_present": bool(crash_files),
        "db_has_crash_event": int(event_counts.get("crash", 0)) >= 1,
    }
    passed = all(checks.values())

    report = {
        "schema": "quantum_forced_crash_check.v1",
        "generated_at_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "passed": passed,
        "session_dir": str(recorder.session_dir),
        "db_path": str(recorder.db_path),
        "checks": checks,
        "event_counts": event_counts,
        "crash_files": [str(p) for p in crash_files],
    }
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

