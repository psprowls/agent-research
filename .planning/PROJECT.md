# deep-agents

## What This Is

A Python monorepo (managed with `uv`) of LangChain/deepagents-based AI tooling. The first package, **`code-wiki-agent`**, is a reimplementation of the existing `lattice-wiki` Claude Code plugin — packaged as both an MCP server (consumed by the DeepAgents CLI) and a headless CLI that runs the full agent loop. It exists primarily so Pat can run the same wiki workflows on AWS Bedrock with within-command subagent fan-out for cost and context savings.

## Core Value

**Faithfully reproduce lattice-wiki's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.**

If everything else fails, a Bedrock-driven `code-wiki-agent query "..."` (or the equivalent MCP tool call) must return answers as good as today's lattice-wiki librarian, on cheaper models, faster.

## Current Milestone: v1.1 Quality Improvements

**Goal:** Close the output-quality gap with lattice-wiki by porting its prompt content into code-wiki-agent, then validate the cost-frontier on Bedrock and prove host-level reliability under the DeepAgents CLI.

**Target features:**
- Lattice-wiki SKILL.md content ported into agent prompts (librarian, ingestor, linter, scanner) — eval flags remaining divergences
- Cost-frontier sweep executed against all 7 roles; `models.toml` defaults swapped to cost-optimal picks
- MCP cancellation polish — verify MCP-06 mid-fan-out cancel under the real DeepAgents CLI host
- DeepAgents CLI integration test — end-to-end stdio subprocess exercising each tool
- Trace/observability polish — `.code-wiki/traces/` format + `code-wiki-agent trace` renderer

**Key context:**
- Quality first: prompt port lands before the cost-frontier sweep so the sweep measures the *improved* agent, not the pre-port baseline.
- BED-01 live-Bedrock gate is approved (AWS onboarding done); verify in passing during the sweep.
- OSS release prep deferred past v1.1.
- Phase numbering continues from v1.0 (next phase = 6).

## Requirements

### Validated

#### Phase 08 Complete — 2026-05-17 (host-reliability)
- [x] MCP cancellation wired through `SubagentPool.run_all` — per-item `status: cancelled` trace records and single `event: batch_cancelled` terminal record on cancel; `_write_trace` / `_write_batch_terminal` never raise (MCP-09, MCP-10)
- [x] Deterministic in-process asyncio cancel test with stubbed LLM — zero Bedrock cost (MCP-11)
- [x] `WikiScanInput.repo_path` field added so the E2E test can scope `wiki_scan` to a `tmp_path` vault (DACLI-01)
- [x] Single sequential E2E integration test exercises all six MCP tools as a stdio subprocess against a fresh `tmp_path` vault; gated behind `CODE_WIKI_RUN_INTEGRATION=1` (DACLI-02, DACLI-03)
- [x] `docs/cancellation.md` — v1.1 reference for `notifications/cancelled` protocol, internal unwinding chain, trace shapes, orphan-thread limitation, v1.2+ paths

#### Milestone v1.0 SHIPPED — 2026-05-15 (code-wiki-agent parity)
- [x] **Phase 04 (Eval Harness)** — `cores/eval-harness` package with fixture corpus (3 repos), headless `claude -p` baseline recorder (EVAL-08 schema), `deepeval` 4.0 integration with `AmazonBedrockModel`, heterogeneous two-judge panel (claude-sonnet-4-6 + nova-pro-v1:0), cost-frontier sweep runner (`pytest-evals`), regression-check AssertionError gate, structural metrics (cites code path / wikilinks resolve / valid frontmatter) (EVAL-01..10)
- [x] **Phase 05 (Remaining Commands)** — `init`, `scan`, `ingest`, `lint`, `log` shipped on both MCP and headless CLI surfaces with a single shared command implementation; `scan` and `lint` use SubagentPool fan-out (scanner across packages; linter across 3 rule-groups); `ingest` routes to package/concept/adr pages via a single ingestor LLM call; `--config` global Typer callback + `WikiConfig` dataclass (CMD-01..08, MCP-01..08, CLI-01..07)

