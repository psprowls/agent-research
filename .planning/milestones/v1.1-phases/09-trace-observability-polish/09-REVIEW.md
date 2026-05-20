---
phase: 09-trace-observability-polish
reviewed: 2026-05-17T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
  - agents/graph-wiki-agent/tests/unit/__snapshots__/test_trace_viewer.ambr
  - agents/graph-wiki-agent/tests/unit/test_query_summary_schema_version.py
  - agents/graph-wiki-agent/tests/unit/test_trace_viewer.py
  - cores/subagent-runtime/src/subagent_runtime/pool.py
  - cores/subagent-runtime/tests/test_pool.py
  - docs/cancellation.md
  - docs/trace-schema.md
findings:
  critical: 1
  warning: 6
  info: 4
  total: 11
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-05-17
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 09 added `schema_version: 1` stamping at producers (`SubagentPool._write_trace`,
`SubagentPool._write_batch_terminal`, `query.py` summary writer), a per-(role, model_id)
cost rollup in the `graph-wiki-agent trace` renderer, consecutive-same-role group
collapsing with `--expand` opt-out, and lenient-consumer / v0-inference warnings. The
producer half is sound. The renderer/aggregator has one correctness bug that breaks
mixed-model fan-outs (CR-01), several formatting and edge-case gaps in the timeline
collapse and warning paths, and minor quality issues. The docs are consistent with
the implementation.

The query_summary writer (`commands/query.py:980-995`) and the schema_version
producer tests are well-pinned; no defects found in those areas. The
schema_version-aware warning logic correctly de-duplicates per file.

## Critical Issues

### CR-01: Mixed-model same-role runs collapse into a single group, hiding the per-model breakdown in the timeline

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:303` (and `_render_collapsed_group` at 164-215)
**Issue:** `_is_groupable` and the run-extension predicate group consecutive records by `role` alone (`current_run[-1].get("role") == record.get("role")`). When a fan-out (or a role override path like `role_model_overrides` in `query.py`) emits items for the *same role* on *different model_ids* (e.g. an A/B sweep of `librarian` across `claude-haiku` and `claude-sonnet`), all such records collapse into one summary line. `_render_collapsed_group` does not print `model_id` at all, so the per-model attribution is lost in the timeline.

The snapshot `test_cost_rollup_snapshot` masks this because it uses `--expand`, and `test_collapsed_default_snapshot` uses a single-model fixture. The cost rollup section still itemizes per `(role, model_id)` correctly, but a reader scanning the timeline can no longer tell which item ran on which model — exactly the information the rollup is supposed to surface alongside the timeline.

This is a correctness bug for the documented Plan 09-04 / OBS-06 intent (collapse fan-outs while preserving model attribution). It will silently misrepresent any cost-sweep trace where `role_model_overrides` is in effect, which is one of the primary observability use cases listed in `commands/query.py:796-799`.

**Fix:** Group by `(role, model_id)` rather than `role`, and include the model in the summary line header (mirroring the rollup format).

```python
def _is_groupable(record: dict) -> bool:
    return "event" not in record and "kind" not in record

def _group_key(record: dict) -> tuple[str, str]:
    return (record.get("role", "-"), record.get("model_id", "-"))

# In the trace() loop:
if current_run and _group_key(current_run[-1]) == _group_key(record):
    current_run.append(record)
else:
    _flush()
    current_run.append(record)

# In _render_collapsed_group, include model_id:
role = records[0].get("role", "-")
model_id = records[0].get("model_id", "-")
model_short = model_id[-30:] if model_id and model_id != "-" else "-"
header = f"[{ts_first} .. {ts_last}] {role} / {model_short} x{n}:"
```

Add a regression test that builds a fixture with two same-role records on different `model_id` values and asserts they render as two separate lines (or one line that names both models) in default mode.

## Warnings

### WR-01: `isinstance(sv, int)` treats booleans as integers — `schema_version: true` is silently accepted

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:267`
**Issue:** `isinstance(sv, int)` returns `True` for `bool`, because `bool` is a subclass of `int` in Python. A producer bug that wrote `"schema_version": true` would be coerced to `1` and never trigger the lenient-consumer warning, even though it is a malformed record. The comment at line 254 ("Non-integer `schema_version` values are silently rendered best-effort (T-09-15: lenient policy)") explains the intent for strings/floats, but bool is not the lenient case — it is a producer bug class that the strict-producer policy in `docs/trace-schema.md` §3 prohibits.

