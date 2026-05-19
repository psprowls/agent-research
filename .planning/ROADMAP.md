# Roadmap: deep-agents / code-wiki-agent

**Project:** deep-agents (v1 = code-wiki-agent)
**Created:** 2026-05-13
**Current milestone:** v1.2 Graph-Wiki Port & Debt Cleanup

---

## Milestones

- ✅ **v1.0 — code-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — Quality Improvements** — Phases 6-10 (shipped 2026-05-17) — [archive](milestones/v1.1-ROADMAP.md)
- 🚧 **v1.2 — Graph-Wiki Port & Debt Cleanup** — Phases 11-16 (scoping → execution, started 2026-05-17)

---

## Phases

<details>
<summary>✅ v1.0 code-wiki-agent parity (Phases 1-5) — SHIPPED 2026-05-15</summary>

- [x] Phase 1: Infrastructure, Vault IO, and MCP Skeleton (5/5 plans) — completed 2026-05-13
- [x] Phase 2: Subagent Fan-Out Runtime (4/4 plans) — completed 2026-05-13
- [x] Phase 3: Query Vertical Slice + Hybrid Search (6/6 plans) — completed 2026-05-14
- [x] Phase 4: Eval Harness (4/4 plans) — completed 2026-05-14
- [x] Phase 5: Remaining Commands (6/6 plans) — completed 2026-05-14