#### Phase 03 Complete — 2026-05-14 (query-vertical-slice-hybrid-search)
- [x] Hybrid search: BM25 via `bm25s` + Titan v2 embeddings in SQLite (WAL), sha256 incremental rebuild, RRF fusion (SEARCH-01..06)
- [x] `commands/query.py` — shared `run_query()` pipeline: hybrid search → librarian fan-out (SubagentPool) → synthesizer → QueryResult (CMD-04, CLI-03)
- [x] `code-wiki-agent query` CLI subcommand with `--top-k`, `--vault`, `--json`, `--no-state-gate` (CLI-01..07, CMD-07, CMD-08)
- [x] `wiki_query` MCP tool with Pydantic schemas, `ctx.report_progress()` notifications (MCP-02, MCP-04, MCP-06, MCP-07)
- [x] G1 citation resolver normalises `.md`-suffixed wikilinks correctly (regression caught in UAT)
- [x] 54 unit tests; 3 integration tests gated behind `CODE_WIKI_RUN_INTEGRATION=1`

#### Phase 02 Complete — 2026-05-14 (subagent-fan-out-runtime)
- [x] `SubagentPool.run_all()` with partial-failure isolation, semaphore throttle, per-role concurrency (SUB-01..07)
- [x] Structured JSONL trace output to `.code-wiki/traces/` for every fan-out call (OBS-01)
- [x] `code-wiki-agent trace` CLI subcommand renders traces as human-readable timeline (OBS-02, OBS-03)
- [x] Real-Bedrock integration tests: 4-parallel with 1 intentional failure → 3 successes, no sibling cancellation (BED-02..05)

#### Phase 01 Complete — 2026-05-13 (infrastructure-vault-io-and-mcp-skeleton)
- [x] `uv` workspace at repo root with tiered layout: `cores/vault-io`, `cores/model-adapter`, `agents/code-wiki-agent`
- [x] Project license + README seeded (MIT, open-source-ready)
- [x] Bedrock model adapter — `make_llm("haiku")` invokes real `ChatBedrockConverse`; `BedrockAccessDenied` raised with ARN on bad credentials
- [x] Vault IO round-trip — reading-then-writing every page produces byte-identical output (29 tests pass)
- [x] MCP stdio surface — FastMCP `code-wiki-mcp` server with `_StdoutGuard`; `wiki_ping` tool; provably stdout-clean
- [x] CI pipeline (ruff + pytest); ruff clean (`ruff check .` and `ruff format --check .` both exit 0)
- [x] **Read-compatible with existing vaults** — preserve frontmatter, layout block, wikilinks, file-map format

### Active

_v1.1 Quality Improvements — scoped 2026-05-15. Requirements will be expanded in `REQUIREMENTS.md`; phases tracked in `ROADMAP.md`._

- [ ] **Lattice-wiki SKILL.md content ported into agent prompts** — librarian, ingestor, linter, scanner roles inherit canonical iron rules / patterns from the existing plugin; eval harness flags remaining divergences from skill-content expectations.
- [ ] **Cost-frontier sweep executed** — run the Phase 04 harness (`CODE_WIKI_RUN_EVAL=1`) against all 7 roles, publish cost-optimal model picks per role, swap defaults in `models.toml`. (Sweep runs against the *post-port* agent, not the v1.0 baseline.)
- [x] **MCP cancellation polish (MCP-06)** — ✓ Validated Phase 08: per-item + terminal trace records on cancel; direct-asyncio + stub-LLM test confirms unwind. Real-DA-CLI host verification + opt-in gate consistency deferred to v1.2+ (owner-approved deviation, see `08-HUMAN-UAT.md`).
- [x] **DeepAgents CLI integration test** — ✓ Validated Phase 08: single sequential subprocess test exercises all six MCP tools (`wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log`) against a fresh `tmp_path` vault; gated behind `CODE_WIKI_RUN_INTEGRATION=1`.
- [ ] **Trace/observability polish** — improve `.code-wiki/traces/` format and the `code-wiki-agent trace` renderer.

