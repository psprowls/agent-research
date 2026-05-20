# Milestones

## v1.2 Graph-Wiki Port & Debt Cleanup (Shipped: 2026-05-19)

**Phases completed:** 6 phases, 21 plans
**Timeline:** 2026-05-17 → 2026-05-19 (~3 calendar days, dense execution)
**Git range:** `92e26fd` → `HEAD` (205 commits)
**Diff:** 715 files changed, +33,296 / −2,412 lines
**Requirements:** 30/30 v1.2 requirements satisfied
**Audit:** none — milestone closed without formal `/gsd:audit-milestone` run (proceeded on green Phase 11-16 VERIFICATION.md + Phase 16 UAT closure)

**Delivered:** Ported `lattice-workspace` into a new `workspace-io` package, swept the `lattice` → `graph-wiki` rebrand across the entire ecosystem, locked + ported the `graph-wiki` Claude Code plugin (`/graph-wiki:*`), re-synced the project's own wiki against the post-rebrand codebase, and closed the v1.1 carry-forward debt around trace pipeline, sweep coverage, MCP cancellation, and model config drift.

### Key accomplishments

- **workspace-io package shipped** — new `packages/workspace-io/` ported from upstream `lattice-workspace` with `.graph-wiki.yaml` manifest filename (replacing legacy `.lattice.yaml`), `GRAPH_WIKI_WORKSPACE` env var, `GraphWikiConfig` dataclass, and `workspace_io.config.resolve()` upward-walk discovery; `vault-io._workspace.resolve_wiki_and_repo` rewritten as a 2-line delegation shim preserving the explicit-vault_path MCP boundary; 67 ported tests green under `uv run --package workspace-io pytest`; `graph-wiki-agent init` performs two-phase bootstrap (`workspace_io.init` first, then `init_wiki`); 18 `GRAPH_WIKI_REAL_VAULT_PATH` references swept to `GRAPH_WIKI_WORKSPACE` across CLI help, MCP tool descriptions, Pydantic Field descriptions, and docstrings (WS-01..10).
- **Selective drift backport** — body-diff inventory of 11 overlapping modules between `vault-io` and upstream `lattice-wiki-core` pinned at a fixed SHA; canonical `packages/vault-io/DRIFT-DECISIONS.md` published with verdicts. Zero PORT verdicts: every drift hunk is an intentional vault-io divergence (lib-ification / MCP error handling / no-tiktoken) or out-of-v1.2 subsystem strip (package-family / CLI `main()`) (BACKPORT-01..04).
- **Ecosystem rebrand complete** — `lattice` / `LATTICE` / `lattice_workspace` / `lattice_wiki_core` swept to `graph-wiki` (kebab) / `graph_wiki` (snake) across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` in 5 atomic commits with `uv run pytest` gated green after each; `scripts/check-brand.sh` + `.brand-grep-allow` enforces ongoing brand discipline; `.planning/spikes/CONVENTIONS.md` `cores/` → `packages/` corrected (BRAND-01/02/04).
- **Plugin contract locked then ported** — Phase 13 (M3a) produced 9-row CONTRACT-INDEX.md (6 commands rename/reshape, 3 dropped per C-01 work-layer scope-out) + SHELL-OUT-PATTERN.md (SO-01..04) locking that the ported plugin runs on **Claude Code inference** (P-01) — NOT a wrapper around `graph-wiki-agent`. The Bedrock-backed `graph-wiki-agent` stays as the parallel cost-frontier surface; the two coexist over the same `vault-io` / `workspace-io` helpers. Phase 14 (M3b) ported the plugin to `plugins/graph-wiki/` with renamed `plugin.json` id, `/graph-wiki:*` namespace, agent/skill rename, and shims wired through vault-io; `workspace_io` manifest extended with `[plugin]` backend-selector block (PLUGIN-01..05).
- **Phase 14 prerequisite ports landed** — `vault_io.lint_wiki` (~509 LOC) and `vault_io.wiki_search` (~194 LOC) verbatim-ported from upstream `lattice_wiki_core` with brand rename and `_version_check` removal, unblocking the `/graph-wiki:lint` and `/graph-wiki:query` plugin shims (VP-01).
- **Project's own wiki self-updated** — `~/Personal/wiki/deep-agents` re-scanned + OTel re-ingested + librarian query run via `graph-wiki-agent` using a one-off Claude role-override profile (Haiku 4.5 fan-out + Sonnet 4.6 reasoning) to bring the wiki into alignment with the post-rebrand codebase; 3 operational deviations encountered and auto-fixed inline (`--config` doesn't propagate `vault_path` to subcommands; stale `cores/` container name in wiki CLAUDE.md; BM25 index requires manual rebuild after scan), documented in `15-VERIFICATION.md` (BRAND-03).
- **v1.1 carry-forward debt closed** — `TaskResult` contract on `SubagentPool.run_all` threads `response.usage_metadata` into JSONL traces; all 4 production fan-out callsites (scanner, linter, librarian, code_reader) emit non-None tokens_in/tokens_out/cost_usd on per-item trace records; gated TRACE-FU-01 regression passes against real Bedrock. DivergenceMetric wired through all 6 in-scope roles with rubrics for code_reader + synthesizer; 6 code_reader cases re-tuned against post-rebrand surfaces; scanner re-swept against fresh-package vault (65% deterministic SCANNER_CHECKS pass-rate accepted as "no regression vs. v1.1 baseline" — 7 SCN-002/SCN-003 failures excused as structural mismatch). MCP wire-level cancel formally re-deferred behind event-driven trigger (langchain-aws#663 merged OR aioboto3 GA/1.0) in `docs/cancellation.md §5`. Integration-gate convention codified in `docs/testing.md` + grep-enforced. `test_load_role_config_synthesizer_uses_sonnet` rewritten to assert the current Qwen synthesizer default (TRACE-FU-01, SWEEP-FU-02/03/04, MCP-CAN-01/02, MODEL-FU-01).

### Known deferred items at close

4 open items (see STATE.md `## Deferred Items`):

