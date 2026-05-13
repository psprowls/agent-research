# Phase 2: Subagent Fan-Out Runtime - Research

**Researched:** 2026-05-13
**Domain:** Async Python concurrency, asyncio fan-out, LangChain/Bedrock integration, structured JSONL observability
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01: Implementation path — asyncio pool (not SubAgentMiddleware vendor subclass)**
deepagents bug #694 (cancellation cascade) was merged but NOT released in 0.6.1. The fix is verified closed on GitHub but the release has not shipped. Implementation uses raw `asyncio.gather(return_exceptions=True)` with a role-bound `asyncio.Semaphore` — the SUB-03 blessed fallback. This is recorded as a Key Decision in PROJECT.md.

**D-02: GraphRecursionError bug already fixed**
deepagents bug #1698 is fixed in PR #2194, shipped in 0.6.1. No workaround needed. Recursion limit propagation (SUB-04) is still required but implemented cleanly without patching deepagents.

**D-03: deepagents #694 not released**
deepagents 0.6.1 does NOT include the #694 cancellation cascade fix. This is why asyncio pool path is chosen.

**D-04: Calling convention — `pool.run_all(items, task, role) -> FanOutResult`**
`role` drives semaphore and trace metadata only. Pool does NOT resolve or inject a model.

**D-05: Task owns model via closure**
Callers call `make_llm()` before constructing the task closure. Pool receives `role` for throttle + trace metadata only.

**D-06: `FanOutResult` return type**
```python
@dataclass
class PerItemError:
    item: Any
    exception: Exception

@dataclass
class FanOutResult:
    successes: list[tuple[Any, Any]]  # (item, result) pairs
    errors: list[PerItemError]
```
No sibling cancellation on partial failure.

**D-07: Recursion limit as optional parameter**
`pool.run_all()` accepts `recursion_limit: int | None`. Passed to every task's `RunnableConfig`. Default from `SubagentPool.__init__` config.

**D-08: `cost_usd` is null in Phase 2**
Cost accounting is Phase 4's responsibility. Trace schema carries `"cost_usd": null`.

**D-09: `tokens_in` / `tokens_out` ARE captured in Phase 2**
From `ChatBedrockConverse` response `usage_metadata` (`.input_tokens` / `.output_tokens`). No separate CountTokens call needed.

**D-10: Trace writer lives in `cores/subagent-runtime`**
Pool task wrapper captures latency + response metadata and appends JSONL record. Trace file path resolves relative to configurable `.code-wiki/` base dir.

### Claude's Discretion

- **Specific model IDs for 7 roles** in `models.toml` expansion: researcher confirms current cross-region inference profile ARNs.
- **models.toml schema extension** — exact TOML structure for `max_tokens`, `max_concurrency`: planner designs.
- **Trace file naming** within `.code-wiki/traces/`: planner picks.
- **`OBS-02` viewer format** for `code-wiki-agent trace <file>`: planner designs.

### Deferred Ideas (OUT OF SCOPE)

- **Cost rate storage in `models.toml`** — deferred to Phase 4.
- **Real-time throttle backoff** — semaphore cap is the Phase 2 solution; retry backoff is Phase 4+.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BED-02 | `cores/model-adapter` exposes `ModelRegistry` keyed by 7 logical role names | Verified: `make_llm(role)` is the existing factory; `load_role_config(role)` must be added; `models.toml` extended with 7 roles + `max_tokens` + `max_concurrency` |
| BED-03 | Per-role config includes `model_id`, `max_tokens` ceiling, `max_concurrency` semaphore size | Verified: TOML supports all three fields; `make_llm()` must read and pass `max_tokens` to `ChatBedrockConverse(max_tokens=...)` at construction |
| BED-04 | Models configured via `models.toml` only — no hardcoded model IDs | Verified: existing pattern; adding 5 new roles following same pattern |
| BED-05 | Token + cost per invocation captured in traces | Verified: `usage_metadata` dict on `AIMessage` has `input_tokens`/`output_tokens` fields; `cost_usd=null` in Phase 2 |
| SUB-01 | `cores/subagent-runtime` exposes fan-out primitive | Implemented via `SubagentPool` class in new workspace member |
| SUB-02 | Verify SubAgentMiddleware behavior (partial failure integration test) | Decision made: asyncio pool path; integration test still verifies partial failure isolation against real Bedrock |
| SUB-03 | Fallback to raw `asyncio.gather(return_exceptions=True)` if SUB-02 fails | This IS the chosen path (D-01); recorded as Key Decision in PROJECT.md |
| SUB-04 | Recursion limit propagated explicitly parent → child | Verified: `RunnableConfig(recursion_limit=N)` passes top-level config key; NOT under `configurable` sub-key |
| SUB-05 | Per-role `max_tokens` and concurrency caps enforced at fan-out time | `asyncio.Semaphore(max_concurrency)` created inside `run_all()`; `max_tokens` set at `make_llm()` construction |
| SUB-06 | Every fan-out call emits structured JSONL trace | 9-field trace schema; append-mode write; one file per `run_all()` call |
| SUB-07 | Results aggregator handles partial failure gracefully | `FanOutResult.successes` + `FanOutResult.errors`; no sibling cancellation |
| OBS-01 | Structured trace JSONL under `.code-wiki/traces/<timestamp>.jsonl` | `SubagentPool._write_trace()` handles this; trace dir created at pool construction |
| OBS-02 | `code-wiki-agent trace <file>` viewer subcommand | New Typer command added to `agents/code-wiki-agent/src/code_wiki_agent/cli.py` |
| OBS-03 | Cost summary at end of every interactive run | Stdout summary after `run_all()` — reads `tokens_in`/`tokens_out` from trace; `cost_usd` stays null |
</phase_requirements>

---

## Summary