_Deferred past v1.1:_
- **Open-source release prep** — README badges, contribution guide, public install instructions, PyPI publish dry-run. (Holding until the cost-frontier sweep validates the cost story.)
- **BED-01 live-Bedrock gate** — AWS onboarding now approved; verification folds into the cost-frontier sweep rather than standing as its own item.

_See "Out of Scope" below for items explicitly deferred past v1.x._

### Out of Scope

- **Custom TUI in v1** — DeepAgents CLI is the host; we ship MCP + headless CLI only. (Revisit if DeepAgents CLI proves inadequate.)
- **Non-Bedrock providers in v1** — no OpenRouter, no local Ollama, no direct Anthropic API. Bedrock is the only path for cost savings on Pat's setup. (Add later if eval shows clear gaps in Bedrock's lineup.)
- **Nested subagents** — only within-command fan-out in v1, no sub-subagents. (Optimization target for later if quality demands it.)
- **Vault format migration** — read-compatible means we don't rewrite the format. (No need; existing format works for Obsidian.)
- **Writing back to old lattice-wiki vaults during transition** — read yes, write no, until the new tool is validated. (Avoids dual-writer drift.)
- **Public PyPI release on day one** — build clean enough to open-source later, but no release pipeline yet. (Personal use first; release after eval validates the cost story.)
- **Real-time file watchers / auto-sync** — commands stay manually triggered, matching lattice-wiki today. (Out of scope unless a clear pain point emerges.)

## Context

**Prior work — the thing being reimplemented:**
- `/Users/pat/Personal/lattice/plugins/lattice-wiki` — Claude Code plugin, ~400 LOC of shims + slash commands
- `/Users/pat/Personal/lattice/packages/lattice-wiki-core` — Python core, ~4,400 LOC across 24 modules + 37 pytest files. v0.4.0, polished, stable schema
- Implements: container detection, monorepo scan, layout YAML IO, vault init, index generation, BM25 search, source ingestion, graph analysis, token counting, lint (mechanical + semantic), git state gating
- Already has a backend selector (`.lattice-wiki.json`) for Claude-Code-SDK vs Bedrock — proves Bedrock is feasible
- Today's subagents (scanner, librarian, linter, ingestor) are per-command and **sequential** — no internal fan-out; this is the big v2 lift

**Pat's experience:**
- Built lattice-wiki himself; deep familiarity with the design, iron rules, frontmatter schema, layout block convention, state-gate mechanism
- Strong opinions on what to preserve (iron rules, layout block, state gate, category-first indexing) and what could be revisited (hand-rolled YAML, bespoke argv parsing, BM25-only search)
- Wants this rewrite to pay back in two ways: lower per-run cost, and a clean eval foundation for future agent work in the monorepo

**Why Bedrock specifically:**
- Cost: a non-trivial Bedrock model lineup is cheaper than direct Anthropic for some calls; mixing in non-Claude models (Llama, Mistral, Nova) opens further savings
- Auth/infra already in place for Pat
- Concentrating on one provider in v1 lets the eval harness move fast — comparing 6 Bedrock models is simpler than comparing 6 models across 3 providers

**Why MCP server + headless CLI (not a custom TUI):**
- DeepAgents CLI already provides a competent conversation loop; rebuilding it is wasted work
- Exposing tools via MCP keeps the surface clean and makes the same core usable from other MCP hosts later (Claude Code, Cursor, etc.)
- Headless CLI is the escape hatch — when no host is running (CI, scripts), the agent loop still works

## Constraints

