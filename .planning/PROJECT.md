# deep-agents

## What This Is

A Python monorepo (managed with `uv`) of LangChain/deepagents-based AI tooling. The first package, **`code-wiki-agent`**, is a reimplementation of the existing `lattice-wiki` Claude Code plugin — packaged as both an MCP server (consumed by the DeepAgents CLI) and a headless CLI that runs the full agent loop. It exists primarily so Pat can run the same wiki workflows on AWS Bedrock with within-command subagent fan-out for cost and context savings.

## Core Value

**Faithfully reproduce lattice-wiki's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.**

If everything else fails, a Bedrock-driven `code-wiki-agent query "..."` (or the equivalent MCP tool call) must return answers as good as today's lattice-wiki librarian, on cheaper models, faster.

## Requirements

### Validated

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

#### Monorepo & Tooling
- [ ] `uv` workspace at repo root with tiered layout: shared core packages + agent packages
- [ ] Initial shared cores: model adapters (Bedrock), subagent runtime, eval harness
- [ ] Project license + README seeded so it can go public later without rework

#### `code-wiki-agent` — Full parity with lattice-wiki
- [ ] `init` — bootstrap wiki vault, discover containers, write CLAUDE/AGENTS/.cursorrules schema files
- [ ] `scan` — walk repo, diff packages vs vault, create/update stubs, flag renames/deletions, update index + log
- [ ] `ingest` — extract source text/metadata, route to package/concept/adr page, update cross-references
- [x] `query` — hybrid BM25+embedding search, librarian fan-out, synthesizer; `--json` output with search_scores; MCP + CLI surfaces (Phase 03)
- [ ] `lint` — mechanical pass (orphans, broken links, stale pages, missing frontmatter, code-drift) + semantic pass + actionable report
- [ ] `log` — append timestamped events to `log.md`
- [ ] **Read-compatible with existing vaults** — preserve frontmatter, layout block, wikilinks, file-map format so Obsidian and the old plugin still work side-by-side

#### Subagent fan-out (within-command parallelism)
- [x] Librarian drills multiple pages in parallel (Phase 03 — via SubagentPool)
- [ ] Linter runs rule-groups concurrently
- [ ] Scanner reviews packages in parallel
- [ ] All subagents are deepagents-native and routable to different Bedrock models per role

#### Delivery surfaces
- [ ] **MCP server mode** — exposes each command as an MCP tool; DeepAgents CLI hosts the conversation
- [ ] **Headless CLI mode** — `code-wiki-agent <command> [...args]` runs the full agent loop in-process on Bedrock; suitable for CI, scripts, cron

#### Eval & test suite
- [ ] Baseline corpus: record outputs of current `lattice-wiki` (Claude Sonnet via Claude Code) against fixture repos
- [ ] Per-subagent eval harness: swap models (Haiku/Sonnet/Llama/etc on Bedrock) holding prompts fixed; score against baseline
- [ ] Cost-frontier report: per-role chart of quality vs $/run; pick cheapest-while-good per role
- [ ] Standard pytest unit/integration tests for non-LLM logic (vault IO, frontmatter parsing, BM25, container detection, lint rules)

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
| Full parity with lattice-wiki v1 (5 commands) | Pat knows the territory; halfway parity creates a confusing transition with the existing tool | In progress — Phase 05 |
| Within-command subagent fan-out (not nested) | Real parallelism wins (librarian across pages, linter rule-groups, scanner across packages) without the debugging cost of nested subagents | Validated Phase 02+03 |
| Read-compatible with existing vaults | Allows side-by-side use during transition; preserves Obsidian compatibility; no migration script needed | Validated Phase 01 |
| Eval = cost-frontier per subagent role, baselined from current tool | Direct measurement of the project's reason for existing; recorded-from-Sonnet baseline avoids hand-curation overhead | Planned Phase 04 |
| Tiered monorepo (shared cores + agent packages) | Anticipates future agents reusing model adapters, subagent runtime, eval harness | Validated Phase 01 |
| Package named `code-wiki-agent` (not `lattice-wiki`) | Clearer description of what it does; avoids confusion with the existing TS plugin during the transition period | Validated Phase 01 |
| No custom TUI in v1 | DeepAgents CLI is sufficient; building a TUI is parallel work that doesn't help the cost-savings goal | Validated Phase 01 |
| Titan Embeddings v2 (`amazon.titan-embed-text-v2:0`, 1024 dims) for embedding search | No extra IAM grants beyond Phase 1 Bedrock access; native to langchain-aws BedrockEmbeddings | Validated Phase 03 |
| CLI-05 (`--config`) deferred; `--vault` used instead in Phase 03 | ROADMAP Phase 03 success criteria do not require `--config`; tracked for Phase 05 | Deferred to Phase 05 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**Last updated:** 2026-05-14 — Phase 03 complete

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
*Last updated: 2026-05-13 — Phase 2 complete (SubagentPool with parallel fan-out, role-based model routing, cost tracking, trace logging — all integration tests passed against live Bedrock)*
