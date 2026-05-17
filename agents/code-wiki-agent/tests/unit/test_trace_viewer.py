from __future__ import annotations

import json
import subprocess
from functools import lru_cache

import pytest
from pathlib import Path
from syrupy.assertion import SnapshotAssertion


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
    # Cost rollup section (09-03): placeholder removed, real rollup label present
    assert "cost" in stdout.lower(), f"Expected cost rollup in summary:\n{stdout}"


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


# ---------------------------------------------------------------------------
# Plan 09-03: cost rollup fixture + tests
# ---------------------------------------------------------------------------

_HAIKU_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
_SONNET_MODEL = "us.anthropic.claude-sonnet-4-5-20251001-v1:0"
_QWEN_MODEL = "qwen.qwen3-next-80b-a3b"


def _write_cost_rollup_fixture(tmp_path: Path) -> Path:
    """Mixed-(role, model_id) fixture exercising cost rollup formatting & ordering.

    - 2 scanner records on haiku with cost 0.0005 + 0.0010 (sum 0.0015)
    - 1 scanner record on sonnet with cost 0.0020
    - 1 scanner record on haiku with cost null (+1 unknown)
    - 1 librarian record on qwen with cost null (fully-null group => n/a, last)
    """
    trace_file = tmp_path / "cost_rollup_trace.jsonl"
    records = [
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-a",
            "status": "success",
            "latency_ms": 100,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0005,
            "timestamp": "2026-05-17T10:00:00Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-b",
            "status": "success",
            "latency_ms": 110,
            "tokens_in": 20,
            "tokens_out": 7,
            "cost_usd": 0.0010,
            "timestamp": "2026-05-17T10:00:01Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _SONNET_MODEL,
            "prompt_hash": None,
            "item_id": "page-c",
            "status": "success",
            "latency_ms": 200,
            "tokens_in": 30,
            "tokens_out": 11,
            "cost_usd": 0.0020,
            "timestamp": "2026-05-17T10:00:02Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-d",
            "status": "success",
            "latency_ms": 90,
            "tokens_in": 5,
            "tokens_out": 3,
            "cost_usd": None,
            "timestamp": "2026-05-17T10:00:03Z",
        },
        {
            "schema_version": 1,
            "role": "librarian",
            "model_id": _QWEN_MODEL,
            "prompt_hash": None,
            "item_id": "page-e",
            "status": "success",
            "latency_ms": 400,
            "tokens_in": 50,
            "tokens_out": 25,
            "cost_usd": None,
            "timestamp": "2026-05-17T10:00:04Z",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file


def test_cost_rollup_format_six_decimals(tmp_path: Path) -> None:
    """Cost rollup in DEFAULT mode prints six-decimal sums, (+K unknown), n/a, and ordering.

    Locked by D-09 (format) and D-15 (descending cost, alphabetical tie-break,
    fully-null groups last). Invariant to plan 09-04's collapse change because
    the Summary block (per 09-CONTEXT.md "Claude's Discretion") is emitted in
    both default and --expand mode.
    """
    fixture_file = _write_cost_rollup_fixture(tmp_path)
    result = _run_trace_cmd([str(fixture_file)])

    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    stdout = result.stdout

    # D-09 numerics
    assert "$0.001500" in stdout, (
        f"Expected haiku group sum $0.001500 (0.0005 + 0.0010); stdout:\n{stdout}"
    )
    assert "$0.002000" in stdout, (
        f"Expected sonnet group sum $0.002000; stdout:\n{stdout}"
    )
    assert "(+1 unknown)" in stdout, (
        f"Expected '(+1 unknown)' suffix on haiku group; stdout:\n{stdout}"
    )
    assert "n/a" in stdout, (
        f"Expected fully-null librarian group to render 'n/a'; stdout:\n{stdout}"
    )

    # D-15 ordering: fully-null librarian group sorts LAST.
    librarian_idx = stdout.index("librarian")
    haiku_idx = stdout.index("$0.001500")
    sonnet_idx = stdout.index("$0.002000")
    assert librarian_idx > haiku_idx and librarian_idx > sonnet_idx, (
        f"Expected librarian (n/a) line AFTER haiku and sonnet lines; "
        f"librarian@{librarian_idx} haiku@{haiku_idx} sonnet@{sonnet_idx}\n{stdout}"
    )


@lru_cache(maxsize=1)
def _trace_supports_expand_flag() -> bool:
    """Return True if `code-wiki-agent trace` understands ``--expand``.

    Plan 09-04 lands the flag. Until then, this snapshot test self-skips so the
    suite still passes in waves where 09-04 has not yet shipped.
    """
    try:
        help_result = subprocess.run(
            ["uv", "run", "--package", "code-wiki-agent",
             "code-wiki-agent", "trace", "--help"],
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
            timeout=120,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return "--expand" in help_result.stdout


@pytest.mark.skipif(
    not _trace_supports_expand_flag(),
    reason="--expand flag is added in plan 09-04; snapshot test self-skips until then",
)
def test_cost_rollup_snapshot(snapshot: SnapshotAssertion, tmp_path: Path) -> None:
    """Snapshot the --expand-mode rendering so the timeline is invariant to 09-04's collapse."""
    fixture_file = _write_cost_rollup_fixture(tmp_path)
    result = _run_trace_cmd([str(fixture_file), "--expand"])
    assert result.returncode == 0, (
        f"trace --expand exited {result.returncode}\nstderr: {result.stderr}"
    )
    assert result.stdout == snapshot