- **Tech stack**: Python 3.11+, `uv` workspace, `langchain` + `langchain-aws` + `deepagents` — chosen to match Pat's stack and to leverage deepagents' subagent primitives without rebuilding them
- **Model provider**: AWS Bedrock only in v1 — single-provider focus simplifies adapter layer and eval harness
- **Protocol**: MCP for the primary delivery surface — interoperates with DeepAgents CLI and other MCP hosts
- **Format compatibility**: must read existing lattice-wiki vaults without modification — preserve frontmatter schema, layout block format, wikilink/citation conventions
- **Budget**: personal project; no team; design for one-developer velocity
- **Audience**: Pat (now); open-source-ready hygiene (license, README, no secrets) for later release

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + `uv` monorepo | Pat's preferred Python tooling; `uv` workspaces fit the tiered (cores + agents) layout cleanly | Validated Phase 01 |
| LangChain + `deepagents` framework | Native subagent primitives; LangChain has mature `langchain-aws` Bedrock binding; deepagents matches the planned conversation host | Validated Phase 02 |
| AWS Bedrock only in v1 | Cost focus; Pat already has auth/setup; single-provider eval is simpler | Validated Phase 01 |
| MCP server as primary surface | DeepAgents CLI hosts the conversation; we expose tools; reusable from other MCP hosts | Validated Phase 01+03 |
| Headless CLI in addition to MCP | Same core, two surfaces; CLI runs full agent loop in-process for CI/scripts | Validated Phase 03 |
| Full parity with lattice-wiki v1 (5 commands) | Pat knows the territory; halfway parity creates a confusing transition with the existing tool | ✓ Validated Phase 05 |
| Within-command subagent fan-out (not nested) | Real parallelism wins (librarian across pages, linter rule-groups, scanner across packages) without the debugging cost of nested subagents | Validated Phase 02+03 |
| Read-compatible with existing vaults | Allows side-by-side use during transition; preserves Obsidian compatibility; no migration script needed | Validated Phase 01 |
| Eval = cost-frontier per subagent role, baselined from current tool | Direct measurement of the project's reason for existing; recorded-from-Sonnet baseline avoids hand-curation overhead | ✓ Validated Phase 04 (harness shipped; sweep run is v1.1 work) |
| Tiered monorepo (shared cores + agent packages) | Anticipates future agents reusing model adapters, subagent runtime, eval harness | Validated Phase 01 |
| Package named `code-wiki-agent` (not `lattice-wiki`) | Clearer description of what it does; avoids confusion with the existing TS plugin during the transition period | Validated Phase 01 |
| No custom TUI in v1 | DeepAgents CLI is sufficient; building a TUI is parallel work that doesn't help the cost-savings goal | Validated Phase 01 |
| Titan Embeddings v2 (`amazon.titan-embed-text-v2:0`, 1024 dims) for embedding search | No extra IAM grants beyond Phase 1 Bedrock access; native to langchain-aws BedrockEmbeddings | Validated Phase 03 |
| CLI-05 (`--config`) deferred; `--vault` used instead in Phase 03 | ROADMAP Phase 03 success criteria do not require `--config`; tracked for Phase 05 | ✓ Closed Phase 05-01 (`--config` global Typer callback + `WikiConfig`) |
| ONE `wiki_ingest` MCP tool with `type: Literal['source','work-item']` discriminator (not two tools) | Single discoverable tool simplifies the MCP surface; type-narrowing happens server-side; matches `lattice-wiki:ingest` semantics | Validated Phase 05 |
| Inline port of `lint_wiki.py:scan()` (mechanical pass) + 3-way SubagentPool fan-out for semantic pass | Mechanical rules are deterministic — porting verbatim avoids re-implementation bugs; LLM-driven semantic checks parallelize cleanly across rule groups | Validated Phase 05 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**Last updated:** 2026-05-17 — Phase 08 (host-reliability) complete: MCP cancellation + DeepAgents CLI integ test + docs/cancellation.md shipped. Two SC deviations approved (real-DA-CLI host + opt-in gate deferred to v1.2+, see 08-HUMAN-UAT.md).

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-15 — milestone v1.1 Quality Improvements scoped. Lattice-wiki SKILL.md content port leads (close the output-quality gap before measuring), then cost-frontier sweep runs against the improved agent, then MCP cancel polish + DeepAgents CLI stdio integration test + trace renderer cleanup. BED-01 live-gate now unblocked (AWS approved); folds into the sweep.*
