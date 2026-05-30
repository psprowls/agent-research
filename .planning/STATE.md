---
gsd_state_version: 1.0
milestone: v1.11
milestone_name: Cost-Frontier Sweep Harness
status: In progress
stopped_at: Phase 60 in progress — harness fixes B–F landed; round-3 answer-degradation debug pending
last_updated: "2026-05-30T14:00:00.000Z"
last_activity: 2026-05-30 — Opened v1.11 (Cost-Frontier Sweep Harness); scaffolded Phase 60 to capture the post-v1.10 sweep quick-task work + remaining round-3 debug
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State: agent-research

**Last updated:** 2026-05-30 — v1.11 (Cost-Frontier Sweep Harness) opened; Phase 60 scaffolded
**Updated by:** manual scaffold (lightweight new-milestone)

---

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-05-29)

**Core Value:** Faithfully reproduce the graph-wiki plugin's wiki-maintenance workflows while running entirely on AWS Bedrock with parallel subagents, at meaningfully lower cost than the current Claude-Code-hosted plugin.

**Current Focus:** v1.11 / Phase 60 — Cost-Frontier Sweep Harness. Harness fixes B–F have landed (as quick tasks since v1.10); the `$3.46` full re-run verified D/E/F mechanically but is NOT authoritative (judge-able quality collapsed). Remaining: round-3 answer-degradation debug → clean re-run → winner selection.

---

## Current Position

Phase: 60 — Cost-Frontier Sweep Harness (v1.11) — in progress
Plan: — (retroactive scaffold; sub-work landed as quick tasks)
Status: In progress — round-3 debug RESOLVED; sweep model-set refreshed (Haiku purged); clean full re-run pending
Last activity: 2026-05-30 — Fixed devDependency-blind app/package classification in graph-io (found via live scan of ~/Personal/mono-repo): Electron+Vite apps (electron/vite under devDependencies) now classify as `app_kind=electron` instead of `pkg:`. `_read_package_json` merges devDependencies into the single classify() input + surfaces a `dev_dependencies` marker on node attrs; new `electron` app-kind with electron-before-spa precedence. 480 graph-io tests green. JS dependency-edge ingestion split out to its own future phase. (quick task 260530-gqp)

## Progress Bar

```
v1.11: [░░░░] Phase 60 in progress — harness fixes B–F landed; debug → re-run → winners remaining
```

## Performance Metrics

| Metric | Value |
|--------|-------|
| Milestones shipped | 11 (v1.0 → v1.10) |
| Phases shipped (cumulative) | 59 |
| Plans shipped (cumulative) | 199 |
| v1.10 requirements | 14/14 satisfied |
| v1.10 phases | 6 (54-59) |

---

## Accumulated Context

### Open blockers

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260529-na9 | Refresh models.toml sweep candidates and judge panel for new cost-frontier sweep | 2026-05-29 | 60c8d77 | [260529-na9-refresh-models-toml-sweep-candidates-and](./quick/260529-na9-refresh-models-toml-sweep-candidates-and/) |
| 260529-ox1 | EvalWorktree provisions initialized graph-io DB so ingestor sweep cells can run | 2026-05-29 | e42ae87 | [260529-ox1-evalworktree-provisions-initialized-grap](./quick/260529-ox1-evalworktree-provisions-initialized-grap/) |
| 260529-pf8 | Update stale config-pinning tests after na9 sweep refresh (Haiku global, qwen3 price, retire D-03 tier map) | 2026-05-29 | 07c81ea | [260529-pf8-update-stale-config-pinning-tests-after-](./quick/260529-pf8-update-stale-config-pinning-tests-after-/) |
| 260529-pzd | Fix B — model-adapter normalizes list-shaped ("thinking"/multi-block) response content to str (preserves reasoning), covers invoke + ainvoke | 2026-05-29 | 02ee3fe | [260529-pzd-fix-b-model-adapter-content-normalizer](./quick/260529-pzd-fix-b-model-adapter-content-normalizer/) |
| 260529-q8r | Fix C — wire per-role DivergenceMetric + baselines_dir into run_full_matrix (Gate 1 was hardcoded None → auto-FAIL for every candidate) | 2026-05-29 | 43c9dd6 | [260529-q8r-fix-c-sweep-gate-1-divergence-wiring](./quick/260529-q8r-fix-c-sweep-gate-1-divergence-wiring/) |
| 260529-sot | Fix D+E+F — route 6 model-override branches through make_llm (D); rate-based Gate 1 + empty-output disqualification (E); populate SweepResult.judge_scores w/ real quality signal (F) | 2026-05-29 | e9cd8b1 | [260529-sot-fix-d-e-f-sweep-harness-override-bypass-](./quick/260529-sot-fix-d-e-f-sweep-harness-override-bypass-/) |
| 260529-sot (follow-up) | Fix D 7th branch — route the code-fallback synthesizer through make_llm(model_override) | 2026-05-30 | aaa3d63 | (committed on main) |
| 260530-jc1 | Fix judge-signal collapse — guard empty-but-valid graph DB in run_query (e42ae87 made read_only_connect succeed on zero-node code.db → graph tools bound → librarian iter-cap → code-fallback disclaimer → judge 0.10); SELECT COUNT(*) FROM nodes == 0 → fallback addendum, no tools | 2026-05-30 | f3a9c2e | [260530-jc1-fix-empty-db-graph-tool-binding](./quick/260530-jc1-fix-empty-db-graph-tool-binding/) |
| 260530-ehv | Refresh sweep model set — purge Haiku from all 6 swept roles + preflight (quota exhaustion); new defaults librarian→kimi-k2.5, code_reader→minimax-m2.5, scanner→gpt-oss-20b, linter→nova-lite (now also a candidate), ingestor→glm-4.7-flash, synthesizer→qwen3-32b (unchanged), preflight→qwen3-32b; config-pinning tests synced (29/29 green); judge-independence finding deferred (note) | 2026-05-30 | 949adc7 | [260530-ehv-refresh-sweep-model-set-in-models-toml-r](./quick/260530-ehv-refresh-sweep-model-set-in-models-toml-r/) |
| 260530-gqp | Fix devDependency-blind package/app classification in graph-io — `_read_package_json` now merges `devDependencies` into the single sorted/deduped `dependencies` list classify() reads, adds an `electron` app-kind (electron-before-spa precedence), and surfaces a `dev_dependencies` marker on package-node attrs_json. Electron+Vite apps (electron/vite under devDependencies) now classify as `app_kind=electron` instead of falling through to `pkg:`. Found via live scan of ~/Personal/mono-repo. 480 graph-io tests green. JS dependency-edge ingestion (npm `dependency:`/`used_by` nodes/edges + cross-ecosystem dev tagging) deliberately split out to its own future phase. | 2026-05-30 | b753ff4 | [260530-gqp-fix-devdependency-blind-package-app-clas](./quick/260530-gqp-fix-devdependency-blind-package-app-clas/) |

