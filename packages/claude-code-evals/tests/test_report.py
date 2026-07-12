from __future__ import annotations

import json
from pathlib import Path

from claude_code_evals.report import build_report, generate_matrix_report


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


def test_build_report_surfaces_failure_reason(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "crashed" / "base" / "1000"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "scenario": "crashed",
                "config": "base",
                "final_status": "error_no_result",
                "error_reason": "error: unknown option '--config-dir'",
                "wall_seconds": 0.3,
            }
        )
    )
    (run_dir / "metrics.json").write_text(json.dumps({"input_tokens": 0, "output_tokens": 0, "verify_passed": False}))
    (run_dir / "verify.json").write_text(json.dumps({"success": False, "verifiers": []}))

    md, data = build_report(runs_dir=runs_dir, runset_name="smoke")

    assert "error_no_result" in md
    assert "unknown option" in md
    assert data[0]["final_status"] == "error_no_result"
    assert data[0]["error_reason"] == "error: unknown option '--config-dir'"


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


def test_report_generates_scenario_by_arm_matrix():
    """Report includes a scenario × arm matrix with verdicts."""
    results = {
        "wiki-design-tokens": {
            "base": {"score": 0.2, "files_read_count": 15},
            "injected": {"score": 1.0, "files_read_count": 8},
            "plugin": {"score": 0.8, "files_read_count": 12},
            "verdict": {
                "verdict": "WIKI_HELPED",
                "reason": "correctness: base failed, injected passed",
            },
        },
        "wiki-api-client": {
            "base": {"score": 1.0, "files_read_count": 29},
            "injected": {"score": 1.0, "files_read_count": 8},
            "plugin": {"score": 1.0, "files_read_count": 11},
            "verdict": {
                "verdict": "WIKI_HELPED",
                "reason": "efficiency: files_read_count improved 62%",
            },
        },
    }

    report = generate_matrix_report(results)

    assert "scenario" in report.lower()
    assert "base" in report
    assert "injected" in report
    assert "plugin" in report
    assert "wiki_design_tokens" in report or "wiki-design-tokens" in report
    assert "WIKI_HELPED" in report


def test_report_generates_json_matrix():
    """Report can be generated in JSON format for programmatic diffing."""
    results = {
        "wiki-design-tokens": {
            "base": {"score": 0.2},
            "verdict": {"verdict": "WIKI_HELPED"},
        },
    }

    report_json = generate_matrix_report(results, format="json")
    parsed = json.loads(report_json)

    assert parsed["wiki-design-tokens"]["verdict"]["verdict"] == "WIKI_HELPED"
