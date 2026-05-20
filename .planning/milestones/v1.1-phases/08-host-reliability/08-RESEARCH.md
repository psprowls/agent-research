# Phase 8: Host Reliability - Research

**Researched:** 2026-05-17
**Domain:** MCP cancellation protocol, FastMCP asyncio internals, SubagentPool cancel contract, E2E integration test harness
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Host harness:**
- D-01: Hand-built spec-conformant MCP host extending `test_mcp_stdio.py`. Both tests spawn `graph-wiki-mcp` via `subprocess.Popen(["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-mcp"])` and drive JSON-RPC over stdin/stdout. No new test-time deps.
- D-02: Framing throughout: "spec-conformant MCP host — same protocol surface DeepAgents CLI uses." Not "the DeepAgents CLI."

**Cancel induction mechanism:**
- D-03: MCP protocol `notifications/cancelled` is the cancel signal: `{"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId": <id>}}`.
- D-04: Propagation chain: FastMCP receives notification → cancels the anyio CancelScope → asyncio task raises `asyncio.CancelledError` → propagates into `await run_query` / `SubagentPool.run_all` → `asyncio.gather(return_exceptions=True)` does NOT swallow outer CancelledError; inner tasks each see CancelledError, write per-item `cancelled` trace, return control.
- D-05: Orphan-call caveat in `docs/cancellation.md`: `ChatBedrockConverse` wraps sync boto3 via `loop.run_in_executor(None, ...)` (the default executor = thread pool). The underlying HTTPS request cannot be interrupted mid-flight. v1.1 "clean cancel" = asyncio task unwinds + trace written; boto3 thread runs to HTTP completion and result is discarded.

**Trace `cancelled` event shape:**
- D-06: Two-layer trace. Per-item `status: cancelled` record + one batch terminal `event: batch_cancelled` summary.
- D-07: `event` field is the discriminator. Per-item records have no `event` key. Summary record has `event: batch_cancelled`.
- D-08: `_write_trace` gains `status: "cancelled"` branch (tokens null, cost null). New `_write_batch_terminal` helper writes the summary. Both keep the "never raises — OSError logged at WARNING" contract.

**Slow-model strategy:**
- D-09: Monkeypatch `model_adapter.loader.make_llm` to return a fake `AsyncMock`-style class (or stub subclass of `ChatBedrockConverse`) that `await asyncio.sleep(N)` then returns a canned `AIMessage` with `usage_metadata`. N ~2-3s.
- D-10: Cancel test runs WITHOUT `GRAPH_WIKI_RUN_INTEGRATION=1` gate (stub model, no Bedrock). 6-tool E2E test IS gated by `GRAPH_WIKI_RUN_INTEGRATION=1`.
- D-11: Orphan-call coverage is documentation only (snippet in `docs/cancellation.md`), not asserted in the automated cancel test.

**Test fixture / vault strategy:**
- D-12: Fresh `tmp_path` per run. Sequence: `wiki_init` → inline seed (3-5 pages + 1 source + 1 work item) → `wiki_scan` → `wiki_ingest` → `wiki_query` → `wiki_lint` → `wiki_log`.
- D-13: CWD discipline — scan target MUST be `tmp_path`, not the deep-agents workspace.
- D-14: One test function, sequential sub-assertions.

**Docs surface:**
- D-15: `docs/cancellation.md` at repo root. Five sections: (1) protocol behavior; (2) internal chain; (3) trace shapes with examples; (4) known limitations; (5) future work.

### Claude's Discretion
- Per-tool input shapes for the 6-tool E2E test.
- Seed-page content (3-5 pages, deterministic frontmatter + wikilink chain).
- Test file layout (`test_mcp_e2e.py` vs `test_mcp_cancel.py` vs extending `test_mcp_stdio.py`).
- Bedrock test budget for the 6-tool test.

### Deferred Ideas (OUT OF SCOPE)
- SIGINT and stdin-close cancel paths (v1.2).
- `aioboto3` / true wire-level cancel (v1.2).
- Real `deepagents` CLI binary in tests.
- Per-tool granular E2E tests.
- Trace renderer enhancements for `cancelled` records (Phase 9).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MCP-09 | Mid-fan-out cancel from a real DeepAgents CLI host is reproduced and current behavior documented | FastMCP cancel chain verified (Q1); MCP spec wire format fetched (Q7); `docs/cancellation.md` structure defined (Q13) |
| MCP-10 | In-flight SubagentPool invocations terminate cleanly on host cancel; traces close with `cancelled` terminal event | `asyncio.gather` + CancelledError propagation verified (Q3); exact `_write_trace` diff shape proposed (Q6) |
| MCP-11 | Automated cancel test covers cancel-mid-fan-out at MCP transport boundary under opt-in gate | Monkeypatch path confirmed (`model_adapter.loader.make_llm`, Q4); `report_progress` timing for race control verified (Q8) |
| DACLI-01 | E2E test launches `graph-wiki-mcp` as a stdio subprocess from a spec-conformant MCP host | Existing `_run_server` / `_send_initialize` pattern reusable; D-01 |
| DACLI-02 | Test exercises all six tools with realistic inputs, asserts non-error outcomes | All 6 tool signatures read; input shapes proposed (Q10, Q12) |
| DACLI-03 | Test runs under `GRAPH_WIKI_RUN_INTEGRATION=1` opt-in gate | `INTEGRATION_GATE` pattern in `conftest.py` confirmed reusable |
</phase_requirements>

---

## Summary

Phase 8 has two independent tracks: (a) proving MCP `notifications/cancelled` unwinds `SubagentPool` cleanly and writing a cancel test at the protocol boundary, and (b) a single 6-tool end-to-end integration test that exercises every shipped MCP tool against a fresh `tmp_path` vault.

The cancel propagation chain is fully understood and verified in this research. FastMCP (mcp 1.27.x) uses anyio's `CancelScope` to track in-flight tool requests. When `notifications/cancelled` arrives, it calls `await self._in_flight[cancelled_id].cancel()` on the corresponding `RequestResponder`, which cancels the anyio scope running the async tool handler. This surfaces as `asyncio.CancelledError` inside the handler's `await run_query(...)` call. Python's `asyncio.gather(return_exceptions=True)` does NOT swallow an outer cancel — the gather itself raises `CancelledError` when the enclosing task is cancelled — all inner tasks also receive `CancelledError`. The `SubagentPool._write_trace` modifications needed for the `cancelled` status branch are small and well-defined.

The E2E test requires one planner-added API surface: `WikiScanInput` in `server.py` currently has NO `repo_path` field and does not pass `repo_path` to `run_scan`. Without this, the E2E test cannot scope scan to `tmp_path` at the MCP protocol layer. The planner must add `repo_path: str = ""` to `WikiScanInput` and wire it through to `run_scan(repo_path=...)`. This is a required code change, not just a test fixture choice.