**Fix:**
```python
if isinstance(sv, int) and not isinstance(sv, bool) and sv > KNOWN_SCHEMA_VERSION and not warned_newer:
    ...
```

### WR-02: `_aggregate_trace` per-role bucket counts non-per-item records and creates a spurious `"unknown"` role for `kind: query_summary` lines

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:124-132`
**Issue:** The per-role loop runs before the `event`/`kind` filter is applied, so the `by_role` dict and the `Total records` count include batch_event and query_summary records. When a `kind: query_summary` line lacks a `role` field, line 125 (`role = record.get("role", "unknown")`) creates a synthetic `"unknown"` bucket. This is visible in the existing snapshot `test_query_summary_interleaved_breaks_group_snapshot`:

```
Per-role breakdown:
  scanner: count=6 tokens_in=60 tokens_out=35
  unknown: count=1 tokens_in=0 tokens_out=0
```

A reader sees `unknown: count=1` and reasonably concludes some scanner subagent dispatched with no role — they cannot tell it is actually the query_summary line. The docstring at line 106-107 acknowledges this is "to keep the Summary block's 'Total records' line backward-compatible," but the cost is misleading per-role attribution.

**Fix:** Either (a) exclude event/kind records from `by_role` too (the cleaner option — total_records and total_tokens can keep counting everything if desired), or (b) when a record has `kind` or `event`, key it by the discriminator value (e.g. `query_summary`, `event:batch_cancelled`) instead of falling through to `"unknown"`. Option (a) plus a separate "Other records" line is most informative.

### WR-03: `_render_collapsed_group` status breakdown silently misclassifies records whose status is not one of {success, error, cancelled}

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:182-189`
**Issue:** The `counts` dict is hardcoded with three keys; any status outside that set is dropped on the floor. A run of N records all carrying `status: "timeout"` (or a future producer-added status) produces empty `breakdown_parts`, and the fallback string `"0 success"` is actively wrong — there are N records and none succeeded. Token sums and cost would still be computed, so the line would read:

```
[ts1 .. tsN] scanner x5: 0 success, 50->25 tokens, $0.001000
```

This is misleading. A reader would interpret this as five successful records with a formatting bug. The strict-producer policy in `docs/trace-schema.md` §2.1 enumerates only `success`/`error`/`cancelled` today, but the renderer should fail loudly (or include an "other" category) rather than coerce.

**Fix:** Add an `other` bucket for unrecognised statuses and surface it in the breakdown:

```python
counts: dict[str, int] = {"success": 0, "error": 0, "cancelled": 0, "other": 0}
for r in records:
    status = r.get("status")
    counts[status if status in counts else "other"] += 1
breakdown_parts = [f"{counts[k]} {k}" for k in ("success", "error", "cancelled", "other") if counts[k]]
if not breakdown_parts:
    breakdown_parts = [f"{len(records)} unknown"]
```

### WR-04: `_render_collapsed_group` and `_render_trace_record` silently use `-` for missing `timestamp`, which produces nonsense range labels

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:178-179, 64-66`
**Issue:** When a malformed record reaches the renderer with no `timestamp`, the collapsed group header becomes `[- .. -] scanner x4: ...`. The snapshot `test_query_summary_interleaved_breaks_group_snapshot` shows this for the query_summary line as `[-] - - - - -ms -->-` — a row of dashes that is hard to interpret. Producers are strict (every per-item record carries `timestamp` per `docs/trace-schema.md` §2.1), so this code path only fires on actual data corruption, but the fallback should at least name the file line number or the record's discriminator instead of dashes.

**Fix:** Either drop the fallback (treat missing `timestamp` as a malformed record at parse time and skip with a stderr warning, matching the `JSONDecodeError` handling at line 250), or replace the dashes with a clearer marker like `<no timestamp>`. Skipping is more aligned with the strict-producer policy.

### WR-05: `_run_code_fallback` truncates `code_excerpts_text` silently, losing the warning emitted on the librarian path

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:485-486`
**Issue:** The regular path at line 896-901 emits a `logger.warning("Truncating librarian excerpts before synthesis...")` when excerpts exceed 60_000 chars. The code-fallback path at 485-486 truncates with no warning, no log, no `query_id` reference. An operator debugging a code-fallback synthesis result has no signal that truncation occurred.

