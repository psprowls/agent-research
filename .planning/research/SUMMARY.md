# Project Research Summary

**Project:** agent-research / graph-wiki-agent
**Domain:** Python MCP server + deepagents subagent fan-out on AWS Bedrock, uv monorepo
**Researched:** 2026-05-13
**Confidence:** HIGH (stack/features/pitfalls verified against PyPI and official docs; architecture MEDIUM on deepagents internal API)

---

## Executive Summary

`graph-wiki-agent` is a reimplementation of a working Claude Code wiki plugin, repackaged as a FastMCP server and headless CLI that runs entirely on AWS Bedrock via deepagents. The primary goal is cost reduction through two mechanisms: routing cheaper Bedrock models (Haiku, Nova) to high-frequency subagent roles, and running those subagents in parallel within a single command invocation rather than sequentially. The project is a port of approximately 800 lines of proven lattice-wiki-core vault IO, wrapped in a new agent framework, with a cost-frontier eval harness as the proof of value.

The research-recommended architecture is a five-phase build: scaffold the monorepo and prove the Bedrock connection, build the shared fan-out runtime with all concurrency safeguards in place, implement a minimum vertical slice (the `query` command) that touches every architectural layer end-to-end, wire the eval harness against that slice, then systematically add the remaining four commands. This ordering follows strict architectural dependencies (no command works without the vault IO layer; no eval is meaningful without a running command) and front-loads the two confirmed upstream bugs in deepagents that must be patched before any fan-out code is correct.

The biggest risk is not the rewrite itself -- the domain is thoroughly understood from lattice-wiki-core -- but the combination of a young agent framework (deepagents 0.6.1) with two confirmed open bugs, Bedrock burst-throttling under parallel invocations, and a vault format that silently corrupts under naive YAML round-tripping. All three risks have known mitigations but they must be addressed in Phases 1 and 2 before any command logic is written, not retrofitted afterward.

---

## Key Findings

### Recommended Stack

All stack picks are verified against PyPI as of 2026-05-13. The selection is tightly constrained: deepagents 0.6.1 requires Python >=3.11 and compiles to a LangGraph graph, so langchain 1.3.0 and langgraph 1.2.0 are the transitive runtime. Bedrock access goes exclusively through langchain-aws 1.4.6 using `ChatBedrockConverse` -- the legacy `ChatBedrock` class is deprecated, and `langchain-anthropic` is explicitly excluded because it routes outside Bedrock and silently incurs non-Bedrock costs if credentials fall back.

The two most consequential non-obvious picks are `bm25s` over `rank-bm25` (rank-bm25 unmaintained since 2022; bm25s is a drop-in replacement with 5-50x better performance) and `deepeval` 4.0.0 over LangSmith or inspect-ai (deepeval is the only option with native Bedrock support, per-metric model configuration, cost tracking fields, and pytest integration in a single free package).

**Core technologies:**
- `uv` 0.11.14: monorepo manager with first-class workspace support; single lockfile; `uv_build` backend (not setuptools)
- `deepagents` 0.6.1 + `langgraph` 1.2.0: agent framework; `SubAgentMiddleware` provides fan-out (two confirmed bugs -- see Pitfalls)
- `langchain-aws` 1.4.6 / `ChatBedrockConverse`: Bedrock Converse API binding; uniform across all models; use this and nothing else for model calls
- `mcp` 1.27.1 / FastMCP: official MCP server SDK; stdio transport for DeepAgents CLI; SSE deprecated as of spec 2025-03-26
- `bm25s` 0.3.8: wiki index search; replaces hand-rolled stdlib BM25 from lattice-wiki-core
- `python-frontmatter` 1.1.0: vault frontmatter parsing (read-only use recommended -- see Pitfall 3)
- `deepeval` 4.0.0: per-subagent eval harness; `AmazonBedrockModel` class; pytest-native; Apache-2.0
- `typer` 0.25.1: headless CLI entry points
- `pytest` >=8.3 + `pytest-asyncio` 1.3.0 + `syrupy` 5.1.0: test stack; mock at `ChatBedrockConverse` boundary
- Bedrock `count_tokens` API (boto3): zero-cost token counting; do not use tiktoken

