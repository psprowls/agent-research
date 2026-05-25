from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache

import pytest
from pathlib import Path
from syrupy.assertion import SnapshotAssertion

# Disable Rich's ANSI rendering so `trace --help` output is plain text — the
# `\x1b[1;36m--expand\x1b[0m` Typer/Rich emits otherwise breaks `"--expand" in stdout`.
_PLAIN_HELP_ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}


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
        ["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-agent", "trace"] + args,
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_trace_command_renders_per_record_lines(tmp_path: Path) -> None:
    """trace --expand outputs one line per record containing key fields.

    Uses --expand because plan 09-04 collapses consecutive same-role runs by
    default; per-record lines are the expand-mode invariant.
    """
    trace_file = _write_trace_fixture(tmp_path)
    result = _run_trace_cmd([str(trace_file), "--expand"])

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
    from graph_wiki_agent.cli import _render_trace_record

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
    from graph_wiki_agent.cli import _aggregate_trace

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

    # --expand keeps per-item lines visible across plan 09-04's default collapse.
    result = _run_trace_cmd([str(trace_file), "--expand"])

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

    # D-15 ordering: fully-null librarian group sorts LAST in the rollup.
    # Anchor on the n/a marker (unique to the librarian rollup line in this
    # fixture) so the assertion is not confused by the librarian's earlier
    # appearance in the Per-role breakdown section.
    librarian_rollup_idx = stdout.index("$n/a")
    haiku_idx = stdout.index("$0.001500")
    sonnet_idx = stdout.index("$0.002000")
    assert librarian_rollup_idx > haiku_idx and librarian_rollup_idx > sonnet_idx, (
        f"Expected librarian (n/a) rollup line AFTER haiku and sonnet rollup lines; "
        f"librarian_rollup@{librarian_rollup_idx} haiku@{haiku_idx} sonnet@{sonnet_idx}\n{stdout}"
    )