- 🟡 3 pending tooling todos: `fix-bedrock-count-tokens-api-shape-in-update-tokens`, `fix-workspace-repo-resolution-in-init-vault-and-detect-conta`, `rename-graph-wiki-init-command-to-init-wiki` — defer to v1.3
- 🔵 `next-milestone-planning` thread (intentional carry-forward to v1.3)

Phase 16 code review surfaced 6 warnings + 9 info findings (0 critical); not blocking but rolled into v1.3 backlog.

Phase 14 SC#4 was accepted on structural evidence (plugin loads + brand-gate clean) without a captured `/graph-wiki:query` smoke transcript from Claude Code; v1.3 should record the transcript as a regression artifact.

### v1.3 carry-forward themes

Open-source release prep (README badges, contribution guide, PyPI publish dry-run) — explicitly deferred to v2.0 GA in PROJECT.md. Nyquist compliance retroactive validation (0/5 v1.1 phases + 0/6 v1.2 phases reached `nyquist_compliant: true`) — needs a v1.3 decision (retro-validate vs. disable the toggle).

---

## v1.1 Quality Improvements (Shipped: 2026-05-17)

**Phases completed:** 5 phases, 39 plans, ~150 tasks
**Timeline:** 2026-05-15 → 2026-05-17 (~3 calendar days, dense execution)
**Git range:** `8aa21d5` → `92e26fd` (230 commits; 49 feat-prefixed)
**Diff:** 323 files changed, +37,702 / −27,672 lines
**Requirements:** 29/29 v1.1 requirements satisfied
**Audit:** `milestones/v1.1-MILESTONE-AUDIT.md` (status: tech_debt — 0 critical blockers, 6 known debt items)

