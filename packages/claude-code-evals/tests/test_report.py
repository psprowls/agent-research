from __future__ import annotations

import json
from pathlib import Path

from claude_code_evals.report import RunRecord, build_report


def _write_run(run_dir: Path, scenario: str, config: str, passed: bool) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "scenario": scenario,
                "config": config,
                "final_status": "success",
                "wall_seconds": 5.0,
            }
        )
    )
    (run_dir / "metrics.json").write_text(
        json.dumps(
            {
                "input_tokens": 100,
                "output_tokens": 50,
                "turn_count": 2,
                "verify_passed": passed,
                "distinct_paths_touched": 1,
            }
        )
    )
    (run_dir / "verify.json").write_text(
        json.dumps(
            {
                "success": passed,
                "verifiers": [],
            }
        )
    )


def test_build_report_markdown(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir / "scenario-a" / "base" / "1000", "scenario-a", "base", True)
    _write_run(runs_dir / "scenario-b" / "base" / "1001", "scenario-b", "base", False)

    md, data = build_report(runs_dir=runs_dir, runset_name="smoke")

    assert "smoke" in md
    assert "scenario-a" in md
    assert "scenario-b" in md
    assert isinstance(data, list)
    assert len(data) == 2


def test_build_report_pass_fail_counts(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir / "s1" / "base" / "100", "s1", "base", True)
    _write_run(runs_dir / "s2" / "base" / "101", "s2", "base", True)
    _write_run(runs_dir / "s3" / "base" / "102", "s3", "base", False)

    _, data = build_report(runs_dir=runs_dir, runset_name="test")
    passed = sum(1 for r in data if r.get("verify_passed"))
    assert passed == 2


def test_run_record_dataclass():
    r = RunRecord(
        scenario="x",
        config="base",
        passed=True,
        wall_seconds=3.0,
        input_tokens=10,
        output_tokens=5,
        run_dir=Path("/tmp/x"),
    )
    assert r.passed is True
