# Phase 2: Subagent Fan-Out Runtime - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers `cores/subagent-runtime` — the shared fan-out primitive that every command depends on before any command can wire fan-out in. Three deliverables:

1. **ModelRegistry** — Extends `cores/model-adapter`'s `models.toml` + `make_llm()` to the full 7 logical roles (`librarian`, `scanner`, `linter`, `ingestor`, `synthesizer`, `judge_a`, `judge_b`) with per-role `max_tokens` ceilings and `max_concurrency` semaphore sizes. No rewrite of Phase 1 loader — additions only (D-10 from Phase 1 CONTEXT).

2. **SubagentPool** — A fan-out primitive that runs N tasks concurrently against a role-bound model with partial-failure handling, per-role throttle caps, and explicit recursion-limit propagation. API: `pool.run_all(items, task, role) → FanOutResult`. Implementation path (SubAgentMiddleware vs raw asyncio) is researcher's decision after reading #694 PR.

3. **Structured trace output** — Every fan-out call writes a JSONL record to `.code-wiki/traces/<timestamp>.jsonl` with `role`, `model`, `prompt_hash`, `item_id`, `status`, `latency_ms`, `tokens_in`, `tokens_out`, `cost_usd`. Trace viewer subcommand (`code-wiki-agent trace <file>`) renders as a human-readable timeline. This is Phase 2's responsibility — not retrofitted later.

**Out of scope this phase:** any wiki command logic (query/scan/lint/etc.), hybrid search, eval harness, the headless CLI beyond stub level, cost_usd accounting (null in Phase 2, added in Phase 4).

</domain>

<decisions>
## Implementation Decisions

### deepagents SubAgentMiddleware Decision (SUB-02/03)

- **D-01 [informational]:** Researcher reads the #694 PR before writing any fan-out code. Based on the PR's complexity, researcher recommends one of two paths — and has full discretion to pick:
  - **Vendor path:** If #694's fix is a single subclass override of `SubAgentMiddleware`, vendor it as a thin wrapper. Use it as our pool. Upgrade path: delete our subclass when deepagents ships a release with the fix included.
  - **Asyncio pool path:** If the fix touches `SubAgentMiddleware` internals at more than one point, skip SubAgentMiddleware entirely. Implement `SubagentPool` on `asyncio.gather(return_exceptions=True)` directly — this is the explicitly blessed SUB-03 fallback.
  *Resolved by research: asyncio pool path chosen. SubAgentMiddleware not used. Plans implement asyncio.gather path directly.*

- **D-02 [informational]:** deepagents bug #1698 (recursion limit / `GraphRecursionError`) is **already fixed** in 0.5.4 (PR #2194) and shipped in 0.6.1. No workaround needed. Recursion limit propagation (SUB-04) is still required but can be implemented cleanly without patching deepagents.

- **D-03 [informational]:** deepagents bug #694 (cancellation cascade on partial failure) was **merged but not released** as of 2026-05-13. deepagents 0.6.1 does NOT have this fix. This is why researcher must read the PR before choosing the implementation path. *Resolved: asyncio path chosen precisely because #694 is not in 0.6.1.*

### SubagentPool API Shape

- **D-04: Calling convention:**
  ```python
  result: FanOutResult = await pool.run_all(
      items=pages,          # list[Any] — one per task
      task=summarize_page,  # Callable[[Any], Awaitable[Any]]
      role="librarian",     # str — role name from models.toml
  )
  ```
  `role` is used by the pool for two things only: applying the role's `max_concurrency` semaphore and writing `role` + `model_id` into the trace record. The pool does NOT resolve or inject a model — callers own model construction.

- **D-05: Task owns the model via closure:**
  ```python
  llm = make_llm("librarian")
  async def summarize_page(page: VaultPage) -> str:
      return await llm.ainvoke(build_prompt(page))
  ```
  The pool receives `role="librarian"` to enforce throttle + emit trace metadata. Callers call `make_llm()` themselves before constructing the task. Simpler pool, easier to test, no signature coupling.