@lru_cache(maxsize=1)
def _trace_supports_expand_flag() -> bool:
    """Return True if `graph-wiki-agent trace` understands ``--expand``.

    Plan 09-04 lands the flag. Until then, this snapshot test self-skips so the
    suite still passes in waves where 09-04 has not yet shipped.
    """
    try:
        help_result = subprocess.run(
            ["uv", "run", "--package", "graph-wiki-agent",
             "graph-wiki-agent", "trace", "--help"],
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
            timeout=120,
            env=_PLAIN_HELP_ENV,
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


# ---------------------------------------------------------------------------
# Plan 09-04: --expand flag + consecutive-same-role group collapsing (OBS-06)
# ---------------------------------------------------------------------------


def _write_fan_out_fixture(
    tmp_path: Path,
    n: int = 4,
    role: str = "scanner",
    model_id: str = _HAIKU_MODEL,
) -> Path:
    """Write `n` consecutive per-item records with the same role/model_id.

    Each record carries schema_version=1, status='success', cost_usd=0.0001,
    monotonically increasing timestamps (HH:MM:00Z, :01Z, :02Z, :03Z, ...),
    tokens_in=10, tokens_out=5, and a distinct item_id ('page-0', 'page-1', ...).
    """
    trace_file = tmp_path / "fan_out_trace.jsonl"
    records = []
    for i in range(n):
        records.append({
            "schema_version": 1,
            "role": role,
            "model_id": model_id,
            "prompt_hash": None,
            "item_id": f"page-{i}",
            "status": "success",
            "latency_ms": 100 + i,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0001,
            "timestamp": f"2026-05-17T10:00:{i:02d}Z",
        })
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file


def test_trace_command_has_expand_flag() -> None:
    """`graph-wiki-agent trace --help` advertises the --expand flag (Task 1, D-14)."""
    result = subprocess.run(
        ["uv", "run", "--package", "graph-wiki-agent",
         "graph-wiki-agent", "trace", "--help"],
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
        timeout=120,
        env=_PLAIN_HELP_ENV,
    )
    assert result.returncode == 0, f"trace --help exited {result.returncode}: {result.stderr}"
    assert "--expand" in result.stdout, (
        f"Expected '--expand' in trace --help output:\n{result.stdout}"
    )


def test_default_mode_collapses_consecutive_same_role(tmp_path: Path) -> None:
    """Default mode collapses a 4-record same-role fan-out into ONE summary line (D-11, D-12, D-13).

    The summary line shape is `[<ts_first> .. <ts_last>] <role> x<N>: ...` per D-13.
    The per-item lines (with item_id substrings) must NOT appear in default mode.
    """
    fixture_file = _write_fan_out_fixture(tmp_path, n=4)
    result = _run_trace_cmd([str(fixture_file)])
    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    stdout = result.stdout

    # Exactly ONE collapsed group line for the 4 records. The collapsed-group
    # header surfaces both role and model_id (per CR-01 fix in plan 09-06), so
    # we assert each substring separately and pin them to the same line.
    timeline_for_marker = stdout.split("=== Summary ===")[0]
    marker_lines = [
        ln for ln in timeline_for_marker.splitlines()
        if "scanner" in ln and "x4:" in ln
    ]
    assert marker_lines, (
        f"Expected one collapsed-group line with 'scanner' and 'x4:' in default mode output:\n{stdout}"
    )
    # Per-item item_id substrings must not appear in the timeline portion
    # (Summary block contains aggregate counts only.)
    timeline = stdout.split("=== Summary ===")[0]
    assert "page-0" not in timeline, (
        f"Expected NO per-item 'page-0' line in collapsed timeline:\n{timeline}"
    )
    # ISO-8601 first/last timestamps in the summary line
    assert "2026-05-17T10:00:00Z" in stdout and "2026-05-17T10:00:03Z" in stdout, (
        f"Expected first/last timestamps in collapsed line:\n{stdout}"
    )
    # 4 success breakdown + summed tokens 40->20 + summed cost $0.000400 (4 * 0.0001)
    assert "4 success" in stdout, f"Expected '4 success' breakdown:\n{stdout}"
    assert "40->20 tokens" in stdout, f"Expected summed tokens '40->20 tokens':\n{stdout}"
    assert "$0.000400" in stdout, f"Expected summed cost '$0.000400':\n{stdout}"


def test_expand_mode_renders_every_record_full_line(tmp_path: Path) -> None:
    """--expand disables collapsing; every record renders full-line (D-14)."""
    fixture_file = _write_fan_out_fixture(tmp_path, n=4)
    result = _run_trace_cmd([str(fixture_file), "--expand"])
    assert result.returncode == 0, (
        f"trace --expand exited {result.returncode}\nstderr: {result.stderr}"
    )
    stdout = result.stdout
    timeline = stdout.split("=== Summary ===")[0]
    # All 4 item_ids appear as separate lines
    for i in range(4):
        assert f"page-{i}" in timeline, (
            f"Expected per-item 'page-{i}' line in --expand timeline:\n{timeline}"
        )
    # No collapsed-group marker (e.g. ` x4:` token); per-record lines never
    # carry the ` x<N>:` marker, only collapsed-group headers do.
    assert "x4:" not in stdout, (
        f"Did NOT expect ' x4:' collapse marker in --expand mode:\n{stdout}"
    )


# ---------------------------------------------------------------------------
# Plan 09-04 Task 2: snapshot tests covering collapse/expand/interleave/mixed
# ---------------------------------------------------------------------------


def _write_mixed_status_fixture(tmp_path: Path) -> Path:
    """Write 4 scanner records with statuses [success, success, error, cancelled].

    The cancelled record has cost_usd=null (drives the `(+1 unknown)` suffix in
    the collapsed line); the error record carries an `error` field with a short
    string; all share role/model_id so they form one group.
    """
    trace_file = tmp_path / "mixed_status_trace.jsonl"
    base_ts = "2026-05-17T10:00:"
    records = [
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-ok-1",
            "status": "success",
            "latency_ms": 100,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0001,
            "timestamp": f"{base_ts}00Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-ok-2",
            "status": "success",
            "latency_ms": 110,
            "tokens_in": 12,
            "tokens_out": 6,
            "cost_usd": 0.0002,
            "timestamp": f"{base_ts}01Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-err",
            "status": "error",
            "latency_ms": 80,
            "tokens_in": 5,
            "tokens_out": 0,
            "cost_usd": 0.0001,
            "timestamp": f"{base_ts}02Z",
            "error": "ThrottlingException",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-cancel",
            "status": "cancelled",
            "latency_ms": 50,
            "tokens_in": None,
            "tokens_out": None,
            "cost_usd": None,
            "timestamp": f"{base_ts}03Z",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file


def _write_interleaved_fixture(tmp_path: Path) -> Path:
    """Write 3 scanner records, then a `kind: query_summary` record, then 2 scanner records,
    then a final `event: batch_cancelled` record.

    Per D-11 the kind/event records break runs: expected default-mode timeline is
    `scanner x3:` (collapsed), then the query_summary full-line, then `scanner x2:`
    (collapsed), then the batch_cancelled full-line.
    """
    trace_file = tmp_path / "interleaved_trace.jsonl"
    base_ts = "2026-05-17T10:00:"
    records = [
        # Run 1 (groupable, 3 scanner records)
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
            "cost_usd": 0.0001,
            "timestamp": f"{base_ts}00Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-b",
            "status": "success",
            "latency_ms": 110,
            "tokens_in": 11,
            "tokens_out": 6,
            "cost_usd": 0.0001,
            "timestamp": f"{base_ts}01Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-c",
            "status": "success",
            "latency_ms": 120,
            "tokens_in": 12,
            "tokens_out": 7,
            "cost_usd": 0.0001,
            "timestamp": f"{base_ts}02Z",
        },
        # Non-groupable: kind=query_summary breaks the run
        {
            "schema_version": 1,
            "kind": "query_summary",
            "query_id": "q1",
            "query": "test",
            "top_k": 5,
            "pages_retrieved": 3,
            "pages_drilled": 1,
            "code_fallback": False,
            "started_at": f"{base_ts}03Z",
            "ended_at": f"{base_ts}04Z",
        },
        # Run 2 (groupable, 2 scanner records)
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-d",
            "status": "success",
            "latency_ms": 130,
            "tokens_in": 13,
            "tokens_out": 8,
            "cost_usd": 0.0001,
            "timestamp": f"{base_ts}05Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-e",
            "status": "success",
            "latency_ms": 140,
            "tokens_in": 14,
            "tokens_out": 9,
            "cost_usd": 0.0001,
            "timestamp": f"{base_ts}06Z",
        },
        # Non-groupable: event=batch_cancelled terminator also breaks runs
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "event": "batch_cancelled",
            "items_total": 5,
            "items_completed": 5,
            "items_cancelled": 0,
            "wall_clock_ms": 5000,
            "timestamp": f"{base_ts}07Z",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file


def _write_two_roles_fixture(tmp_path: Path) -> Path:
    """Write two records of DIFFERENT roles — each is a run of length 1.

    Isolated records (run length 1) must render full-line in default mode (no
    collapse marker `x1:` should appear).
    """
    trace_file = tmp_path / "two_roles_trace.jsonl"
    records = [
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "scanner-page",
            "status": "success",
            "latency_ms": 100,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0001,
            "timestamp": "2026-05-17T10:00:00Z",
        },
        {
            "schema_version": 1,
            "role": "librarian",
            "model_id": _QWEN_MODEL,
            "prompt_hash": None,
            "item_id": "librarian-page",
            "status": "success",
            "latency_ms": 400,
            "tokens_in": 50,
            "tokens_out": 25,
            "cost_usd": None,
            "timestamp": "2026-05-17T10:00:01Z",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file


def test_collapsed_default_snapshot(snapshot: SnapshotAssertion, tmp_path: Path) -> None:
    """4 consecutive same-role records, default mode, snapshot ONE collapsed line + Summary."""
    fixture_file = _write_fan_out_fixture(tmp_path, n=4)
    result = _run_trace_cmd([str(fixture_file)])
    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstderr: {result.stderr}"
    )
    assert result.stdout == snapshot


def test_expand_snapshot(snapshot: SnapshotAssertion, tmp_path: Path) -> None:
    """Same 4-record fixture as collapsed_default but with --expand: FOUR full-line records."""
    fixture_file = _write_fan_out_fixture(tmp_path, n=4)
    result = _run_trace_cmd([str(fixture_file), "--expand"])
    assert result.returncode == 0, (
        f"trace --expand exited {result.returncode}\nstderr: {result.stderr}"
    )
    assert result.stdout == snapshot


def test_mixed_status_in_run_snapshot(snapshot: SnapshotAssertion, tmp_path: Path) -> None:
    """4 same-role records with statuses (success, success, error, cancelled).

    Snapshot must show breakdown `2 success / 1 error / 1 cancelled` (zero categories
    omitted from breakdown if any were zero) and `(+1 unknown)` cost suffix
    (cancelled record has null cost_usd).
    """
    fixture_file = _write_mixed_status_fixture(tmp_path)
    result = _run_trace_cmd([str(fixture_file)])
    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstderr: {result.stderr}"
    )
    assert result.stdout == snapshot


