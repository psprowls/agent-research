"""Build Markdown + JSON report from runset run artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, PackageLoader


@dataclass
class RunRecord:
    scenario: str
    config: str
    passed: bool
    wall_seconds: float
    input_tokens: int
    output_tokens: int
    run_dir: Path
    final_status: str = "success"
    error_reason: str | None = None


def _load_run_record(run_dir: Path) -> RunRecord | None:
    meta_path = run_dir / "meta.json"
    metrics_path = run_dir / "metrics.json"
    verify_path = run_dir / "verify.json"
    if not (meta_path.exists() and metrics_path.exists()):
        return None
    meta = json.loads(meta_path.read_text())
    metrics = json.loads(metrics_path.read_text())
    verify = json.loads(verify_path.read_text()) if verify_path.exists() else {}
    return RunRecord(
        scenario=meta.get("scenario", run_dir.parent.parent.name),
        config=meta.get("config", run_dir.parent.name),
        passed=verify.get("success", metrics.get("verify_passed", False)),
        wall_seconds=meta.get("wall_seconds", 0.0),
        input_tokens=metrics.get("input_tokens", 0),
        output_tokens=metrics.get("output_tokens", 0),
        run_dir=run_dir,
        final_status=meta.get("final_status", "success"),
        error_reason=meta.get("error_reason"),
    )


def collect_runs(runs_dir: Path) -> list[RunRecord]:
    """Walk runs/ tree and collect the latest run per (scenario, config)."""
    records: list[RunRecord] = []
    if not runs_dir.exists():
        return records
    for scenario_dir in sorted(runs_dir.iterdir()):
        if not scenario_dir.is_dir():
            continue
        for config_dir in sorted(scenario_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            ts_dirs = sorted(config_dir.iterdir(), key=lambda p: p.name, reverse=True)
            for ts_dir in ts_dirs[:1]:
                rec = _load_run_record(ts_dir)
                if rec:
                    records.append(rec)
    return records


def build_report(*, runs_dir: Path, runset_name: str) -> tuple[str, list[dict]]:
    """Build Markdown report + JSON data from runs_dir."""
    records = collect_runs(runs_dir)
    data = [
        {
            "scenario": r.scenario,
            "config": r.config,
            "verify_passed": r.passed,
            "final_status": r.final_status,
            "error_reason": r.error_reason,
            "wall_seconds": round(r.wall_seconds, 2),
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
        }
        for r in records
    ]

    env = Environment(loader=PackageLoader("claude_code_evals", "templates"))
    template = env.get_template("report.md.j2")

    passed = sum(1 for r in records if r.passed)
    total = len(records)
    md = template.render(
        runset_name=runset_name,
        records=records,
        passed=passed,
        total=total,
        failed=total - passed,
    )
    return md, data
