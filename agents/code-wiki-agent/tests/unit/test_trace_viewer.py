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
