# Phase 8: Host Reliability - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove `graph-wiki-mcp` behaves correctly under a real stdio MCP host: (a) when the host sends `notifications/cancelled` mid-fan-out, in-flight `SubagentPool` tasks unwind cleanly and traces close with a `cancelled` terminal event; (b) a single integration test launches `graph-wiki-mcp` as a subprocess and exercises all six shipped tools (`wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log`) end-to-end. Both tracks gate behind `GRAPH_WIKI_RUN_INTEGRATION=1` consistent with v1.0 integration tests.

**In scope:**
- Reproduce the cancel-mid-fan-out scenario at the MCP transport boundary via a hand-built spec-conformant MCP host (extension of the Phase 3 `test_mcp_stdio.py` pattern) — same protocol surface DeepAgents CLI implements (MCP-09).
- Wire `notifications/cancelled` through FastMCP into `SubagentPool.run_all` so in-flight tasks see `asyncio.CancelledError`; surface the orphan-thread caveat from `ChatBedrockConverse`'s sync-wrap-in-async (MCP-10).
- Extend `_write_trace` in `cores/subagent-runtime/src/subagent_runtime/pool.py` to emit two new trace shapes: per-item `status: cancelled` records for tasks interrupted in flight, plus one batch terminal `event: batch_cancelled` summary record (MCP-10).
- Automated cancel-mid-fan-out test under `GRAPH_WIKI_RUN_INTEGRATION=1` driving cancel via JSON-RPC `notifications/cancelled`; uses a monkeypatched slow model (no real Bedrock cost on the cancel test) for deterministic timing (MCP-11).
- A single end-to-end integration test launching `graph-wiki-mcp` as a stdio subprocess and exercising all six tools against a fresh `tmp_path` vault seeded inline; non-error assertions for each (DACLI-01, DACLI-02, DACLI-03).
- A short `docs/cancellation.md` at the repo root documenting what `notifications/cancelled` triggers, the unwinding chain, the orphan-thread caveat, and what "clean" means in v1.1 (MCP-09 "current behavior documented").

**Out of scope (explicit):**
- Replacing `boto3` with an async-native AWS client / `aioboto3` (would actually interrupt the HTTP call mid-flight) — too invasive for v1.1.
- Real `deepagents` CLI binary as the test host — the synthesized spec-conformant host is equivalent at the protocol layer and avoids version-drift fragility.
- Adding SIGINT / stdin-close fallback cancel tests — protocol-correct `notifications/cancelled` is the v1.1 gate; rough-cancel paths can land in v1.2 if needed.
- Trace schema versioning / renderer enhancements (Phase 9 owns OBS-04/05/06; this phase only extends the JSONL shape additively).
- Cost-frontier sweep, prompt-content port (Phases 6 & 7, both complete).
- OSS release prep (deferred past v1.1).

</domain>

<decisions>
## Implementation Decisions

### Host harness
- **D-01:** **Hand-built spec-conformant MCP host** extending the Phase 3 pattern in `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py`. Both the cancel test and the 6-tool test launch `graph-wiki-mcp` via `subprocess.Popen(["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-mcp"])` and drive JSON-RPC over stdin/stdout. No new test-time deps (no real `deepagents` CLI, no `langchain-mcp-adapters` consumer path).
- **D-02:** Framing throughout planning/docs: "spec-conformant MCP host — same protocol surface DeepAgents CLI uses." Avoid claiming the test *is* the DeepAgents CLI; claim parity at the protocol boundary.