**Primary recommendation:** Start with the cancel chain wiring in `pool.py` (no new API surface required), then add `WikiScanInput.repo_path` + the 6-tool E2E test, then write `docs/cancellation.md`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| MCP cancel signal reception | MCP transport (FastMCP / anyio) | — | `notifications/cancelled` is handled by `mcp.shared.session.BaseSession`; no application code involved |
| Tool handler cancellation | FastMCP / anyio CancelScope | asyncio event loop | FastMCP cancels the anyio scope; asyncio sees `CancelledError` in the awaiting coroutine |
| Fan-out task cancellation | SubagentPool (`pool.py`) | asyncio.gather | Outer `CancelledError` propagates into `gather`; each `_run_one` must catch and write `cancelled` trace |
| Trace write on cancel | SubagentPool (`pool.py`) | — | `_write_trace` (per-item) and new `_write_batch_terminal` (summary) — both at the subagent-runtime layer |
| boto3 thread lifecycle | OS thread pool (executor) | — | `loop.run_in_executor(None, ...)` puts boto3 in a daemon thread; cancelled asyncio task does not kill the thread |
| E2E test subprocess launch | Test harness (`subprocess.Popen`) | — | Existing `_run_server` pattern; no new infrastructure |
| Scan target isolation (CWD) | `run_scan(repo_path=...)` + `WikiScanInput.repo_path` | — | `repo_path` override in `run_scan` already exists; must be exposed on the MCP input schema |
| Cancel test monkeypatch | `model_adapter.loader.make_llm` | — | Patching `make_llm` is the single injection point for all role-bound model creation |

---

## Standard Stack

### Core (all already in the workspace — no new deps)

| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| `mcp` | 1.27.1 | MCP server SDK; `notifications/cancelled` handling via `BaseSession` | [VERIFIED: CLAUDE.md] |
| `pytest` | ≥8.3 | Test runner | [VERIFIED: CLAUDE.md] |
| `pytest-asyncio` | 1.3.0 | `asyncio_mode = "auto"` for async test functions | [VERIFIED: CLAUDE.md] |
| `subprocess` | stdlib | Spawn `graph-wiki-mcp` subprocess in test harness | [VERIFIED: codebase] |
| `asyncio` | stdlib | CancelledError propagation; `run_in_executor` thread dispatch | [VERIFIED: codebase] |
| `langchain-aws` | 1.4.6 | `ChatBedrockConverse._generate` (sync); `_agenerate` inherited from `BaseChatModel` | [VERIFIED: CLAUDE.md] |
| `langchain-core` | 1.4.0 | `BaseChatModel._agenerate` → `run_in_executor(None, self._generate, ...)` | [VERIFIED: codebase inspection] |

**No new packages required for this phase.** All work is in existing code and tests.

---

## Package Legitimacy Audit

No new packages are installed in this phase. All dependencies are already present in the workspace. This section is not applicable.

---

## Architecture Patterns

### System Architecture Diagram

```
MCP Client (test harness subprocess stdin)
   |
   | JSON-RPC: tools/call wiki_query {requestId: "X"}
   v
FastMCP stdio_server (mcp 1.27.x)
   |
   | spawns anyio task with CancelScope
   v
wiki_query tool handler (server.py)
   |
   | await ctx.report_progress(0, top_k, "Starting...")  <--- cancel test observes this
   |
   | await run_query(...)
   v
run_query (commands/query.py)
   |
   | await pool.run_all(items=top_pages, task=drill_page, ...)
   v
SubagentPool.run_all (pool.py)
   |
   | asyncio.gather(*[_run_one(i) for i in items], return_exceptions=True)
   |
   +---> _run_one(page_1) -----> await librarian_llm.ainvoke(msgs)
   +---> _run_one(page_2) -----> await librarian_llm.ainvoke(msgs)
   +---> _run_one(page_N) -----> await librarian_llm.ainvoke(msgs)
              |
              | BaseChatModel._agenerate calls:
              | loop.run_in_executor(None, self._generate, ...)
              v
         OS Thread (boto3 HTTPS to Bedrock — cannot be interrupted)

MCP Client sends:  {"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":"X"}}
   |
   | mcp.shared.session.BaseSession processes CancelledNotification
   | _in_flight["X"].cancel() -> cancels anyio CancelScope
   |
   v
wiki_query handler task gets CancelledError at: await run_query(...)
   |
   v
run_query gets CancelledError at: await pool.run_all(...)
   |
   v
asyncio.gather(..., return_exceptions=True) — outer task is cancelled
   | each _run_one task also receives CancelledError
   v
Each _run_one: catches CancelledError, calls _write_trace(..., "cancelled"), re-raises
   |
   v
run_all: outer CancelledError propagates; run_all calls _write_batch_terminal(...)
   |
   v
JSONL trace file:
  {"role":"librarian","status":"cancelled","latency_ms":NNN,"tokens_in":null,...}  x N
  {"role":"librarian","event":"batch_cancelled","items_total":N,...}

FastMCP: per MCP spec, does NOT send a response to the cancelled request ID.
```

### Recommended Project Structure (changes only)

```
cores/subagent-runtime/src/subagent_runtime/
├── pool.py                    # MODIFY: add _run_one CancelledError branch + _write_batch_terminal

agents/graph-wiki-agent/src/graph_wiki_mcp/
├── server.py                  # MODIFY: add repo_path field to WikiScanInput, wire to run_scan

agents/graph-wiki-agent/tests/integration/
├── test_mcp_stdio.py          # UNCHANGED (keep existing tests)
├── test_mcp_cancel.py         # NEW: cancel-mid-fan-out test (no INTEGRATION_GATE)
├── test_mcp_e2e.py            # NEW: 6-tool E2E test (INTEGRATION_GATE gated)

docs/
├── cancellation.md            # NEW: protocol + chain + trace + caveats + future work
```

### Pattern 1: FastMCP Cancel Chain (mcp 1.27.x)

**What:** `BaseSession` tracks all in-flight requests in `_in_flight: dict[RequestId, RequestResponder]`. On receiving `CancelledNotification`, it calls `await self._in_flight[cancelled_id].cancel()`. `RequestResponder.cancel()` cancels the anyio `CancelScope` that wraps the async tool handler. This surfaces as `asyncio.CancelledError` inside the handler at whatever `await` point is currently suspended.