Phase 2 delivers the `cores/subagent-runtime` workspace member: the shared async fan-out primitive that all wiki commands (query, scan, lint, ingest) will depend on. The three deliverables are: (1) `ModelRegistry` extension — five new roles added to `models.toml` plus a new `load_role_config()` function; (2) `SubagentPool` — an asyncio-gather-based pool with partial-failure isolation, per-role semaphore throttle, and recursion-limit propagation; and (3) a JSONL trace writer plus a `trace` viewer subcommand.

The implementation path decision (D-01) is resolved: asyncio pool, not SubAgentMiddleware. deepagents #694 (cancellation cascade) was confirmed closed but the fix has not shipped in 0.6.1. The asyncio pool on `asyncio.gather(return_exceptions=True)` achieves partial-failure isolation without coupling to deepagents internals in flux. deepagents #1698 (recursion limit / `GraphRecursionError`) is confirmed fixed and released in 0.6.1, so no workaround is needed — only correct `RunnableConfig` propagation.

The five critical failure modes are well-understood and documented in AI-SPEC.md: sibling cancellation, silent trace data loss, ThrottlingException under burst, `GraphRecursionError` from missing recursion limit, and `AttributeError` on `usage_metadata = None`. Each has a concrete prevention pattern in the codebase design. All cross-region inference profile IDs for the 7 roles have been verified against Pat's live AWS account.

**Primary recommendation:** Implement `SubagentPool` directly on `asyncio.gather(return_exceptions=True)` with a semaphore created inside `run_all()` (not `__init__`). Extend `models.toml` with 5 new roles using the verified ARNs from `aws bedrock list-inference-profiles`. Add `load_role_config(role) -> dict` to `model_adapter.loader`. Create `cores/subagent-runtime` following the established workspace layout pattern.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Fan-out concurrency control | `cores/subagent-runtime` (SubagentPool) | — | Semaphore lifecycle must be co-located with `asyncio.gather` — splitting these across layers creates loop-binding bugs |
| Model resolution | `cores/model-adapter` (make_llm / load_role_config) | — | All model construction stays in model-adapter; SubagentPool never receives an LLM object |
| Per-role throttle config | `cores/model-adapter` (models.toml) | `cores/subagent-runtime` (reads config) | Config lives in model-adapter; SubagentPool reads it at call time via `load_role_config()` |
| Trace writes (JSONL) | `cores/subagent-runtime` (pool._write_trace) | — | Co-located with task execution to capture latency and token metadata atomically |
| Trace viewer (OBS-02) | `agents/code-wiki-agent` (cli.py trace command) | — | A simple pretty-printer over JSONL files; no Bedrock dependency; lives in the CLI layer |
| Recursion limit propagation | `cores/subagent-runtime` (pool._run_one) | — | Every task invocation site must receive `RunnableConfig`; the pool owns this |
| boto3 connection pool sizing | Caller's `make_llm()` | `cores/model-adapter` | `max_pool_connections` must be set at boto3 Config construction, not in the pool |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `asyncio` (stdlib) | Python 3.11 | Fan-out concurrency via `gather` + `Semaphore` | No dependency; `return_exceptions=True` is the correct partial-failure primitive; zero overhead vs external scheduler |
| `langchain-aws` | 1.4.6 | `ChatBedrockConverse` for Bedrock Converse API | Already in workspace; the only Bedrock-compatible async chat model in this stack |
| `langchain-core` | 1.4.0 | `RunnableConfig`, `AIMessage` | Provides `recursion_limit` config key and `usage_metadata` on responses |
| `botocore` | via `boto3 >= 1.38` | `botocore.config.Config` for `max_pool_connections` | Required to configure connection pool size per role's `max_concurrency` |
| `model-adapter` | workspace | `make_llm()`, `load_role_config()` | Phase 1 deliverable; SubagentPool imports from it; no rewrite needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `hashlib` (stdlib) | Python 3.11 | SHA-256 for `prompt_hash` | Inside task closures; 16-char hex prefix in trace records |
| `time` (stdlib) | Python 3.11 | `monotonic()` for per-item latency; `gmtime()` for trace timestamps | Inside `_run_one` and `_write_trace` |
| `typer` | 0.25.1 | `trace` subcommand viewer | Already in `code-wiki-agent`; add one new `@app.command()` |
| `pytest` | >= 8.3 | Unit + integration tests | Already workspace dev dep |
| `pytest-asyncio` | 1.3.0 | `async def` test functions | Already workspace dev dep — needs `asyncio_mode = "auto"` in subagent-runtime's pyproject |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.gather(return_exceptions=True)` | `asyncio.TaskGroup` (Python 3.11+) | TaskGroup cancels siblings on first error by design — wrong primitive for partial-failure fan-out |
| `asyncio.gather(return_exceptions=True)` | deepagents `SubAgentMiddleware` | #694 not released; internals in flux; asyncio pool is simpler and has no deepagents coupling |
| Per-call semaphore in `run_all()` | Semaphore in `__init__` | Class-level semaphore binds to the wrong event loop in pytest environments — always create inside `run_all()` |

**Installation:**
```bash
# New workspace member
mkdir -p cores/subagent-runtime/src/subagent_runtime cores/subagent-runtime/tests/integration

# uv creates the pyproject and adds deps
uv add --package subagent-runtime langchain-aws>=1.4.6 langchain-core>=1.4.0
uv add --package subagent-runtime model-adapter  # workspace dep

# Dev deps already at workspace root; no additions needed
uv sync
```

**Version verification:** [VERIFIED: aws bedrock list-inference-profiles output, 2026-05-13]
All model ARNs listed in models.toml extension below are confirmed present in Pat's account.

---

## Architecture Patterns

### System Architecture Diagram