**Fix:**
```python
if len(code_excerpts_text) > 60000:
    logger.warning(
        "Truncating code-fallback excerpts before synthesis (query_id=%s, len=%d)",
        query_id, len(code_excerpts_text),
    )
    code_excerpts_text = code_excerpts_text[:60000]
```

### WR-06: `_run_code_fallback` does not enforce a token/cost cap on the code-reader tool-call loop beyond a 5-iteration count

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:355-462`
**Issue:** `_CODE_READER_MAX_ITERS = 5` caps iterations, but on each iteration the model can request multiple `read_file` calls in one tool batch (`for call in tool_calls` at 442). The bounded read at 200_000 bytes is per-file, so a single iteration that requests 5 files of 200KB each pushes 1MB of source into the next prompt. With 5 iterations cap, the worst case is ~5MB delivered to the LLM context — beyond every Bedrock model's input window and well beyond a reasonable cost cap.

The 200_000-byte per-file cap and the 5-iteration cap are necessary but not sufficient. There is no aggregate cap.

**Fix:** Track cumulative bytes returned by `_read_file_bounded` across the iteration loop and short-circuit when a budget (e.g. 500_000 bytes / ~125K tokens) is exceeded:

```python
bytes_returned = 0
BUDGET = 500_000
for iteration in range(_CODE_READER_MAX_ITERS):
    ...
    for call in tool_calls:
        ...
        tool_output = _read_file_bounded(repo_root, requested)
        bytes_returned += len(tool_output)
        if bytes_returned > BUDGET:
            tool_output = (
                f"ERROR: code-reader byte budget ({BUDGET}) exceeded; "
                "stop reading and answer with what you have, or return NO_RELEVANT_CONTENT."
            )
        msgs.append(ToolMessage(content=tool_output, tool_call_id=call_id))
    if bytes_returned > BUDGET:
        logger.warning(...)
        break
```

## Info

### IN-01: `cli.py:153` raises `ValueError` on non-numeric `cost_usd` instead of the documented "raise loudly"

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py:150-153`
**Issue:** The comment promises "raise loudly rather than silently mis-sum," but `float(cost)` on a non-numeric string raises `ValueError` mid-iteration with no record context — the operator sees `ValueError: could not convert string to float: 'foo'` and no record line number or `item_id`. Wrap with context.

**Fix:**
```python
try:
    bucket["cost_usd_sum"] += float(cost)
except (TypeError, ValueError) as exc:
    raise ValueError(
        f"malformed cost_usd in record (role={role}, model_id={model_id}, "
        f"item_id={record.get('item_id', '-')}): {cost!r}"
    ) from exc
```

### IN-02: `from __future__ import annotations` placed AFTER module docstring in `commands/query.py`

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:1-3`
**Issue:** `from __future__ import annotations` is at line 1, then the module docstring is at line 3. Python's accepted convention is `docstring first, then __future__ import`. The current order works (Python permits `__future__` imports as the first non-docstring, non-comment statement), but it is unusual and tools like `flake8-future-import` flag it. This is a style nit, not a bug.

### IN-03: Duplicate G1 unresolved-link logic between `apply_guardrails` and `_compute_unresolved_wikilinks`

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py:507-526, 615-626`
**Issue:** `_compute_unresolved_wikilinks` (added for the retry path) and the G1 loop inside `apply_guardrails` implement the exact same resolution rules (direct lookup → `**/<base>.md` glob). Drift between the two would silently divergent the retry trigger condition from the G1 warning condition. Have `apply_guardrails` call `_compute_unresolved_wikilinks` to share one implementation.

### IN-04: `docs/cancellation.md:96` cross-reference to `docs/trace-schema.md` is correct, but the inline JSON blocks in §3 still omit `schema_version`

**File:** `docs/cancellation.md:103-131`
**Issue:** The intro says "the JSON blocks in this section remain inline for illustration only" and points at the schema doc for the authoritative shape. The inline examples, however, lack the `schema_version: 1` field that producers now stamp. A reader skimming `cancellation.md` would copy the example into a test fixture and produce a v0-shaped record. Either drop the inline blocks (leaving only the cross-reference) or add `"schema_version": 1` to both examples to match what `_write_trace` / `_write_batch_terminal` actually emit (verified at `cores/subagent-runtime/src/subagent_runtime/pool.py:212, 251`).

---

_Reviewed: 2026-05-17_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