**Confirmed mechanism** [VERIFIED: mcp sdk source via WebFetch]:
```python
# Inside mcp.shared.session.BaseSession (pseudocode — actual is in session.py)
if isinstance(notification, CancelledNotification):
    cancelled_id = notification.params.request_id
    if cancelled_id in self._in_flight:
        await self._in_flight[cancelled_id].cancel()
```

**Key facts:**
- `notifications/cancelled` is a notification (no `id` field), so no response is required or sent.
- The MCP spec says receivers SHOULD stop processing and NOT send a response for the cancelled request. [CITED: modelcontextprotocol.io/specification/2025-03-26/basic/utilities/cancellation]
- FastMCP uses anyio (not bare asyncio), so the cancellation goes through anyio's cancel scope machinery before becoming `asyncio.CancelledError`.

### Pattern 2: `asyncio.gather(return_exceptions=True)` + Outer Cancel

**What:** When the enclosing asyncio task is cancelled while inside `asyncio.gather(..., return_exceptions=True)`, the gather itself propagates `CancelledError` to the task. The `return_exceptions=True` flag only suppresses exceptions from the *inner* tasks — it does NOT protect the outer task from being cancelled.

**Verified empirically** [VERIFIED: codebase — ran live test]:
```python
# Proof: all 3 inner tasks received CancelledError, outer got CancelledError
async def outer():
    tasks = [asyncio.ensure_future(task_that_hangs()) for _ in range(3)]
    result = await asyncio.gather(*tasks, return_exceptions=True)  # outer cancel propagates through

outer_task = asyncio.ensure_future(outer())
await asyncio.sleep(0.01)
outer_task.cancel()  # -> inner tasks: CancelledError; outer: CancelledError
```

**Implication for `pool.py`:** `_run_one` must catch `CancelledError` specifically (not just `Exception`, which the current code uses) to write the per-item cancelled trace, then re-raise so the outer cancel propagates. `run_all` must catch the propagating `CancelledError` from `gather` to write the batch terminal record, then re-raise.

### Pattern 3: `ChatBedrockConverse` Async Internals (Orphan Thread)

**What:** `ChatBedrockConverse` does NOT override `_agenerate`. It inherits `BaseChatModel._agenerate`, which calls:

```python
# Source: langchain_core.language_models.chat_models.BaseChatModel._agenerate
# [VERIFIED: codebase inspection via uv run python]
return await run_in_executor(
    None,
    self._generate,
    messages, stop, run_manager, **kwargs,
)
```

`run_in_executor` (from `langchain_core.runnables.config`) calls:
```python
# [VERIFIED: codebase inspection]
return await asyncio.get_running_loop().run_in_executor(
    None,  # None = default ThreadPoolExecutor
    partial(copy_context().run, wrapper),
)
```

This puts `ChatBedrockConverse._generate` (which calls `self.client.converse(...)`) in a **default ThreadPoolExecutor daemon thread**. When the asyncio task is cancelled, `run_in_executor` raises `CancelledError` in the asyncio task, but **the thread continues executing until boto3 gets the HTTP response**. The thread's result is then discarded.

**Orphan thread caveat for `docs/cancellation.md`:**
- "Clean cancel" in v1.1 means: asyncio task unwinds + trace record written. The boto3 thread running the HTTPS call to Bedrock completes in the background and its result is silently dropped.
- boto3's `botocore.endpoint` does not expose a socket-close API. Interrupting the HTTP call at the wire level requires `aioboto3` (deferred to v1.2+).
- This is a "fire-and-forget discard" — no data loss or corruption, just a wasted Bedrock call.

### Pattern 4: Monkeypatch Strategy for Cancel Test

**What:** Patch `model_adapter.loader.make_llm` to return a slow stub. The stub must:
1. `await asyncio.sleep(N)` where N is 2-3 seconds (so the cancel arrives before completion)
2. Return a canned `AIMessage` if not cancelled (to keep `_run_one` happy on the success path)
3. Have `usage_metadata` attribute set to `None` or a canned dict (for `_write_trace` guards)

**Exact import path** [VERIFIED: codebase]:
```
model_adapter.loader.make_llm
```

**Monkeypatch target** (in `test_mcp_cancel.py`): The cancel test launches `graph-wiki-mcp` as a subprocess, so in-process `monkeypatch` does NOT work. The slow model must be injected via **environment variable** or a **custom `models.toml`** file that sets `max_tokens = 1` on all roles, plus the subprocess must be launched with a patched `GRAPH_WIKI_CONFIG` pointing to a minimal models.toml where all role `model_id`s point to a fast stub model.

**CRITICAL INSIGHT:** Since the cancel test uses a subprocess, standard pytest `monkeypatch` does NOT reach into the subprocess. The mechanism must be:
- Write a custom `models.toml`-like config to a `tmp_path` file
- Pass `GRAPH_WIKI_CONFIG=<path>` as an environment variable to `subprocess.Popen`
- OR patch at a different layer (e.g., replace `make_llm` with a module loaded from an env-pointed conftest)

However, D-09 says "monkeypatch `ChatBedrockConverse` via `model_adapter.factory.make_chat_model`". The factory in code is `model_adapter.loader.make_llm` (there is no `factory.py` or `make_chat_model`; D-09 has a slightly wrong path). The actual function is `make_llm` in `model_adapter.loader`.

**Since the cancel test uses a subprocess**, the cleanest mechanism is to set `max_tokens` very small and use a real test vault with real Bedrock but an immediately-expiring model — but D-10 says "no Bedrock cost on cancel test." This is a contradiction that the planner must resolve. The options are:

1. **Option A (recommended):** Rather than a subprocess-launched server, drive the cancel test via **in-process FastMCP** (not subprocess) — start the FastMCP ASGI app in-process and send cancel notifications over an in-memory transport. This allows `monkeypatch` to work.

2. **Option B:** Inject a fake via `GRAPH_WIKI_CONFIG` pointing to a custom `.toml` that references a real (but tiny) bedrock call, gated under `GRAPH_WIKI_RUN_INTEGRATION` — but D-10 says cancel test does NOT require this gate.

3. **Option C:** Write a small Python helper script that patches `make_llm` and then runs as a FastMCP server, invoked by the subprocess instead of the real `graph-wiki-mcp` entry point.

**Research recommendation:** Option A (in-process FastMCP) using `anyio.from_thread` or a `MemoryTransport`-style approach is the cleanest. The mcp SDK supports in-process testing without subprocess; the existing `test_mcp_stdio.py` chose subprocess for its subprocess-correctness benefit (real `_StdoutGuard` etc.) which is less critical for the cancel test. Alternatively, the planner may decide that the cancel test bypasses the subprocess and directly calls `run_query` with the stub model, skipping the MCP protocol layer for the cancel assertion — the FastMCP cancel chain is confirmed by unit testing the mcp SDK separately.