> **Note (2026-05-30):** the cost-frontier-sweep quick tasks above (na9/ox1/pf8/pzd/q8r/sot) are now organized under **v1.11 / Phase 60** — see `.planning/phases/60-cost-frontier-sweep-harness/60-CONTEXT.md`.

### Key decisions (v1.10 — locked, now shipped)

- Per-entity summaries come from a scanner-written `summary:` frontmatter field (index reads it uniformly).
- Deps/test-suites nest under packages only; flat By-Kind lists for those two kinds are dropped entirely.
- Internal package-as-dependency becomes a distinct `depends_on_package` package→package edge (not a `dependency` node, and not the Domain→Domain `depends_on` kind).
- `graph-wiki-agent` consumes only the typed `graph_io` library API (`queries`/`update`/`store` + public `render`); nothing in the agent imports `graph_io.cli`. Whether to keep the `cg` CLI as a human debug surface is deferred to a later decision.

Full decision log: `.planning/PROJECT.md` ## Key Decisions.

---

## Deferred Items

Carried forward (process debt + one v1.10 feature deferral):

| Category | Item | Status |
|----------|------|--------|
| audit | v1.6 + v1.8 + v1.9 + v1.10 milestone audits | all shipped without `/gsd:audit-milestone` — backfill or accept as process-only debt |
| security | v1.8/v1.9 phase-level security reviews (42-52) | `workflow.security_enforcement=true` but phases shipped without `*-SECURITY.md` |
| nyquist | 0/35+ phases produced VALIDATION.md | decision pending (retro-validate vs. disable toggle) — carried since v1.4 |
| verification | Phase 50 (App Reclassification) has no VERIFICATION.md | accepted as debt at v1.9 close |
| schema | SUMMARY.md `one_liner:` write-time enforcement | GSD-tool debt, not graph-wiki code; filed separately |
| feature | Entity `## Related` dynamic population from graph edges | deferred at v1.10 (Phase 58 CONTEXT D-01); todo in `.planning/todos/deferred/2026-05-28-populate-entity-related-section-from-graph-edges.md` |

---

## Session Continuity

Last session: 2026-05-30 — opened v1.11, scaffolded Phase 60
Stopped at: Phase 60 (Cost-Frontier Sweep Harness) in progress — harness fixes B–F landed; round-3 judge-signal collapse debugged + fixed (260530-jc1, `f3a9c2e`); clean full re-run pending

**Next action:** Run the clean full sweep (Haiku-free set now in models.toml — the daily-token quota throttle that blocked the prior re-run no longer applies). Sweep spec: `/tmp/sweep_driver.py` (`.planning/CONTINUE-sweep-harness-fixes-3.md` Step 2 / CONTINUE-2 Step B; repeats=3, `output_dir=.planning/sweep`, `GRAPH_WIKI_RUN_EVAL=1 GRAPH_WIKI_RUN_JUDGES=1`; pre-approved ~$7, hard cap $25). Per-role defaults: librarian→kimi-k2.5, code_reader→minimax-m2.5, scanner→gpt-oss-20b, linter→nova-lite, ingestor→glm-4.7-flash, synthesizer→qwen3-32b, preflight→qwen3-32b. Judges intentionally held (Mistral/Nova; see `.planning/notes/sweep-judge-independence-deferred.md`). narrator + domain-proposer still on Haiku (deferred). Verify judge-able quality discriminates (not all ~0.10), then overwrite-commit `.planning/sweep/*.md` + `INDEX.md` as authoritative and help Pat pick per-role winners. Stash `stash@{0}` holds stray bedrock-models JSON snapshots — decide keep/discard with Pat. Known follow-up G (cost=N/A for many models) still open.

---

*State initialized: 2026-05-13*
*v1.6 archived: 2026-05-26 — 7 phases (28-34), 30 plans*
*v1.7 archived: 2026-05-26 — 7 phases (35-41), 10 plans, 27 requirements*
*v1.8 archived: 2026-05-27 — 7 phases (42-48), 20 plans, 38 requirements*
*v1.9 archived: 2026-05-28 — 5 phases (49-53), 15 plans, 24 requirements*
*v1.10 archived: 2026-05-29 — 6 phases (54-59), 14 plans, 14 requirements*
*v1.11 opened: 2026-05-30 — Phase 60 (Cost-Frontier Sweep Harness), in progress*

## Operator Next Steps

- Continue Phase 60: debug per `.planning/CONTINUE-sweep-harness-fixes-3.md`, then clean re-run + winner selection
