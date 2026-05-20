# Phase 9: Trace/Observability Polish - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 8 targets (6 modify, 1 create, 1 cross-link doc)
**Analogs found:** 8 / 8 — every target file already exists in some form (extensions only), so analogs are the targets themselves except for the brand-new `docs/trace-schema.md` (analog: `docs/cancellation.md`).

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `cores/subagent-runtime/src/subagent_runtime/pool.py` | writer (producer) | event-driven JSONL append | itself (extend in place) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` | writer (producer) | one-shot JSONL write | itself (extend in place) | exact |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` | renderer (consumer) | batch read-then-format | itself (extend in place) | exact |
| `docs/trace-schema.md` | documentation | static reference | `docs/cancellation.md` | role-match (sibling doc) |
| `docs/cancellation.md` | documentation | one-line cross-link edit | itself | exact |
| `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` | test (subprocess + syrupy) | snapshot + subprocess | `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py` (syrupy pattern), self (subprocess pattern) | hybrid |
| `cores/subagent-runtime/tests/test_pool.py` | test (unit) | assertion on written record | itself (extend in place) | exact |
| `agents/graph-wiki-agent/tests/unit/test_query_*.py` | test (unit, optional) | assertion on written record | `test_pool.py` test 7 (`test_trace_record_completeness_success_path`) | role-match |

---

## Pattern Assignments

### `cores/subagent-runtime/src/subagent_runtime/pool.py` (writer, event-driven JSONL append)

**Analog:** itself — extend in place. The two writers already construct an inline `record: dict[str, Any]` and `json.dumps` it.

**Writer pattern to preserve — `_write_trace`** (`pool.py:211-230`):
```python
record: dict[str, Any] = {
    "role": role,
    "model_id": model_id,
    "prompt_hash": None,  # caller may set; None until computed upstream
    "item_id": getattr(item, "id", None) or str(item),
    "status": status,
    "latency_ms": latency_ms,
    "tokens_in": tokens_in,
    "tokens_out": tokens_out,
    "cost_usd": _compute_cost_usd(model_id, tokens_in, tokens_out),
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
if error:
    record["error"] = error

try:
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
except OSError as exc:
    logger.warning("Trace write failed (data loss): %s", exc)
```

**Writer pattern to preserve — `_write_batch_terminal`** (`pool.py:249-263`):
```python
record: dict[str, Any] = {
    "role": role,
    "model_id": model_id,
    "event": "batch_cancelled",
    "items_total": items_total,
    "items_completed": items_completed,
    "items_cancelled": items_cancelled,
    "wall_clock_ms": wall_clock_ms,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}
try:
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
except OSError as exc:
    logger.warning("Batch terminal trace write failed: %s", exc)
```

**Change spec (Phase 9):** insert `"schema_version": 1,` as the first key of the `record` dict in BOTH writers. One-line diff each. No other edits.

**Stylistic conventions to preserve:**
- Record dict is constructed inline (no helper function) — keep that shape.
- `OSError` is caught at the `path.open("a")` boundary and logged at WARNING. **Never raise from trace writers** — AI-SPEC Failure Mode #2 / docstring at `pool.py:196-198`.
- Field ordering: put `schema_version` first so it shows up first in JSONL output (matches the "self-describing line" rationale in D-01).

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` (writer, one-shot JSONL write)

**Analog:** itself — the `query_summary` writer lives at `query.py:976-995`.

**Writer pattern to preserve:**
```python
ended_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
trace_dir = wiki / ".code-wiki" / "traces"
trace_dir.mkdir(parents=True, exist_ok=True)
summary_file = trace_dir / f"query_{query_id}.jsonl"
try:
    summary_record = {
        "kind": "query_summary",
        "query_id": query_id,
        "query": query,
        "top_k": top_k,
        "pages_retrieved": len(top_pages),
        "pages_drilled": query_result.pages_drilled,
        "code_fallback": code_fallback_used,
        "started_at": started_at,
        "ended_at": ended_at,
    }
    with summary_file.open("w") as f:
        f.write(json.dumps(summary_record) + "\n")
