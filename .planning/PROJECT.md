# deep-agents

## What This Is

A Python monorepo (managed with `uv`) of LangChain/deepagents-based AI tooling. The first package, **`graph-wiki-agent`**, is a reimplementation of the upstream `lattice-wiki` Claude Code plugin (being ported in this repo as `graph-wiki`) — packaged as both an MCP server (consumed by the DeepAgents CLI) and a headless CLI that runs the full agent loop. It exists primarily so Pat can run the same wiki workflows on AWS Bedrock with within-command subagent fan-out for cost and context savings.

## Core Value

**Faithfully reproduce the upstream lattice-wiki plugin's wiki-maintenance workflows (now ported as `graph-wiki`) while running entirely on AWS Bedrock with parallel subagents, so the same outcomes can be achieved at meaningfully lower cost than the current Claude-Code-hosted plugin.**

If everything else fails, a Bedrock-driven `graph-wiki-agent query "..."` (or the equivalent MCP tool call) must return answers as good as today's upstream lattice-wiki librarian, on cheaper models, faster.

## Current State: v1.3 Shipped — 2026-05-20

**Shipped:** v1.0 (graph-wiki-agent parity, 2026-05-15) + v1.1 (Quality Improvements, 2026-05-17) + v1.2 (Graph-Wiki Port & Debt Cleanup, 2026-05-19) + v1.3 (Tooling Cleanup, 2026-05-20). 21 phases, 110 plans, 145/145 requirements satisfied across four milestones.