**Simpler alternative:** The cancel test can bypass the subprocess and use a direct asyncio test:
```python
# test_mcp_cancel.py — direct asyncio approach (no subprocess needed for cancel test)
async def test_cancel_mid_fan_out(tmp_path, monkeypatch):
    # 1. monkeypatch model_adapter.loader.make_llm to return slow stub
    # 2. call run_query(...) directly as an asyncio task
    # 3. cancel the task after observing it is in-flight
    # 4. assert CancelledError propagates and trace file has cancelled records
```

This approach tests the cancel chain (pool.py, _write_trace, batch_cancelled) without testing the MCP protocol framing. The MCP protocol framing (notifications/cancelled → anyio CancelScope → asyncio task) is validated by the FastMCP SDK itself. **This is the recommended approach for the cancel test.**

### Pattern 5: `report_progress` Timing for Race Control

**Status of progress calls per tool** [VERIFIED: server.py]:

| Tool | First `report_progress` call | When it fires |
|------|------------------------------|---------------|
| `wiki_query` | `progress=0, total=top_k, "Starting hybrid search"` | Immediately, before `run_query` (BEFORE any Bedrock call) |
| `wiki_scan` | `progress=0, total=2, "Starting scan"` | Immediately, before `run_scan` |
| `wiki_ingest` | `progress=0, total=2, "Starting ingest"` | Immediately, before `run_ingest_*` |
| `wiki_lint` | `progress=0, total=2, "Starting lint"` | Immediately, before `run_lint` |
| `wiki_log` | None | No `report_progress` call |
| `wiki_init` | None | No `report_progress` call |

**Finding:** `wiki_log` and `wiki_init` do NOT call `report_progress`. For the cancel test (which targets `wiki_query`), the first `report_progress` fires immediately (before any `await`) — it is the very first line of the handler. The cancel test can observe the `notifications/progress` JSON-RPC notification in stdout, confirming the tool is in-flight, then send `notifications/cancelled`.

**Implication for the direct-asyncio cancel test:** If using the direct approach (not subprocess), `report_progress` is not observable. The race control strategy changes to: start the task, yield once with `await asyncio.sleep(0)` to let the gather start, then cancel. At 2-3s stub sleep, this is deterministic.

### Anti-Patterns to Avoid

- **Catching `BaseException` instead of `CancelledError` in `_run_one`:** The current `except Exception` in `_run_one` does NOT catch `CancelledError` (which inherits from `BaseException`, not `Exception` in Python 3.8+). This is correct behavior — `CancelledError` propagates out naturally. The new `cancelled` branch must be added as `except asyncio.CancelledError` BEFORE the existing `except Exception` handler.
- **Subprocess monkeypatching:** `pytest.monkeypatch` does not reach into child processes. Do NOT attempt to inject a stub model into a subprocess-launched server.
- **Swallowing the outer CancelledError in `run_all`:** After writing the batch terminal record, `run_all` MUST re-raise `CancelledError` so the FastMCP tool handler's `CancelledError` propagates back to the anyio scope (which is what FastMCP expects to see).
- **Writing to stdout in cancel cleanup:** Any log lines during cancel unwinding must go to `sys.stderr` (or via `logging`). The `_StdoutGuard` is still active; a stray `print()` in the cancel path corrupts the JSON-RPC stream.
- **Assuming `wiki_log` or `wiki_init` have `report_progress` calls:** They do not. The 6-tool E2E test cannot use progress-notification timing for these two tools.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP cancel reception | Custom notification router | `mcp.shared.session.BaseSession` (already wired in FastMCP) | Already handles `notifications/cancelled` → anyio CancelScope |
| Subprocess JSON-RPC framing | Custom JSON-RPC wire format | Copy `_run_server` / `_send_initialize` from `test_mcp_stdio.py` | Proven pattern; already handles encode/decode correctly |
| Async test coordination | `time.sleep` + race-prone sleeps | `asyncio.sleep(0)` yield + deterministic stub sleep time | Avoids flakiness without adding test deps |
| Thread-pool async wrap | Custom async wrapper for boto3 | `loop.run_in_executor(None, ...)` via langchain_core | This is what `BaseChatModel._agenerate` already does |

---

## Runtime State Inventory

This phase is not a rename/refactor/migration phase. Section omitted.

---

## Common Pitfalls

### Pitfall 1: `except Exception` does not catch `CancelledError`

**What goes wrong:** Adding the `cancelled` trace branch inside the existing `except Exception` block in `_run_one` fails silently — `asyncio.CancelledError` inherits from `BaseException`, not `Exception`, so it passes through the existing handler and no cancelled trace is written.

**Why it happens:** Python 3.8 changed `CancelledError` to inherit from `BaseException` (not `Exception`) specifically to prevent it from being caught by broad `except Exception` clauses.

**How to avoid:** Add `except asyncio.CancelledError as exc:` BEFORE `except Exception as exc:` in `_run_one`. After writing the trace, re-raise.

**Warning signs:** Cancel test shows no `status: cancelled` records in the JSONL trace; the batch terminal `event: batch_cancelled` record also does not appear.

### Pitfall 2: Subprocess monkeypatching does not work

**What goes wrong:** If the planner designs the cancel test as a subprocess-launched server and tries to inject a slow stub via in-process `monkeypatch`, the stub is applied to the test process, not the subprocess. The subprocess imports `model_adapter.loader` fresh and calls real Bedrock.

**Why it happens:** `subprocess.Popen` creates a new Python interpreter. `pytest.monkeypatch` only patches the current interpreter's module cache.

**How to avoid:** Use the direct-asyncio test approach (call `run_query` directly in the test process, patch `make_llm` via `monkeypatch`, cancel the asyncio task). Or use `GRAPH_WIKI_CONFIG` env var injection with a custom `models.toml` pointing to a real-but-cheap model (and gate under `GRAPH_WIKI_RUN_INTEGRATION`).

**Warning signs:** Cancel test actually calls Bedrock during what should be a no-Bedrock-cost run.

### Pitfall 3: `asyncio.gather(return_exceptions=True)` does not prevent outer cancel

**What goes wrong:** Assuming `return_exceptions=True` means "the gather absorbs ALL exceptions including CancelledError." This is wrong. `return_exceptions=True` only prevents inner task exceptions from propagating; it does NOT protect the outer task from being cancelled.

**Why it happens:** Misreading the Python docs. The flag controls what happens when an inner task raises; it has no effect on external cancellation of the gather coroutine.

**How to avoid:** The outer `run_all` must wrap `await asyncio.gather(...)` in a `try: ... except asyncio.CancelledError:` to write the batch terminal record.