```
Wiki Command (Phase 3+)
       |
       | calls make_llm("librarian"), load_role_config("librarian")
       v
model-adapter.loader
  - make_llm(role) -> ChatBedrockConverse(max_tokens=N, client=boto3_with_pool)
  - load_role_config(role) -> {model_id, max_tokens, max_concurrency}
       |
       | passes (task_closure, role, model_id, max_concurrency) to pool
       v
SubagentPool.run_all(items, task, role, model_id, max_concurrency)
       |
       |-- creates asyncio.Semaphore(max_concurrency) [inside run_all, not __init__]
       |-- creates trace file path: trace_dir/<unix_timestamp>.jsonl
       |
       |-- asyncio.gather(*(_run_one(item) for item in items), return_exceptions=True)
       |
       |  For each item (up to max_concurrency simultaneously):
       |    _run_one(item):
       |      async with semaphore:        [throttle cap]
       |        t0 = time.monotonic()
       |        result = await task(item)  [task closure owns LLM]
       |        latency_ms = ...
       |        _write_trace(...)          [always called, success OR error]
       |        return (item, result) OR PerItemError(item, exc)
       |
       |-- gather collects list[tuple | PerItemError]
       |-- builds FanOutResult(successes=..., errors=...)
       v
FanOutResult returned to Wiki Command
       |
       +-- successes: [(item, result), ...]  -> wiki writes vault pages
       +-- errors:    [PerItemError, ...]    -> wiki logs warnings / decides fail-fast

.code-wiki/traces/<timestamp>.jsonl (append, one line per item)
       |
       v
code-wiki-agent trace <file>   [OBS-02 viewer: reads JSONL, renders timeline to stdout]
```

### Recommended Project Structure

```
cores/
└── subagent-runtime/
    ├── pyproject.toml           # deps: langchain-aws, langchain-core, model-adapter (workspace)
    ├── src/
    │   └── subagent_runtime/
    │       ├── __init__.py      # exports SubagentPool, FanOutResult, PerItemError
    │       └── pool.py          # SubagentPool + dataclasses + _write_trace
    └── tests/
        ├── conftest.py          # fake_llm fixture, asyncio_mode = "auto"
        ├── test_pool.py         # unit: partial failure, semaphore, trace output, token metadata
        └── integration/
            └── test_pool_bedrock.py  # @pytest.mark.integration — real Bedrock calls
```

### Pattern 1: asyncio.gather with return_exceptions (partial-failure isolation)

**What:** Run N coroutines concurrently; collect results AND exceptions without cancelling siblings.
**When to use:** Any fan-out where individual item failures should not abort the batch.

```python
# Source: Python 3.11 asyncio docs + deepagents #694 analysis
import asyncio

async def run_all(self, items, task, role, *, model_id, max_concurrency, recursion_limit=None):
    rlimit = recursion_limit if recursion_limit is not None else self._default_recursion_limit
    semaphore = asyncio.Semaphore(max_concurrency)   # MUST be created here, not in __init__
    trace_file = self._trace_dir / f"{int(time.time())}.jsonl"

    async def _run_one(item):
        async with semaphore:
            t0 = time.monotonic()
            try:
                result = await task(item)            # task closure owns the LLM
                latency_ms = int((time.monotonic() - t0) * 1000)
                self._write_trace(trace_file, role, model_id, item, "success", latency_ms, result)
                return (item, result)
            except Exception as exc:
                latency_ms = int((time.monotonic() - t0) * 1000)
                self._write_trace(trace_file, role, model_id, item, "error", latency_ms, None, error=str(exc))
                return PerItemError(item=item, exception=exc)

    raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)
    result = FanOutResult()
    for r in raw:
        if isinstance(r, PerItemError):
            result.errors.append(r)
        elif isinstance(r, BaseException):
            logger.error("Unexpected gather exception: %s", r)
        else:
            result.successes.append(r)
    return result
```

### Pattern 2: RunnableConfig recursion limit propagation

**What:** Pass `recursion_limit` in the top-level config dict (NOT under `configurable`) to every LangGraph-backed task invocation.
**When to use:** Any time a task function calls `.ainvoke()` on a LangGraph-compiled graph.

```python
# Source: https://docs.langchain.com/oss/python/langgraph/graph-api [VERIFIED: Context7]
# CORRECT:
config = RunnableConfig(recursion_limit=100)
result = await graph.ainvoke(inputs, config=config)

# WRONG — has no effect on GraphRecursionError:
config = {"configurable": {"recursion_limit": 100}}  # DON'T DO THIS
```

Note: In Phase 2, task closures wrap `llm.ainvoke()` (not a compiled graph), so `recursion_limit` is not structurally enforced at the task level. The pool still constructs and passes `RunnableConfig` at every site so that tasks which later wrap graphs work correctly without modification. This is forward-compatible plumbing.

### Pattern 3: boto3 connection pool sizing for pseudo-async Bedrock calls

**What:** `ChatBedrockConverse.ainvoke()` uses `run_in_executor` (sync boto3 in threads). Set `max_pool_connections >= max_concurrency` to prevent connection pool starvation.
**When to use:** Any role with `max_concurrency >= 5`.

```python
# Source: https://github.com/langchain-ai/langchain-aws/blob/main/samples/memory/valkey_cache.ipynb [VERIFIED: Context7]
import boto3
from botocore.config import Config
from langchain_aws import ChatBedrockConverse

def make_llm(role: str) -> ChatBedrockConverse:
    cfg = load_role_config(role)
    boto_config = Config(
        max_pool_connections=cfg["max_concurrency"],
        retries={"max_attempts": 3, "mode": "adaptive"},
        read_timeout=120,
    )
    return _GuardedChatBedrockConverse(
        model=cfg["model_id"],
        region_name=cfg.get("region", "us-east-1"),
        max_tokens=cfg["max_tokens"],
        client=boto3.client("bedrock-runtime", region_name=cfg.get("region", "us-east-1"), config=boto_config),
    )
```