**Delivered:** Closed the output-quality gap with lattice-wiki by porting its prompt content, validated the cost-frontier on Bedrock, proved host-level reliability under the DeepAgents CLI, polished trace/observability, and closed the subagent context gap.

### Key accomplishments

- **Lattice-wiki SKILL.md content ported** — librarian, ingestor, linter, scanner prompts now incorporate canonical iron rules / citation rules / ingestion patterns / lint rules / package-detection rules via 8 shared fragments under `prompts/_fragments/` with `# Source: / # Anchor: / # Source-commit:` provenance headers (PORT-01..06).
- **Divergence detection eval shipped** — 15 programmatic check rules (LIB/ING/LNT/SCN) + 4 LLM-judge rubrics + 37 unit tests + regression gate (`--accept-divergence-baseline`); 0 hard-severity divergences against the lattice-wiki baseline (EVAL-11..13).
- **Cost-frontier validated on Bedrock** — two-gate scoring (divergence vs. baseline + LLM-judge quality) across 6 in-scope roles against the post-port agent; `models.toml` defaults updated to cost-optimal picks (Qwen3-32B fan-out + Qwen3-80B synthesis) with provenance comments; full results doc under `.planning/sweep/` (SWEEP-01..05).
- **Host reliability proven** — `SubagentPool` terminates cleanly on MCP host cancel with per-item `status: cancelled` records and single `event: batch_cancelled` terminal trace; all 6 MCP tools (`wiki_init/scan/ingest/query/lint/log`) exercised via stdio subprocess E2E test against fresh tmp_path vault, gated by `GRAPH_WIKI_RUN_INTEGRATION=1`; 210-line `docs/cancellation.md` documents protocol + v1.2+ paths (MCP-09..11, DACLI-01..03).
- **Trace schema versioned + cost-aware renderer** — `schema_version: 1` stamped as first key on every JSONL record by all 3 producers; renderer surfaces per-(role,model) cost rollup with `(+K unknown)` accounting (sorted desc cost, alphabetical tie-break); collapses ≥2 consecutive same-role groups by default into single summary line, `--expand` for full per-record view; lenient consumer warns once per file on v0 or unknown future versions (OBS-04..06).
- **Subagent context completion** — `prompts/project_context.py::render_project_context(wiki_path)` reads `wiki/CLAUDE.md` (or `AGENTS.md`), parses the layout block via `vault_io.layout_io`, returns deterministic ~30-line block of project layout + style + log format; wired through 4 prompt builders (scanner, linter, ingestor, librarian) and 3 commands at SystemMessage construction; +1500 token cap per role enforced via syrupy snapshot tests; divergence eval re-ran live (us-east-1, 193s, 4/4 PASSED), no regression (CTX-01..05).

### Known deferred items at close

4 open items (see STATE.md `## Deferred Items` and `milestones/v1.1-MILESTONE-AUDIT.md`):

- Phase 8 SC#1 + SC#2 documented scope narrowings awaiting owner sign-off (acknowledged; not blocking)
- 06-UAT.md metadata-only status mismatch (0 open scenarios)
- `next-milestone-planning` thread (intentional carry-forward to v1.2)

### v1.2 backlog filed during v1.1

TRACE-FU-01 (trace pipeline missing `usage_metadata`), SWEEP-FU-02/03/04 (sweep coverage gaps), MODEL-FU-01 (synthesizer test drift). Full text in `milestones/v1.1-REQUIREMENTS.md`.

---

## v1.0 graph-wiki-agent parity (Shipped: 2026-05-15)

**Phases completed:** 5 phases, 25 plans
**Timeline:** 2026-05-13 → 2026-05-15 (3 calendar days, ~12 sessions)
**Requirements:** 67/67 v1 requirements complete

**Delivered:** End-to-end `graph-wiki-agent` reaches full parity with the existing `lattice-wiki` Claude Code plugin, running entirely on AWS Bedrock with within-command subagent fan-out for cost and context savings.