Full detail: [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Quality Improvements (Phases 6-10) — SHIPPED 2026-05-17</summary>

- [x] Phase 6: Prompt Content Port + Divergence Eval (16/16 plans) — completed 2026-05-17
- [x] Phase 7: Cost-Frontier Sweep (7/7 plans) — completed 2026-05-17
- [x] Phase 8: Host Reliability (3/3 plans) — completed 2026-05-17
- [x] Phase 9: Trace/Observability Polish (6/6 plans) — completed 2026-05-17
- [x] Phase 10: Subagent Context Completion (7/7 plans) — completed 2026-05-17

Full detail: [`milestones/v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md)
Audit: [`milestones/v1.1-MILESTONE-AUDIT.md`](milestones/v1.1-MILESTONE-AUDIT.md)

</details>

### 🚧 v1.2 Graph-Wiki Port & Debt Cleanup (Phases 11-16)

- [x] **Phase 11: workspace-io Port (M1)** — New `packages/workspace-io/` ported from `lattice-workspace`; vault-io delegates manifest/path resolution to it (completed 2026-05-18)
- [x] **Phase 12: Drift Backport + Ecosystem Rebrand (M2)** — Body-diff backport of `lint/*`, `init_vault.py`; `lattice` → `graph-wiki` rename across packages, agents, planning (completed 2026-05-18)
- [x] **Phase 13: Plugin Spec (M3a)** — Lock the plugin contract surface (what slash commands shell out to) before any code is moved (completed 2026-05-18)
- [ ] **Phase 14: Plugin Port (M3b)** — `lattice-wiki` plugin ported to `plugins/graph-wiki/`; namespace renamed; scripts route through vault-io
- [x] **Phase 15: Wiki Self-Update** — `~/Personal/wiki/deep-agents` scanned + ingested against the rebranded ecosystem; naming sweep verified post-port (completed 2026-05-19)
- [ ] **Phase 16: Carry-Forward Debt Cleanup** — Trace `usage_metadata`, full sweep coverage, MCP cancellation closure, model config test drift

---

## Phase Details

### Phase 11: workspace-io Port (M1)
**Goal**: A new `packages/workspace-io/` Python package owns workspace bootstrap, manifest IO, and config resolution under the `graph-wiki` brand, and `vault-io` delegates to it cleanly.
**Depends on**: Nothing (first phase of v1.2)
**Requirements**: WS-01, WS-02, WS-03, WS-04, WS-05, WS-06, WS-07, WS-08, WS-09, WS-10
**Success Criteria** (what must be TRUE):
  1. `uv sync` resolves a `workspace-io` member at `packages/workspace-io/` whose tests pass via `uv run --package workspace-io pytest`.
  2. Running any vault-io command in a directory with a `.graph-wiki.yaml` ancestor resolves the wiki + repo paths without `LATTICE_WORKSPACE` being set; `GRAPH_WIKI_WORKSPACE` is the env override that works.
  3. `vault-io._workspace.resolve_wiki_and_repo` returns the same explicit-path override behavior as before (MCP boundary contract unchanged), now backed by `workspace_io.config.resolve()`.
  4. The `~/Personal/wiki/deep-agents/wiki-config.toml` ↔ `.graph-wiki.yaml` question has a written answer in PROJECT.md Key Decisions (migration script shipped, or decision recorded as "not the same surface").
  5. Every ported test from `lattice-workspace/tests/` runs green under the new module path with `.graph-wiki.yaml` filename expectations.
**Plans**: 6 plans
- [x] 11-01-PLAN.md — Scaffold packages/workspace-io/ uv workspace member (pyproject hatchling, empty __init__, uv sync verify)
- [x] 11-02-PLAN.md — Port 8 workspace_io source modules + asset template; drop schema.py (D-06); strict resolve (D-03); v1-raises manifest (D-14)
- [x] 11-03-PLAN.md — Port 11 workspace_io test files (~67 tests); rewrite v1-coercion test; new strict-raises test; suite green
- [x] 11-04-PLAN.md — Rewrite vault-io._workspace as delegation shim; rename env var in vault-io src docstrings + 2 tests; add new strict-raises test
- [x] 11-05-PLAN.md — Wire workspace_io.init into code-wiki-agent init (D-07); rebrand env var across CLI help (6), MCP Field descriptions (8), and 3 docstrings
- [x] 11-06-PLAN.md — Record WS-10 decision in PROJECT.md (wiki-config.toml vs .graph-wiki.yaml); end-to-end verification gate

### Phase 12: Drift Backport + Ecosystem Rebrand (M2)
**Goal**: Substantive upstream improvements from `lattice-wiki-core` land in `vault-io`, deliberate forks stay forked with written rationale, and no `lattice*` symbol survives in the in-scope code/planning surface.
**Depends on**: Phase 11 (vault-io rebrand assumes `workspace-io` exists and `.graph-wiki.yaml` is the manifest filename)
**Requirements**: BACKPORT-01, BACKPORT-02, BACKPORT-03, BACKPORT-04, BRAND-01, BRAND-02, BRAND-04
**Success Criteria** (what must be TRUE):
  1. `packages/vault-io/lint/` matches upstream behavior on substantive changes; `packages/vault-io/DRIFT-DECISIONS.md` records a per-file verdict (port vs. leave) with one-line rationale for each candidate module from spike 002.
  2. `init_vault.py` and `ingest_work_item.py` divergence decisions are documented in `DRIFT-DECISIONS.md` with backport applied or explicit leave-alone justification.
  3. `grep -rE 'lattice|LATTICE|lattice_workspace|lattice_wiki_core' packages/ agents/ .planning/ CLAUDE.md` returns zero hits (excluding commit-history references to `~/Personal/lattice/`).
  4. `.planning/spikes/CONVENTIONS.md` correctly reflects `packages/` (not `cores/`) and no other planning docs reference the old path.
  5. The full existing test suite passes after the rebrand (`uv run pytest`) — no regressions from rename surgery.
**Plans**: 4 plans
- [x] 12-01-PLAN.md — P-A: Scripted raw diff dump for the 11 overlapping modules; pin upstream SHA in DRIFT-DECISIONS-RAW.md header
- [x] 12-02-PLAN.md — P-B: Verdict assignment + atomic backport commits per PORT row; finalize DRIFT-DECISIONS.md verdict table (BACKPORT-01..04)
- [x] 12-03-PLAN.md — P-C: Five-commit rebrand sweep (packages/, agents/, plugins/ placeholder, live planning surface + CONVENTIONS.md) with per-commit uv run pytest gate
- [x] 12-04-PLAN.md — P-D: scripts/check-brand.sh + .brand-grep-allow grep-gate; final BRAND-04 verification (grep clean + pytest green)

### Phase 13: Plugin Spec (M3a)
**Goal**: The open question "what do `lattice-wiki` plugin slash commands actually shell out to?" has a locked answer, and the contract surface between the plugin and deep-agents is documented before any plugin code is moved.
**Depends on**: Phase 12 (spec references the rebranded package names and the locked vault-io/workspace-io API surface)
**Requirements**: PLUGIN-01
**Success Criteria** (what must be TRUE):
  1. A spec doc under `.planning/spec/` enumerates every `lattice-wiki` plugin slash command and names what each one will shell out to (deep-agents CLI subcommand, MCP tool, or lattice CLI to be replaced).
  2. The spec calls out which plugin commands change shape during the port vs. which are byte-for-byte renames, with one-line rationale per change.
  3. The contract surface is locked in PROJECT.md Key Decisions (or equivalent), so Phase 14 has no open questions left about plugin → deep-agents wiring.
**Plans**: 5 plans
- [x] 13-01-PLAN.md — Per-command port specs for /graph-wiki:init + /graph-wiki:scan (rename verdicts)
- [x] 13-02-PLAN.md — Per-command port specs for /graph-wiki:ingest (source-only) + /graph-wiki:lint (reshape, drops work-layer pass 1b)
- [x] 13-03-PLAN.md — Per-command port specs for /graph-wiki:query (LLM + BM25 fallback) + /graph-wiki:log (prose-only, no script)
- [x] 13-04-PLAN.md — Cross-cutting: CONTRACT-INDEX.md (9-row verdict table) + SHELL-OUT-PATTERN.md (SO-01..SO-04 + rename map)
- [x] 13-05-PLAN.md — Lock the contract surface in PROJECT.md Key Decisions (SP-05) + REQUIREMENTS.md VP-01 prereq note

### Phase 14: Plugin Port (M3b)
**Goal**: The `lattice-wiki` Claude Code plugin runs as `plugins/graph-wiki/` against the deep-agents vault, with no `lattice_*` imports and at least one slash command exercising the end-to-end path.
**Depends on**: Phase 13 (contract locked); transitively Phase 11 + Phase 12 (vault-io and workspace-io are the new IO surface)
**Requirements**: PLUGIN-02, PLUGIN-03, PLUGIN-04, PLUGIN-05
**Success Criteria** (what must be TRUE):
  1. `plugins/graph-wiki/.claude-plugin/plugin.json` exists with the renamed plugin id and metadata; the plugin loads cleanly in a Claude Code host without errors.
  2. All slash commands appear in the `/graph-wiki:*` namespace (no `/lattice-wiki:*` remnants); agent and skill names follow the rebrand.
  3. `grep -r 'lattice_' plugins/graph-wiki/` returns zero hits — plugin scripts call through `vault-io` (which itself uses `workspace-io`).
  4. `/graph-wiki:query` runs end-to-end from a Claude Code session against `~/Personal/wiki/deep-agents` and returns a real librarian answer (manual smoke check).
**Plans**: 3 plans
- [x] 14-01-PLAN.md — Port `vault_io.lint_wiki` from upstream lattice_wiki_core (VP-01 prereq for plugin lint shim)
- [x] 14-02-PLAN.md — Port `vault_io.wiki_search` from upstream lattice_wiki_core (VP-01 prereq for plugin query shim)
- [ ] 14-03-PLAN.md — Bundled plugin port: manifest `[plugin]` block + plugins/graph-wiki/ scaffold + 6 shims + SC#4 smoke transcript

### Phase 15: Wiki Self-Update
**Goal**: The project's own wiki at `~/Personal/wiki/deep-agents` reflects the post-rebrand codebase — new package names, `.graph-wiki.yaml` manifest awareness, plugin port outcomes — so future librarian queries return answers consistent with the shipped code.
**Depends on**: Phase 14 (plugin port complete so the wiki captures the full rebrand surface)
**Requirements**: BRAND-03
**Success Criteria** (what must be TRUE):
  1. `code-wiki-agent scan ~/Personal/wiki/deep-agents` completes against the post-rebrand repo and the resulting `scan-log.md` shows the new package names (`workspace-io`, `graph-wiki` references) without `lattice` artifacts.
  2. `code-wiki-agent ingest` re-ingests changed package pages so the wiki body reflects the rebrand; spot-check at least one page (e.g., a `workspace-io` package page) exists and is well-formed.
  3. A follow-up `code-wiki-agent query "what is workspace-io?"` returns a librarian answer that cites the new code paths (not `lattice-workspace`).
**Plans**: 1 plan
- [x] 15-01-PLAN.md — Bundled atomic plan: models-claude.toml + wiki-config-claude.toml + scan + ingest (OTel) + query + workspace-io spot-check + 15-VERIFICATION.md (completed 2026-05-19)

### Phase 16: Carry-Forward Debt Cleanup
**Goal**: The v1.1 close-out debt items (trace pipeline gap, sweep matrix gaps, MCP cancel closure, model-config test drift) are resolved or explicitly re-deferred with documented justification.
**Depends on**: Phase 12 (sweep against fresh-package vault needs the rebrand landed; other items are independent and could parallel earlier phases, but bundling them here keeps debt-cleanup atomic)
**Requirements**: TRACE-FU-01, SWEEP-FU-02, SWEEP-FU-03, SWEEP-FU-04, MCP-CAN-01, MCP-CAN-02, MODEL-FU-01
**Success Criteria** (what must be TRUE):
  1. Every production trace JSONL record from `commands/{scan,lint,ingest,query}` includes `usage_metadata` with input/output token counts (verified by a regression test that runs a real fan-out and asserts the field is populated).
  2. `pytest-evals` sweep matrix runs DivergenceMetric across all in-scope roles and writes per-role scores; `code_reader` cases produce non-trivial scores against the current fixture corpus; scanner re-sweep against a fresh-package vault completes without regression vs. v1.1 baseline.
  3. Either real DA-CLI wire-level cancel is verified end-to-end (Phase 8 SC#1 closed), or the deferral is re-documented in `docs/cancellation.md` with the current blocker (e.g., aioboto3 status) and a fresh re-evaluation date.
  4. `CODE_WIKI_RUN_INTEGRATION` opt-in gate semantics are consistent across all gated tests (a single rule documented somewhere central; no test diverges silently).
  5. `test_load_role_config_synthesizer_uses_sonnet` is renamed/rewritten to assert the current Qwen synthesizer default; `uv run pytest` is green.
**Plans**: 1 plan
- [ ] 16-01-PLAN.md — Bundled atomic plan: 9 step-commits (trace_io extraction + ingest/query refactor + regression test, code_reader/synthesizer divergence rubrics, code_reader_cases expansion, fixture-vault scanner regression, MCP cancel spike + cancellation.md refresh, docs/testing.md + grep gate, synthesizer model_id assertion, live-vault re-sweep + 16-VERIFICATION.md)

---

## Progress

| Milestone | Phases | Plans | Status | Shipped |
|-----------|--------|-------|--------|---------|
| v1.0 code-wiki-agent parity | 5 | 25/25 | ✅ Shipped | 2026-05-15 |
| v1.1 Quality Improvements | 5 | 39/39 | ✅ Shipped | 2026-05-17 |
| v1.2 Graph-Wiki Port & Debt | 6 | 0/0 | 🚧 Planning | — |

### v1.2 Phase Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 11. workspace-io Port (M1) | 6/6 | Complete   | 2026-05-18 |
| 12. Drift Backport + Rebrand (M2) | 4/4 | Complete   | 2026-05-18 |
| 13. Plugin Spec (M3a) | 5/5 | Complete    | 2026-05-18 |
| 14. Plugin Port (M3b) | 2/3 | In Progress|  |
| 15. Wiki Self-Update | 1/1 | Complete   | 2026-05-19 |
| 16. Carry-Forward Debt Cleanup | 0/1 | Planned    | — |

---

*Last updated: 2026-05-19 — Phase 16 plan 16-01 written; ready for execution. Next: `/gsd:execute-phase 16`.*