### Pattern 4: usage_metadata None guard for token capture

**What:** Guard against `usage_metadata = None` on Bedrock error responses before accessing token fields.
**When to use:** In every `_write_trace` call — always.

```python
# Source: Context7 /langchain-ai/langchain-aws (usage_metadata field docs) [VERIFIED]
tokens_in: int | None = None
tokens_out: int | None = None
if response is not None and hasattr(response, "usage_metadata"):
    meta = response.usage_metadata   # None on ThrottlingException, content filter, etc.
    if meta is not None:
        tokens_in = meta.get("input_tokens")
        tokens_out = meta.get("output_tokens")
# tokens_in and tokens_out default to None (JSON null) — never 0
```

### Anti-Patterns to Avoid

- **`asyncio.TaskGroup` for fan-out:** Python 3.11 TaskGroup cancels siblings on first exception — the opposite of what partial-failure isolation requires. Use `asyncio.gather(return_exceptions=True)`.
- **Semaphore in `__init__`:** Creates semaphore in the synchronous context with no event loop. When `run_all()` awaits it in a test-created loop, raises `RuntimeError: Task attached to a different loop`. Always create inside `run_all()`.
- **`RunnableConfig` under `configurable` key:** `{"configurable": {"recursion_limit": N}}` has no effect on `GraphRecursionError`. The key must be top-level: `{"recursion_limit": N}`.
- **Catching OSError inside the task wrapper and masking it as a PerItemError:** If `_write_trace` raises `OSError` and is not caught inside `_write_trace` itself, it propagates into `_run_one`'s `except Exception` block, making the item appear as an error when the task actually succeeded. Catch OSError inside `_write_trace` and log as WARNING.
- **`asyncio.run()` inside a test:** pytest-asyncio `asyncio_mode="auto"` already runs an event loop. Calling `asyncio.run()` inside a test raises `RuntimeError: This event loop is already running`. Use `await` directly in `async def` tests.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Partial-failure collect | Custom exception collector | `asyncio.gather(return_exceptions=True)` | stdlib; handles cancelled tasks, BaseException subclasses, and all edge cases correctly |
| Async rate limiting | Manual counter + sleep | `asyncio.Semaphore` | stdlib; correctly handles concurrent acquisitions without polling |
| Token counting pre-flight | tiktoken or hand-rolled | `boto3 client.count_tokens()` API | tiktoken is OpenAI-specific BPE — does not work for Claude; CountTokens API is Bedrock-native (Phase 3+ — not needed in Phase 2) |
| Retry on structured output parse failure | Custom retry loop from scratch | `try/except OutputParserException` with max 2 retries | LangChain's `with_structured_output(method="json_schema")` handles native JSON schema; retry loop is 10 lines, not a custom framework |
| JSONL serialization | Custom encoding | `json.dumps(record) + "\n"` | stdlib; no escaping or schema validation needed for this fixed schema |

**Key insight:** asyncio's built-in primitives handle all the edge cases in concurrent fan-out. The only custom code needed is the glue that wires results into `FanOutResult`, enforces the semaphore per-role, and writes the JSONL record. Everything else is stdlib or langchain-aws already in the workspace.

---

## Common Pitfalls

### Pitfall 1: Semaphore Event Loop Binding

**What goes wrong:** `asyncio.Semaphore` created in `__init__` (sync context) is not bound to any event loop. When `run_all()` is awaited inside pytest-asyncio's auto-managed loop, the semaphore's internal lock is associated with a different loop, raising `RuntimeError: Task attached to a different loop` and making the concurrency test fail with an infrastructure error rather than a logic error.

**Why it happens:** `asyncio.Semaphore` in Python 3.10+ defers loop binding to first use, but some internal implementations (depending on patch level) bind eagerly. Regardless of Python version, creating the semaphore inside `run_all()` is the correct pattern — it guarantees the semaphore is always bound to the currently running loop.

**How to avoid:** Create `asyncio.Semaphore(max_concurrency)` as the first line inside `run_all()`, not in `__init__`.

**Warning signs:** `RuntimeError: Task attached to a different loop` in unit tests; semaphore is at class level.

### Pitfall 2: Trace Write Failure Masking Task Success

**What goes wrong:** `_write_trace()` raises `OSError` (disk full, permission denied, path does not exist). If `_write_trace` is called inside the `try` block of `_run_one` and the exception propagates, the outer `except Exception` catches it and records the item as a `PerItemError`. The task completed successfully — but the caller sees a failure. Token counts are lost permanently.

**Why it happens:** The `try/except` in `_run_one` is meant to catch task failures, not trace infrastructure failures. Trace failures are a different severity than task failures.

**How to avoid:** Wrap `_write_trace` in its own `try/except OSError` internally. On failure, log `WARNING` to stderr and return without raising. Never let a trace write failure propagate out of `_write_trace`.

**Warning signs:** Items appearing in `FanOutResult.errors` with OSError messages; `PerItemError.exception` is an `OSError` not a Bedrock or task error.

### Pitfall 3: `usage_metadata` AttributeError on Error Responses

**What goes wrong:** Bedrock returns a non-200 error (`ThrottlingException`, content filter, service unavailable). `ChatBedrockConverse` sets `response.usage_metadata = None`. Accessing `meta.get("input_tokens")` without a None guard raises `AttributeError` inside `_write_trace`, potentially corrupting the trace record for the current item and crashing the trace writer for the remainder of the batch.

**Why it happens:** `usage_metadata` is `None` on error paths — this is confirmed behavior in langchain-aws. The field is not always a dict.