### Cancel-induction mechanism
- **D-03:** **MCP protocol `notifications/cancelled`** is the cancel signal: client sends `{"jsonrpc":"2.0","method":"notifications/cancelled","params":{"requestId": <id>}}` after kicking off a fan-out tool call but before it completes. SIGINT/stdin-close paths are deferred (see Out of scope).
- **D-04:** Cancel propagation chain to verify in research: FastMCP receives the notification → cancels the asyncio task running the tool handler → handler's `await` on `run_query`/`SubagentPool.run_all` raises `asyncio.CancelledError` → `asyncio.gather(..., return_exceptions=True)` does NOT swallow CancelledError of the gather itself; it propagates to each `_run_one` → each `_run_one` raises `CancelledError`, writes its per-item `cancelled` trace, returns control.
- **D-05:** **Orphan-call caveat (must be surfaced in `docs/cancellation.md`):** `ChatBedrockConverse` wraps sync boto3 in a worker thread (`asyncio.to_thread`-style); the underlying HTTPS request to Bedrock cannot be interrupted mid-flight without dropping the connection at the socket layer (which boto3 does not expose cleanly). v1.1 "clean cancel" means the asyncio task unwinds and the trace record is written; the boto3 thread completes its HTTP call in the background and its result is discarded. This is best-effort — true wire-level cancel is a v1.2+ concern (would need `aioboto3` or socket-close).

### Trace `cancelled` event shape
- **D-06:** **Two-layer trace cancellation.** Schema is purely additive — existing readers ignore unknown fields.
  - **Per-item record** for each `_run_one` that received `asyncio.CancelledError`:
    ```json
    {"role": "...", "model_id": "...", "item_id": "...", "status": "cancelled",
     "latency_ms": <t0_to_cancel_receipt>, "tokens_in": null, "tokens_out": null,
     "cost_usd": null, "timestamp": "..."}
    ```
  - **Batch terminal summary record** written once by `run_all` when CancelledError propagates out of `gather`:
    ```json
    {"role": "...", "model_id": "...", "event": "batch_cancelled",
     "items_total": N, "items_completed": K_success + K_error, "items_cancelled": M,
     "wall_clock_ms": <t0_to_cancel_complete>, "timestamp": "..."}
    ```
