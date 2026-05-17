from __future__ import annotations

import json
import subprocess

import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared JSONL fixture factory
# ---------------------------------------------------------------------------

def _write_trace_fixture(tmp_path: Path) -> Path:
    """Write a 2-record JSONL trace file: 1 success, 1 error."""
    trace_file = tmp_path / "test_trace.jsonl"
    records = [
        {
            "role": "scanner",
            "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "prompt_hash": None,
            "item_id": "page-a",
            "status": "success",
            "latency_ms": 350,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": None,
            "timestamp": "2026-05-13T10:00:00Z",
        },
        {
            "role": "scanner",
            "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "prompt_hash": None,
            "item_id": "page-b",
            "status": "error",
            "latency_ms": 120,
            "tokens_in": None,
            "tokens_out": None,
            "cost_usd": None,
            "timestamp": "2026-05-13T10:00:01Z",
            "error": "ThrottlingException",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file


_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


def _run_trace_cmd(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-agent", "trace"] + args,
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_trace_command_renders_per_record_lines(tmp_path: Path) -> None:
    """trace command outputs one line per record containing key fields."""
    trace_file = _write_trace_fixture(tmp_path)
    result = _run_trace_cmd([str(trace_file)])

    assert result.returncode == 0, f"trace exited {result.returncode}\n{result.stderr}"
    # Both records should produce lines with the role name
    lines = result.stdout.splitlines()
    role_lines = [l for l in lines if "scanner" in l]
    assert len(role_lines) >= 2, f"Expected >=2 lines with 'scanner'; got: {lines}"
    # Status indicators should appear
    assert "success" in result.stdout
    assert "error" in result.stdout
    # Latency values should appear
    assert "350" in result.stdout
    assert "120" in result.stdout


def test_trace_command_prints_summary_block(tmp_path: Path) -> None:
    """trace command prints a Summary block with aggregated token counts."""
    trace_file = _write_trace_fixture(tmp_path)
    result = _run_trace_cmd([str(trace_file)])

    assert result.returncode == 0, f"trace exited {result.returncode}\n{result.stderr}"
    stdout = result.stdout
    # Summary header must appear
    assert "Summary" in stdout, f"No 'Summary' in output:\n{stdout}"
    # Total tokens: success record contributes 10 in / 5 out; error record 0/0 (None treated as 0)
    # The aggregated total tokens_in=10, tokens_out=5 should appear
    assert "10" in stdout, f"Expected tokens_in total (10) in summary:\n{stdout}"
    assert "5" in stdout, f"Expected tokens_out total (5) in summary:\n{stdout}"
    # Record count should appear
    assert "2" in stdout, f"Expected 2 total records in summary:\n{stdout}"
    # Cost placeholder per CONTEXT D-08
    assert "Phase 4" in stdout or "cost" in stdout.lower(), f"Expected cost placeholder in summary:\n{stdout}"


def test_trace_command_missing_file_exits_nonzero() -> None:
    """trace command exits non-zero with actionable stderr when file is missing."""
    result = _run_trace_cmd(["/nonexistent/path.jsonl"])

    assert result.returncode != 0, f"Expected non-zero exit; got 0\nstdout: {result.stdout}"
    # Stderr should mention the path
    assert "/nonexistent/path.jsonl" in result.stderr, (
        f"Expected path in stderr; stderr was: {result.stderr}"
    )


def test_render_trace_record_pure_function() -> None:
    """_render_trace_record returns a string with role, item_id, status, latency_ms."""
    from code_wiki_agent.cli import _render_trace_record

    record = {
        "role": "scanner",
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "item_id": "page-a",
        "status": "success",
        "latency_ms": 350,
        "tokens_in": 10,
        "tokens_out": 5,
        "timestamp": "2026-05-13T10:00:00Z",
    }
    output = _render_trace_record(record)

    assert isinstance(output, str), "Expected string return"
    assert "scanner" in output, f"Expected 'scanner' in: {output}"
    assert "page-a" in output, f"Expected 'page-a' in: {output}"
    assert "success" in output, f"Expected 'success' in: {output}"
    assert "350" in output, f"Expected '350' in: {output}"


def test_aggregate_trace_by_role_model_groups_and_costs() -> None:
    """_aggregate_trace returns a by_role_model breakdown that:
    - keys per-item records by (role, model_id)
    - sums cost_usd across non-null records into cost_usd_sum
    - counts null-cost records into unknown_cost_count
    - excludes records carrying an 'event' or 'kind' key
    """
    from code_wiki_agent.cli import _aggregate_trace

    records = [
        # (a) two scanner records on haiku
        {
            "role": "scanner",
            "model_id": "claude-haiku-4-5",
            "item_id": "p-a",
            "status": "success",
            "latency_ms": 100,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0005,
            "timestamp": "2026-05-17T10:00:00Z",
        },
        {
            "role": "scanner",
            "model_id": "claude-haiku-4-5",
            "item_id": "p-b",
            "status": "success",
            "latency_ms": 110,
            "tokens_in": 20,
            "tokens_out": 7,
            "cost_usd": 0.001,
            "timestamp": "2026-05-17T10:00:01Z",
        },
        # (b) one scanner record on sonnet
        {
            "role": "scanner",
            "model_id": "claude-sonnet-4-5",
            "item_id": "p-c",
            "status": "success",
            "latency_ms": 200,
            "tokens_in": 30,
            "tokens_out": 11,
            "cost_usd": 0.002,
            "timestamp": "2026-05-17T10:00:02Z",
        },
        # (c) one scanner record on haiku with cost_usd null
        {
            "role": "scanner",
            "model_id": "claude-haiku-4-5",
            "item_id": "p-d",
            "status": "success",
            "latency_ms": 90,
            "tokens_in": 5,
            "tokens_out": 3,
            "cost_usd": None,
            "timestamp": "2026-05-17T10:00:03Z",
        },
        # (d) event record — excluded from rollup
        {
            "role": "scanner",
            "model_id": "claude-haiku-4-5",
            "event": "batch_cancelled",
            "items_total": 4,
            "items_completed": 4,
            "items_cancelled": 0,
            "wall_clock_ms": 1234,
            "timestamp": "2026-05-17T10:00:04Z",
        },
        # (e) kind: query_summary — excluded from rollup
        {
            "kind": "query_summary",
            "query_id": "q-1",
            "query": "what",
            "top_k": 5,
            "pages_retrieved": 3,
            "pages_drilled": 2,
            "code_fallback": False,
            "started_at": "2026-05-17T10:00:05Z",
            "ended_at": "2026-05-17T10:00:06Z",
        },
    ]

    agg = _aggregate_trace(records)

    assert "by_role_model" in agg, f"Expected 'by_role_model' key in agg: {agg}"
    brm = agg["by_role_model"]

    # Locate the haiku scanner group regardless of exact key shape (tuple, "role|model", or
    # list of dicts) by walking the structure into a canonical (role, model_id) -> stats dict.
    canonical: dict = {}
    if isinstance(brm, dict):
        for key, stats in brm.items():
            if isinstance(key, tuple):
                role, model_id = key
            elif isinstance(key, str) and "|" in key:
                role, model_id = key.split("|", 1)
            else:
                # dict-of-dicts where inner has role/model_id fields
                role = stats.get("role")
                model_id = stats.get("model_id")
            canonical[(role, model_id)] = stats
    elif isinstance(brm, list):
        for entry in brm:
            canonical[(entry["role"], entry["model_id"])] = entry
    else:
        raise AssertionError(f"by_role_model has unexpected type: {type(brm)!r}")

    haiku = canonical[("scanner", "claude-haiku-4-5")]
    sonnet = canonical[("scanner", "claude-sonnet-4-5")]

    assert haiku["count"] == 3, f"haiku count expected 3; got {haiku['count']}"
    assert haiku["cost_usd_sum"] == pytest.approx(0.0015), (
        f"haiku cost sum expected 0.0015; got {haiku['cost_usd_sum']}"
    )
    assert haiku["unknown_cost_count"] == 1, (
        f"haiku unknown_cost_count expected 1; got {haiku['unknown_cost_count']}"
    )

    assert sonnet["count"] == 1, f"sonnet count expected 1; got {sonnet['count']}"
    assert sonnet["cost_usd_sum"] == pytest.approx(0.002), (
        f"sonnet cost sum expected 0.002; got {sonnet['cost_usd_sum']}"
    )
    assert sonnet["unknown_cost_count"] == 0, (
        f"sonnet unknown_cost_count expected 0; got {sonnet['unknown_cost_count']}"
    )

    # event and kind records must be excluded
    assert len(canonical) == 2, (
        f"Expected exactly 2 (role, model_id) groups (event/kind excluded); got {list(canonical)}"
    )


def test_trace_command_skips_malformed_lines(tmp_path: Path) -> None:
    """trace command skips malformed JSONL lines with a stderr warning and continues rendering."""
    trace_file = tmp_path / "trace_with_bad_lines.jsonl"

    valid_a = {
        "role": "scanner",
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "prompt_hash": None,
        "item_id": "page-good-a",
        "status": "success",
        "latency_ms": 100,
        "tokens_in": 10,
        "tokens_out": 5,
        "cost_usd": None,
        "timestamp": "2026-05-13T10:00:00Z",
    }
    valid_b = {
        "role": "scanner",
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "prompt_hash": None,
        "item_id": "page-good-b",
        "status": "success",
        "latency_ms": 200,
        "tokens_in": 20,
        "tokens_out": 10,
        "cost_usd": None,
        "timestamp": "2026-05-13T10:00:01Z",
    }
    trace_file.write_text(
        json.dumps(valid_a) + "\n"
        + "not a valid {json line\n"
        + json.dumps(valid_b) + "\n"
    )

    result = _run_trace_cmd([str(trace_file)])

    assert result.returncode == 0, (
        f"Expected exit code 0; got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "page-good-a" in result.stdout, f"Expected 'page-good-a' in stdout: {result.stdout}"
    assert "page-good-b" in result.stdout, f"Expected 'page-good-b' in stdout: {result.stdout}"
    stderr_lower = result.stderr.lower()
    assert "malformed" in stderr_lower or "line 2" in stderr_lower, (
        f"Expected 'malformed' or 'line 2' in stderr; stderr was: {result.stderr}"
    )