**Warning signs:** `run_all` never writes the `event: batch_cancelled` record; the batch terminal entry is absent from the JSONL trace.

### Pitfall 4: `wiki_scan` in MCP server has no `repo_path` field

**What goes wrong:** The E2E test calls `wiki_scan` with `vault_path=str(tmp_path)` but scan still walks the deep-agents workspace because `resolve_wiki_and_repo` returns `repo_root=None` and `run_scan` falls back to `Path.cwd()`. Scan fans out over the entire monorepo, times out, and racks up Bedrock cost.

**Why it happens:** `WikiScanInput` in `server.py` only exposes `vault_path`, `no_file_map`, and `max_depth`. The `repo_path` override in `run_scan` is never passed through the MCP tool layer.

**How to avoid:** The planner must add `repo_path: str = Field("", description="...")` to `WikiScanInput` and pass `repo_path=Path(input.repo_path) if input.repo_path else None` to `run_scan(...)`. This is a required code change for the E2E test.

**Warning signs:** E2E scan call takes >30 seconds; errors mentioning the deep-agents monorepo packages appear in the scan output; cost spikes during test.

### Pitfall 5: FastMCP does not send a response to a cancelled request

**What goes wrong:** The cancel test harness waits for a response JSON-RPC line (with `"id": <requestId>`) after sending `notifications/cancelled`. No response ever arrives, and the test times out.

**Why it happens:** MCP spec §Cancellation says receivers SHOULD NOT send a response for the cancelled request. FastMCP complies.

**How to avoid:** After sending `notifications/cancelled`, the test harness should close stdin (or send a `shutdown` request) and assert that the server exits cleanly — NOT wait for a response with the original request ID. Alternatively, assert the trace file contents (requires the direct-asyncio approach, which is recommended).

**Warning signs:** 15s timeout in `proc.communicate()` is hit; test fails with `MCP server did not respond within 15s`.

### Pitfall 6: `boto3` import order and the `_StdoutGuard`

**What goes wrong:** If a cancel test path triggers logging to stdout (e.g., via a `print()` added for debugging), `_StdoutGuard` raises `RuntimeError`, which shows up as a confusing crash rather than a test failure.

**Why it happens:** `_StdoutGuard` is installed at module import time and cannot be bypassed.

**How to avoid:** All cancel-path logging must use `logging.warning(...)` (→ stderr). No `print()` anywhere in cancel-path code.

---

## Code Examples

### Q1: FastMCP `notifications/cancelled` wire format and server behavior

[VERIFIED: modelcontextprotocol.io/specification/2025-03-26/basic/utilities/cancellation]

```json
// Client sends (notification — no "id" field):
{
  "jsonrpc": "2.0",
  "method": "notifications/cancelled",
  "params": {
    "requestId": "123",
    "reason": "User requested cancellation"
  }
}

// Server: does NOT send a response to request "123"
// Server: stops processing, frees resources
```

### Q2: FastMCP internal cancel mechanism

[CITED: github.com/modelcontextprotocol/python-sdk — mcp/shared/session.py]

```python
# Inside BaseSession (pseudocode from source inspection)
_in_flight: dict[RequestId, RequestResponder] = {}

# On receiving CancelledNotification:
cancelled_id = notification.params.request_id
if cancelled_id in self._in_flight:
    await self._in_flight[cancelled_id].cancel()
    # cancel() cancels the anyio CancelScope wrapping the tool handler
    # -> asyncio.CancelledError appears at the tool handler's next await point
```

### Q3: `asyncio.gather(return_exceptions=True)` cancel behavior

[VERIFIED: codebase — live test]

```python
# Confirmed: outer task cancel propagates through gather even with return_exceptions=True
# Each inner task receives CancelledError; outer task receives CancelledError

async def _run_one(item):
    try:
        result = await some_slow_task(item)  # CancelledError raised here
        ...
    except asyncio.CancelledError:
        # Write per-item cancelled trace here
        _write_trace(..., status="cancelled", ...)
        raise  # MUST re-raise to propagate outer cancel

async def run_all(items, ...):
    try:
        raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)
    except asyncio.CancelledError:
        # Write batch terminal record here
        _write_batch_terminal(...)
        raise  # MUST re-raise so FastMCP's anyio scope sees the cancel
```

### Q4: `ChatBedrockConverse` async internals — confirmed execution path

[VERIFIED: codebase inspection via `uv run python`]

```python
# BaseChatModel._agenerate (inherited by ChatBedrockConverse — NOT overridden):
async def _agenerate(self, messages, stop, run_manager, **kwargs):
    return await run_in_executor(
        None,                           # None = default ThreadPoolExecutor
        self._generate,                 # sync boto3 call lives here
        messages, stop, run_manager, **kwargs
    )

# run_in_executor (langchain_core.runnables.config):
async def run_in_executor(executor_or_config, func, *args, **kwargs):
    return await asyncio.get_running_loop().run_in_executor(
        None,                           # default ThreadPoolExecutor
        partial(copy_context().run, wrapper)
    )
```

**Conclusion:** boto3's HTTP call runs in a **default ThreadPoolExecutor thread**. When the asyncio task is cancelled, `run_in_executor` raises `CancelledError` in the asyncio task. The thread continues until boto3 gets the HTTP response; the result is discarded. This is the "orphan thread" caveat. [ASSUMED: thread result is silently discarded — standard CPython behavior for run_in_executor on cancel]

### Q5: Fan-out entry point for the cancel test

[VERIFIED: codebase]

```
wiki_query (server.py)
  -> await run_query(query, vault_path, top_k)        [commands/query.py]
       -> await pool.run_all(
              items=top_pages,                         # list of page paths
              task=drill_page,                         # async closure: librarian_llm.ainvoke
              role="librarian",
              model_id=lib_cfg["model_id"],
              max_concurrency=lib_cfg["max_concurrency"],
          )
```

There is exactly ONE fan-out path through `wiki_query`. The cancel test should target this path: kick off `wiki_query` (or `run_query` directly in the recommended direct-asyncio approach), then cancel the task.

### Q6: Proposed `pool.py` diff shape

[ASSUMED — planner must verify exact line numbers against current source]