### Key accomplishments

- **All 6 commands shipped** on both MCP (`graph-wiki-mcp` stdio server) and headless Typer CLI (`graph-wiki-agent <cmd>`) surfaces, sharing a single command-implementation module: `init`, `scan`, `ingest`, `query`, `lint`, `log` (CMD-01..08, MCP-01..08, CLI-01..07).
- **`cores/subagent-runtime` → `SubagentPool.run_all()`** with partial-failure isolation (one failure ≠ sibling cancellation), per-role semaphore throttling, explicit recursion-limit propagation, and structured JSONL trace output to `.graph-wiki/traces/` from day one (SUB-01..07, OBS-01..03). Powers fan-out for librarian (Phase 3), scanner (Phase 5), and 3-way linter (Phase 5).
- **`cores/vault-io`** — 11 modules ported verbatim from `lattice-wiki-core` with import surgery only; round-trip golden test green on a 148-page real-vault fixture (byte-identical write-back). `python-frontmatter` for reads only; all writes route through the ported `layout_io.py` emitter to preserve hand-rolled YAML formatting (VAULT-01..07).
- **Hybrid search**: BM25 via `bm25s` 0.3.8 + Titan Embeddings v2 in SQLite (WAL mode), sha256-keyed incremental rebuild, RRF fusion with configurable weights, raw + fused scores exposed in `--json` (SEARCH-01..06).
- **`cores/model-adapter`** — `ModelRegistry` resolves logical role names (`librarian`, `scanner`, `linter`, `ingestor`, `synthesizer`, `judge_a`, `judge_b`, etc.) to `ChatBedrockConverse` instances via a single `models.toml`. No hardcoded model IDs anywhere. `BedrockAccessDenied` raised with attempted ARN + IAM verb on permission failure (BED-01..05).
- **`cores/eval-harness`** — fixture corpus (3 repos), headless `claude -p` baseline recorder with EVAL-08 reproducibility schema, `deepeval` 4.0 integration with `AmazonBedrockModel`, heterogeneous two-judge GEval panel (`claude-sonnet-4-6` + `nova-pro-v1:0`) with position-bias check, cost-frontier sweep runner via `pytest-evals`, structural metrics (cites code path / wikilinks resolve / valid frontmatter), and a regression-check AssertionError gate (EVAL-01..10).
- **MCP stdout discipline** locked at infrastructure level — `_StdoutGuard` sentinel + subprocess JSON-RPC integrity test that asserts every stdout byte is valid framing (MCP-05).
- **`ingest` ships as ONE MCP tool** (`wiki_ingest`) with `type: Literal['source', 'work-item']` discriminator rather than two tools — cleaner schema, type-narrowing server-side, matches lattice-wiki semantics.
- **CI hygiene** — ruff lint+format clean across the workspace; `uv` single shared `uv.lock`; per-member pytest isolation; GitHub Actions wired for both CI and opt-in eval workflows (INFRA-01..06).

### Outcomes against thesis

The infrastructure to measure the project's core thesis (cost-frontier on Bedrock vs current Claude-Code-hosted plugin) shipped in this milestone; *executing* the sweep — running it against all 7 roles, picking cost-optimal models, swapping `models.toml` defaults — is the v1.1 lift.

### Known deferred items (carried into v1.1)

- **BED-01 live-Bedrock gate** — code-side acceptance passed; the live `make_llm("haiku").invoke("ping")` call against real Bedrock remains blocked on a one-time AWS account onboarding form ("Anthropic use case details") that Pat needs to complete out-of-band.
- **Cost-frontier sweep execution** — harness shipped; results pending `GRAPH_WIKI_RUN_EVAL=1` runs.

For full milestone detail see [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md) and [`milestones/v1.0-REQUIREMENTS.md`](milestones/v1.0-REQUIREMENTS.md). For lessons learned see [`RETROSPECTIVE.md`](RETROSPECTIVE.md).

---