- **D-06: Return type — `FanOutResult`:**
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
  On partial failure: `successes` contains results for tasks that completed; `errors` contains per-item errors for tasks that raised. Parent caller decides whether to fail-fast or degrade-gracefully (SUB-07). No sibling cancellation.

- **D-07: Recursion limit (SUB-04)** — `pool.run_all()` accepts an optional `recursion_limit: int` parameter. Passed explicitly to each subagent invocation's `RunnableConfig`. Default value set in `SubagentPool.__init__` from config, not hardcoded. Researcher confirms the correct LangGraph config key.

### Trace Schema and Cost Accounting

- **D-08: `cost_usd` is `null` in Phase 2.** Cost accounting is Phase 4's responsibility (eval harness has the model ARNs and pricing context). Trace record schema:
  ```json
  {
    "role": "librarian",
    "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "prompt_hash": "<sha256 of rendered prompt>",
    "item_id": "<str(item) or explicit id field if item has one>",
    "status": "success|error",
    "latency_ms": 1234,
    "tokens_in": 850,
    "tokens_out": 312,
    "cost_usd": null,
    "timestamp": "2026-05-13T10:00:00Z"
  }
  ```

- **D-09: `tokens_in` / `tokens_out` ARE captured in Phase 2** from `ChatBedrockConverse`'s response `usage_metadata` (`.input_tokens` / `.output_tokens`). These are already available from the Bedrock Converse API response — no separate token-counting call needed.

- **D-10: Trace writer lives in `cores/subagent-runtime`**, not in each command. Pool's task wrapper captures latency + response metadata and appends the JSONL record to the trace file. Trace file path resolves relative to a configurable `.code-wiki/` base dir (defaulting to `<vault_root>/.code-wiki/traces/`). Planner chooses the exact file-naming convention (timestamp vs timestamp+command).

### Claude's Discretion

- **SubAgentMiddleware vs asyncio pool:** Researcher's call after reading #694 PR. See D-01.
- **Specific model IDs for 7 roles** in `models.toml` expansion: researcher confirms current cross-region inference profile ARNs for the full role set from Bedrock's lineup.
- **models.toml schema extension** — exact TOML structure for `max_tokens`, `max_concurrency`, and any cost-rate fields: planner designs.
- **Trace file naming** within `.code-wiki/traces/`: planner picks (e.g., `<ISO8601>.jsonl` vs `<timestamp>-<command>.jsonl`).
- **`OBS-02` viewer format** for `code-wiki-agent trace <file>`: planner designs.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 2" — phase goal, success criteria, requirement list (BED-02..05, SUB-01..07, OBS-01..03)
- `.planning/REQUIREMENTS.md` §"Bedrock & Model Routing" (BED-02..05) + §"Subagent Runtime" (SUB-01..07) + §"Observability" (OBS-01..03) — full requirement text
- `.planning/STATE.md` §"Key Decisions" — structured trace is Phase 2 (not retrofitted); SubagentPool over SubAgentMiddleware is the default preference
- `.planning/PROJECT.md` §"Constraints" + §"Key Decisions" — Bedrock-only, no hardcoded model IDs, fan-out strategy

### Phase 1 CONTEXT (critical — sets patterns this phase extends)
- `.planning/phases/01-infrastructure-vault-io-and-mcp-skeleton/01-CONTEXT.md` — D-10 (Phase 2 extends models.toml without rewrite), D-11 (no hardcoded model IDs), D-03 (cores/subagent-runtime created by Phase 2, not Phase 1)

### Existing Code — Phase 1 deliverables
- `cores/model-adapter/src/model_adapter/loader.py` — `make_llm(role)` implementation; `_GuardedChatBedrockConverse` subclass pattern; how to extend without rewriting
- `cores/model-adapter/src/model_adapter/models.toml` — current schema shape (haiku + sonnet); Phase 2 extends with 7 full roles + max_tokens + max_concurrency
- `cores/model-adapter/tests/test_loader.py` — test patterns; monkeypatch via `_original_invoke`; integration test skip pattern

### deepagents Bug Tracker (RESEARCHER: MUST READ before writing fan-out code)
- `https://github.com/langchain-ai/deepagents/issues/694` — cancellation cascade bug; linked PR contains the fix under review; read to assess vendor complexity
- `https://github.com/langchain-ai/deepagents/pull/2194` — #1698 recursion limit fix (released in 0.5.4, already in 0.6.1; confirms this issue is closed)

