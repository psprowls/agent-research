# Roadmap: deep-agents / code-wiki-agent

**Project:** deep-agents (v1 = code-wiki-agent)
**Created:** 2026-05-13

---

## Milestones

- ✅ **v1.0 — code-wiki-agent parity** — Phases 1-5 (shipped 2026-05-15) — [archive](milestones/v1.0-ROADMAP.md)
- 🔄 **v1.1 — Quality Improvements** — Phases 6-9 (in progress)

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

### 📋 v1.1 Quality Improvements (Phases 6-9)

- [ ] **Phase 6: Prompt Content Port + Divergence Eval** — Port lattice-wiki SKILL.md content into agent prompts and wire the divergence-detection eval metric (11/16 plans complete; 5 gap-closure plans for UAT issues pending)
- [ ] **Phase 7: Cost-Frontier Sweep** — Execute the sweep against the post-port agent, publish cost-optimal model picks, update models.toml defaults
- [ ] **Phase 8: Host Reliability** — MCP cancellation polish and DeepAgents CLI stdio integration test
- [ ] **Phase 9: Trace/Observability Polish** — Document and version the trace schema; enhance the trace renderer with per-subagent cost and collapsing

---

## Phase Details

### Phase 6: Prompt Content Port + Divergence Eval
**Goal**: Agent prompts faithfully encode lattice-wiki's canonical rules and the eval harness can detect remaining divergences
**Depends on**: Phase 5 (code-wiki-agent v1.0 complete)
**Requirements**: PORT-01, PORT-02, PORT-03, PORT-04, PORT-05, PORT-06, EVAL-11, EVAL-12, EVAL-13
**Success Criteria** (what must be TRUE):
  1. Running `code-wiki-agent query` against the fixture corpus produces citations that follow lattice-wiki iron rules (no hallucinated wikilinks, correct refusal patterns)
  2. Running `code-wiki-agent ingest` routes source vs work-item pages correctly and generates frontmatter that passes the mechanical lint pass
  3. Running `code-wiki-agent lint` applies the canonical rule set (not a paraphrased version) — provenance comments in `prompts/` trace every rule to a source path + anchor
  4. The divergence eval metric runs against the fixture corpus and emits per-role divergence counts with concrete examples
  5. A recorded divergence baseline exists; re-running without `--accept-divergence-baseline` fails the gate if divergence increases
**Plans**: 16 plans (11 original + 5 gap-closure from 06-UAT.md)
Plans:
- [x] 06-01-PLAN.md — Vendor lattice-wiki canonical sources into cores/prompt-sources/ (Wave 1)
- [x] 06-02-PLAN.md — Wave 0 test scaffolding (snapshot + provenance + divergence test stubs) (Wave 1)
- [x] 06-03-PLAN.md — prompts/ module + shared fragments (iron_rules, page_categories, citation_rules, frontmatter_rules) (Wave 2)
- [x] 06-04-PLAN.md — Librarian prompt port + synthesizer/code_reader relocation + query.py refactor (Wave 3)
- [x] 06-05-PLAN.md — Ingestor prompt port + ingest.py refactor (Wave 3)
- [x] 06-06-PLAN.md — Linter 3-group prompt port + lint.py refactor (Wave 3)
- [x] 06-07-PLAN.md — Scanner prompt port + scan.py refactor (Wave 3)
- [x] 06-08-PLAN.md — Divergence rule modules + judge rubrics + per-rule unit tests (Wave 4)
- [x] 06-09-PLAN.md — DivergenceMetric class (programmatic + GEval judge composition) (Wave 5)
- [x] 06-10-PLAN.md — Baseline JSON loader + write + regression gate + initial baselines (Wave 6)
- [x] 06-11-PLAN.md — End-to-end eval-gated divergence test + baseline acceptance flow (Wave 7)
- [x] 06-12-PLAN.md — Ingestor frontmatter no-code-fence rule + _parse_ingestor_response fence-strip (UAT G1) (Wave 8)
- [x] 06-13-PLAN.md — page_type=source routing + target_slug ↔ filename equality (UAT G2, G3) (Wave 9)
- [x] 06-14-PLAN.md — Wikilink hallucination guardrails: _resolve_wikilinks + named anti-patterns in prompt (UAT G4) (Wave 10)
- [x] 06-15-PLAN.md — Scanner fixture coverage via run_scan repo_path override + baseline re-record (UAT G5) (Wave 8)
- [x] 06-16-PLAN.md — Test hygiene: hoist pythonpath to root, remove sys.path.insert (WR-05 residual) (Wave 9)