- **D-07:** **`event` field is the discriminator.** Per-item records keep their current shape (no `event` key) so existing readers (Phase 2 trace renderer) continue to work. The terminal summary line is the only record carrying `event: batch_cancelled`; new readers in Phase 9 can branch on `event` presence.
- **D-08:** `_write_trace` in `cores/subagent-runtime/src/subagent_runtime/pool.py` gains a `status: "cancelled"` branch (tokens null, cost null). A new internal helper `_write_batch_terminal` writes the summary line. Both keep the existing "never raises — OSError logged at WARNING" contract (AI-SPEC Failure Mode #2).

### Slow-model strategy for cancel test
- **D-09:** **Monkeypatch `ChatBedrockConverse` via `model_adapter.factory.make_chat_model`** to return a fake that `await asyncio.sleep(N)` and returns a canned `AIMessage` with synthesized `usage_metadata`. `N` set to ~2–3s so the cancel notification can be sent reliably after the fan-out is in flight and before any task naturally completes. Cancel test runs deterministically without Bedrock cost.
- **D-10:** **The cancel test runs unconditionally** (not gated on `GRAPH_WIKI_RUN_INTEGRATION=1`) because it uses the stub — same pattern as the existing JSON-RPC stdout test (`test_mcp_stdout_is_valid_jsonrpc`). The 6-tool E2E test is the one gated by `GRAPH_WIKI_RUN_INTEGRATION=1` because 4/6 tools call real Bedrock.
- **D-11:** **Orphan-call coverage is verification-only, not the cancel-test scope.** Researcher to recommend a short manual repro snippet or smoke test (GRAPH_WIKI_RUN_INTEGRATION=1 gated) that confirms the asyncio task returns promptly even though the boto3 worker thread is still alive — surfaced in `docs/cancellation.md` rather than asserted in the automated cancel test.

### Test fixture/vault strategy
- **D-12:** **Fresh `tmp_path` per run, init + inline seed.** Test sequence: (1) `wiki_init` against `tmp_path` (validates DACLI-02 init coverage); (2) write a small deterministic seed inline (3–5 pages + 1 source file + 1 work item) so scan/ingest/lint/query/log have material; (3) drive each remaining tool with realistic inputs; (4) assert non-error outcomes. Each tool runs against the same evolving vault — natural ordering reflects real usage.
- **D-13:** **CWD discipline.** `wiki_scan` walks the configured repo root, so tests MUST set the scan target to `tmp_path` (not the agent-research workspace) — otherwise scanner fan-out would walk the live repo and either time out or rack up Bedrock cost. Planner: confirm the env-var or config plumbing for scan target; extend if needed.
- **D-14:** **One test function with sequential sub-assertions**, not six independent tests. Reason: vault state has a natural dependency chain (init → scan → ingest → query → lint → log), and six independent tests would each pay subprocess-spawn overhead (~1s) plus Bedrock latency. Single subprocess, single stdin pipeline keeps the test under a reasonable wall-clock budget.

### Docs surface (MCP-09)
- **D-15:** **`docs/cancellation.md` at repo root** (~100–200 lines). Sections: (1) protocol behavior — what `notifications/cancelled` triggers; (2) internal chain — FastMCP → asyncio task → `SubagentPool.run_all` → per-item CancelledError → trace records; (3) trace shapes — per-item `cancelled` record + `event: batch_cancelled` summary, with examples; (4) **known limitations** — boto3 worker thread continues after cancel; what this means for "clean"; (5) future work — `aioboto3` / socket-close paths deferred to v1.2+. The doc is OSS-release-friendly and reusable past v1.1.

### Claude's Discretion
- **Per-tool input shapes for the 6-tool E2E test** — planner picks realistic small inputs (e.g., scan `max_depth=2`, query a question answerable from the seed pages, lint with default thresholds, log a single `note`-op entry). Derive from existing unit tests in `agents/graph-wiki-agent/tests/unit/`.
- **Seed-page content** — 3–5 pages with deterministic frontmatter + a wikilink chain that the query test can verify; planner picks the exact text.
- **Test file layout** — likely `tests/integration/test_mcp_e2e.py` (6-tool) and `tests/integration/test_mcp_cancel.py` (cancel); could also live alongside the existing `test_mcp_stdio.py`. Planner decides.
- **Bedrock test budget for the 6-tool test** — researcher to estimate cost of one run (4 of 6 tools hit Bedrock with small inputs); planner documents expected cost in CONTEXT-or-RESEARCH.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap / requirements
- `.planning/ROADMAP.md` §"Phase 8: Host Reliability" — phase goal, success criteria, requirement IDs.
- `.planning/REQUIREMENTS.md` §MCP-CAN (MCP-09/10/11) and §DA-CLI (DACLI-01/02/03) — the six requirements this phase closes.
- `.planning/PROJECT.md` §"Active" — v1.1 scope including the MCP cancellation + DACLI items.

### Prior-phase context (decisions still binding)
- `.planning/milestones/v1.0-REQUIREMENTS.md` — MCP-06 originally landed as "best-effort" in Phase 3; this phase tightens behavior under a real host.
- `.planning/phases/06-prompt-content-port-divergence-eval/06-CONTEXT.md` — `prompts/` module structure; relevant only as background on the agent surface the cancel test interacts with.
- `.planning/phases/07-cost-frontier-sweep/07-CONTEXT.md` — `models.toml` role-tiered defaults; cancel test will use whatever default is current at run time, but monkeypatches the model factory so the actual model id is unused.

### Reference code (read before planning)
- `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` — FastMCP server entry, all six tool definitions, `_StdoutGuard` (DO NOT regress).
- `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py` — pattern the new tests extend (subprocess.Popen, JSON-RPC framing, `_send_initialize` / `_send_initialized_notification` / `_send_tools_call`, `INTEGRATION_GATE`).
- `cores/subagent-runtime/src/subagent_runtime/pool.py` — `SubagentPool.run_all` and `_write_trace`; the new `cancelled` per-item branch and batch terminal record live here.
- `agents/graph-wiki-agent/tests/conftest.py` §"GRAPH_WIKI_RUN_INTEGRATION" — the gate pattern to reuse for the 6-tool E2E test.
- `cores/model-adapter/` — researcher: confirm the exact factory function (`make_chat_model` or equivalent) to monkeypatch for the slow-model cancel test.

### External spec
- MCP spec §"Cancellation" (`notifications/cancelled`) — protocol semantics for the cancel signal; researcher to fetch the current `modelcontextprotocol.io` page and cite the relevant section in RESEARCH.md.
- LangChain `ChatBedrockConverse` source (`langchain-aws`) — researcher: confirm the sync-wrap mechanism (`asyncio.to_thread` vs an executor) so the orphan-thread caveat in D-05 is precise.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`_run_server()` + `_send_initialize()`/`_send_initialized_notification()`** in `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py` — copy/extend; gives us a working subprocess-driven JSON-RPC harness already proven by MCP-05/07 tests.
- **`INTEGRATION_GATE`** skip-marker pattern in the same file — reused directly for the 6-tool E2E test.
- **`SubagentPool.run_all`** in `cores/subagent-runtime/src/subagent_runtime/pool.py` — already uses `asyncio.gather(..., return_exceptions=True)` which is cancel-safe; new work is mostly in `_write_trace` plus catching the propagating CancelledError to write the batch terminal record.
- **`_StdoutGuard`** in `graph_wiki_mcp/server.py` — already prevents stdout corruption; cancel paths must not bypass this (any log on cancel must go to stderr).
- **`ctx.report_progress`** calls already present in each tool — cancel test can observe one progress notification before sending `notifications/cancelled` for tighter race control.

### Established Patterns
- **Integration gate pattern** — `pytest.mark.skipif(not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"))`. Bedrock-touching tests use it; the cancel test (with stub model) does not.
- **Trace JSONL shape** — additive evolution only; no field renames; new readers branch on field presence (e.g., `event`).
- **MCP error surface** — `RuntimeError` raised inside a tool body becomes a structured MCP error (no crash) per Phase 3 MCP-04 work. Cancel may surface as a CancelledError that propagates — confirm in research that FastMCP turns this into a proper protocol response (not a stdout crash).

### Integration Points
- **FastMCP `Context`** — each tool already receives `ctx: Context`. Investigate whether `ctx` exposes a cancel/abort token or whether asyncio task cancellation alone is the integration point. (Researcher.)
- **`model_adapter.factory.make_chat_model`** — the monkeypatch site for the slow-model cancel test; confirm exact import path.
- **`graph_wiki_agent.commands.query.run_query`** — entry into the fan-out path that the cancel test will interrupt.

</code_context>

<specifics>
## Specific Ideas

- "Honest framing" — phrase used during discussion. CONTEXT, PLAN, and `docs/cancellation.md` should say "spec-conformant MCP host that DeepAgents CLI also implements," not "the DeepAgents CLI." Sets accurate reader expectations and avoids the version-drift trap of pinning to an external CLI binary.
- "Best-effort cancel" must be defined out loud in `docs/cancellation.md` — what completes cleanly (asyncio task, trace record), what remains in flight (boto3 worker thread until the HTTPS response returns), and the v1.2+ path (`aioboto3` / socket-close).
- The cancel test ought to send `notifications/cancelled` **after** observing one `report_progress` notification, not after a fixed sleep — tighter race control without flakiness.

</specifics>

<deferred>
## Deferred Ideas

- **SIGINT and stdin-close cancel paths** — protocol-correct `notifications/cancelled` is the v1.1 gate. If users hit Ctrl-C scenarios that don't unwind cleanly, file as v1.2 hardening.
- **`aioboto3` / true wire-level cancel** — would actually drop the Bedrock HTTPS request mid-flight. Out of scope for v1.1; file as v1.2 if cost / observability of orphan threads becomes a real issue.
- **Real `deepagents` CLI binary in tests** — if/when DeepAgents CLI's behavior diverges from spec, add a smoke test against the real binary. Not needed now.
- **Per-tool granular E2E tests** — if the single sequential E2E test gets too tangled or expensive, split per tool. Not needed at v1.1 scope.
- **Trace renderer enhancements for `cancelled` records** — Phase 9 owns OBS-04/05/06 (renderer + schema versioning). This phase only emits the records; Phase 9 will collapse and surface them.

</deferred>

---

*Phase: 8-host-reliability*
*Context gathered: 2026-05-17*
