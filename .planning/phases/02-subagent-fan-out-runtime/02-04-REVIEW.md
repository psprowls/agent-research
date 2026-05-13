---
phase: 02-subagent-fan-out-runtime
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - agents/code-wiki-agent/src/code_wiki_agent/cli.py
  - agents/code-wiki-agent/tests/unit/test_trace_viewer.py
  - cores/model-adapter/src/model_adapter/__init__.py
  - cores/subagent-runtime/src/subagent_runtime/pool.py
  - cores/subagent-runtime/tests/test_pool.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 02 (Plan 04): Code Review Report

**Reviewed:** 2026-05-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Gap-closure changes for CR-01 (inspect.signature dispatch), CR-02 (UUID trace filename suffix), CR-03 (JSONDecodeError guard in trace command), and BED-02 (load_role_config export). All four stated fixes are present and functionally correct for their documented usage. No blockers found.

One warning: the signature dispatch in pool.py counts all parameter kinds equally, which silently misroutes callables whose second parameter is keyword-only or VAR_KEYWORD. The practical impact is low (all items fail with PerItemError wrapping TypeError rather than crashing the pool), but the failure mode is confusing and the fix is a one-liner.

## Warnings

### WR-01: inspect.signature dispatch counts all param kinds — misroutes keyword-only and **kwargs tasks

**File:** `cores/subagent-runtime/src/subagent_runtime/pool.py:131-135`

**Issue:** The CR-01 dispatch check is `len(sig.parameters) >= 2`, which counts every parameter kind (POSITIONAL_OR_KEYWORD, VAR_POSITIONAL, VAR_KEYWORD, KEYWORD_ONLY) equally. Two edge cases produce wrong behaviour:

1. `async def task(item, **kwargs)` — 2 params counted, dispatch calls `task(item, _config)` positionally, which raises `TypeError: task() takes 1 positional argument but 2 were given`. Caught by `except Exception` → every item becomes a `PerItemError` wrapping the TypeError. The caller gets silent total failure with no indication of the signature mismatch.

2. `async def task(item, *, config=None)` — same count, same positional call, same TypeError. All items fail.

Both patterns are unlikely in the current codebase (the documented API is `async def task(item, config)` positional), but nothing prevents a caller from using either form, and the error surfaced at runtime on every item rather than at registration time.

```python
# pool.py line 131-135 — current (fragile)
sig = inspect.signature(task)
if len(sig.parameters) >= 2:
    result = await task(item, _config)
else:
    result = await task(item)
```

**Fix:** Count only positional-capable parameters:

```python
import inspect

_POSITIONAL_KINDS = (
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.POSITIONAL_ONLY,
)

sig = inspect.signature(task)
positional_count = sum(
    1 for p in sig.parameters.values() if p.kind in _POSITIONAL_KINDS
)
if positional_count >= 2:
    result = await task(item, _config)
else:
    result = await task(item)
```

This correctly handles all edge cases: `*args` functions count 0 positional params (one-arg path), `(item, **kwargs)` counts 1 (one-arg path), `(item, config)` counts 2 (two-arg path).

Note: `inspect.signature` is currently called once per item invocation inside `_run_one`. Move it above the `asyncio.gather` call to compute it once per `run_all` invocation:

```python
# Compute once, reuse across all items
sig = inspect.signature(task)
positional_count = sum(
    1 for p in sig.parameters.values() if p.kind in _POSITIONAL_KINDS
)

async def _run_one(item: Any) -> tuple[Any, Any] | PerItemError:
    async with semaphore:
        ...
        if positional_count >= 2:
            result = await task(item, _config)
        else:
            result = await task(item)
```

## Info

### IN-01: `exc.msg` drops line/column position from JSONDecodeError warning

**File:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py:101`

**Issue:** The malformed-JSONL warning uses `exc.msg` (e.g. `"Expecting value"`), which omits the character-position information that `str(exc)` includes (e.g. `"Expecting value: line 1 column 1 (char 0)"`). When debugging a corrupt trace file, the column offset is the most actionable piece of information.

**Fix:**

```python
# Before
typer.echo(f"warning: skipping malformed JSONL line {line_number}: {exc.msg}", err=True)

# After
typer.echo(f"warning: skipping malformed JSONL line {line_number}: {exc}", err=True)
```

`str(exc)` (or just interpolating `exc` directly) produces the full message with position.

### IN-02: Test 11 does not verify per-file record count

**File:** `cores/subagent-runtime/tests/test_pool.py:357-360`

**Issue:** `test_separate_trace_files_per_run_all` asserts that two distinct `.jsonl` files exist after two sequential `run_all` calls, but does not verify that each file contains exactly one record. If the uniqueness fix regressed (same filename produced twice), the test would catch it (only one file). But a future refactor that routes all records to a single file would also produce two files if renamed mid-run — the test would pass while the isolation guarantee broke. A one-line content assertion closes this gap.

**Fix:** Add after line 360:

```python
for tf in trace_files:
    lines = tf.read_text().strip().splitlines()
    assert len(lines) == 1, f"Expected 1 record per trace file; {tf.name} has {len(lines)}"
```

---

## Confirmed Correct (not flagged)

- **CR-01:** Two-arg dispatch via `inspect.signature` correctly routes `(item, config)` tasks for the documented API.
- **CR-02:** `uuid.uuid4().hex[:8]` suffix guarantees filename uniqueness within the same wall-clock second; test 11 correctly exercises the fix.
- **CR-03:** `json.JSONDecodeError` catch with `continue` correctly skips bad lines, exits 0, and emits a stderr warning. Test coverage in `test_trace_command_skips_malformed_lines` is complete.
- **BED-02:** `load_role_config` is now present in `model_adapter/__init__.__all__`; import from the public API surface works.
- **conftest.py `make_task` fixture:** `raise_for=frozenset()` uses an immutable default — no mutable default argument bug.
- **`_PROJECT_ROOT` calculation:** Five `.parent` traversals from the test file correctly resolve to the workspace root.
- **`asyncio_mode = "auto"`:** Configured in `subagent-runtime/pyproject.toml`; async test functions run without `@pytest.mark.asyncio` decorators as expected.
- **Semaphore inside `run_all()`:** Correctly bound to the running event loop; not created in `__init__`.

---

_Reviewed: 2026-05-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
