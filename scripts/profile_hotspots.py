"""Hotspot profiler for QUANTUM 2.0 paths.

Usage:
  .venv\\Scripts\\python.exe scripts\\profile_hotspots.py
  .venv\\Scripts\\python.exe scripts\\profile_hotspots.py --session <path>
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import sys
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtGui import QImage

from qa_snapshot_native import backend_name, frame_sha1, smallest_hit
from qa_snapshot_tool.settings import AppSettings
from qa_snapshot_tool.uix_parser import UixParser

TARGETS = {
    "balanced": {
        "frame_sha1": {"avg_ms": 8.0, "p95_ms": 16.0},
        "xml_parse": {"avg_ms": 30.0, "p95_ms": 60.0},
        "smallest_hit": {"avg_ms": 4.0, "p95_ms": 8.0},
    },
    "strict": {
        "frame_sha1": {"avg_ms": 5.0, "p95_ms": 10.0},
        "xml_parse": {"avg_ms": 20.0, "p95_ms": 45.0},
        "smallest_hit": {"avg_ms": 2.5, "p95_ms": 5.0},
    },
}


def benchmark(label: str, fn, rounds: int = 100) -> dict:
    samples: List[float] = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    samples.sort()
    p95_idx = int(round((len(samples) - 1) * 0.95))
    return {
        "label": label,
        "rounds": rounds,
        "avg_ms": statistics.fmean(samples),
        "p95_ms": samples[p95_idx],
        "min_ms": samples[0],
        "max_ms": samples[-1],
    }


def evaluate_targets(benchmarks: List[Dict[str, float]], profile: str) -> Dict[str, object]:
    target = TARGETS.get(profile, TARGETS["balanced"])
    by_label = {str(item.get("label")): item for item in benchmarks}
    checks = []
    passed = True
    for label, limits in target.items():
        sample = by_label.get(label)
        if not sample:
            passed = False
            checks.append(
                {
                    "label": label,
                    "status": "missing",
                    "limits": limits,
                }
            )
            continue
        avg_ok = float(sample.get("avg_ms", 0.0)) <= float(limits["avg_ms"])
        p95_ok = float(sample.get("p95_ms", 0.0)) <= float(limits["p95_ms"])
        status = "pass" if (avg_ok and p95_ok) else "fail"
        if status != "pass":
            passed = False
        checks.append(
            {
                "label": label,
                "status": status,
                "avg_ms": sample.get("avg_ms"),
                "p95_ms": sample.get("p95_ms"),
                "limits": limits,
            }
        )
    return {
        "profile": profile,
        "passed": passed,
        "checks": checks,
    }


def newest_session(root: Path) -> Path | None:
    sessions = [p for p in root.iterdir() if p.is_dir() and (p / "session.db").exists()]
    if not sessions:
        return None
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions[0]


def latest_frame(session: Path) -> Path | None:
    frames = list((session / "frames").glob("*.png"))
    if not frames:
        return None
    frames.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return frames[0]


def latest_xml(session: Path) -> Path | None:
    xmls = list((session / "xml").glob("*.uix"))
    if not xmls:
        return None
    xmls.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return xmls[0]


def collect_rects(xml_text: str) -> list:
    root, _ = UixParser.parse(xml_text)
    rects = []
    if not root:
        return rects

    def walk(node):
        if node.valid_bounds:
            rects.append((node.rect, node.class_name))
        for child in node.children:
            walk(child)

    walk(root)
    return rects


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile QUANTUM hotspot functions.")
    parser.add_argument("--session", default="", help="Session folder path. Defaults to newest local session.")
    parser.add_argument("--rounds", type=int, default=100, help="Benchmark rounds per hotspot.")
    parser.add_argument(
        "--targets",
        choices=sorted(TARGETS.keys()),
        default="balanced",
        help="Performance acceptance profile used for pass/fail evaluation.",
    )
    parser.add_argument(
        "--enforce-targets",
        action="store_true",
        help="Return non-zero exit code when target profile checks fail.",
    )
    args = parser.parse_args()

    if args.session:
        session = Path(args.session).resolve()
    else:
        session_root = AppSettings.load().session_root_path()
        candidate = newest_session(session_root)
        if not candidate:
            print("No sessions found. Start a live session first.")
            return 1
        session = candidate

    frame_path = latest_frame(session)
    xml_path = latest_xml(session)
    if not frame_path or not xml_path:
        print(f"Session missing frame/xml data: {session}")
        return 1

    frame_bytes = frame_path.read_bytes()
    xml_text = xml_path.read_text(encoding="utf-8", errors="replace")
    rects = collect_rects(xml_text)
    image = QImage(str(frame_path))
    if image.isNull():
        print(f"Failed to decode frame: {frame_path}")
        return 1

    benchmarks = [
        benchmark("frame_sha1", lambda: frame_sha1(frame_bytes), rounds=args.rounds),
        benchmark("xml_parse", lambda: UixParser.parse(xml_text), rounds=max(20, args.rounds // 4)),
        benchmark(
            "smallest_hit",
            lambda: smallest_hit(rects, image.width() // 2, image.height() // 2),
            rounds=args.rounds,
        ),
    ]
    acceptance = evaluate_targets(benchmarks, profile=args.targets)

    results = {
        "backend": backend_name(),
        "session": str(session),
        "frame": str(frame_path.name),
        "xml": str(xml_path.name),
        "node_rects": len(rects),
        "benchmarks": benchmarks,
        "acceptance": acceptance,
    }
    print(json.dumps(results, indent=2))
    if args.enforce_targets and not bool(acceptance.get("passed")):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
