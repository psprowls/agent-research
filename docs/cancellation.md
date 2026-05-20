# MCP Cancellation in code-wiki-agent

This document describes what happens when a spec-conformant MCP host sends
`notifications/cancelled` to `code-wiki-mcp` while a fan-out tool call is in flight.
It covers the protocol, the internal unwinding chain, the exact trace record shapes
emitted by `SubagentPool`, the known orphan-thread limitation in v1.1, and the
v1.2+ paths that will close that gap.

**v1.1 scope:** `notifications/cancelled` mid-fan-out is supported. SIGINT and
stdin-close fallback cancel paths are deferred to v1.2+.

---

## 1. Protocol Behavior

`notifications/cancelled` is an MCP notification (no `id` field) that a client sends
to ask the server to abandon a previously issued request. The wire format is:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/cancelled",
  "params": {
    "requestId": "123",
    "reason": "User requested cancellation"
  }
}
```

The `reason` field is optional. The `requestId` must match the `id` of an outstanding
`tools/call` (or other) request.

**Server behavior per spec:** the server stops processing the targeted request and
does NOT send a response for that request ID. Sending a response would violate the
MCP specification.

**Race condition handling:** a `notifications/cancelled` notification MAY arrive after
the request has already completed and its response has been sent. Receivers SHOULD
tolerate this silently — the notification is a best-effort hint, not a guaranteed
interrupt.

Spec: `modelcontextprotocol.io/specification/2025-03-26/basic/utilities/cancellation`

---

## 2. Internal Cancellation Chain

When `notifications/cancelled` arrives for an in-flight `wiki_query` call, the
propagation path is:

```text
MCP host sends: {"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId":"X"}}

  mcp.shared.session.BaseSession
    _in_flight["X"].cancel()           # cancels the anyio CancelScope wrapping the handler
    |
    v
  wiki_query handler (server.py)
    asyncio.CancelledError raised at:  await run_query(...)
    |
    v
  run_query (commands/query.py)
    asyncio.CancelledError raised at:  await pool.run_all(...)
    |
    v
  SubagentPool.run_all (pool.py)
    asyncio.CancelledError raised at:  await asyncio.gather(...)
    |
    +-> _run_one(page_1): CancelledError -> _write_trace(..."cancelled"...) -> re-raise
    +-> _run_one(page_2): CancelledError -> _write_trace(..."cancelled"...) -> re-raise
    +-> _run_one(page_N): CancelledError -> _write_trace(..."cancelled"...) -> re-raise
    |
    v
  run_all except asyncio.CancelledError:
    _write_batch_terminal(event="batch_cancelled")
    raise                              # MUST re-raise so FastMCP anyio scope exits cleanly

  FastMCP: anyio CancelScope exits. No response sent to request "X".