**What works today (post-v1.3):**
- `graph-wiki-agent {init|scan|ingest|query|lint|log|trace}` — full graph-wiki workflow on Bedrock with within-command subagent fan-out
- All MCP tools exposed via `graph-wiki-mcp` stdio server; verified end-to-end via DA-CLI integration test
- Agent prompts incorporate canonical SKILL.md content; divergence eval flags remaining drift
- Cost-frontier validated: per-workspace `<workspace>/.graph-wiki.yaml` `plugins[].roles[]` block carries the role-model map; packaged `models.toml` is the per-role fallback
- Trace renderer with per-(role,model) cost rollup, `usage_metadata` populated across all 4 production fan-out callsites
- Subagent context completion: `wiki/CLAUDE.md` layout + style + log format injected into scanner/linter/ingestor system prompts
- `packages/workspace-io/` owns workspace bootstrap + manifest IO + config resolution under the `graph-wiki` brand; `vault-io._workspace` delegates to it; `.graph-wiki.yaml` is the per-workspace manifest filename; `GRAPH_WIKI_WORKSPACE` is the env override
- `plugins/graph-wiki/` is the ported Claude Code plugin (runs on Claude Code inference, NOT a wrapper around `graph-wiki-agent`); `/graph-wiki:*` namespace; `/graph-wiki:bootstrap` (renamed from `/graph-wiki:init` in v1.3 Phase 18 so Claude Code's native `/init` is reachable)
- **New in v1.3:** vault-io scan no longer reports 28 phantom companion-page deletions; CountTokens API uses correct `input=...` boto3 shape; workspace/repo resolution works at the v2 `<workspace>/wiki/` layout
- **New in v1.3:** Agent package mechanically renamed `code-wiki-agent → graph-wiki-agent` across the full repository (Phase 21 — `git mv` preserved history; brand-gate enforces no reintroduction)
- **New in v1.3:** Phase 16 review burndown complete — 15 findings dispositioned (13 fixed + 2 no-action); `19-REVIEW-BURNDOWN.md` is the canonical record

**Workspace rename history:** `cores/` → `packages/` (commit `c5a47ba`, v1.1). Brand rename `lattice` → `graph-wiki` swept in v1.2 Phase 12. Agent package rename `code-wiki-agent` → `graph-wiki-agent` swept in v1.3 Phase 21.

## Current Milestone: v1.4 Workspace Path Resolution Cleanup

**Goal:** Eliminate `vault`/`vault_path` nomenclature globally. The canonical input becomes `workspace_path`; the wiki dir is always derived via `workspace_io.paths.wiki_dir()`. Hard-rename external surfaces (MCP, CLI) with no back-compat. Fix one known bootstrap bug along the way.

**Target features:**

1. **Internal API rename** — `resolve_wiki_and_repo(workspace_path, repo_path)`, all 6 command `run_*` signatures, all test mock setups, `.graph-wiki.local.yaml` key rename (`graph-wiki-directory` → `workspace-directory`).
2. **External surface rename** — 6 MCP tool fields (`vault_path` → `workspace_path`), 7 Typer flags (`--vault` → `--workspace`), scan JSON field (`vault_path` → `wiki_relative_path`), plugin doc sync.
3. **eval-harness sweep** — `vault_path` params across `sweep.py`/`baseline.py`/`structural.py`/`divergence/*.py`; bare `vault:` in divergence helpers → `wiki:`.
4. **Packages-dir misclassification fix** — `_classify_dir` heuristic accepts majority-manifested dirs as `package`; `--interactive` opt-in on bootstrap (closes pending todo 2026-05-20).

**Key context:**
- Phase numbering continues from Phase 21 → v1.4 starts at Phase 22.
- No research needed — mechanical rename + one localized bug fix.
- Hard-rename strategy: breaks any external MCP consumer; DA-CLI integration test updates in the same phase as the schema rename.
- Carry-forward items from v1.3 (Nyquist decision, plugin smoke transcript, manual UAT, slug-only regex fix) are **not** in v1.4 — they remain candidates for v1.5.

## Deferred to v1.5+

- **Nyquist compliance retroactive decision** — 0/16 v1.1+v1.2+v1.3 phases produced VALIDATION.md despite the toggle being enabled. Decide: retro-validate the 16 phases vs. disable the toggle.
- **Phase 14 SC#4 plugin smoke transcript** — manual `/graph-wiki:query` transcript not captured at v1.2 close; carried forward through v1.3 close.
- **Phase 18 SC#3 manual UAT** — install graph-wiki plugin in Claude Code, type `/init`, confirm native CLAUDE.md workflow fires. By-design manual gate from v1.3 Phase 18 D-07.
- **`librarian.py:21` `_SLUG_ONLY_RE` parity fix** — out-of-scope observation from v1.3 Phase 19 (same issue as the synthesizer fix; not load-bearing today).

**Explicitly out of v1.x (deferred to v2.0+):**
- Open-source release prep (README badges, contribution guide, PyPI publish dry-run) → **v2.0 GA**.
- `work/` subsystem port — GSD covers work-item lifecycle (thread decision 2026-05-17).
- Package-family monorepo support restoration — different approach planned (thread decision 2026-05-17).
- Modules where vault-io was ahead of upstream lattice — leave as-is per spike 002 / v1.2 Phase 12 verdicts.

Full v1.3 retrospective in `.planning/RETROSPECTIVE.md`; v1.3 archive in `.planning/milestones/v1.3-ROADMAP.md`; v1.3 audit in `.planning/milestones/v1.3-MILESTONE-AUDIT.md`.

## Requirements

### Validated

#### Milestone v1.2 SHIPPED — 2026-05-19 (Graph-Wiki Port & Debt Cleanup)

30/30 requirements satisfied across Phases 11-16. Full detail: `.planning/milestones/v1.2-ROADMAP.md` and `.planning/milestones/v1.2-REQUIREMENTS.md`.

- ✓ **workspace-io package shipped** — v1.2 (WS-01..10): new `packages/workspace-io/` ported from upstream `lattice-workspace` with `.graph-wiki.yaml` manifest, `GRAPH_WIKI_WORKSPACE` env var, `GraphWikiConfig` dataclass; `vault-io._workspace.resolve_wiki_and_repo` delegates to `workspace_io.config.resolve()`; 67 ported tests green; two-phase `graph-wiki-agent init` bootstrap.
- ✓ **Selective drift backport** — v1.2 (BACKPORT-01..04): body-diff inventory of 11 overlapping modules between `vault-io` and upstream `lattice-wiki-core` at pinned SHA; zero PORT verdicts (every drift hunk intentional or out-of-v1.2 subsystem); decisions logged in `packages/vault-io/DRIFT-DECISIONS.md`.
- ✓ **Ecosystem rebrand complete** — v1.2 (BRAND-01/02/04): `lattice` → `graph-wiki` (kebab) / `graph_wiki` (snake) swept across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` in 5 atomic commits; `scripts/check-brand.sh` + `.brand-grep-allow` grep-gate enforces ongoing discipline; `.planning/spikes/CONVENTIONS.md` corrected.
- ✓ **Plugin contract locked + ported** — v1.2 (PLUGIN-01..05): Phase 13 produced CONTRACT-INDEX.md + SHELL-OUT-PATTERN.md locking that the ported `plugins/graph-wiki/` plugin runs on **Claude Code inference** (not a wrapper around `graph-wiki-agent`); Phase 14 ported the plugin with renamed `plugin.json` id, `/graph-wiki:*` namespace, agent/skill renames, and shims wired through vault-io. Phase 14 prerequisite: `vault_io.lint_wiki` (~509 LOC) + `vault_io.wiki_search` (~194 LOC) verbatim-ported from upstream (VP-01).
- ✓ **Wiki self-update** — v1.2 (BRAND-03): `~/Personal/wiki/deep-agents` re-scanned + OTel re-ingested + librarian query run against post-rebrand codebase via Claude role-override profile (Haiku 4.5 fan-out + Sonnet 4.6 reasoning); 3 operational deviations auto-fixed inline.
- ✓ **v1.1 carry-forward debt closed** — v1.2 (TRACE-FU-01, SWEEP-FU-02/03/04, MCP-CAN-01/02, MODEL-FU-01): `TaskResult` contract on `SubagentPool` threads `response.usage_metadata` into JSONL traces; all 4 fan-out callsites emit non-None tokens/cost; DivergenceMetric wired through all 6 in-scope roles with code_reader + synthesizer rubrics; scanner re-swept against fresh-package vault; MCP wire-level cancel re-deferred behind event-driven trigger (langchain-aws#663 OR aioboto3 GA); integration-gate convention codified + grep-enforced; synthesizer model_id assertion locked to Qwen reality.

#### Milestone v1.1 SHIPPED — 2026-05-17 (Quality Improvements)

29/29 requirements satisfied across Phases 6-10. Full audit: `.planning/milestones/v1.1-MILESTONE-AUDIT.md`.

- ✓ **Lattice-wiki SKILL.md content ported** — v1.1 (PORT-01..06): librarian/ingestor/linter/scanner prompts incorporate canonical iron rules, citation rules, ingestion patterns, lint rule definitions, and scanner package-detection rules via 8 shared fragments under `prompts/_fragments/` with `# Source: / # Anchor:` provenance comments
- ✓ **Divergence detection eval shipped** — v1.1 (EVAL-11..13): 15 programmatic check rules + 4 LLM-judge rubrics + 37 unit tests + regression gate (`--accept-divergence-baseline`); flagged 0 hard-severity divergences against lattice-wiki baseline
- ✓ **Cost-frontier sweep validated the cost story** — v1.1 (SWEEP-01..05): two-gate scoring across 6 in-scope roles (corrected from "7" in original roadmap — 2 judges out of scope); BED-01 live-gate confirmed; `models.toml` defaults updated with provenance comments; full results doc under `.planning/sweep/`
- ✓ **Trace schema versioned + cost-aware renderer** — v1.1 (OBS-04..06): `schema_version: 1` stamped on every JSONL record; renderer surfaces per-(role,model) cost rollup with `(+K unknown)` accounting; collapses repeated subagent groups by default with `--expand` flag

#### Phase 10 Complete — 2026-05-17 (subagent-context-completion)
- [x] Four shared fragments shipped under `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/` — `architecture_overview.py`, `style_rules.py`, `log_format.py`, `claude_md_disambiguation.py` — each with the standard `# Source: / # Anchor: / # Source-commit:` provenance header (CTX-01, CTX-02)
- [x] `prompts/project_context.py::render_project_context(wiki_path)` reads `wiki/CLAUDE.md` (or `AGENTS.md` fallback), parses the embedded layout block via existing `vault_io.layout_io`, returns deterministic ~30-line block or `""` on missing schema files (CTX-03)
- [x] Four prompt builders converted to `build_X_system(project_context="")` functions (scanner, linter, ingestor, librarian) with backward-compat module-level `*_SYSTEM` constant aliases preserved; three commands (scan, lint, ingest) wire `render_project_context()` at SystemMessage construction (CTX-03)
- [x] Snapshot tests in `test_prompt_snapshots.py` cover with-context, without-context, and missing-CLAUDE.md degradation paths — 14 snapshots, 26 prompt tests total pass (CTX-04)
- [x] Token-budget regression in `test_token_budget.py` enforces +1500 tokens per role ceiling; ingestor tightest at +751/1500 headroom (CTX-05)
- [x] Phase 6 divergence eval re-run live against AWS Bedrock (`GRAPH_WIKI_RUN_EVAL=1`) — librarian/ingestor/linter/scanner all PASSED, no hard-severity regression (CTX-05)

#### Phase 08 Complete — 2026-05-17 (host-reliability)
- [x] MCP cancellation wired through `SubagentPool.run_all` — per-item `status: cancelled` trace records and single `event: batch_cancelled` terminal record on cancel; `_write_trace` / `_write_batch_terminal` never raise (MCP-09, MCP-10)
- [x] Deterministic in-process asyncio cancel test with stubbed LLM — zero Bedrock cost (MCP-11)
- [x] `WikiScanInput.repo_path` field added so the E2E test can scope `wiki_scan` to a `tmp_path` vault (DACLI-01)
- [x] Single sequential E2E integration test exercises all six MCP tools as a stdio subprocess against a fresh `tmp_path` vault; gated behind `GRAPH_WIKI_RUN_INTEGRATION=1` (DACLI-02, DACLI-03)
- [x] `docs/cancellation.md` — v1.1 reference for `notifications/cancelled` protocol, internal unwinding chain, trace shapes, orphan-thread limitation, v1.2+ paths

#### Milestone v1.0 SHIPPED — 2026-05-15 (graph-wiki-agent parity)
- [x] **Phase 04 (Eval Harness)** — `cores/eval-harness` package with fixture corpus (3 repos), headless `claude -p` baseline recorder (EVAL-08 schema), `deepeval` 4.0 integration with `AmazonBedrockModel`, heterogeneous two-judge panel (claude-sonnet-4-6 + nova-pro-v1:0), cost-frontier sweep runner (`pytest-evals`), regression-check AssertionError gate, structural metrics (cites code path / wikilinks resolve / valid frontmatter) (EVAL-01..10)
- [x] **Phase 05 (Remaining Commands)** — `init`, `scan`, `ingest`, `lint`, `log` shipped on both MCP and headless CLI surfaces with a single shared command implementation; `scan` and `lint` use SubagentPool fan-out (scanner across packages; linter across 3 rule-groups); `ingest` routes to package/concept/adr pages via a single ingestor LLM call; `--config` global Typer callback + `WikiConfig` dataclass (CMD-01..08, MCP-01..08, CLI-01..07)

#### Phase 03 Complete — 2026-05-14 (query-vertical-slice-hybrid-search)
- [x] Hybrid search: BM25 via `bm25s` + Titan v2 embeddings in SQLite (WAL), sha256 incremental rebuild, RRF fusion (SEARCH-01..06)
- [x] `commands/query.py` — shared `run_query()` pipeline: hybrid search → librarian fan-out (SubagentPool) → synthesizer → QueryResult (CMD-04, CLI-03)
- [x] `graph-wiki-agent query` CLI subcommand with `--top-k`, `--vault`, `--json`, `--no-state-gate` (CLI-01..07, CMD-07, CMD-08)
- [x] `wiki_query` MCP tool with Pydantic schemas, `ctx.report_progress()` notifications (MCP-02, MCP-04, MCP-06, MCP-07)
- [x] G1 citation resolver normalises `.md`-suffixed wikilinks correctly (regression caught in UAT)
- [x] 54 unit tests; 3 integration tests gated behind `GRAPH_WIKI_RUN_INTEGRATION=1`

#### Phase 02 Complete — 2026-05-14 (subagent-fan-out-runtime)
- [x] `SubagentPool.run_all()` with partial-failure isolation, semaphore throttle, per-role concurrency (SUB-01..07)
- [x] Structured JSONL trace output to `.graph-wiki/traces/` for every fan-out call (OBS-01)
- [x] `graph-wiki-agent trace` CLI subcommand renders traces as human-readable timeline (OBS-02, OBS-03)
- [x] Real-Bedrock integration tests: 4-parallel with 1 intentional failure → 3 successes, no sibling cancellation (BED-02..05)

#### Phase 01 Complete — 2026-05-13 (infrastructure-vault-io-and-mcp-skeleton)
- [x] `uv` workspace at repo root with tiered layout: `cores/vault-io`, `cores/model-adapter`, `agents/graph-wiki-agent`
- [x] Project license + README seeded (MIT, open-source-ready)
- [x] Bedrock model adapter — `make_llm("haiku")` invokes real `ChatBedrockConverse`; `BedrockAccessDenied` raised with ARN on bad credentials
- [x] Vault IO round-trip — reading-then-writing every page produces byte-identical output (29 tests pass)
- [x] MCP stdio surface — FastMCP `graph-wiki-mcp` server with `_StdoutGuard`; `wiki_ping` tool; provably stdout-clean
- [x] CI pipeline (ruff + pytest); ruff clean (`ruff check .` and `ruff format --check .` both exit 0)
- [x] **Read-compatible with existing vaults** — preserve frontmatter, layout block, wikilinks, file-map format

### Active

_Milestone v1.3 (Tooling Cleanup) — requirements live in `.planning/REQUIREMENTS.md` after `/gsd:new-milestone` scoping. See "Current Milestone" section above for the goal + target features._

_Carry-forward acknowledgments NOT in v1.3 scope (documented tech debt, not blockers):_
- **Nyquist compliance** — 0/5 v1.1 + 0/6 v1.2 phases reached `nyquist_compliant: true` despite toggle enabled. Decide: retro-validate the 11 phases or disable the toggle. Deferred past v1.3.
- **Phase 14 SC#4 plugin smoke transcript** — accepted on structural evidence at close; capture as regression artifact in a later milestone.
- **`next-milestone-planning` thread** — carried forward through v1.0 → v1.1 → v1.2 → v1.3; close at v1.3 close or convert to requirements at v1.4 scoping.
- **MCP wire-level cancel deferral** — re-anchored to event-driven trigger (langchain-aws#663 merged OR aioboto3 GA/1.0), not calendar date. See `docs/cancellation.md §5`.

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
| Package named `graph-wiki-agent` (not `lattice-wiki`) | Clearer description of what it does; avoids confusion with the existing TS plugin during the transition period | Validated Phase 01 |
| No custom TUI in v1 | DeepAgents CLI is sufficient; building a TUI is parallel work that doesn't help the cost-savings goal | Validated Phase 01 |
| Titan Embeddings v2 (`amazon.titan-embed-text-v2:0`, 1024 dims) for embedding search | No extra IAM grants beyond Phase 1 Bedrock access; native to langchain-aws BedrockEmbeddings | Validated Phase 03 |
| CLI-05 (`--config`) deferred; `--vault` used instead in Phase 03 | ROADMAP Phase 03 success criteria do not require `--config`; tracked for Phase 05 | ✓ Closed Phase 05-01 (`--config` global Typer callback + `WikiConfig`) |
| ONE `wiki_ingest` MCP tool with `type: Literal['source','work-item']` discriminator (not two tools) | Single discoverable tool simplifies the MCP surface; type-narrowing happens server-side; matches `lattice-wiki:ingest` semantics | Validated Phase 05 |
| Inline port of `lint_wiki.py:scan()` (mechanical pass) + 3-way SubagentPool fan-out for semantic pass | Mechanical rules are deterministic — porting verbatim avoids re-implementation bugs; LLM-driven semantic checks parallelize cleanly across rule groups | Validated Phase 05 |
| Prompt content lives in `prompts/` Python module per role with provenance comments (not separate markdown files) | Drift detection: provenance comments + snapshot tests + import-based sourcing make divergence visible in code review | ✓ Validated Phase 06 |
| Two-gate qualification (Gate 1 = divergence vs. baseline, Gate 2 = LLM-judge quality) for cost-frontier sweep | Cheap models that pass divergence checks but produce subjectively worse output need to be filtered — neither gate alone is sufficient | ✓ Validated Phase 07 |
| `models.toml` updated to Qwen3-32B fan-out + Qwen3-80B synthesis as the cost-optimal default | Sweep data showed Qwen variants meet quality bar at meaningful cost reduction vs Claude defaults | ✓ Validated Phase 07 |
| Cancel test uses direct asyncio + stub LLM (deviation from "under real DA-CLI host" wording) | FastMCP SDK validates MCP protocol framing; aioboto3 not yet available for wire-level Bedrock cancel | ✓ Validated Phase 08 (scope narrowing documented in `docs/cancellation.md §4`; owner-acknowledged) |
| Single sequential E2E integration test (not 6 separate tests) exercising all MCP tools against tmp_path vault | One stdio subprocess spawn amortized across all tools; matches DA-CLI runtime shape; gated to opt-in for cost discipline | ✓ Validated Phase 08 |
| `schema_version: 1` stamped as first key on every trace JSONL record + lenient consumer that warns once per file on v0 or higher-than-known | Allows future schema evolution without breaking existing renderers; warn-but-render avoids silent skips | ✓ Validated Phase 09 |
| `render_project_context()` at command entry (not per-subagent invocation) | Render once, pass through; respects token budget (+1500 cap per role); avoids redundant `wiki/CLAUDE.md` reads on fan-out | ✓ Validated Phase 10 |
| No deepagents `SubAgentMiddleware` migration — keep existing `SubagentPool` dispatch | Architectural cost of migration outweighs the context-injection benefit; fragment curation pattern + project_context renderer achieve the same outcome | ✓ Validated Phase 10 |
| `wiki-config.toml` and `.graph-wiki.yaml` are different surfaces — no migration script (WS-10, 2026-05-18) | `wiki-config.toml` (repo root) is the runtime CLI config read by `WikiConfig` dataclass — fields `{models_path, vault_path}` — pointing the CLI at models + a default vault. `.graph-wiki.yaml` (per workspace) is the manifest read/written by `workspace_io.manifest` — fields `{version, initialized_at, plugins[{name, installed_version, applied_version}]}` — tracking which plugins initialized the workspace. The two coexist with no overlap, so no migration is needed; per D-05 the existing throwaway `~/Personal/wiki/deep-agents/` is deleted and re-inited via `graph-wiki-agent init` rather than migrated. | ✓ Validated Phase 11 |
| **Plugin shell-out via `uv run --project "$DEEP_AGENTS_ROOT"`** (SO-01, v1.2) | Plugin scripts at `plugins/graph-wiki/scripts/*.py` shell out to deep-agents Python helpers via `uv run --project "$DEEP_AGENTS_ROOT" python3 -m ...`; backend selection per command via `[plugin]` block in `.graph-wiki.yaml` (SO-03), defaulting to `claude` everywhere with `bedrock` as documented per-command opt-in. | ✓ Validated Phase 14 |
| **`TaskResult` contract on `SubagentPool.run_all`** (TRACE-FU-01, v1.2) | All fan-out callbacks return a `TaskResult` wrapping the LangChain `AIMessage.usage_metadata` instead of raw scalars. JSONL trace records now emit non-None `tokens_in` / `tokens_out` / `cost_usd` per item; gated regression test verifies against real Bedrock. | ✓ Validated Phase 16 |
| **MCP wire-level cancel deferral re-anchored to event trigger** (Phase 16 D-09, 2026-05-19) | Calendar re-evaluation dates generated noise without changing the gate outcome. Replaced with event-driven trigger: re-evaluate when `langchain-aws#663` merges OR aioboto3 GA/1.0 lands. Anchored signal, no scheduled toil. | ✓ Validated Phase 16 |
| **No `lattice` symbols survive in-scope** (BRAND-04, v1.2) | `scripts/check-brand.sh` runs `grep -rE` across packages/agents/plugins/.planning/CLAUDE.md and pipes through `.brand-grep-allow` (52 intentionally-preserved historical refs). Exit non-zero on unallowlisted hit. Runs as a normal pytest gate. | ✓ Validated Phase 12 |
| Phase 13 (M3a) — graph-wiki plugin contract surface locked (SP-05, 2026-05-18) | Foundational reframe: the ported graph-wiki plugin runs on **Claude Code inference** (P-01) — it is NOT a wrapper around `graph-wiki-agent`. `graph-wiki-agent` (Bedrock-backed CLI + MCP server) stays as the separate, headless, cost-frontier surface. The two coexist as parallel surfaces over the same underlying Python helpers in `vault-io` / `workspace-io`. Verdicts: 6 upstream commands rename or reshape (`init`, `scan`, `ingest`, `lint`, `query`, `log`) + 3 dropped (`archive`, `regen-index`, `status` — work-layer out of v1.2 per C-01). Shell-out shape: `uv run --project "$DEEP_AGENTS_ROOT" python3 ...` (SO-01) with the `[plugin]` backend-selector block in `.graph-wiki.yaml` (SO-03); backend defaults to `claude` everywhere, `bedrock` is the documented per-command opt-in (P-02). Phase 14 prerequisite: `lint_wiki.py` (~508 LOC) and `wiki_search.py` (~194 LOC) must be ported into `packages/vault-io/` as Phase 14 Plans 1 and 2 respectively before the `/graph-wiki:lint` and `/graph-wiki:query` shims can shell out (VP-01). Source-of-truth spec: [`.planning/spec/13-plugin-contract/CONTRACT-INDEX.md`](.planning/spec/13-plugin-contract/CONTRACT-INDEX.md) (audit summary) and [`.planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md`](.planning/spec/13-plugin-contract/SHELL-OUT-PATTERN.md) (cross-cutting decisions). | ✓ Validated Phase 13 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**Last updated:** 2026-05-20 — milestone v1.4 (Workspace Path Resolution Cleanup) STARTED. Scope: 3-phase `vault`/`vault_path` → `workspace`/`workspace_path` rename (internal API, external MCP+CLI surface, eval-harness) + packages-dir misclassification bug fix. Phase numbering continues from Phase 22.

**Prior update:** 2026-05-20 — milestone v1.3 (Tooling Cleanup) SHIPPED. 5 phases, 25 plans, 19/19 requirements satisfied.

**Earlier:** 2026-05-19 — milestone v1.2 (Graph-Wiki Port & Debt Cleanup) SHIPPED. 6 phases, 21 plans, 30/30 requirements satisfied.

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
*Last updated: 2026-05-20 — milestone v1.4 Workspace Path Resolution Cleanup STARTED (phase numbering continues from Phase 22). 21 phases / 110 plans / 145/145 requirements shipped across v1.0+v1.1+v1.2+v1.3. v1.4 requirements in `.planning/REQUIREMENTS.md`; roadmap in `.planning/ROADMAP.md`.*