except OSError as exc:
    logger.warning("Could not write query summary trace: %s", exc)
```

**Change spec (Phase 9):** insert `"schema_version": 1,` as the first key of `summary_record`. One-line diff. Note this writer uses `open("w")` not `open("a")` because each query produces its own file — that's fine and unchanged.

**Stylistic conventions to preserve:**
- `kind: query_summary` is the discriminator for this record shape — already documented in `08-CONTEXT.md` D-06/D-07 as an additive new record kind. Do not change.
- `OSError` is caught at WARNING; never raises. Same contract as `pool.py` writers.

---

### `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` (renderer, batch read-then-format)

**Analog:** itself — `_render_trace_record` (lines 48-73), `_aggregate_trace` (lines 76-107), `trace` command (lines 110-144) are all extension targets.

**Current renderer pattern — `_render_trace_record`** (`cli.py:48-73`):
```python
def _render_trace_record(record: dict) -> str:
    timestamp = record.get("timestamp", "-")
    role = record.get("role", "-")
    model_id = record.get("model_id", "-")
    model_short = model_id[-30:] if model_id != "-" else "-"
    item_id = record.get("item_id", "-")
    item_short = item_id[:40] if item_id != "-" else "-"
    status = record.get("status", "-")
    latency_ms = record.get("latency_ms", "-")
    tokens_in = record.get("tokens_in", "-")
    tokens_out = record.get("tokens_out", "-")

    line = (
        f"[{timestamp}] {role} {model_short} {item_short} "
        f"{status} {latency_ms}ms {tokens_in}->{tokens_out}"
    )
    if record.get("status") == "error":
        line += f"  ERROR: {record.get('error', '')}"
    return line
```

**Current aggregator pattern — `_aggregate_trace`** (`cli.py:76-107`):
```python
def _aggregate_trace(records: list[dict]) -> dict:
    by_role: dict = defaultdict(lambda: {"count": 0, "tokens_in": 0, "tokens_out": 0})
    total_tokens_in = 0
    total_tokens_out = 0

    for record in records:
        role = record.get("role", "unknown")
        tin = record.get("tokens_in") or 0
        tout = record.get("tokens_out") or 0
        by_role[role]["count"] += 1
        by_role[role]["tokens_in"] += tin
        by_role[role]["tokens_out"] += tout
        total_tokens_in += tin
        total_tokens_out += tout

    return {
        "by_role": dict(by_role),
        "total_records": len(records),
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
    }