```

**Important:** `asyncio.gather(return_exceptions=True)` does NOT swallow an outer
cancel. The `return_exceptions=True` flag only suppresses exceptions raised by *inner*
tasks — it has no effect on cancellation of the enclosing task. When the tool handler's
asyncio task is cancelled, the outer `gather` raises `asyncio.CancelledError` and each
`_run_one` inner task also receives `CancelledError`.

`_run_one` catches `asyncio.CancelledError` specifically (before the existing
`except Exception` handler) because `CancelledError` inherits from `BaseException`,
not `Exception`, in Python 3.8+. After writing the per-item trace it re-raises, which
propagates the outer cancel correctly.

---

## 3. Trace Shapes

See [`docs/trace-schema.md`](./trace-schema.md) for the authoritative field tables and per-record schema; the JSON blocks in this section remain inline for illustration only.

`SubagentPool` writes two kinds of records when a fan-out is cancelled.

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

**Batch terminal summary record** — exactly one per cancelled fan-out, written by
`run_all` after `gather` raises:

```json
{
  "role": "librarian",
  "model_id": "qwen.qwen3-next-80b-a3b",
  "event": "batch_cancelled",
  "items_total": 5,
  "items_completed": 0,
  "items_cancelled": 5,
  "wall_clock_ms": 1243,
  "timestamp": "2026-05-17T14:23:01Z"
}
```

**Discriminator:** the presence of the `event` field distinguishes the batch terminal
summary from per-item records. Per-item records (success, error, cancelled) never carry
an `event` key. Phase 9 trace renderer branches on `event` presence.

**Field semantics on cancelled records:**
- `tokens_in`, `tokens_out`, `cost_usd` are `null` — the Bedrock response was discarded
  before usage metadata could be read.
- `latency_ms` reflects the wall-clock time from task start to `CancelledError` receipt
  (not the full Bedrock round-trip time, which may still be in progress in the thread).
- `items_completed` in the batch terminal record uses a conservative count of `0` when
  no items completed before the cancel arrived. `items_cancelled` is set to
  `items_total` as an upper bound. Phase 9 can compute accurate per-status counts by
  reading per-item records.

**Ordering invariant:** the `event: batch_cancelled` record is the LAST line written
to the trace file when a cancel occurs. Per-item `cancelled` records are written inside
each `_run_one` before the re-raise; the batch terminal record is written in `run_all`'s
catch block after all `_run_one` tasks have raised.

---

## 4. Known Limitations (v1.1 — re-confirmed 2026-05-19 in Phase 16 spike)

Cancellation is best-effort at the asyncio layer, not at the wire layer.
The Phase 16 spike re-checked both upstream channels on 2026-05-19:

- **`langchain-aws` 1.4.6** (current as of Phase 16, per CLAUDE.md §3) does NOT
  include the merged form of PR #663 (the upstream issue that would expose a
  cancel-aware code path on `ChatBedrockConverse`). Source:
  <https://github.com/langchain-ai/langchain-aws/pull/663>.
- **`aioboto3`** has not reached a named GA / 1.0 milestone. The dependency is
  still excluded from the workspace; CLAUDE.md §3 documents:
  "`ChatBedrockConverse` async is pseudo-async — `astream()`/`ainvoke()` wrap
  sync boto3; no aioboto3 dependency available yet." Source:
  <https://pypi.org/project/aioboto3/>.

Neither path qualifies as a "working integration path" today, so Phase 16
re-defers the wire-level cancel work. The asyncio-layer behavior described
below is unchanged from v1.1.

`ChatBedrockConverse` does not override `_agenerate`. It inherits
`BaseChatModel._agenerate` from `langchain-core`, which calls:

```python
return await run_in_executor(
    None,               # None = default ThreadPoolExecutor
    self._generate,     # sync boto3 call lives here
    messages, stop, run_manager, **kwargs
)
```

`run_in_executor` dispatches `self._generate` (which calls `botocore` → HTTPS to
Bedrock) to a **default ThreadPoolExecutor daemon thread**. When the asyncio task is
cancelled, `run_in_executor` raises `CancelledError` in the asyncio task — but the
thread keeps running until boto3 receives the full HTTPS response from Bedrock. The
thread's result is then silently discarded by CPython (standard `run_in_executor`
behavior on cancel).

**Why the thread cannot be interrupted:** `botocore.endpoint` does not expose a
socket-close API. Interrupting the HTTP call at the wire layer requires an
async-native AWS client (`aioboto3` / `aiobotocore`), which is deferred to v1.2+.

**Operational meaning of "clean cancel" in v1.1:**
- The asyncio task unwinds immediately.
- The per-item `status: cancelled` trace record is written.
- The `event: batch_cancelled` summary record is written.
- The Bedrock HTTPS request completes in the background thread.
- The response is discarded — no data loss, no corruption, but the Bedrock call cost
  is incurred for the wasted invocation.

**Tools without fan-out:** `wiki_log` and `wiki_bootstrap` have no `report_progress` calls
and no `SubagentPool` fan-out. For these tools, cancellation takes effect immediately
at the handler entry point — there is no boto3 worker thread to orphan.

---

## 5. Future Work

**Re-evaluation trigger (event-driven, not date-driven — Phase 16 D-09):**
Re-evaluate the wire-level cancel work when langchain-aws cuts a release with #663 merged, OR when aioboto3 reaches a named milestone (GA / 1.0). Pat tracks upstream; whichever lands first re-opens the cancel work. Do NOT re-attempt on a calendar cadence — calendar-driven re-checks generated noise in v1.1 → v1.2 carry-forward without changing the gate outcome.

- **`aioboto3` / `aiobotocore`** — replace the sync `boto3` client with an async-native
  AWS client, making wire-level cancel possible by dropping the HTTPS request at the
  socket layer. This eliminates the orphan-thread cost.
- **SIGINT and stdin-close fallback cancel paths** — protocol-correct
  `notifications/cancelled` is the v1.1 gate. Rough-cancel paths (Ctrl-C from a
  terminal host, stdin EOF) remain deferred until the orphan-thread cost proves
  significant in operation.
- **Orphan-thread monitoring / cleanup hooks** — optionally surface the count of
  in-flight orphan threads via a debug trace field or a dedicated endpoint, so
  operators can observe wasted-call frequency.
- **Per-tool granular E2E cancel tests** — if behavioral nuances emerge
  (e.g., partial-batch cancel, cancel during `wiki_scan` fan-out), expand beyond the
  single `wiki_query` cancel test.

---

*Source: Phase 8 (Host Reliability) — see .planning/phases/08-host-reliability/08-CONTEXT.md and 08-RESEARCH.md for the design record.*