def test_query_summary_interleaved_breaks_group_snapshot(
    snapshot: SnapshotAssertion, tmp_path: Path
) -> None:
    """3 scanner -> kind:query_summary -> 2 scanner -> event:batch_cancelled.

    Snapshot must show: first collapsed group (`scanner x3:`), then full-line
    query_summary record, then second collapsed group (`scanner x2:`), then
    full-line batch_cancelled terminator. Both kind and event break runs (D-11).
    """
    fixture_file = _write_interleaved_fixture(tmp_path)
    result = _run_trace_cmd([str(fixture_file)])
    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstderr: {result.stderr}"
    )
    assert result.stdout == snapshot


def test_aggregate_excludes_event_kind_from_by_role(tmp_path: Path) -> None:
    """WR-02 regression: by_role aggregator excludes event/kind discriminator records.

    A fixture mixing one per-item scanner record with one kind:query_summary
    record must render a Per-role breakdown that contains 'scanner:' but NOT a
    phantom 'unknown:' bucket. The kind:query_summary record still appears as a
    full-line timeline entry via _render_trace_record (non-groupable per
    _is_groupable) and contributes to Total records, but it does not synthesize
    a role bucket.
    """
    trace_file = tmp_path / "event_kind_excluded_trace.jsonl"
    records = [
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-0",
            "status": "success",
            "latency_ms": 100,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0001,
            "timestamp": "2026-05-17T10:00:00Z",
        },
        {
            "schema_version": 1,
            "kind": "query_summary",
            "query_id": "q1",
            "query": "test",
            "top_k": 5,
            "pages_retrieved": 3,
            "pages_drilled": 1,
            "code_fallback": False,
            "started_at": "2026-05-17T10:00:01Z",
            "ended_at": "2026-05-17T10:00:02Z",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    result = _run_trace_cmd([str(trace_file)])
    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Per-role section sits between 'Per-role breakdown:' and the next blank-line section.
    per_role_section = result.stdout.split("Per-role breakdown:")[1].split("Cost rollup")[0]
    assert "scanner:" in per_role_section, (
        f"Expected legitimate 'scanner:' bucket in per-role section:\n{per_role_section}"
    )
    assert "unknown:" not in per_role_section, (
        f"Expected NO synthetic 'unknown:' bucket (WR-02 fix); per-role section:\n{per_role_section}"
    )


def test_collapsed_group_surfaces_unknown_status_in_other_bucket(tmp_path: Path) -> None:
    """WR-03 regression: non-canonical statuses surface under an `other` bucket.

    A run of 3 same-(role, model_id) records all carrying status='timeout' (a
    status not in the canonical {success, error, cancelled} set) collapses into
    one summary line whose breakdown reports `3 other`, NOT the previously
    misleading `0 success`.
    """
    trace_file = tmp_path / "unknown_status_trace.jsonl"
    records = [
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": f"page-{i}",
            "status": "timeout",
            "latency_ms": 100 + i,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0001,
            "timestamp": f"2026-05-17T10:00:{i:02d}Z",
        }
        for i in range(3)
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    result = _run_trace_cmd([str(trace_file)])
    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    timeline = result.stdout.split("=== Summary ===")[0]
    assert "x3" in timeline, f"Expected collapsed-group marker 'x3' in timeline:\n{timeline}"
    assert "3 other" in timeline, (
        f"Expected '3 other' in collapsed-group breakdown:\n{timeline}"
    )
    assert "0 success" not in timeline, (
        f"Did NOT expect misleading '0 success' fallback:\n{timeline}"
    )


def test_mixed_model_same_role_breaks_collapse(tmp_path: Path) -> None:
    """CR-01 regression: two same-role records on different model_ids must NOT collapse.

    Default-mode collapse keys by (role, model_id), mirroring the cost rollup at
    cli.py:329-345. Two scanner records with different model_ids form two runs of
    length 1 each; each renders full-line via _render_trace_record and the haiku
    and sonnet model substrings appear on DISTINCT timeline lines.
    """
    trace_file = tmp_path / "mixed_model_trace.jsonl"
    records = [
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-0",
            "status": "success",
            "latency_ms": 100,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0001,
            "timestamp": "2026-05-17T10:00:00Z",
        },
        {
            "schema_version": 1,
            "role": "scanner",
            "model_id": _SONNET_MODEL,
            "prompt_hash": None,
            "item_id": "page-1",
            "status": "success",
            "latency_ms": 110,
            "tokens_in": 20,
            "tokens_out": 10,
            "cost_usd": 0.0002,
            "timestamp": "2026-05-17T10:00:01Z",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")

    result = _run_trace_cmd([str(trace_file)])
    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    timeline = result.stdout.split("=== Summary ===")[0]
    assert "haiku-4-5" in timeline, f"expected haiku substring in timeline; got:\n{timeline}"
    assert "sonnet-4-5" in timeline, f"expected sonnet substring in timeline; got:\n{timeline}"

    haiku_lines = [ln for ln in timeline.splitlines() if "haiku-4-5" in ln]
    sonnet_lines = [ln for ln in timeline.splitlines() if "sonnet-4-5" in ln]
    assert haiku_lines, f"expected haiku line in timeline; got:\n{timeline}"
    assert sonnet_lines, f"expected sonnet line in timeline; got:\n{timeline}"
    assert haiku_lines != sonnet_lines, (
        f"expected haiku and sonnet on distinct lines; both matched same line(s):\n"
        f"haiku_lines={haiku_lines}\nsonnet_lines={sonnet_lines}"
    )


def test_isolated_record_renders_full_line(tmp_path: Path) -> None:
    """Two records of different roles each form a run of length 1 — both render full-line.

    Verifies D-12's "isolated single records (run length 1) still render full-line by
    default." No `x1:` collapsed-group marker should appear.
    """
    fixture_file = _write_two_roles_fixture(tmp_path)
    result = _run_trace_cmd([str(fixture_file)])
    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstderr: {result.stderr}"
    )
    stdout = result.stdout
    timeline = stdout.split("=== Summary ===")[0]
    # Each role's item_id appears as a per-item full line
    assert "scanner-page" in timeline, (
        f"Expected 'scanner-page' full-line in timeline:\n{timeline}"
    )
    assert "librarian-page" in timeline, (
        f"Expected 'librarian-page' full-line in timeline:\n{timeline}"
    )
    # No collapsed-group marker — runs of length 1 are NOT collapsed
    assert "x1:" not in stdout, (
        f"Did NOT expect 'x1:' collapse marker (isolated records render full-line):\n{stdout}"
    )


# ---------------------------------------------------------------------------
# Plan 09-05: schema_version-aware warnings (OBS-04 consumer half)
# ---------------------------------------------------------------------------

_REAL_V0_FIXTURE_DIR = (
    Path(__file__).resolve().parents[4]
    / "packages"
    / "wiki-io"
    / "tests"
    / "fixtures"
    / "round-trip-vault"
    / ".graph-wiki"
    / "traces"
)


def _write_newer_version_fixture(tmp_path: Path) -> Path:
    """Write a 2-record JSONL fixture with `schema_version: 99` on every record.

    Exercises the D-03 lenient-consumer path: a renderer that only knows
    `KNOWN_SCHEMA_VERSION = 1` must still render and exit 0, emitting one
    stderr warning naming the actual version.
    """
    trace_file = tmp_path / "newer_version_trace.jsonl"
    records = [
        {
            "schema_version": 99,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-future",
            "status": "success",
            "latency_ms": 100,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": 0.0001,
            "timestamp": "2026-05-17T10:00:00Z",
        },
        {
            "schema_version": 99,
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "page-future-2",
            "status": "success",
            "latency_ms": 110,
            "tokens_in": 12,
            "tokens_out": 6,
            "cost_usd": 0.0002,
            "timestamp": "2026-05-17T10:00:01Z",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file


def _write_unversioned_inline_fixture(tmp_path: Path) -> Path:
    """Write a 2-record JSONL fixture where NO record carries `schema_version`.

    Exercises the D-04 v0-inference one-shot warning path.
    """
    trace_file = tmp_path / "unversioned_inline_trace.jsonl"
    records = [
        {
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "a",
            "status": "success",
            "latency_ms": 100,
            "tokens_in": 10,
            "tokens_out": 5,
            "cost_usd": None,
            "timestamp": "2026-05-17T10:00:00Z",
        },
        {
            "role": "scanner",
            "model_id": _HAIKU_MODEL,
            "prompt_hash": None,
            "item_id": "b",
            "status": "success",
            "latency_ms": 110,
            "tokens_in": 12,
            "tokens_out": 6,
            "cost_usd": None,
            "timestamp": "2026-05-17T10:00:01Z",
        },
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file


def test_v0_real_fixture_renders_and_warns_once(tmp_path: Path) -> None:
    """A real unversioned fixture renders successfully and emits exactly ONE v0 warning line.

    The warning line must mention the file path (D-04). Renders ALL real v0 fixtures
    successfully — fixtures are NOT rewritten by this phase.
    """
    fixtures = sorted(_REAL_V0_FIXTURE_DIR.glob("*.jsonl"))
    assert fixtures, f"No real v0 fixtures found at {_REAL_V0_FIXTURE_DIR}"
    fixture = fixtures[0]

    result = _run_trace_cmd([str(fixture)])

    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Exactly one stderr line carries a v0 marker, and that line mentions the file path.
    v0_markers = ("unversioned", "schema_version=0", "pre-Phase-9")
    v0_lines = [
        line
        for line in result.stderr.splitlines()
        if any(marker in line for marker in v0_markers)
    ]
    assert len(v0_lines) == 1, (
        f"Expected exactly one v0 warning line; found {len(v0_lines)}:\n{result.stderr}"
    )
    assert str(fixture) in v0_lines[0], (
        f"Expected v0 warning to mention file path {fixture}; got:\n{v0_lines[0]}"
    )

    # Stdout still rendered: contains the per-item Summary block at minimum.
    assert result.stdout, "Expected non-empty stdout from successful v0 render"
    assert "=== Summary ===" in result.stdout, (
        f"Expected Summary block in stdout:\n{result.stdout}"
    )


def test_newer_version_warns_lenient(tmp_path: Path) -> None:
    """A fixture with schema_version=99 emits the D-03 lenient-consumer warning verbatim.

    Exit code stays 0; warning string includes the literal `schema_version 99 is newer
    than supported (1)` and `rendering best-effort`; warning appears exactly once per
    file regardless of record count.
    """
    fixture_file = _write_newer_version_fixture(tmp_path)
    result = _run_trace_cmd([str(fixture_file)])

    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "schema_version 99 is newer than supported (1)" in result.stderr, (
        f"Expected D-03 lenient-consumer wording in stderr:\n{result.stderr}"
    )
    assert "rendering best-effort" in result.stderr, (
        f"Expected 'rendering best-effort' in stderr:\n{result.stderr}"
    )
    assert result.stderr.count("is newer than supported") == 1, (
        f"Expected exactly ONE 'is newer than supported' occurrence (one-shot per file):\n{result.stderr}"
    )
    # Records still flow through to the timeline.
    assert "scanner" in result.stdout, (
        f"Expected records to render in timeline despite newer version:\n{result.stdout}"
    )


def test_versioned_clean_emits_no_version_warning(tmp_path: Path) -> None:
    """A fixture where every record carries schema_version=1 emits NO version-related warning."""
    fixture_file = _write_fan_out_fixture(tmp_path, n=2)
    result = _run_trace_cmd([str(fixture_file)])

    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "newer than supported" not in result.stderr, (
        f"Did NOT expect 'newer than supported' in stderr for clean v1 file:\n{result.stderr}"
    )
    for marker in ("unversioned", "pre-Phase-9", "schema_version=0"):
        assert marker not in result.stderr, (
            f"Did NOT expect v0 marker '{marker}' in stderr for clean v1 file:\n{result.stderr}"
        )


def test_v0_warning_emitted_once_per_file(tmp_path: Path) -> None:
    """Two unversioned records in one file produce EXACTLY ONE stderr line carrying any v0 marker.

    Per-line semantics: the chosen v0 warning string may legitimately bundle multiple
    markers (`unversioned`, `schema_version=0`, `pre-Phase-9`) on a single emitted line.
    A substring `.count()` would over-count; correct measure is the count of DISTINCT
    stderr line indices carrying any marker.
    """
    fixture_file = _write_unversioned_inline_fixture(tmp_path)
    result = _run_trace_cmd([str(fixture_file)])

    assert result.returncode == 0, (
        f"trace exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    v0_markers = ("unversioned", "schema_version=0", "pre-Phase-9")
    v0_line_indices = {
        idx
        for idx, line in enumerate(result.stderr.splitlines())
        if any(marker in line for marker in v0_markers)
    }
    assert len(v0_line_indices) == 1, (
        f"Expected exactly one stderr line carrying a v0 marker; "
        f"found {len(v0_line_indices)} line(s): {v0_line_indices}\nstderr:\n{result.stderr}"
    )