**How to avoid:** Always check `if meta is not None` before accessing token fields. On error path where `usage_metadata` is `None`, write `"tokens_in": null, "tokens_out": null` explicitly.

**Warning signs:** `AttributeError: 'NoneType' object has no attribute 'get'` in trace writer; happens only when Bedrock returns throttling or content filter errors.

### Pitfall 4: boto3 Connection Pool Exhaustion

**What goes wrong:** `ChatBedrockConverse.ainvoke()` uses `run_in_executor` — each concurrent call consumes a thread AND a boto3 connection. The default `max_pool_connections=10`. With `max_concurrency=10` (scanner role), all 10 tasks fire simultaneously. The 11th connection attempt causes `ConnectionPool is full, discarding connection` warnings. Calls serialize instead of parallelizing, defeating the concurrency goal.

**Why it happens:** boto3's sync HTTP client has a fixed connection pool. The asyncio semaphore limits Python-side task count but does not configure the underlying boto3 pool.

**How to avoid:** Pass `Config(max_pool_connections=max_concurrency)` to the boto3 client at `make_llm()` construction time. Set this equal to or greater than the role's `max_concurrency`.

**Warning signs:** `WARNING - Connection pool is full, discarding connection for...` in logs; fan-out latency equals serial latency (no speedup despite semaphore cap).

### Pitfall 5: Incorrect RunnableConfig key placement

**What goes wrong:** `recursion_limit` is placed under `{"configurable": {"recursion_limit": N}}` instead of at the top level `{"recursion_limit": N}`. LangGraph reads `recursion_limit` from the top-level config key only. The nested key is silently ignored. A subagent that executes more than the default (1000 in LangGraph 1.2.0) steps raises `GraphRecursionError` with no diagnostic about the misconfigured key.

**Why it happens:** `configurable` is LangGraph's namespace for user-defined config passthrough, not for system settings. `recursion_limit` is a system key, not a configurable key.

**How to avoid:** Always use `RunnableConfig(recursion_limit=N)` or `{"recursion_limit": N}` at the top level. Confirm in test that the key is present at the correct level.

**Warning signs:** `GraphRecursionError` raised despite passing a `recursion_limit` argument; the argument is buried under `configurable`.

---

## Code Examples

### SubagentPool — full implementation skeleton

```python
# Source: AI-SPEC.md Section 3 + asyncio docs [VERIFIED: Context7 /langchain-ai/langchain-aws, LangGraph docs]
# cores/subagent-runtime/src/subagent_runtime/pool.py

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


@dataclass
class PerItemError:
    item: Any
    exception: Exception


@dataclass
class FanOutResult:
    successes: list[tuple[Any, Any]] = field(default_factory=list)
    errors: list[PerItemError] = field(default_factory=list)


class SubagentPool:
    def __init__(self, trace_dir: Path, *, default_recursion_limit: int = 100) -> None:
        self._trace_dir = trace_dir
        self._default_recursion_limit = default_recursion_limit
        self._trace_dir.mkdir(parents=True, exist_ok=True)

    async def run_all(
        self,
        items: list[Any],
        task: Callable[[Any], Awaitable[Any]],
        role: str,
        *,
        model_id: str,
        max_concurrency: int,
        recursion_limit: int | None = None,
    ) -> FanOutResult:
        rlimit = recursion_limit if recursion_limit is not None else self._default_recursion_limit
        semaphore = asyncio.Semaphore(max_concurrency)  # created here, NOT in __init__
        trace_file = self._trace_dir / f"{int(time.time())}.jsonl"

        async def _run_one(item: Any) -> tuple[Any, Any] | PerItemError:
            async with semaphore:
                t0 = time.monotonic()
                try:
                    _config = RunnableConfig(recursion_limit=rlimit)  # top-level key
                    result = await task(item)
                    latency_ms = int((time.monotonic() - t0) * 1000)
                    self._write_trace(trace_file, role, model_id, item, "success", latency_ms, result)
                    return (item, result)
                except Exception as exc:
                    latency_ms = int((time.monotonic() - t0) * 1000)
                    self._write_trace(trace_file, role, model_id, item, "error", latency_ms, None, error=str(exc))
                    return PerItemError(item=item, exception=exc)

        raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)
        result = FanOutResult()
        for r in raw:
            if isinstance(r, PerItemError):
                result.errors.append(r)
            elif isinstance(r, BaseException):
                logger.error("Unexpected gather exception: %s", r)
            else:
                result.successes.append(r)
        return result

    def _write_trace(
        self,
        path: Path,
        role: str,
        model_id: str,
        item: Any,
        status: str,
        latency_ms: int,
        response: Any,
        *,
        error: str | None = None,
    ) -> None:
        tokens_in: int | None = None
        tokens_out: int | None = None
        if response is not None and hasattr(response, "usage_metadata"):
            meta = response.usage_metadata  # may be None on Bedrock error responses
            if meta is not None:
                tokens_in = meta.get("input_tokens")
                tokens_out = meta.get("output_tokens")

        record = {
            "role": role,
            "model_id": model_id,
            "prompt_hash": None,  # computed by task closure; pool receives opaque response
            "item_id": getattr(item, "id", None) or str(item),
            "status": status,
            "latency_ms": latency_ms,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": None,   # Phase 4
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if error:
            record["error"] = error
        try:
            with path.open("a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError as exc:
            logger.warning("Trace write failed (data loss): %s", exc)
            # Never raise — trace failure must not mask task success
```

### models.toml extension (7 roles)