```

**Current command pattern — `trace`** (`cli.py:110-144`):
```python
@app.command()
def trace(file: Path) -> None:
    """Render a JSONL trace file as a human-readable timeline."""
    if not file.exists():
        typer.echo(f"trace file not found: {file}", err=True)
        raise typer.Exit(code=1)

    records: list[dict] = []
    for line_number, raw_line in enumerate(file.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            typer.echo(f"warning: skipping malformed JSONL line {line_number}: {exc.msg}", err=True)
            continue
        records.append(record)
        typer.echo(_render_trace_record(record))

    agg = _aggregate_trace(records)
    typer.echo("")
    typer.echo("=== Summary ===")
    typer.echo(f"Total records : {agg['total_records']}")
    typer.echo(f"Total tokens_in  : {agg['total_tokens_in']}")
    typer.echo(f"Total tokens_out : {agg['total_tokens_out']}")
    typer.echo("")
    typer.echo("Per-role breakdown:")
    for role, stats in agg["by_role"].items():
        typer.echo(
            f"  {role}: count={stats['count']} "
            f"tokens_in={stats['tokens_in']} tokens_out={stats['tokens_out']}"
        )
    typer.echo("")
    typer.echo("Cost USD: (Phase 4)")
```

**Change spec (Phase 9):**
1. Add `expand: bool = typer.Option(False, "--expand", help="Disable consecutive-same-role collapsing; render every record full-line.")` to the `trace` command signature.
2. Replace the eager `typer.echo(_render_trace_record(record))` inside the `for raw_line` loop with a deferred pass: collect records first, then walk records and emit either per-record lines (when `expand=True` or record is non-groupable) or a single dense group summary line (collapse threshold N=2, group definition: consecutive per-item records with same `role`, no `event` key, no `kind` key — D-11/D-12). Group summary shape from D-13.
3. Extend `_aggregate_trace` to key by `(role, model_id)` AND accumulate `cost_usd` with separate tracking of `n/a` counts (null-cost records). Return shape adds e.g. `"by_role_model": {(role, model_id): {"count": N, "tokens_in": X, "tokens_out": Y, "cost_usd": float, "unknown_cost_count": N}}`.
4. Replace the `Cost USD: (Phase 4)` placeholder at line 144 with the per-`(role, model_id)` rollup, sorted by descending total cost (n/a groups last; tie-break alphabetical) per D-15. Format: `$0.000000` (six decimals) per D-09. Excluded-record count appended as ` (+N unknown)` when present.
5. Emit a one-time-per-file stderr warning when ANY record lacks `schema_version` (D-04, v0-inference) — string is Claude-discretion but should mention the file path. Emit a one-time-per-file stderr warning when `schema_version > 1` (D-03 lenient-consumer).
6. Renderer **MUST NOT import from `eval_harness`** (D-10) — read `cost_usd` as-written; treat `None` as `n/a`.

**Stylistic conventions to preserve:**
- All output via `typer.echo` — no `rich`, no `textual` (CLAUDE.md §6 v1 stack constraint, explicit deferred item).
- All field access via `record.get(..., "-")` or `record.get(...) or 0` so missing keys never raise.
- Stderr for warnings/errors (`err=True`), stdout for the rendered timeline + Summary block.
- The `event` and `kind` discriminators in Phase 8 stay authoritative: presence of `event` → batch terminal; presence of `kind` → query summary; absence of both → per-item record.

---

### `docs/trace-schema.md` (documentation, static reference — NEW)

**Analog:** `docs/cancellation.md` (sibling doc written in Phase 8, same audience, same OSS-release-friendly bar).

**Section ordering pattern from cancellation.md to mirror:**
1. Title + opening paragraph (what / why / scope-statement)
2. **v1.1 scope** callout block (in-scope / deferred)
3. Numbered top-level sections — cancellation.md used: `1. Protocol Behavior`, `2. Internal Cancellation Chain`, `3. Trace Shapes`, `4. Known Limitations (v1.1)`, `5. Future Work (v1.2+)`.
4. Bottom-of-file `*Source:*` italic line pointing back to the phase context.

**Excerpt: opening pattern** (`docs/cancellation.md:1-12`):
```markdown
# MCP Cancellation in graph-wiki-agent

This document describes what happens when a spec-conformant MCP host sends
`notifications/cancelled` to `graph-wiki-mcp` while a fan-out tool call is in flight.
It covers the protocol, the internal unwinding chain, the exact trace record shapes
emitted by `SubagentPool`, the known orphan-thread limitation in v1.1, and the
v1.2+ paths that will close that gap.

**v1.1 scope:** `notifications/cancelled` mid-fan-out is supported. SIGINT and
stdin-close fallback cancel paths are deferred to v1.2+.

---
```

**Excerpt: JSON record-shape pattern** (`docs/cancellation.md:97-114`):
```markdown
**Per-item cancelled record** — one per `_run_one` that received `CancelledError`.
These records have no `event` key:

```json
{
  "role": "librarian",
  "model_id": "qwen.qwen3-next-80b-a3b",
  "prompt_hash": null,
  "item_id": "wiki/packages/alpha/alpha.md",
  "status": "cancelled",
  "latency_ms": 1240,
  "tokens_in": null,
  "tokens_out": null,
  "cost_usd": null,
  "timestamp": "2026-05-17T14:23:01Z"
}
```
```

**Excerpt: bottom-of-file source line** (`docs/cancellation.md:210`):
```markdown
*Source: Phase 8 (Host Reliability) — see .planning/phases/08-host-reliability/08-CONTEXT.md and 08-RESEARCH.md for the design record.*
```

**Change spec (Phase 9):** create `docs/trace-schema.md` at repo root. Required sections per D-05:
1. Overview of `.graph-wiki/traces/` directory layout and filename convention (per-batch `{int_timestamp}_{uuid8}.jsonl`, per-query `query_{query_id}.jsonl`).
2. Per-record-shape spec — three shapes: per-item subagent record, `event: batch_cancelled` terminator, `kind: query_summary`. Each with field table (name | type | required? | semantics). Pull JSON examples from real fixture files under `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/` (add `"schema_version": 1` to the examples — fixtures themselves are v0 and stay v0 per D-04).
3. `schema_version` field — what it is, lenient-consumer / strict-producer policy (D-03), bump rules (D-02).
4. "Additive-shape" rule cross-referencing Phase 8 D-06/D-07.
5. v0 (unversioned) compatibility note (D-04).
6. Examples — copy from fixtures.

Length target ~150-250 lines. Markdown style: match cancellation.md (H2 sections, fenced `json` blocks, em-dashes, OSS-friendly prose).

**Stylistic conventions to preserve:**
- No project-internal jargon without explanation — this doc is OSS-release-friendly.
- Cross-link `docs/cancellation.md` from the `event: batch_cancelled` section ("see also `docs/cancellation.md` for the cancellation propagation chain that produces this record") rather than duplicating field tables.
- Use `*Source: Phase 9 (Trace/Observability Polish) — see .planning/phases/09-trace-observability-polish/09-CONTEXT.md for the design record.*` as the bottom-of-file marker.

---

### `docs/cancellation.md` (documentation, one-line cross-link edit)

**Analog:** itself.

**Change spec (Phase 9):** add ONE cross-link sentence inside Section 3 ("Trace Shapes") that points to `docs/trace-schema.md` as the authoritative field-table source. Keep the existing in-line JSON examples — they remain illustrative. No other edits to this file. Per D-06.

**Stylistic conventions to preserve:**
- No content rewrite. One-line surgical addition.

---

### `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` (test, snapshot + subprocess)

**Existing pattern in this file — subprocess-driven assertion** (`test_trace_viewer.py:53-59`):
```python
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent


def _run_trace_cmd(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-agent", "trace"] + args,
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
    )
```

**Existing pattern in this file — JSONL fixture factory** (`test_trace_viewer.py:14-47`):
```python
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
        ...
    ]
    with trace_file.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")
    return trace_file