### Expected Features

The feature set is constrained by lattice-wiki full parity as the v1 goal. Six commands must exist before the tool replaces the current plugin. The differentiating v1 features are subagent parallelism and per-role model routing -- everything else is a port.

**Must have (table stakes -- v1 parity gate):**
- All 6 MCP tools with typed Pydantic schemas (`wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log`)
- stdio MCP transport
- `ctx.info()` + `ctx.report_progress()` in scan, ingest, lint (commands take 30-120s)
- Graceful error returns (`isError=true`)
- Per-role model routing (scanner/librarian to Haiku; orchestrator/linter to Sonnet)
- Parallel fan-out in query (librarian per page), lint (rule-groups), scan (packages)
- Partial-failure handling in fan-out
- Structured trace output per subagent run (role, model_id, tokens, duration, status) -- must be designed before fan-out is built
- Fixture repos committed + baseline corpus recorded from current lattice-wiki
- Structural scoring (frontmatter valid, wikilinks resolve, all packages present) + CI integration
- Cost tracking per run (token counts x Bedrock pricing) + JSON trial output

**Should have (differentiators -- v1.x after validation):**
- Semantic hybrid search: BM25 + Bedrock Titan Embeddings v2 re-ranking, config-gated
- Structured scan diff output: {added, updated, deleted} JSON alongside human log
- Query answer confidence signal: HIGH/LOW coverage flag
- Retry policy with exponential backoff
- Cost-vs-quality frontier chart
- LLM-judge scoring with heterogeneous panel (one Claude + one non-Claude judge)

**Defer to v2+:**
- Vector store / persistent embedding index
- Git-diff-aware ingest
- ADR cross-referencing as first-class page category
- Streaming query responses
- LangSmith dataset integration

### Architecture Approach

The architecture is a strict tiered monorepo: `cores/` packages (model-adapters, subagent-runtime, eval-harness) provide shared infrastructure with no upward dependencies; `agents/graph-wiki-agent` depends on all three cores. Two thin dispatch surfaces (MCP server and CLI) call identical `commands/` functions, which orchestrate vault IO (pure Python, no LLM) and fan-out via `SubagentPool`. The vault IO layer is a direct port of approximately 800 lines from lattice-wiki-core with no cross-repo runtime dependency, preserving read-compatibility on day one.

**Major components:**
1. `cores/model-adapters` (leaf): `ChatBedrockConverse` factory + `ModelRegistry` (role to model_id) -- single source of truth for model assignments
2. `cores/subagent-runtime`: `SubagentPool.fanout()` with `asyncio.gather(return_exceptions=True)` and explicit recursion limit propagation -- patches the two deepagents bugs at the shared layer
3. `cores/eval-harness`: `recorder.py` (captures lattice-wiki baseline as subprocess), `runner.py` (replays with model sweep), `scorer.py` (similarity + rubric), `report.py` (cost-frontier chart)
4. `agents/graph-wiki-agent/vault/`: pure Python vault IO ports from lattice-wiki-core -- must pass round-trip fidelity test before any command touches it
5. `agents/graph-wiki-agent/commands/`: one module per wiki command; owns aggregation logic; surface-agnostic (same function handles MCP and CLI)
6. `mcp_server.py` + `cli.py`: thin dispatch only -- no agent logic; both call the same command functions

### Critical Pitfalls

Twelve pitfalls were identified. Top five by rewrite/data-loss risk:

