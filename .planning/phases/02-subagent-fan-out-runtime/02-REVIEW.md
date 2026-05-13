---
phase: 02-subagent-fan-out-runtime
reviewed: 2026-05-13T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - agents/code-wiki-agent/src/code_wiki_agent/cli.py
  - agents/code-wiki-agent/tests/unit/test_trace_viewer.py
  - cores/model-adapter/src/model_adapter/loader.py
  - cores/model-adapter/src/model_adapter/models.toml
  - cores/model-adapter/tests/test_loader.py
  - cores/subagent-runtime/pyproject.toml
  - cores/subagent-runtime/src/subagent_runtime/__init__.py
  - cores/subagent-runtime/src/subagent_runtime/pool.py
  - cores/subagent-runtime/tests/__init__.py
  - cores/subagent-runtime/tests/conftest.py
  - cores/subagent-runtime/tests/integration/__init__.py
  - cores/subagent-runtime/tests/integration/test_pool_bedrock.py
  - cores/subagent-runtime/tests/test_pool.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

This phase delivers the `subagent-runtime` core package (`SubagentPool`), the `model-adapter` core package (`make_llm` / `load_role_config`), and the `trace` CLI command on `code-wiki-agent`. The code is generally well-structured and the design rationale is well-documented. However, there are three blockers:

1. The `_config = RunnableConfig(...)` object is created inside every task invocation but is **never passed to `task()`**. The recursion limit is assembled but silently dropped, so Test 12 passes only because it monkeypatches `RunnableConfig` and never verifies the config reaches the task.
2. The trace file path is keyed on `int(time.time())` (one-second resolution). Two `run_all()` calls within the same wall-clock second produce the **same filename** and one silently overwrites the other.
3. `json.loads()` in `cli.py trace` has no error handling; a single malformed JSONL line aborts the entire command with an unhandled `json.JSONDecodeError` traceback instead of an actionable error message.

There are also five warnings covering an unchecked `e.response` dict access, a flawed concurrency test that does not actually guarantee ordering, model IDs that cross Bedrock service boundaries, a missing `load_role_config` export from `model_adapter.__init__`, and a one-second `asyncio.sleep` in a unit test that slows the suite needlessly.

---

## Critical Issues

### CR-01: RunnableConfig recursion_limit is created but never passed to the task

**File:** `cores/subagent-runtime/src/subagent_runtime/pool.py:122-123`

**Issue:** `_config` is created on line 122 but `task(item)` on line 123 is called with no arguments besides the item. The `RunnableConfig` object is constructed, assigned to a local variable, and then discarded. No LangChain or LangGraph component receives the recursion limit. The feature is entirely non-functional for tasks that wrap compiled graphs.

Test 12 (`test_recursion_limit_propagated_to_runnableconfig`) passes only because it monkeypatches `RunnableConfig` itself and observes the *call* to `RunnableConfig(recursion_limit=42)` — it never checks whether the config object reaches the task callable. The integration test (`test_recursion_limit_propagated_real_bedrock`) uses raw `ainvoke` calls (not a compiled graph) and therefore cannot expose the bug.

**Fix:** Task callables must accept an optional config parameter, or the pool must pass it via LangChain's `with_config` mechanism. The simplest approach that requires no signature change to every task:

```python
# pool.py — _run_one, lines 122-123
_config = RunnableConfig(recursion_limit=rlimit)
# Option A: task signature is (item, config) — requires caller contract change
result = await task(item, _config)

# Option B: if tasks are Runnables, use with_config:
#   result = await task.with_config(_config).ainvoke(item)

# Option C: inject via contextvars so LangGraph picks it up automatically:
from langchain_core.runnables import ensure_config
# ... ensure_config(_config) before calling task
```

Pick one contract and enforce it in the type annotation for `task`. Currently the type hint `Callable[[Any], Awaitable[Any]]` does not accommodate a config argument.

---

### CR-02: Trace file name collision when two run_all() calls occur within the same second

**File:** `cores/subagent-runtime/src/subagent_runtime/pool.py:114`

**Issue:** The trace file is named `f"{int(time.time())}.jsonl"`. `time.time()` has one-second resolution after the `int()` cast. If `run_all()` is called twice within the same wall-clock second — which is trivially possible in any real workflow, and is the normal case for rapid sequential calls in the same event loop — the second call opens the **same path** in `"a"` (append) mode and writes into the same file. Test 11 works around this with `await asyncio.sleep(1.1)`, but the bug is real in production.

Downstream, the `trace` CLI command iterates all trace files and prints them; merging two logically separate runs' records into one file destroys lineage. The assumption "1 trace file = 1 run_all() call" (asserted in multiple integration tests) breaks silently.