```python
async def _run_one(item: Any) -> tuple[Any, Any] | PerItemError:
    async with semaphore:
        t0 = time.monotonic()
        try:
            # ... existing task invocation ...
            result = await task(item)
            latency_ms = int((time.monotonic() - t0) * 1000)
            self._write_trace(trace_file, role, model_id, item, "success", latency_ms, result)
            return (item, result)
        except asyncio.CancelledError:                          # NEW — must be BEFORE Exception
            latency_ms = int((time.monotonic() - t0) * 1000)
            self._write_trace(
                trace_file, role, model_id, item, "cancelled", latency_ms, None
            )
            raise                                               # re-raise: outer cancel must propagate
        except Exception as exc:
            # ... existing error branch (unchanged) ...

# In run_all, wrap gather:
batch_t0 = time.monotonic()
items_completed = 0
items_cancelled = 0
try:
    raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)
    # ... existing result classification ...
except asyncio.CancelledError:                                  # NEW
    wall_ms = int((time.monotonic() - batch_t0) * 1000)
    self._write_batch_terminal(
        trace_file, role, model_id,
        items_total=len(items),
        items_completed=items_completed,
        items_cancelled=items_cancelled,  # NOTE: counting is tricky here — see below
        wall_clock_ms=wall_ms,
    )
    raise

def _write_batch_terminal(
    self, path, role, model_id, *,
    items_total, items_completed, items_cancelled, wall_clock_ms
) -> None:
    """Write the batch_cancelled summary record. Never raises."""
    record = {
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

**Counting note:** When `gather` raises `CancelledError`, the `raw` list is not returned. The planner should count items from the trace file (count lines with `status: cancelled` vs `status: success/error`) or track completions with a shared counter. Simplest approach: count ALL items as `items_cancelled` (conservative) since we don't know which completed before the cancel.

### Q7: `_write_trace` `cancelled` branch changes

[VERIFIED: codebase — current `_write_trace` logic]

The current `_write_trace` always computes `tokens_in`/`tokens_out` from `response.usage_metadata`. For `status: "cancelled"`, `response` is `None`, so the existing guard already handles this:

```python
# Current code already handles None response (no change needed in token extraction):
if response is not None and hasattr(response, "usage_metadata"):
    meta = response.usage_metadata
    ...
# tokens_in and tokens_out remain None when response is None
```

The only changes needed in `_write_trace` for the `cancelled` status branch:
1. No logic change in `_write_trace` itself — the existing None-guard covers it.
2. `_compute_cost_usd` with `tokens_in=None` already returns `None` (existing guard).
3. The `status` field in the record will be `"cancelled"` (a new valid value; additive to `"success"` and `"error"`).

**Conclusion:** `_write_trace` requires NO code changes. The only new code is in `_run_one` (catch `CancelledError` and call `_write_trace(..., "cancelled", ...)`) and in `run_all` (catch outer `CancelledError` and call `_write_batch_terminal`).

### Q8: `report_progress` timing for race control

[VERIFIED: server.py]

`wiki_query` emits `report_progress(progress=0, ...)` as its FIRST line, before `await run_query(...)`. This fires immediately (no Bedrock call needed) and produces a `notifications/progress` JSON-RPC notification on stdout.

For the **subprocess-based harness** (if used for cancel test), the test can:
1. Send `initialize` + `notifications/initialized` + `tools/call wiki_query {requestId: "X"}`
2. Read stdout lines until a `notifications/progress` line appears (confirming the tool is running)
3. Send `notifications/cancelled {requestId: "X"}`
4. Close stdin; collect remaining stdout; verify server exits cleanly

For the **direct-asyncio approach** (recommended), `report_progress` is not observable. Race control: `await asyncio.sleep(0)` to let the `gather` start, then cancel. With a 2-3s stub sleep, this is deterministic.

### Q9: 6-tool E2E seed-page content (recommended)

[ASSUMED — planner picks exact text; this is a starting proposal]

Seed for `tmp_path`:

```
tmp_path/wiki/                     # vault root (after wiki_init)
  .graph-wiki/
  index.md
  packages/
    alpha/
      alpha.md                     # frontmatter: title, page_type: package, tags: [alpha]
  concepts/
    architecture.md                # frontmatter: title, page_type: concept; body: [[alpha]]
  work/
    task-001.md                    # created by wiki_ingest work-item
tmp_path/raw/
  sample.py                        # source file ingested by wiki_ingest source

# 5 seed pages total:
# alpha.md — package overview (query target)
# architecture.md — concept linking to [[packages/alpha]]
# index.md — generated by wiki_init
# (task-001.md created by ingest step, not pre-seeded)
# (log.md written by wiki_log)
```

Sample query the E2E test can assert: `"What is alpha?"` should return an answer containing `"alpha"`.

### Q10: `docs/cancellation.md` structure

[VERIFIED: D-15 in CONTEXT.md]

```markdown
# MCP Cancellation in graph-wiki-agent

## 1. Protocol Behavior
- What `notifications/cancelled` is (MCP spec cite + wire format)
- Fire-and-forget; server does NOT send a response to the cancelled request
- Race condition handling: cancel may arrive after completion

## 2. Internal Cancellation Chain
- FastMCP → anyio CancelScope → asyncio.CancelledError at tool handler's next await
- wiki_query handler → run_query → SubagentPool.run_all → asyncio.gather
- Each _run_one catches CancelledError, writes cancelled trace, re-raises
- run_all catches outer CancelledError, writes batch_cancelled summary, re-raises
- FastMCP: anyio CancelScope exits cleanly; no response sent to client

## 3. Trace Shapes
- Per-item cancelled record example (JSON)
- Batch terminal batch_cancelled summary record example (JSON)
- Note: `event` field discriminates summary from per-item records

## 4. Known Limitations (v1.1)
- boto3 worker thread continues after asyncio task is cancelled
- The underlying HTTPS request to Bedrock completes in background; result discarded
- "Clean cancel" = asyncio unwind + trace written; wire-level interrupt not implemented
- Why: ChatBedrockConverse wraps sync boto3 via loop.run_in_executor(None, ...) — no socket-close API