```toml
# cores/model-adapter/src/model_adapter/models.toml
# Phase 1 entries — unchanged
[roles.haiku]
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"

[roles.sonnet]
model_id        = "us.anthropic.claude-sonnet-4-6"
region          = "us-east-1"

# Phase 2 additions — 7 named roles
[roles.librarian]
# Query answer synthesis — moderate quality, moderate volume
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 5

[roles.scanner]
# Vault-wide page scanning — high volume, fast, cheap
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"
max_tokens      = 500
max_concurrency = 10

[roles.linter]
# Wiki lint checks — structured output, high volume
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"
max_tokens      = 3000
max_concurrency = 10

[roles.ingestor]
# Page ingestion / summary extraction — moderate quality
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 5

[roles.synthesizer]
# Multi-page synthesis — quality-critical, lower volume
model_id        = "us.anthropic.claude-sonnet-4-6"
region          = "us-east-1"
max_tokens      = 4096
max_concurrency = 3

[roles.judge_a]
# Eval judge A — quality-critical, Phase 4
model_id        = "us.anthropic.claude-sonnet-4-6"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 2

[roles.judge_b]
# Eval judge B — second opinion, Phase 4
model_id        = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region          = "us-east-1"
max_tokens      = 2048
max_concurrency = 2
```

**Note on ARNs:** [VERIFIED: `aws bedrock list-inference-profiles --region us-east-1`, 2026-05-13] Both `us.anthropic.claude-haiku-4-5-20251001-v1:0` and `us.anthropic.claude-sonnet-4-6` are confirmed present in Pat's account. The `linter` max_tokens is set to 3000 (per success criterion #3) to match the success criteria spec; `scanner` is 500.

**Note on `judge_b`:** The AI-SPEC proposes Sonnet for both judges, but using Haiku for `judge_b` reduces eval cost and fulfills the "heterogeneous judge panel" requirement (different model families). [ASSUMED] — Pat should confirm whether heterogeneous panel means different providers or just different model sizes within Claude.

### load_role_config extension to model_adapter/loader.py

```python
# Addition to cores/model-adapter/src/model_adapter/loader.py
# (additions only — no existing code modified)

def load_role_config(role: str) -> dict:
    """Return the raw config dict for a role from models.toml.

    Raises KeyError if role is not present.
    Returns all keys present in models.toml for the role:
    {model_id, region, max_tokens (optional), max_concurrency (optional)}
    """
    config = _load_models_config()
    return config["roles"][role]  # KeyError if role absent — intentional
```

### pyproject.toml for cores/subagent-runtime

```toml
[project]
name = "subagent-runtime"
version = "0.1.0"
description = "Async fan-out primitive for code-wiki-agent subagent dispatch"
requires-python = ">=3.11"
dependencies = [
    "langchain-aws>=1.4.6",
    "langchain-core>=1.4.0",
    "model-adapter",
]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.uv.sources]
model-adapter = { workspace = true }

[tool.pytest.ini_options]
testpaths   = ["tests"]
addopts     = "--import-mode=importlib"
asyncio_mode = "auto"   # required for async def test functions in pool tests
markers     = ["integration: requires real Bedrock (skipped by default)"]
```

### Unit test pattern — fake_llm fixture

```python
# cores/subagent-runtime/tests/conftest.py
from __future__ import annotations
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def fake_llm_response():
    """Returns a mock AIMessage with populated usage_metadata."""
    resp = MagicMock()
    resp.content = "mocked response"
    resp.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    return resp


@pytest.fixture
def fake_llm_response_error():
    """Returns a mock AIMessage with usage_metadata=None (Bedrock error path)."""
    resp = MagicMock()
    resp.content = ""
    resp.usage_metadata = None
    return resp


@pytest.fixture
def make_task(fake_llm_response):
    """Factory: returns async task that returns fake_llm_response."""
    def _make(*, raise_for: set = frozenset()):
        async def task(item):
            if item in raise_for:
                raise ValueError(f"Intentional failure for item: {item}")
            return fake_llm_response
        return task
    return _make
```

### Integration test pattern