1. **Parallel subagent cancellation cascade** -- deepagents uses `asyncio.gather()` without `return_exceptions=True` (confirmed open issue #694); one failure silently cancels all siblings. Fix: `SubagentPool` uses `asyncio.gather(*tasks, return_exceptions=True)`; integration test with 1-of-4 intentional failure. Phase 2.

2. **Bedrock burst-throttling from unbounded `max_tokens`** -- Bedrock reserves `max_tokens` from TPM quota at request start; Claude Sonnet 4 output tokens burn at 5x rate; 5 parallel subagents with default max_tokens produce `ThrottlingException` at low actual usage. Fix: role-specific `max_tokens` in `RoleSpec` (librarian: 2000, scanner stub: 500, linter: 3000). Phase 2.

3. **Vault YAML round-trip format drift** -- `python-frontmatter` uses PyYAML Dumper which normalizes YAML on write; after one round-trip `git diff` shows changes on every page, destroying git blame. Fix: port `layout_io.py` verbatim for writes; use `python-frontmatter` for reading only; round-trip fidelity test on real vault. Phase 1.

4. **Wikilink placeholder false positives in lint** -- template tokens (`[[wiki/...]]`, `[[work/<slug>]]`) produce hundreds of false-positive broken-link violations; original tool shipped a dedicated fix (commits 9502c45, 9388cdd). Fix: port `_is_placeholder_target()` predicate verbatim from `lint_wiki.py` before implementing any wikilink resolver. Phase 5 (lint).

5. **Recursion limit not propagated to subagents** -- subagents use LangGraph hardcoded default of 25 steps (confirmed open issue #1698); librarian with 13+ tool calls raises `GraphRecursionError` surfacing as `CancelledError` in parent. Fix: every subagent invocation site passes `config={"recursion_limit": 150}`. Phase 2.

---

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Infrastructure + Vault IO Foundations
**Rationale:** Three hard blockers must be cleared before any agent code is correct: Bedrock IAM proven with cross-region inference profiles; vault IO passing round-trip fidelity on the real vault; pytest isolation correct per monorepo member.
**Delivers:** uv workspace with `cores/model-adapters`; `ChatBedrockConverse` proven against real Bedrock; vault IO modules ported with round-trip fidelity test passing on real vault; MCP server skeleton with stderr-only logging enforced; pytest isolation confirmed per member
**Uses:** uv 0.11.14, Python 3.11, `langchain-aws` 1.4.6, `python-frontmatter` 1.1.0, `mcp` 1.27.1
**Avoids:** vault YAML drift, MCP stdout contamination, cross-region IAM missing ARN, truncated frontmatter crash, uv pytest collision, uv single-version enforcement
**Gate:** `make_llm("haiku").invoke("ping")` works against real Bedrock; `git diff` empty after vault round-trip on real vault; MCP server subprocess stdout contains only valid JSON-RPC

### Phase 2: Subagent Fan-Out Runtime
**Rationale:** Both confirmed deepagents bugs affect the fan-out path and must be patched in the shared `SubagentPool` layer before any command uses fan-out. Retrofitting these fixes after multiple commands are written is expensive.
**Delivers:** `SubagentPool.fanout()` with `return_exceptions=True`; per-role `max_tokens` enforcement; asyncio semaphore; explicit recursion limit propagation; structured trace output per invocation (role, model_id, tokens, duration, status); integration test: 4 parallel subagents with 1 intentional failure and 30-step tool chain
**Uses:** `deepagents` 0.6.1, `cores/subagent-runtime`, asyncio
**Avoids:** parallel cancellation cascade, Bedrock burst throttling, recursion limit not propagated
**Gate:** 4 subagents dispatched, 1 raises, 3 results returned; subagent with 30 tool calls completes without `GraphRecursionError`; 5 parallel subagents with role-sized `max_tokens` produce no `ThrottlingException`

### Phase 3: Minimum Vertical Slice -- query End-to-End
**Rationale:** The `query` command touches every architectural layer. Getting it working end-to-end proves the architecture before building four more commands on top. Structural problems caught here cost 5x less than after all commands are wired.
**Delivers:** `vault/search.py` with bm25s; `agents/librarian.py` (RoleSpec + prompt); `commands/query.py` (BM25 to fan-out to synthesis); `mcp_server.py` exposing `wiki_query`; `cli.py` with `query` subcommand; end-to-end test against real lattice-wiki vault
**Uses:** `bm25s` 0.3.8, `mcp` 1.27.1 / FastMCP, `typer` 0.25.1
**Implements:** commands/ layer, vault/ search layer, SubagentPool integration, both delivery surfaces
**Gate:** `graph-wiki-agent query "..."` returns a coherent answer with `[[wikilink]]` citations from the real vault; DeepAgents CLI can invoke `wiki_query` and receive a result

### Phase 4: Eval Harness
**Rationale:** Build eval against the working query command before adding remaining commands. Forces judge architecture (heterogeneous panel, pinned ARNs, output hashing) to be correct before any baselines are committed to git.
**Delivers:** 2-3 fixture repos committed; baseline corpus recorded from current lattice-wiki for `query`; `recorder.py` / `runner.py` / `scorer.py` / `report.py`; structural scoring; cost tracking; JSON trial output; `@pytest.mark.eval` CI integration; cost-vs-quality table for librarian role across >=3 Bedrock models
**Uses:** `deepeval` 4.0.0, `cores/eval-harness`, `syrupy` 5.1.0
**Avoids:** LLM-judge self-preference, eval baseline drift
**Gate:** Cost-frontier table shows >=2 models at different quality/cost tradeoffs; heterogeneous judge panel in use; re-recording baseline with same pinned ARN produces identical hash

### Phase 5: Remaining Commands
**Rationale:** With SubagentPool validated, eval harness operational, and vault IO proven, remaining commands are additive. Sub-ordering by complexity: `log` (trivial, no fan-out) to `init` (template scaffolding) to `scan` (scanner fan-out) to `ingest` (ingestor fan-out, complex routing) to `lint` (largest: mechanical port + semantic fan-out + placeholder filter).
**Delivers:** Full parity with lattice-wiki: all 6 commands via MCP and headless CLI; eval baselines for all commands; parity test passing per command
**Uses:** existing stack
**Avoids:** wikilink placeholder false positives (must address at start of lint)
**Gate per command:** parity test against recorded lattice-wiki output for same fixture vault

### Phase Ordering Rationale

- Phase 1 before Phase 2: `SubagentPool` depends on `cores/model-adapters` and vault IO must be clean before any command uses it
- Phase 2 before Phase 3: the query command uses fan-out; fan-out must be correct before any command is built
- Phase 3 before Phase 4: eval needs a working command to record baselines against
- Phase 4 before Phase 5: baseline corpus for each new command should be recorded as that command is implemented; the harness must exist first
- Within Phase 5: `log` and `init` before `scan`/`ingest`/`lint` because they are prerequisites for an initialized vault in integration tests

### Architecture Build-Order as the Spine

| Phase | Enabling Stack | Key Features Delivered | Top Pitfalls Addressed |
|-------|----------------|------------------------|------------------------|
| 1: Infrastructure + Vault IO | uv 0.11.14, `cores/model-adapters`, `vault/` ports | Bedrock proven, vault round-trip safe, MCP skeleton clean | Vault YAML drift, MCP stdout contamination, IAM cross-region, truncated frontmatter |
| 2: Fan-Out Runtime | `cores/subagent-runtime`, deepagents 0.6.1, asyncio | Per-role routing, partial-failure handling, structured trace | Cancellation cascade, burst throttling, recursion limit |
| 3: Query (Vertical Slice) | `bm25s`, FastMCP, Typer | `wiki_query` via MCP + CLI, librarian fan-out | Relies on P1+P2 mitigations |
| 4: Eval Harness | `deepeval` 4.0, `cores/eval-harness`, fixture repos | Baseline corpus, cost tracking, CI gate, cost-frontier report | LLM judge self-preference, baseline drift |
| 5: Remaining Commands | existing stack | Full 6-command parity | Wikilink placeholder false positives (lint) |

### Minimum Vertical Slice (Plain Language)

Build exactly this, in order:

1. uv workspace with `cores/model-adapters` -- call `make_llm("haiku").invoke("ping")` against real Bedrock. If this fails, stop and fix IAM.
2. `vault/search.py` with bm25s -- index a real lattice-wiki vault and get back 10 page paths for a test question.
3. `SubagentPool.fanout()` -- dispatch 5 mock librarian calls in parallel, verify partial failure returns the 4 successes.
4. `agents/librarian.py` -- a `RoleSpec` with system prompt and model_id.
5. `commands/query.py` -- BM25 retrieval to librarian fan-out to single synthesis call to structured result.
6. `mcp_server.py` -- one `@mcp.tool("wiki_query")` that calls `commands/query.py`.
7. `cli.py` -- `graph-wiki-agent query "..."` subcommand that calls the same function.

When step 7 returns a real answer with wikilink citations from the real vault via the DeepAgents CLI, the architecture is proven. Everything else is additive.

### Cross-Document Connections

These are the interdependencies no single research document could see:

**`bm25s` vs `rank-bm25` and hybrid search.** STACK recommends `bm25s` for performance. `bm25s` also supports BM25L, BM25+, and Lucene variants that `rank-bm25` lacks, meaning the hybrid search feature (BM25 + Bedrock embedding re-ranking, P2 in FEATURES) has a richer foundation. No feature priority change, but the upgrade path is cleaner than FEATURES implies.

**`deepeval` 4.0 and the heterogeneous judge panel.** STACK selects `deepeval` 4.0 `AmazonBedrockModel` as the judge class. PITFALLS recommends a heterogeneous judge panel (one Claude + one non-Claude) to avoid self-preference bias. `GEval` takes a `model=` argument, meaning the panel is directly supported without custom plumbing -- pass two `AmazonBedrockModel` instances to two `GEval` metrics and average scores. The LLM-judge feature is cheaper to implement correctly than FEATURES implies.

**deepagents 0.6.1 bugs make `SubagentPool` load-bearing, not optional.** STACK recommends using deepagents `SubAgentMiddleware` for fan-out. PITFALLS reveals two confirmed open bugs in that middleware (issues #694, #1698). ARCHITECTURE's `SubagentPool` in `cores/subagent-runtime` -- using `ChatBedrockConverse.ainvoke` directly with `return_exceptions=True` and explicit `recursion_limit` propagation -- is the correct resolution. Skipping `SubagentPool` and using `SubAgentMiddleware` directly is not safe in v1.

**`python-frontmatter` is read-only; writes go through the ported emitter.** STACK recommends `python-frontmatter` for vault IO. PITFALLS flags that its PyYAML Dumper reformats existing vault files on write-back. ARCHITECTURE resolves this by porting `layout_io.py` verbatim. `python-frontmatter` should be used for reading only; all writes go through the ported hand-rolled emitter. This layering must be explicit in Phase 1 -- it is not obvious from reading STACK or ARCHITECTURE in isolation.

**Structured trace output must be designed in Phase 2, not Phase 4.** FEATURES marks structured trace output as a table-stakes requirement. ARCHITECTURE places it at the `SubagentPool` level. PITFALLS implies it is needed for cost tracking in Phase 4. The critical connection: trace output is a cross-cutting concern that must be designed when `SubagentPool` is built (Phase 2). If Phase 3 ships without trace output in `SubagentPool`, retrofitting means touching every command function. This is the most common "discovered in Phase 4" mistake in eval harness projects.

### Open Questions: Triage

**Must answer before roadmap finalization:**
- Is deepagents 0.6.1 `SubAgentMiddleware` usable at all, or should the project skip it entirely and build `SubagentPool` as a pure asyncio wrapper? The two confirmed bugs suggest the latter. The roadmap must make this explicit in Phase 2 scope.
- Does Pat's existing Bedrock IAM role include the inference-profile ARN resource? This blocks Phase 1. Answer by running `aws bedrock invoke-model` with the cross-region profile ARN before writing any code.

**Can answer during phase research:**
- What is deepeval 4.0's exact API for `AmazonBedrockModel.cost_per_input_token`? Verify against the 4.0.0 release before Phase 4 implementation.
- Does `asyncio.to_thread()` around vault file reads make a measurable difference for initial vault sizes? Profile during Phase 3.
- What is the real Bedrock on-demand `max_tokens` ceiling for Haiku and Nova Micro on Pat's account? This affects per-role `max_tokens` values in `RoleSpec`.

**Can defer:**
- Whether `ruamel.yaml` is needed or targeted string replacement in the ported `layout_io.py` suffices -- evaluate during Phase 1 round-trip test.
- Whether `langchain-mcp-adapters` 0.2.2 is needed in v1 -- no current use case for calling other MCP servers as tools.
- Streamable HTTP transport -- no use case beyond local DeepAgents CLI.

### Research Flags

Phases needing deeper research during planning:
- **Phase 2 (Fan-Out Runtime):** deepagents `SubAgentMiddleware` internal API is MEDIUM confidence; read the 0.6.1 source before implementing to confirm whether the bugs have partial workarounds.
- **Phase 4 (Eval Harness):** deepeval 4.0 `AmazonBedrockModel` cost tracking fields need verification against the actual release; heterogeneous judge panel composition with two `GEval` instances has no established prior art in deepeval docs -- plan a spike.

Phases with standard patterns (research phase not needed):
- **Phase 1 (Infrastructure):** uv workspace patterns are well-documented and verified; vault IO is a direct port of known-working code; MCP skeleton is one-liner via FastMCP.
- **Phase 3 (Query):** Call graph is fully specified in ARCHITECTURE; `bm25s` integration follows library docs; no novel patterns.
- **Phase 5 (Remaining Commands):** Each command follows the Phase 3 pattern; complexity is in porting lattice-wiki-core logic, not discovering new patterns.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI 2026-05-13; no speculative picks |
| Features | HIGH | Derived from known lattice-wiki requirements + MCP/deepagents official docs via Context7 |
| Architecture | MEDIUM-HIGH | Monorepo and MCP patterns are HIGH; deepagents SubAgentMiddleware internal API is MEDIUM -- library is young (v0.6.1) with two open bugs on the primary fan-out path |
| Pitfalls | HIGH (infra/runtime) / MEDIUM (eval methodology) | Deepagents bugs confirmed via GitHub issues; Bedrock throttling confirmed via AWS docs; eval self-preference from research literature |

**Overall confidence:** HIGH for stack and build sequence; MEDIUM for deepagents fan-out internals

### Gaps to Address

- **deepagents `SubAgentMiddleware` vs raw asyncio:** The confirmed bugs make raw asyncio (`ChatBedrockConverse.ainvoke` in `asyncio.gather`) the safer path. The roadmap must make this architectural choice explicit in Phase 2 scope.
- **Bedrock `max_tokens` on-demand ceilings per model:** Role-specific values are specified conceptually but need validation against Pat's actual account limits before Phase 2 gates are set.
- **Eval judge calibration:** Heterogeneous judge panel using two `AmazonBedrockModel` instances in deepeval 4.0 needs a confirmed implementation example before Phase 4 planning finalizes.

---

## Sources

### Primary (HIGH confidence)
- PyPI: `deepagents` 0.6.1, `langchain-aws` 1.4.6, `langchain` 1.3.0, `langgraph` 1.2.0, `mcp` 1.27.1, `deepeval` 4.0.0, `bm25s` 0.3.8, `typer` 0.25.1, `python-frontmatter` 1.1.0, `pytest-asyncio` 1.3.0, `syrupy` 5.1.0, `uv` 0.11.14 -- all verified 2026-05-13
- Context7 `/langchain-ai/langchain-aws` -- `ChatBedrockConverse` usage, token metadata, `init_chat_model` provider strings
- Context7 `/astral-sh/uv` -- workspace pyproject.toml patterns, dependency-groups, member declaration
- Context7 `/modelcontextprotocol/python-sdk` -- tool registration, progress, structured output, transport options
- Context7 `/langchain-ai/deepagents` -- `runSwarm`, SubAgent model config, eval trial schema
- AWS Bedrock docs: CountTokens API, token burndown rates, cross-region inference IAM requirements
- deepagents GitHub issues #694 (cancellation cascade), #1698 (recursion limit not propagated)
- lattice-wiki-core source (direct inspection): commits `ae6872e` (truncated frontmatter fix), `9502c45` / `9388cdd` (placeholder wikilink fix)

### Secondary (MEDIUM confidence)
- DeepEval docs: `AmazonBedrockModel` API, cost tracking fields -- verified against docs page but not against 4.0.0 release artifacts directly
- AWS re:Post: parallel LangGraph throttling from TPM reservation; cross-region inference `AccessDeniedException` root cause
- deepwiki.com/langchain-ai/deepagents: SubAgentMiddleware sync vs async, per-role model config

### Tertiary (LOW confidence -- validate during implementation)
- LLM-as-judge self-preference bias (arXiv 2410.21819) -- research literature; applies by analogy to Bedrock-hosted models
- deepagents streaming best practices docs -- thin docs for a young library; treat as guidance, not specification

---
*Research completed: 2026-05-13*
*Ready for roadmap: yes*
