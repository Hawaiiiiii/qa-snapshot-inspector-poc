"""Capture QUANTUM hotspot profiling evidence for local/RDP A/B runs.

Usage:
  .venv\\Scripts\\python.exe scripts\\perf_ab_capture.py --env local --runs 3
  .venv\\Scripts\\python.exe scripts\\perf_ab_capture.py --env rdp --runs 3 --session <session_dir>
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_SCRIPT = REPO_ROOT / "scripts" / "profile_hotspots.py"
DEFAULT_OUT = REPO_ROOT / "docs" / "evidence" / "perf"
UTC = dt.UTC


def _extract_json(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON payload found in profiler output")
    return json.loads(text[start : end + 1])


def _run_once(
    python_exe: Path,
    env_name: str,
    run_idx: int,
    runs: int,
    targets: str,
    rounds: int,
    session: str,
    out_dir: Path,
    enforce_targets: bool,
) -> Dict[str, Any]:
    cmd: List[str] = [
        str(python_exe),
        str(PROFILE_SCRIPT),
        "--targets",
        targets,
        "--rounds",
        str(rounds),
    ]
    if session:
        cmd += ["--session", session]
    if enforce_targets:
        cmd += ["--enforce-targets"]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")

    stamp = dt.datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    base = f"{env_name}_run_{run_idx:02d}_of_{runs}_{stamp}"
    log_path = out_dir / f"{base}.log"
    json_path = out_dir / f"{base}.json"
    log_path.write_text(combined, encoding="utf-8", errors="replace")

    parsed: Dict[str, Any] = {}
    parse_error = ""
    try:
        parsed = _extract_json(combined)
        json_path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    except Exception as ex:
        snippet = combined.strip().splitlines()[-1] if combined.strip() else ""
        parse_error = f"{ex}: {snippet}".strip()

    return {
        "run": run_idx,
        "exit_code": int(proc.returncode),
        "log_path": str(log_path),
        "json_path": str(json_path),
        "parsed": parsed,
        "parse_error": parse_error,
    }


def _summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_runs = [r for r in results if r.get("parsed")]
    acceptance_pass_count = 0
    metrics: Dict[str, List[Dict[str, float]]] = {}

    for run in ok_runs:
        parsed = run["parsed"]
        acceptance = parsed.get("acceptance", {})
        if bool(acceptance.get("passed")):
            acceptance_pass_count += 1
        for bench in parsed.get("benchmarks", []):
            label = str(bench.get("label"))
            metrics.setdefault(label, []).append(
                {
                    "avg_ms": float(bench.get("avg_ms", 0.0)),
                    "p95_ms": float(bench.get("p95_ms", 0.0)),
                }
            )

    metric_summary: Dict[str, Dict[str, float]] = {}
    for label, samples in metrics.items():
        metric_summary[label] = {
            "avg_of_avg_ms": statistics.fmean([s["avg_ms"] for s in samples]),
            "avg_of_p95_ms": statistics.fmean([s["p95_ms"] for s in samples]),
            "worst_avg_ms": max(s["avg_ms"] for s in samples),
            "worst_p95_ms": max(s["p95_ms"] for s in samples),
            "samples": float(len(samples)),
        }

    return {
        "runs_total": len(results),
        "runs_with_parsed_json": len(ok_runs),
        "acceptance_pass_count": acceptance_pass_count,
        "metric_summary": metric_summary,
    }


def _write_markdown(
    out_path: Path,
    env_name: str,
    target_profile: str,
    results: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> None:
    lines: List[str] = []
    lines.append(f"# QUANTUM perf evidence ({env_name})")
    lines.append("")
    lines.append(f"- Target profile: `{target_profile}`")
    lines.append(f"- Runs total: {summary['runs_total']}")
    lines.append(f"- Runs parsed: {summary['runs_with_parsed_json']}")
    lines.append(f"- Acceptance pass count: {summary['acceptance_pass_count']}")
    lines.append("")

    lines.append("## Run results")
    lines.append("")
    lines.append("| Run | Exit | Parsed | Acceptance | JSON | Log |")
    lines.append("| --- | ---: | :---: | :---: | --- | --- |")
    for run in results:
        parsed = bool(run.get("parsed"))
        acceptance = "n/a"
        if parsed:
            acceptance = "pass" if run["parsed"].get("acceptance", {}).get("passed") else "fail"
        lines.append(
            "| "
            f"{run['run']} | {run['exit_code']} | {'yes' if parsed else 'no'} | {acceptance} | "
            f"`{Path(run['json_path']).name}` | `{Path(run['log_path']).name}` |"
        )

    lines.append("")
    lines.append("## Metric summary")
    lines.append("")
    lines.append("| Metric | avg(avg_ms) | avg(p95_ms) | worst(avg_ms) | worst(p95_ms) | samples |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for label, data in summary.get("metric_summary", {}).items():
        lines.append(
            "| "
            f"{label} | {data['avg_of_avg_ms']:.2f} | {data['avg_of_p95_ms']:.2f} | "
            f"{data['worst_avg_ms']:.2f} | {data['worst_p95_ms']:.2f} | {int(data['samples'])} |"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture A/B profiling evidence for QUANTUM signoff.")
    parser.add_argument("--env", required=True, help="Environment label (for example: local, rdp).")
    parser.add_argument("--runs", type=int, default=3, help="Number of profiling runs.")
    parser.add_argument("--targets", default="balanced", help="Target profile passed to profile_hotspots.py.")
    parser.add_argument("--rounds", type=int, default=100, help="Rounds per profiler run.")
    parser.add_argument("--session", default="", help="Optional explicit session directory.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUT), help="Output directory root.")
    parser.add_argument("--enforce-targets", action="store_true", help="Fail run if profiler target check fails.")
    parser.add_argument("--require-all-pass", action="store_true", help="Exit non-zero unless all runs pass acceptance.")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter used for subprocess runs.")
    args = parser.parse_args()

    runs = max(1, int(args.runs))
    out_root = Path(args.output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    batch_stamp = dt.datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_dir = out_root / f"{args.env}_{batch_stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    python_exe = Path(args.python).resolve()
    results: List[Dict[str, Any]] = []
    for idx in range(1, runs + 1):
        print(f"[perf] {args.env} run {idx}/{runs}")
        results.append(
            _run_once(
                python_exe=python_exe,
                env_name=args.env,
                run_idx=idx,
                runs=runs,
                targets=args.targets,
                rounds=max(10, int(args.rounds)),
                session=str(args.session or ""),
                out_dir=out_dir,
                enforce_targets=bool(args.enforce_targets),
            )
        )

    summary = _summarize(results)
    report = {
        "schema": "quantum_perf_ab.v1",
        "generated_at_utc": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": args.env,
        "target_profile": args.targets,
        "runs": runs,
        "host": {
            "platform": platform.platform(),
            "python": sys.version,
        },
        "batch_dir": str(out_dir),
        "summary": summary,
        "results": [
            {
                "run": r["run"],
                "exit_code": r["exit_code"],
                "log_path": r["log_path"],
                "json_path": r["json_path"],
                "parse_error": r["parse_error"],
                "acceptance_passed": bool(r.get("parsed", {}).get("acceptance", {}).get("passed")),
            }
            for r in results
        ],
    }

    report_json = out_dir / f"summary_{args.env}.json"
    report_md = out_dir / f"summary_{args.env}.md"
    report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(report_md, args.env, args.targets, results, summary)

    print(json.dumps(report, indent=2))

    if args.require_all_pass:
        if summary["runs_with_parsed_json"] != runs:
            return 3
        if summary["acceptance_pass_count"] != runs:
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