### Phase 7: Cost-Frontier Sweep
**Goal**: The cost-frontier across all 7 Bedrock roles is measured against the post-port agent and models.toml defaults reflect the cost-optimal picks
**Depends on**: Phase 6
**Requirements**: SWEEP-01, SWEEP-02, SWEEP-03, SWEEP-04, SWEEP-05
**Success Criteria** (what must be TRUE):
  1. `CODE_WIKI_RUN_EVAL=1 pytest` completes against all 7 roles on live Bedrock without credential or access errors (BED-01 gate passes in passing)
  2. A committed cost-frontier table exists under `.planning/` or `docs/` showing model × quality × cost per role
  3. `models.toml` defaults point to the cost-optimal pick per role; previous defaults are preserved as commented provenance
  4. A results summary doc exists that tells the cost story v1.0 promised to validate
**Plans**: 7 plans
Plans:
**Wave 1**
- [x] 07-01-PLAN.md — Wave 0 test scaffolds (skipped tests for runner/two-gate/report/estimator/recommendation/dry-run)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 07-02-PLAN.md — Per-role model_override surfaces on query/scan/lint/ingest commands (D-06)
- [x] 07-03-PLAN.md — sweep_candidates arrays in models.toml + code_reader vault-thin fixtures (D-03, D-05, D-09)

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 07-04-PLAN.md — Pre-flight cost estimator + BED-01 ping + dry-run plumbing (D-13, SWEEP-02)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 07-05-PLAN.md — run_role_sweep + two-gate scoring (D-06, D-07, D-08, SWEEP-01)

**Wave 5** *(blocked on Wave 4 completion)*
- [x] 07-06-PLAN.md — Pareto frontier renderer + per-role doc + recommendation block + dry-run integration test (SWEEP-03, SWEEP-04)

**Wave 6** *(blocked on Wave 5 completion)*
- [ ] 07-07-PLAN.md — Live matrix execution + REQUIREMENTS/ROADMAP correction + manual models.toml swap + STORY.md (SWEEP-01..05, D-02)

### Phase 8: Host Reliability
**Goal**: MCP cancellation is proven clean under a real DeepAgents CLI host and every MCP tool is exercised by an end-to-end integration test
**Depends on**: Phase 5 (no dependency on Phase 6 or 7 — parallel-eligible)
**Requirements**: MCP-09, MCP-10, MCP-11, DACLI-01, DACLI-02, DACLI-03
**Success Criteria** (what must be TRUE):
  1. A cancel-mid-fan-out scenario under the real DeepAgents CLI host terminates in-flight Bedrock calls cleanly — no orphaned calls, traces close with a `cancelled` terminal event
  2. An automated cancel test covers the cancel-mid-fan-out scenario at the MCP transport boundary and runs under the standard opt-in gate
  3. A single integration test launches `code-wiki-mcp` as a stdio subprocess, exercises all six tools (`wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log`) with realistic inputs, and asserts non-error outcomes
  4. The integration test runs under `CODE_WIKI_RUN_INTEGRATION=1` (consistent with existing opt-in gate pattern)
**Plans**: TBD

### Phase 9: Trace/Observability Polish
**Goal**: The trace format is documented and versioned, and the trace renderer surfaces per-subagent cost and collapses noisy output by default
**Depends on**: Phase 2 (trace infrastructure exists)
**Requirements**: OBS-04, OBS-05, OBS-06
**Success Criteria** (what must be TRUE):
  1. Every JSONL trace file contains a `schema_version` field; the schema is documented with a breaking-change policy
  2. `code-wiki-agent trace <file>` displays per-subagent cost (input/output tokens × model price) for each fan-out call
  3. `code-wiki-agent trace <file>` collapses repeated subagent-role groups into a summary line by default; `--expand` drills into the full event stream
**Plans**: TBD

---

## Progress

| Phase                                       | Milestone | Plans Complete | Status      | Completed   |
| ------------------------------------------- | --------- | -------------- | ----------- | ----------- |
| 1. Infrastructure, Vault IO, MCP Skeleton   | v1.0      | 5/5            | Complete    | 2026-05-13  |
| 2. Subagent Fan-Out Runtime                 | v1.0      | 4/4            | Complete    | 2026-05-13  |
| 3. Query Vertical Slice + Hybrid Search     | v1.0      | 6/6            | Complete    | 2026-05-14  |
| 4. Eval Harness                             | v1.0      | 4/4            | Complete    | 2026-05-14  |
| 5. Remaining Commands                       | v1.0      | 6/6            | Complete    | 2026-05-14  |
| 6. Prompt Content Port + Divergence Eval   | v1.1      | 11/16 | Gap-closure | -           |
| 7. Cost-Frontier Sweep                      | v1.1      | 0/7            | Planned     | -           |
| 8. Host Reliability                         | v1.1      | 0/TBD          | Not started | -           |
| 9. Trace/Observability Polish               | v1.1      | 0/TBD          | Not started | -           |

---

*Last updated: 2026-05-16 — Phase 7 planned (7 plans, 6 waves; Wave 6 has the live-Bedrock matrix run + two human checkpoints for the manual models.toml swap and STORY.md review)*