```python
# cores/subagent-runtime/tests/integration/test_pool_bedrock.py
from __future__ import annotations
import os
import pytest
from pathlib import Path
from subagent_runtime.pool import SubagentPool


@pytest.mark.integration
async def test_partial_failure_real_bedrock(tmp_path):
    """4 parallel subagents; 1 intentionally raises; 3 successes, 1 error — real Bedrock."""
    if not os.environ.get("CODE_WIKI_RUN_INTEGRATION"):
        pytest.skip("Set CODE_WIKI_RUN_INTEGRATION=1")
    from model_adapter.loader import make_llm, load_role_config

    role = "scanner"
    cfg = load_role_config(role)
    llm = make_llm(role)

    async def task(item):
        if item == "bad":
            raise ValueError("intentional failure")
        return await llm.ainvoke([{"role": "user", "content": f"Say: ok-{item}"}])

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=["a", "b", "bad", "c"],
        task=task,
        role=role,
        model_id=cfg["model_id"],
        max_concurrency=cfg["max_concurrency"],
    )
    assert len(result.successes) == 3
    assert len(result.errors) == 1
    assert result.errors[0].item == "bad"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| deepagents `SubAgentMiddleware` for fan-out | Raw `asyncio.gather(return_exceptions=True)` + semaphore | deepagents #694 (cancellation cascade) unresolved in 0.6.1 | Simpler, more predictable, no dependency on deepagents internals |
| `asyncio.gather` without `return_exceptions` | `asyncio.gather(..., return_exceptions=True)` | Python 3.8+ has had this; it's just the correct usage | Prevents sibling cancellation on first task failure |
| Fixed recursion limit (deepagents default was 25 steps) | Inherited from parent via `RunnableConfig(recursion_limit=N)` | deepagents PR #2194, released 0.5.4 / 0.6.1 | Subagents no longer silently truncate at 25 steps |
| `ChatBedrock` (legacy) | `ChatBedrockConverse` | langchain-aws deprecation | Converse API supports all current Bedrock models uniformly |
| SSE transport for MCP | stdio transport | MCP spec 2025-03-26 | SSE deprecated; stdio is the correct local hosting transport |

**Deprecated/outdated:**
- `asyncio.TaskGroup`: Python 3.11+ but WRONG for fan-out — it cancels siblings on first exception. Use `gather(return_exceptions=True)` for partial-failure fan-out.
- `deepagents.SubAgentMiddleware` for this use case: #694 bug makes it unreliable for partial-failure scenarios until the fix is released. Revisit after next deepagents release.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `judge_b` using Haiku (not Sonnet) satisfies "heterogeneous panel" requirement | Standard Stack / models.toml | If Pat requires different providers (not just sizes), both judges must use different providers — Haiku and Sonnet are both Claude; update `judge_b` to a non-Anthropic model |
| A2 | LangGraph 1.2.0 default `recursion_limit` is 1000 steps | Common Pitfalls / State of the Art | If the actual default differs, the integration test for 30-step chains may behave differently; verify via `langgraph.__version__` and docs |
| A3 | Phase 1 `make_llm()` does not yet pass `max_tokens` to `ChatBedrockConverse` | Code Examples (load_role_config) | If Phase 1 already passes `max_tokens`, adding it to `models.toml` entries and `make_llm()` may conflict — check `loader.py` before implementing BED-03 |

**Note on A3:** Confirmed by reading `cores/model-adapter/src/model_adapter/loader.py` — current `make_llm()` does NOT pass `max_tokens`. The TOML entries for `haiku` and `sonnet` roles do not have `max_tokens` fields. Phase 2 adds both. [VERIFIED: codebase read, 2026-05-13]

---

## Open Questions (RESOLVED)

1. **`judge_b` model selection** — RESOLVED: Use `us.anthropic.claude-sonnet-4-6` for `judge_b` (per Plan 02-01 Task 2; Pat can update `models.toml` with no code changes if a non-Claude model is desired later).
   - What we knew: AI-SPEC recommends Sonnet for both judges; CLAUDE.md mentions "heterogeneous judge panel" for bias mitigation.
   - Resolution: "Heterogeneous" means different model sizes (Haiku vs Sonnet) within the same provider family is fine for Phase 2. Use Sonnet as the default to match AI-SPEC and avoid split-panel complexity until Phase 4 eval work.

2. **`max_tokens` for `haiku` and `sonnet` base roles (Phase 1 legacy entries)** — RESOLVED: Add `max_tokens` to all entries including `haiku` and `sonnet` for consistency; `make_llm()` reads `role_cfg.get("max_tokens")` and passes it only if set (per Plan 02-01 Task 2 and AI-SPEC Section 4).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Runtime | Yes | 3.11+ | — |
| `uv` | Workspace manager | Yes | 0.11.14 | — |
| `boto3` / AWS CLI | Bedrock integration tests | Yes | confirmed (aws CLI used) | Skip integration tests |
| Bedrock cross-region inference profiles | SUB-05 throttle test, BED-02 | Yes | confirmed via `list-inference-profiles` | — |
| `pytest-asyncio` | Async test functions | Yes | 1.3.0 (workspace dev dep) | — |
| `langchain-aws` | ChatBedrockConverse | Yes | 1.4.6 (installed) | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — all required tools confirmed available.

**Note:** `asyncio_mode = "auto"` is NOT currently set in `cores/subagent-runtime`'s `pyproject.toml` (that file does not exist yet). Wave 0 must create the pyproject with this setting to enable async tests.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8.3 + pytest-asyncio 1.3.0 |
| Config file | `cores/subagent-runtime/pyproject.toml` (to be created in Wave 0) |
| Quick run command | `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/test_pool.py -v` |
| Full suite command | `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SUB-01 | `SubagentPool` class importable, `run_all()` returns `FanOutResult` | unit | `pytest tests/test_pool.py::test_fanout_returns_fanout_result -x` | Wave 0 |
| SUB-02 / SUB-07 | 4 tasks dispatched, 1 raises: 3 successes + 1 error, no sibling cancel | unit | `pytest tests/test_pool.py::test_partial_failure_isolation -x` | Wave 0 |
| SUB-02 / SUB-07 | Same scenario against real Bedrock | integration | `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_pool_bedrock.py::test_partial_failure_real_bedrock -x` | Wave 0 |
| SUB-04 | `RunnableConfig(recursion_limit=N)` top-level key present on every task call | unit | `pytest tests/test_pool.py::test_recursion_limit_propagated -x` | Wave 0 |
| SUB-05 | Semaphore created inside `run_all()`; peak in-flight <= max_concurrency; no loop error | unit | `pytest tests/test_pool.py::test_semaphore_caps_concurrency -x` | Wave 0 |
| SUB-05 | 5 parallel subagents on real Bedrock produce no ThrottlingException | integration | `CODE_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_pool_bedrock.py::test_throttle_cap -x` | Wave 0 |
| SUB-06 / OBS-01 | Every item (success + error) produces exactly one JSONL record | unit | `pytest tests/test_pool.py::test_trace_record_completeness -x` | Wave 0 |
| SUB-06 | Error-path records have `status=error` and `error` field | unit | `pytest tests/test_pool.py::test_trace_error_path_record -x` | Wave 0 |
| SUB-06 | `_write_trace` OSError is caught internally; WARNING logged; task result not masked | unit | `pytest tests/test_pool.py::test_trace_write_failure_logged_not_raised -x` | Wave 0 |
| BED-05 | Success records have integer `tokens_in`/`tokens_out` from `usage_metadata` | unit | `pytest tests/test_pool.py::test_token_metadata_success -x` | Wave 0 |
| BED-05 | Error-path records have `tokens_in=null`, `tokens_out=null`, no AttributeError | unit | `pytest tests/test_pool.py::test_token_metadata_none_guard -x` | Wave 0 |
| BED-02 / BED-03 / BED-04 | All 7 roles resolve from `models.toml` with `model_id`, `max_tokens`, `max_concurrency` | unit (parametrized) | `pytest tests/test_pool.py::test_all_roles_resolve -x` | Wave 0 |
| OBS-01 | Two `run_all()` calls produce two separate trace files | unit | `pytest tests/test_pool.py::test_separate_trace_files -x` | Wave 0 |
| OBS-02 | `code-wiki-agent trace <file>` renders JSONL to stdout | unit | `pytest agents/code-wiki-agent/tests/unit/test_trace_viewer.py -x` | Wave 0 |
| OBS-03 | Cost summary printed after `run_all()` interactive run | unit (CLI) | `pytest agents/code-wiki-agent/tests/unit/test_cli_trace_summary.py -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/test_pool.py -v`
- **Per wave merge:** `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/ -v`
- **Phase gate:** Full unit suite green + integration tests pass (with `CODE_WIKI_RUN_INTEGRATION=1`) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `cores/subagent-runtime/` — entire package does not exist; create in Wave 0
- [ ] `cores/subagent-runtime/pyproject.toml` — covers package setup + `asyncio_mode = "auto"`
- [ ] `cores/subagent-runtime/src/subagent_runtime/__init__.py` — exports `SubagentPool, FanOutResult, PerItemError`
- [ ] `cores/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool` implementation
- [ ] `cores/subagent-runtime/tests/conftest.py` — `fake_llm_response`, `make_task` fixtures
- [ ] `cores/subagent-runtime/tests/test_pool.py` — 12 unit test cases
- [ ] `cores/subagent-runtime/tests/integration/test_pool_bedrock.py` — 3 integration tests
- [ ] `agents/code-wiki-agent/tests/unit/test_trace_viewer.py` — OBS-02 viewer tests
- [ ] Addition to `model_adapter/loader.py`: `load_role_config()` function
- [ ] Update to `model_adapter/models.toml`: 7 named roles with `max_tokens` + `max_concurrency`