## 5. Future Work (v1.2+)
- aioboto3 / aiobotocore for truly async Bedrock calls → wire-level cancel possible
- SIGINT and stdin-close cancel paths
- Orphan-thread monitoring / cleanup hooks
```

---

## 6-Tool E2E Test: CWD Discipline Detail

**Problem confirmed by code reading:** `WikiScanInput` in `server.py` has NO `repo_path` field. `run_scan` is called with only `vault_path`, `no_file_map`, and `max_depth`. Inside `run_scan`, when `repo_path` argument is `None` (as it currently always is from the MCP tool), it falls back to `Path.cwd()` as the scan root.

**Required planner action:**
1. Add `repo_path: str = Field("", description="Override repo root for scanner (default: resolved from vault_path). Use for testing.")` to `WikiScanInput`.
2. Modify `wiki_scan` handler to pass `repo_path=Path(input.repo_path).resolve() if input.repo_path else None` to `run_scan(...)`.
3. E2E test passes `"repo_path": str(tmp_path)` in the scan tool arguments.

**Behavior with `tmp_path` as repo root:** `discover_workspaces(tmp_path)` will find zero workspaces (no `pyproject.toml` etc. unless the seed adds one). Scan will produce `added=[], updated=[], deleted=[]` — this is a valid non-error outcome (DACLI-02 requires non-error, not specific counts). To get scan to actually produce output, the seed must include a minimal `pyproject.toml` at `tmp_path` level.

**Alternative:** Write a minimal `pyproject.toml` at `tmp_path` listing one fake package. `discover_workspaces` will find it, scanner fan-out will call Bedrock once (or use stub model — but this is the Bedrock-gated E2E test, so a real call is acceptable).

---

## Bedrock Cost Estimate for 6-Tool E2E Test

**Tools with Bedrock calls** (from code reading): `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`. `wiki_init` and `wiki_log` make no LLM calls.

**Model defaults** (from `models-qwen.toml`):
- Scanner: `qwen.qwen3-32b-v1:0` — $0.40/M in, $1.60/M out
- Ingestor: `qwen.qwen3-32b-v1:0`
- Librarian: `qwen.qwen3-next-80b-a3b` — **NOT in `eval_harness/pricing.py`** (gap — pricing unknown)
- Synthesizer: `qwen.qwen3-next-80b-a3b`
- Linter: `qwen.qwen3-32b-v1:0`

**Estimates for small-seed vault (3-5 pages, 1 source file):**

| Tool | Roles called | Approx tokens in | Approx tokens out | Est. cost |
|------|-------------|------------------|-------------------|-----------|
| `wiki_scan` | scanner × 1 stub | ~1000 in | ~500 out | ~$0.0002 |
| `wiki_ingest` (source) | ingestor × 1 | ~1500 in | ~800 out | ~$0.0019 |
| `wiki_query` | librarian × 3-5 + synthesizer × 1 | ~5000 in | ~2000 out | [ASSUMED: depends on Qwen3-80B pricing] |
| `wiki_lint` | linter × 1 (semantic lint, 5 pages) | ~2000 in | ~500 out | ~$0.0009 |
| **Total** | | | | **~$0.003–0.01 per run** [ASSUMED] |

**Note:** `qwen.qwen3-next-80b-a3b` pricing is not in `eval_harness/pricing.py`. The planner should add a pricing entry or accept that cost tracking for librarian/synthesizer calls will show `cost_usd=null` in traces during the E2E test. This is not a test failure condition; it's a known gap (TRACE-FU-01 from v1.2 backlog).

---

## Test File Layout Recommendation

**Two new files** (Claude's Discretion):

```
agents/graph-wiki-agent/tests/integration/
├── test_mcp_stdio.py       # UNCHANGED — existing 3 tests
├── test_mcp_cancel.py      # NEW: cancel-mid-fan-out (direct asyncio; no INTEGRATION_GATE)
├── test_mcp_e2e.py         # NEW: 6-tool sequential E2E (INTEGRATION_GATE)
```

**Rationale:**
- Keeping cancel and E2E separate makes it clear which test requires real Bedrock.
- `test_mcp_cancel.py` can be co-located with `test_mcp_stdio.py` without muddying the integration gate.
- The existing `test_mcp_stdio.py` file has grown to ~200 lines; adding 200+ more lines for cancel + E2E would make it unwieldy.
- Fixture sharing: both new files can import `INTEGRATION_GATE` from `conftest.py` (it's already defined there as well as in `test_mcp_stdio.py` — the conftest version is canonical).

**Test function layout:**

`test_mcp_cancel.py`:
```python
# No INTEGRATION_GATE (stub model, no Bedrock)
async def test_cancel_mid_fan_out(tmp_path, monkeypatch):
    # Patch make_llm to return slow stub
    # Build small vault in tmp_path
    # Run run_query as an asyncio task
    # Cancel after asyncio.sleep(0)
    # Assert: CancelledError propagated; trace has cancelled records + batch_cancelled
```

`test_mcp_e2e.py`:
```python
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run integration tests",
)

@INTEGRATION_GATE
def test_all_six_tools_end_to_end(tmp_path):
    # subprocess.Popen graph-wiki-mcp
    # wiki_init -> wiki_scan -> wiki_ingest -> wiki_query -> wiki_lint -> wiki_log
    # Assert non-error response for each
```

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 + pytest-asyncio 1.3.0 |
| Config | `asyncio_mode = "auto"` (in `agents/graph-wiki-agent/pyproject.toml`) |
| Quick run | `uv run --package graph-wiki-agent pytest tests/integration/test_mcp_cancel.py -x` |
| Integration run | `GRAPH_WIKI_RUN_INTEGRATION=1 uv run --package graph-wiki-agent pytest tests/integration/test_mcp_e2e.py -x` |
| Full suite | `uv run --package graph-wiki-agent pytest -x` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MCP-09 | Cancel behavior documented | manual/doc | — | No — `docs/cancellation.md` is written by executor |
| MCP-10 | In-flight SubagentPool tasks write `cancelled` trace records; `batch_cancelled` summary written | unit (direct asyncio) | `pytest tests/integration/test_mcp_cancel.py -x` | No — Wave 0 |
| MCP-11 | Cancel test gate consistent with v1.0 pattern (no gate for stub test) | unit | `pytest tests/integration/test_mcp_cancel.py -x` | No — Wave 0 |
| DACLI-01 | E2E test launches `graph-wiki-mcp` subprocess | integration | `GRAPH_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_mcp_e2e.py -x` | No — Wave 0 |
| DACLI-02 | All 6 tools exercised, non-error outcomes | integration | same | No — Wave 0 |
| DACLI-03 | `GRAPH_WIKI_RUN_INTEGRATION=1` gate | integration | same | No — Wave 0 |

### Signal Sources (for cancel test)

| Signal | How to observe |
|--------|---------------|
| FastMCP cancel chain | anyio CancelScope → asyncio.CancelledError propagation (not directly observable — rely on cancel test calling `run_query` directly with stub model) |
| Trace JSONL | Assert trace file has ≥1 line with `status: cancelled`, then one line with `event: batch_cancelled` |
| No orphan asyncio tasks | `asyncio.all_tasks()` after await is clean (optionally assert in cancel test) |
| No orphan threads | Not asserted in automated cancel test (documented caveat; orphan threads are expected) |

### Invariants

1. `_write_trace` never raises — OSError logged at WARNING, no exception propagates to `_run_one`.
2. `_write_batch_terminal` never raises — same contract.
3. After outer cancel, `run_all` always re-raises `CancelledError` (FastMCP depends on this).
4. Per-item `cancelled` records are written BEFORE the re-raise in `_run_one` (ordering invariant for atomic trace writes).
5. The `event: batch_cancelled` record is the final record in the trace file when a cancel occurs.

### Sampling Rate

- **Per task commit:** `pytest tests/integration/test_mcp_cancel.py -x` (fast, no Bedrock)
- **Per wave merge:** Full suite excluding integration gate: `pytest agents/graph-wiki-agent/tests/ -x`
- **Phase gate:** `GRAPH_WIKI_RUN_INTEGRATION=1 pytest agents/graph-wiki-agent/tests/ -x` before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/integration/test_mcp_cancel.py` — covers MCP-10, MCP-11
- [ ] `tests/integration/test_mcp_e2e.py` — covers DACLI-01, DACLI-02, DACLI-03