```

**Sibling analog — syrupy snapshot pattern** (`tests/prompts/test_prompt_snapshots.py:14-25`):
```python
import pytest
from syrupy.assertion import SnapshotAssertion


def test_librarian_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """LIBRARIAN_SYSTEM matches recorded snapshot."""
    try:
        from graph_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert LIBRARIAN_SYSTEM == snapshot
```

**Snapshots directory analog:** `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` (syrupy default `.ambr` format) — Phase 9 snapshots land at `agents/graph-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr`.

**Change spec (Phase 9):**
1. KEEP the existing subprocess-driven tests (5 tests, lines 67-182) — they still pass with the renderer extensions because they assert on `'Phase 4' in stdout or 'cost' in stdout.lower()` (line 101), and the new rollup will contain "cost". Adjust only that assertion to drop the `'Phase 4'` half once the placeholder is removed.
2. ADD new syrupy snapshot tests via `from syrupy.assertion import SnapshotAssertion`:
   - `test_collapsed_default_snapshot` — fan-out of 4 same-role records, no `--expand`, snapshot the collapsed group summary line + Summary block.
   - `test_expand_snapshot` — same fixture, `--expand`, snapshot every per-record line.
   - `test_cost_rollup_snapshot` — mixed-model fan-out (e.g., 3 scanner@haiku + 2 scanner@sonnet) to lock the `(role, model_id)` rollup ordering (descending cost, alphabetical tie-break — D-15).
   - `test_query_summary_interleaved_snapshot` — fan-out + `kind: query_summary` record + `event: batch_cancelled` terminator in the same file, snapshot the output (verify groupable / non-groupable interleaving — D-11).
3. ADD a v0 backward-compat unit test that loads a real fixture (e.g., `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/1778766775_3d8c7377.jsonl`), runs the renderer via subprocess, asserts (a) exit code 0, (b) stderr contains a one-time warning line mentioning the file path, (c) stdout still contains the per-item role / item_id / status.

**Stylistic conventions to preserve:**
- `_PROJECT_ROOT` resolution via `Path(__file__).parent.parent.parent.parent.parent` and `uv run --package graph-wiki-agent graph-wiki-agent ...` subprocess invocation — this is the established CLI test pattern.
- Fixture records are constructed as Python dicts and `json.dumps`'d line by line — match this for collapse/expand fixtures.
- syrupy is already in the project's `pyproject.toml` (root) — no dep changes needed.

---

### `cores/subagent-runtime/tests/test_pool.py` (test, unit assertion on written record)

**Analog:** itself — Test 7 `test_trace_record_completeness_success_path` (lines 178-213) is the closest existing test for "assert field X is present on the written record."

**Existing pattern to mirror — required-keys subset assertion** (`test_pool.py:200-213`):
```python
lines = trace_files[0].read_text().strip().splitlines()
assert len(lines) == 1