### External Documentation
- AWS Bedrock CountTokens API: `https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html` — for token pre-flight if needed
- `langchain-aws` ChatBedrockConverse: Context7 `/langchain-ai/langchain-aws` — usage_metadata field names for tokens_in/tokens_out
- `deepagents` SubAgentMiddleware: Context7 or deepwiki `/langchain-ai/deepagents` — SubAgentMiddleware API, SubagentPool primitives
- AWS Bedrock inference profiles: `https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html` — for researcher to confirm 7-role model ARNs

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `make_llm(role) -> ChatBedrockConverse` in `cores/model-adapter/src/model_adapter/loader.py` — Phase 2 extends `models.toml` entries and `make_llm()` continues to be the model resolver for the pool
- `_GuardedChatBedrockConverse` subclass — shows the established pattern for extending `ChatBedrockConverse` without triggering Pydantic v2's `extra='forbid'`; relevant if the #694 vendor path is chosen
- `@pytest.mark.integration` + `CODE_WIKI_RUN_INTEGRATION=1` skip pattern from `agents/code-wiki-agent/tests/integration/` — the SubagentPool integration tests (SUB-02 partial failure test, SUB-04 recursion limit test, SUB-05 throttle test) follow the same pattern

### Established Patterns
- **Workspace member structure** — `<member>/pyproject.toml` + `<member>/src/<package_name>/` + `<member>/tests/`; Phase 2 creates `cores/subagent-runtime/` following this exact layout
- **Cross-package imports** — `from model_adapter.loader import make_llm` is the import pattern; `cores/subagent-runtime` imports `model_adapter` as a workspace dependency
- **Stderr-only logging** — all Python modules must route logging to stderr (or standard `logging` configured to stderr); pool and trace writer are no exception

### Integration Points
- `cores/subagent-runtime` → imports `cores/model-adapter` (adds `model-adapter` as a workspace dependency in `subagent-runtime`'s `pyproject.toml`)
- Phase 3 (query command) → imports `SubagentPool` from `cores/subagent-runtime` for librarian fan-out
- Phase 5 (scan, lint commands) → imports `SubagentPool` for scanner + linter fan-out
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — Phase 2 adds `trace` subcommand to the Typer app (OBS-02 viewer)

</code_context>

<specifics>
## Specific Ideas

- The integration test for SUB-02 (partial failure) should dispatch 4 parallel subagents where 1 intentionally raises. Assert `FanOutResult.errors` has exactly 1 entry and `FanOutResult.successes` has exactly 3 — no more, no less. This is the acceptance test for the no-sibling-cancellation guarantee.
- Recursion limit: deepagents uses `RunnableConfig` to propagate `recursion_limit`. The pool should accept a `recursion_limit` parameter and pass it into every task invocation's config. Researcher confirms the exact config key in deepagents/LangGraph.
- The trace viewer (`code-wiki-agent trace <file>`) is a simple pretty-printer — not a TUI. Planner has discretion on format (tree, table, timeline). It doesn't need Bedrock — it reads local JSONL and renders to stdout.
- Pat confirmed that `cost_usd` being `null` in Phase 2 is intentional — Phase 4 has the full model pricing context and will add the accounting layer. Don't approximate or hardcode rates in Phase 2.

</specifics>

<deferred>
## Deferred Ideas

- **Cost rate storage in `models.toml`** — storing `cost_per_1k_input_tokens` / `cost_per_1k_output_tokens` in models.toml alongside model config was discussed but deferred. Phase 4 (eval harness) will design this when cost accounting is actually needed.
- **Real-time throttle backoff** — if Bedrock returns `ThrottlingException` at runtime, the pool could implement exponential backoff. Not in Phase 2 scope; the success criterion is that 5 parallel subagents with role-sized max_tokens produce no ThrottlingException, implying the semaphore cap is correctly set.

</deferred>

---

*Phase: 2-Subagent Fan-Out Runtime*
*Context gathered: 2026-05-13*