**Fix:** Use a monotonically unique identifier — a UUID or a combination of timestamp + sequential counter:

```python
import uuid

# In run_all():
trace_file = self._trace_dir / f"{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"
```

Alternatively, use a per-instance counter initialized in `__init__`:

```python
# __init__:
self._run_counter = 0

# run_all():
self._run_counter += 1
trace_file = self._trace_dir / f"{int(time.time())}_{self._run_counter:04d}.jsonl"
```

---

### CR-03: Unhandled json.JSONDecodeError crashes the trace command on malformed input

**File:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py:98`

**Issue:** `json.loads(line)` on line 98 has no exception handler. A single malformed JSONL line (truncated write, binary content, BOM) causes an unhandled `json.JSONDecodeError` traceback that exits with a non-zero code but prints a Python stack trace to stdout instead of an actionable error message. There is no test for this path.

**Fix:**

```python
try:
    record = json.loads(line)
except json.JSONDecodeError as exc:
    typer.echo(f"WARNING: skipping malformed line ({exc}): {line[:80]}", err=True)
    continue
records.append(record)
typer.echo(_render_trace_record(record))
```

---

## Warnings

### WR-01: Unchecked dict access on e.response before inspecting Error Code

**File:** `cores/model-adapter/src/model_adapter/loader.py:65`

**Issue:** The guard `e.response.get("Error", {}).get("Code")` calls `.get()` on `e.response`, but `e.response` itself is never checked for `None` before the first `.get()`. `botocore.exceptions.ClientError.response` is documented as always present, but `botocore.exceptions.ClientError` can theoretically be constructed with any dict — including `{}`. If `response` is `None` (e.g., constructed programmatically in tests without the standard dict shape), this raises `AttributeError: 'NoneType' object has no attribute 'get'`, which leaks through the except clause unhandled and surfaces as an unexpected `AttributeError` rather than re-raising the original `ClientError`.

More practically: a `ClientError` constructed as `ClientError({}, "op")` has `response == {}`, which is fine — but a subclass or mock that sets `response = None` will crash here silently. The existing test helper `_build_client_error` always provides the correct structure, so tests do not catch this.

**Fix:**

```python
code = (e.response or {}).get("Error", {}).get("Code")
if code == "AccessDeniedException":
    raise BedrockAccessDenied(...) from e
raise
```

---

### WR-02: Semaphore concurrency test is not race-condition-proof

**File:** `cores/subagent-runtime/tests/test_pool.py:114-138`

**Issue:** `test_semaphore_caps_concurrency` uses a `nonlocal` `peak` / `current` counter updated without any lock. In Python's asyncio single-threaded event loop this is safe under normal circumstances, but the pattern has a subtle flaw: the `current += 1` / `current -= 1` increment-check sequence is correct *only* because `await asyncio.sleep(0.01)` is the sole yield point. If the implementation ever introduces additional `await` points between increment and decrement (which is the whole point of the real task), the single yield point assumption breaks. More critically, the test asserts `peak <= 2` but passes `max_concurrency=2` and 6 items. With 6 coroutines all submitted to `asyncio.gather`, all 6 are scheduled *before* any runs; the semaphore guarantees at most 2 acquire at the same time, but the `current += 1` happens *after* acquiring the semaphore, so the assertion should hold. The test is correct today but fragile — it silently passes even if the semaphore is broken, because the `asyncio.sleep(0.01)` sleep time is too short to guarantee interleaving under any scheduler.

**Fix:** Use an `asyncio.Event` or `asyncio.Barrier` to guarantee that all slots are occupied simultaneously before any task exits, making the peak measurement deterministic:

```python
async def counting_task(item):
    nonlocal peak, current
    current += 1
    peak = max(peak, current)
    await asyncio.sleep(0)   # yield to let siblings start
    current -= 1
    return item
```

Pair with `asyncio.sleep(0)` to force the scheduler to run all ready coroutines before continuing — this makes the peak measurement reliable.

---

### WR-03: `load_role_config` is not exported from model_adapter's public __init__

**File:** `cores/model-adapter/src/model_adapter/__init__.py:13`

**Issue:** `loader.py` exposes both `make_llm` and `load_role_config` as its public API. The integration tests and the subagent-runtime pool integration tests both import `load_role_config` from `model_adapter.loader` directly rather than from `model_adapter`. The `__init__.py` only re-exports `make_llm` and `BedrockAccessDenied`. If callers import `from model_adapter import load_role_config`, they get `ImportError`. This is an incomplete public API surface.

**Fix:**

```python
# cores/model-adapter/src/model_adapter/__init__.py
from model_adapter.exceptions import BedrockAccessDenied
from model_adapter.loader import make_llm, load_role_config