record = json.loads(lines[0])
required_keys = {
    "role", "model_id", "prompt_hash", "item_id",
    "status", "latency_ms", "tokens_in", "tokens_out",
    "cost_usd", "timestamp",
}
assert required_keys.issubset(record.keys())
assert record["status"] == "success"
assert record["tokens_in"] == 10
assert record["tokens_out"] == 5
assert record["cost_usd"] is None
```

**Change spec (Phase 9):**
1. Update the `required_keys` set in `test_trace_record_completeness_success_path` to include `"schema_version"`.
2. Add an explicit assertion: `assert record["schema_version"] == 1`.
3. Update `test_trace_record_error_path` (lines 221-249) similarly.
4. Add a new test for the batch-terminal path (cancel scenario already partially covered in Phase 8 — extend or add `test_batch_terminal_includes_schema_version` asserting the `event: batch_cancelled` record also has `schema_version: 1`).

**Stylistic conventions to preserve:**
- `async def test_...` (pytest-asyncio auto mode is in effect per CLAUDE.md §8 — no `@pytest.mark.asyncio` needed).
- Use `make_task` / `fake_llm_response` fixtures from `conftest.py:7-33`. Do not re-roll new fakes.
- Field assertions via `record["key"] == value` (strict equality, not `in`) — match Phase 2 / Phase 8 style.

---

### `agents/graph-wiki-agent/tests/unit/test_query_*.py` (test, unit — optional)

**Analog:** `test_pool.py` Test 7 — same "load JSONL file, parse, assert field present" pattern transplanted to the `query_summary` writer.

**Change spec (Phase 9):** find the existing test that exercises `run_query` end-to-end and writes a `query_{id}.jsonl` summary (likely `test_query_search.py` or `test_query_result.py` — the planner should grep for "query_summary" or "summary_record" usage). Add an assertion that the written summary record contains `schema_version: 1`. If no such test exists yet, add a minimal one. Planner's call whether to extend an existing file or create `test_query_summary_schema_version.py`.

**Stylistic conventions to preserve:**
- `json.loads(summary_file.read_text())` to read the one-line file, then assert `record["schema_version"] == 1`.

---

## Shared Patterns

### Trace writers never raise (cross-cutting — applies to both `pool.py` writers AND `query.py` query_summary writer)

**Source:** `cores/subagent-runtime/src/subagent_runtime/pool.py:226-230` (and mirrored at 259-263, 994-995 in query.py).

**Pattern:**
```python
try:
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
except OSError as exc:
    logger.warning("Trace write failed (data loss): %s", exc)