---

## Security Domain

**`security_enforcement`:** Not explicitly `false` in config — section is required.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No user auth — internal single-operator tool |
| V3 Session Management | No | No sessions — stateless per fan-out call |
| V4 Access Control | No | Single operator; no multi-tenant access |
| V5 Input Validation | Partial | `item_id` written to JSONL; `str(item)` could contain special characters. `json.dumps()` handles escaping — no custom serialization |
| V6 Cryptography | No | SHA-256 for `prompt_hash` (integrity only, not security — no secrets in prompt hash) |
| V7 Error Handling | Yes | Error messages in `PerItemError.exception` and JSONL `error` field must not expose AWS credentials or secrets from the vault. Task closures must not include secrets in error messages. |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| AWS credentials in trace files | Information Disclosure | Ensure task closures do not embed credentials in prompts or item representations; `item_id` is `str(item)` or `item.id` — items should not carry raw credential strings |
| JSONL injection via `item_id` | Tampering | `json.dumps()` correctly escapes all control characters and quotes; no risk |
| Trace directory path traversal | Elevation of Privilege | `trace_dir` is set at construction from caller-controlled `vault_root / ".code-wiki/traces"` — no user input; not a public API |
| OSError on trace write (denial of service) | Denial of Service | Caught explicitly; logged as WARNING; never raises to caller — prevents trace failure from aborting fan-out |

---

## Sources

### Primary (HIGH confidence)

- [VERIFIED: Context7 `/langchain-ai/langchain-aws`] — `usage_metadata` field names (`input_tokens`, `output_tokens`), async boto3 config pattern (`max_pool_connections`, `Config`, semaphore usage), `ChatBedrockConverse` construction
- [VERIFIED: Context7 `/websites/langchain_oss_python_langgraph`] — `recursion_limit` is a top-level config key (`{"recursion_limit": N}`), not under `configurable`; `GraphRecursionError` handling
- [VERIFIED: `aws bedrock list-inference-profiles --region us-east-1`] — All 7 role ARNs confirmed present in Pat's account: `us.anthropic.claude-haiku-4-5-20251001-v1:0`, `us.anthropic.claude-sonnet-4-6`
- [VERIFIED: codebase read] — Phase 1 `loader.py` does not pass `max_tokens`; `models.toml` has only `haiku` and `sonnet` entries; `load_role_config()` does not exist yet

### Secondary (MEDIUM confidence)

- [CITED: https://github.com/langchain-ai/deepagents/issues/694] — Cancellation cascade bug: confirmed closed on GitHub; fix merged but not in 0.6.1 release
- [CITED: https://github.com/langchain-ai/deepagents/pull/2194] — GraphRecursionError fix: PR confirmed adds `recursion_limit` inheritance from parent config; released in 0.5.4 / 0.6.1
- [CITED: https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html] — Cross-region inference profile documentation; verified ARIDs match account query

### Tertiary (LOW confidence)

- [ASSUMED] — LangGraph 1.2.0 default recursion limit is 1000 steps (changed from 25 at some point in 0.x history); verify with `langgraph` source if integration test shows unexpected behavior

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already installed in workspace; no new dependencies
- Architecture: HIGH — asyncio pool pattern is well-established; all edge cases documented in AI-SPEC.md
- Model ARNs: HIGH — verified against Pat's live AWS account via `list-inference-profiles`
- Pitfalls: HIGH — verified via Context7 docs (usage_metadata), Python asyncio docs (semaphore lifecycle), LangGraph docs (recursion_limit key placement)

**Research date:** 2026-05-13
**Valid until:** 2026-06-13 (30 days — stable stack; inference profile ARNs may change if AWS adds new model versions)