__all__ = ["BedrockAccessDenied", "make_llm", "load_role_config"]
```

---

### WR-04: models.toml contains model IDs that mix cross-region inference profile format with direct Bedrock IDs

**File:** `cores/model-adapter/src/model_adapter/models.toml:8,39`

**Issue:** `roles.sonnet` and `roles.synthesizer` use `model_id = "us.anthropic.claude-sonnet-4-6"` — the cross-region inference profile URI format (prefix `us.`). `roles.haiku`, `roles.scanner`, etc. use `"us.anthropic.claude-haiku-4-5-20251001-v1:0"` — also the cross-region inference profile format, but with an explicit version suffix.

`"us.anthropic.claude-sonnet-4-6"` is not a valid Bedrock model ID or cross-region inference profile ID. The correct cross-region inference profile ID for Claude Sonnet 4.6 would include a version suffix (e.g., `us.anthropic.claude-sonnet-4-6-20260101-v1:0`) or use the direct foundation model ARN. Without the version suffix, the Converse API will return a `ValidationException: model not found` at invocation time. Tests that monkeypatch `_original_invoke` never hit the Bedrock API, so this bug is invisible in CI but will fail in production and integration tests.

**Fix:** Verify the exact model ID from the AWS Bedrock console or `aws bedrock list-foundation-models` output and replace both occurrences:

```toml
# roles.sonnet — use the verified ARN
model_id = "us.anthropic.claude-sonnet-4-6-YYYYMMDD-v1:0"

# roles.synthesizer — same
model_id = "us.anthropic.claude-sonnet-4-6-YYYYMMDD-v1:0"
```

If a versionless alias is available (Bedrock does offer some), verify it explicitly with `aws bedrock get-foundation-model --model-identifier us.anthropic.claude-sonnet-4-6` before shipping.

---

### WR-05: asyncio.sleep(1.1) in unit test slows suite by over 1 second unconditionally

**File:** `cores/subagent-runtime/tests/test_pool.py:349`

**Issue:** `test_separate_trace_files_per_run_all` uses `await asyncio.sleep(1.1)` to guarantee distinct `int(time.time())` values between two `run_all()` calls. This is a direct consequence of the CR-02 filename collision bug. Beyond being a symptom of the underlying bug, the 1.1-second sleep adds wall-clock time to every unit test run unconditionally. Unit tests should run in milliseconds.

**Fix:** Fix CR-02 first (add UUID suffix to trace file names). Once filenames are unique regardless of timestamp, the sleep can be removed entirely and the test can simply call `run_all()` twice in sequence:

```python
await pool.run_all(items=["a"], ...)
await pool.run_all(items=["b"], ...)
trace_files = list(traces_dir.glob("*.jsonl"))
assert len(trace_files) == 2
```

---

## Info

### IN-01: json.loads result is not validated as a dict before use in cli.py

**File:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py:98-100`

**Issue:** `json.loads(line)` can return any JSON value (string, list, int, `null`). If a JSONL file contains a non-object line (e.g., `"null"` or `"[1,2,3]"`), `record.get(...)` on line 100 raises `AttributeError`. This is a minor issue given the JSONL is always written by `_write_trace`, but the `trace` command is also used for debugging externally-produced files.

**Fix:** Add a type check after parsing:

```python
record = json.loads(line)
if not isinstance(record, dict):
    typer.echo(f"WARNING: skipping non-object JSONL line: {line[:80]}", err=True)
    continue
```

---

### IN-02: Variable name `l` used in integration test list comprehensions

**File:** `cores/subagent-runtime/tests/integration/test_pool_bedrock.py:71,166`

**Issue:** `[l for l in trace_files[0].read_text().splitlines() if l.strip()]` uses `l` as a loop variable name. `l` (lowercase L) is visually ambiguous with `1` (one) and `I` (uppercase i) in many monospace fonts. This is a minor readability issue in test code.

**Fix:** Use `line` as the loop variable:

```python
lines = [line for line in trace_files[0].read_text().splitlines() if line.strip()]
```

---

### IN-03: _load_models_config() re-reads and re-parses models.toml on every call

**File:** `cores/model-adapter/src/model_adapter/loader.py:28-32`

**Issue:** `_load_models_config()` is called inside both `make_llm()` and `load_role_config()` with no caching. For a long-running MCP server that creates many LLM instances, this opens and re-parses the TOML file on every `make_llm()` call. This is a quality/maintainability note, not a correctness bug.

**Fix:** Cache the parsed config with `functools.lru_cache`:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def _load_models_config() -> dict:
    with resources.files("model_adapter").joinpath("models.toml").open("rb") as f:
        return tomllib.load(f)
```

Note: if hot-reload of models.toml is ever needed, the cache would need manual invalidation. For this project's scope, caching is appropriate.

---

_Reviewed: 2026-05-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