*(Existing test infrastructure is present; only new files needed.)*

---

## Security Domain

This phase adds no new user-facing input surfaces, no new credentials handling, and no new network endpoints. The subprocess harness is test-only. No ASVS categories apply beyond what Phase 1–5 already covered. Security enforcement: pass-through (no new vectors introduced).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `uv` | Subprocess spawn of `graph-wiki-mcp` in E2E test | ✓ | 0.11.14+ | None — tests skip if not found |
| Python 3.11 | All tests | ✓ | 3.11.x | None |
| AWS credentials | `GRAPH_WIKI_RUN_INTEGRATION=1` tests only | [ASSUMED: present from Phase 7 sweep] | — | Tests skip without gate |
| `graph-wiki-mcp` entry point | E2E subprocess | ✓ | From `pyproject.toml` console_scripts | None |

---

## Open Questions (RESOLVED)

1. **Counting cancelled items in `run_all`**
   - What we know: When `gather` raises `CancelledError`, the `raw` list is not returned. The exact count of items that completed vs. were cancelled before the outer cancel is not trivially available.
   - What's unclear: Whether to track counts via a `threading.local` counter inside `_run_one` or simply report `items_cancelled = len(items)` (conservative upper bound).
   - Recommendation: Use `items_cancelled = len(items)` as the upper bound in the batch terminal record. Phase 9 (trace renderer) can compute accurate counts by reading per-item records from the trace file.

2. **`qwen.qwen3-next-80b-a3b` pricing entry**
   - What we know: This model is the default librarian/synthesizer in `models-qwen.toml`. It is NOT in `eval_harness/pricing.py`. The E2E test's librarian/synthesizer calls will produce `cost_usd=null` in traces.
   - What's unclear: AWS pricing for this model.
   - Recommendation: The planner should add a placeholder pricing entry (e.g., `0.50/M in, `2.00/M out`) or document as a known gap. This is not a blocker for Phase 8.

3. **`wiki_log` and `wiki_init` lack `report_progress` calls**
   - What we know: These two tools have no `report_progress` calls (confirmed in server.py).
   - What's unclear: Whether this is intentional or an oversight.
   - Recommendation: Leave as-is for Phase 8 (out of scope). Note in `docs/cancellation.md` that cancel for these tools takes effect immediately at the tool handler entry point (no fan-out to cancel).

4. **cancel test approach: direct-asyncio vs subprocess**
   - What we know: Subprocess monkeypatching does not work. Direct asyncio avoids the problem. D-09 says "monkeypatch `ChatBedrockConverse` via `make_chat_model`" — this implies in-process, suggesting the intent is a direct asyncio test.
   - What's unclear: Whether CONTEXT.md's D-01 constraint (subprocess-based host) applies to the cancel test or only the E2E test.
   - Recommendation: Use direct asyncio for the cancel test (monkeypatch `make_llm`, call `run_query` directly). Use subprocess for the 6-tool E2E test. This is consistent with D-10 ("cancel test runs unconditionally" — i.e., no subprocess-launch overhead) and D-14 (sequential sub-assertions, which implies the E2E test owns the subprocess).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `loop.run_in_executor` thread result is silently discarded when asyncio task is cancelled | Code Examples §Q4 | If CPython recycles the thread result back to the task post-cancel, the cancellation semantics could be different — low risk, this is standard CPython behavior |
| A2 | `qwen.qwen3-next-80b-a3b` Bedrock pricing is approximately $0.50-2.00/M tokens | Cost estimate | If significantly higher, E2E test costs more than estimated — impact: low (manual test, not CI) |
| A3 | `discover_workspaces(tmp_path)` with a minimal `pyproject.toml` will produce ≥1 workspace for scan | Pitfall 4 + Q12 | If discover_workspaces requires additional workspace markers, scan returns 0 items — acceptable (non-error) |
| A4 | Direct asyncio test approach for cancel test is what D-09 intends by "monkeypatch `make_chat_model`" | Q4 + Open Questions | If planner interprets D-09 as requiring subprocess, the cancel test design changes substantially |

---

## Sources

### Primary (HIGH confidence)
- MCP Cancellation spec — `modelcontextprotocol.io/specification/2025-03-26/basic/utilities/cancellation` — wire format, behavior requirements, timing considerations
- `mcp/shared/session.py` (mcp 1.27.x source) — `_in_flight` dict, `RequestResponder.cancel()`, anyio CancelScope mechanism
- `langchain_core.language_models.chat_models.BaseChatModel._agenerate` — `run_in_executor(None, self._generate, ...)` — confirmed via live `uv run python`
- `langchain_core.runnables.config.run_in_executor` — `asyncio.get_running_loop().run_in_executor(None, ...)` — confirmed via live `uv run python`
- `asyncio.gather(return_exceptions=True)` outer cancel behavior — confirmed via live asyncio test run
- Codebase: `server.py`, `pool.py`, `query.py`, `scan.py`, `loader.py`, `test_mcp_stdio.py`, `conftest.py` — all read directly

### Secondary (MEDIUM confidence)
- WebFetch of `mcp/shared/session.py` via GitHub — cancellation mechanism pseudocode (mcp BaseSession implementation)

### Tertiary (LOW confidence / ASSUMED)
- `qwen.qwen3-next-80b-a3b` pricing estimate — training knowledge, not verified against AWS pricing page
- Boto3 thread result discard behavior on asyncio cancel — well-known CPython behavior, not re-verified in this session

---

## Metadata

**Confidence breakdown:**
- FastMCP cancel chain: HIGH — source code confirmed
- `asyncio.gather` + cancel semantics: HIGH — verified empirically
- `ChatBedrockConverse` async internals: HIGH — source code confirmed via `uv run python`
- `pool.py` diff shape: MEDIUM — proposed based on code reading; exact line numbers are planner's job
- E2E test `wiki_scan` gap (no `repo_path`): HIGH — confirmed by reading `server.py` and `scan.py`
- Bedrock cost estimate: LOW — Qwen3-80B pricing unknown

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (mcp SDK and langchain-aws are actively developed; re-verify if major versions change)