```

**Apply to:** Every place that touches a `.jsonl` write in this phase. New code MUST NOT introduce a `try`/`except` that re-raises — AI-SPEC Failure Mode #2.

---

### Lazy import for cross-package boundary

**Source:** `cores/subagent-runtime/src/subagent_runtime/pool.py:266-284` (`_compute_cost_usd`).

**Pattern:**
```python
def _compute_cost_usd(model_id, tokens_in, tokens_out) -> float | None:
    if tokens_in is None or tokens_out is None:
        return None
    try:
        from eval_harness.pricing import UnknownModelError, cost_for_usage  # noqa: PLC0415
        return cost_for_usage(model_id, {"input": tokens_in, "output": tokens_out})
    except (ImportError, KeyError, UnknownModelError):
        return None
```

**Apply to:** None directly in Phase 9 — but the **inverse rule** governs the renderer per D-10: `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` MUST NOT import `eval_harness` at all (not at module level, not lazily). Read `cost_usd` as-written.

---

### `typer.echo` is the only output primitive

**Source:** Every command in `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — no `print()`, no `rich.print`, no `logging` for user-facing output.

**Pattern:**
```python
typer.echo(f"Total records : {agg['total_records']}")          # stdout
typer.echo(f"trace file not found: {file}", err=True)         # stderr
```

**Apply to:** All renderer changes in Phase 9. Stderr (`err=True`) for warnings (v0-inference, schema_version too new) and errors; stdout for the timeline and Summary block.

---

### syrupy snapshot test (`SnapshotAssertion`)

**Source:** `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py:16-25`.

**Pattern:**
```python
from syrupy.assertion import SnapshotAssertion


def test_collapsed_default_snapshot(snapshot: SnapshotAssertion, tmp_path: Path) -> None:
    trace_file = _write_collapse_fixture(tmp_path)
    result = _run_trace_cmd([str(trace_file)])
    assert result.returncode == 0
    assert result.stdout == snapshot
```

**Snapshots auto-land at:** `agents/graph-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr` (syrupy default `.ambr` format). Initial generation via `pytest --snapshot-update`.

**Apply to:** New collapsed/expand/cost-rollup/query-summary-interleave snapshot tests.

---

### Doc cross-link without duplication

**Source:** `docs/cancellation.md` (Phase 8) — uses `event: batch_cancelled` JSON example inline but defers field-table authority elsewhere.

**Pattern (Phase 9 application):**
- `docs/trace-schema.md` is the authoritative source of field tables.
- `docs/cancellation.md` keeps its existing JSON examples (illustrative) and adds ONE sentence linking to `docs/trace-schema.md` for the table.
- The trace-schema doc, in its `event: batch_cancelled` section, links back to `docs/cancellation.md` for the propagation chain.

**Apply to:** D-06 — single line edit in `cancellation.md`, single cross-link reference in the new `trace-schema.md`.

---

## No Analog Found

None. Every file in scope has a close existing pattern (`docs/cancellation.md` is the analog for the only brand-new file).

---

## Metadata

**Analog search scope:**
- `cores/subagent-runtime/src/subagent_runtime/`
- `cores/subagent-runtime/tests/`
- `agents/graph-wiki-agent/src/graph_wiki_agent/`
- `agents/graph-wiki-agent/tests/unit/`
- `agents/graph-wiki-agent/tests/prompts/` (syrupy pattern)
- `docs/`
- `cores/vault-io/tests/fixtures/round-trip-vault/.graph-wiki/traces/` (real v0 fixtures)

**Files scanned:**
- Source: `pool.py`, `cli.py`, `query.py` (full read of each).
- Tests: `test_pool.py`, `test_trace_viewer.py`, `test_prompt_snapshots.py`, `conftest.py` (subagent-runtime).
- Docs: `cancellation.md` (full read).
- Fixtures: sampled two JSONL files to confirm v0 record shape (no `schema_version`, has `cost_usd: null`, has `kind: query_summary` for the per-query file).
- Config: confirmed `syrupy` is declared in root `pyproject.toml` (no per-package dep change needed).

**Pattern extraction date:** 2026-05-17
