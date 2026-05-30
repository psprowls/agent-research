---
gsd_state_version: 1.0
milestone: v1.11
milestone_name: Cost-Frontier Sweep Harness
status: In progress
stopped_at: Phase 60 in progress — harness fixes B–F landed; round-3 answer-degradation debug pending
last_updated: "2026-05-30T20:25:00.000Z"
last_activity: 2026-05-30 — Fix JS/npm dependency population in graph_io (260530-k5y): dep nodes (ecosystem=npm), used_by edges, dev marker, internal-workspace routing, versions_in_use; DERIVER_VERSION=3; 495 graph-io tests green
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
Last activity: 2026-05-30 — Completed a parallel batch of 4 graph/bootstrap quick tasks (concurrent isolated worktrees): 260530-iqo (deriver-version-stamp → auto full rebuild on logic change), 260530-iqp (remove legacy apps/packages/domains/dependencies bootstrap folders), 260530-iqq (scope gitignore entry to workspace dir), 260530-iqr (converge propose_domains onto shared _resolve_paths). All merged to main; affected suites green (graph-io/wiki-io/workspace-io 954 passed; graph-wiki-agent green modulo 2 pre-existing unrelated fails). Then 260530-jap (dist/build import-target node sweep — `resolve.sweep_skip_dir_files`, DERIVER_VERSION 1→2, full graph-io suite 487 passed). Earlier: 260530-hxy (graph build repo resolution). Phase 60 (cost-frontier sweep) still parked until the graph is trustworthy + a clean baseline can be established. Then RESOLVED the "functions missing path/line" investigation todo: full-rebuilt mono-repo's graph against the post-sweep deriver (v2) and captured before/after — file nodes 4633→1463, the 2455 path-less functions are UNCHANGED and all are unresolved call-edge targets → confirmed EXPECTED (out-of-tree symbols, no in-tree location), not a bug. No code change; JS-dep injection is now an enhancement, not a fix. Then 260530-nfj: added `scripts/graph_health.py` (read-only code.db auditor) for future diagnostics. **CORRECTION (quick-260530-nsr, 2026-05-30):** the earlier "NULL-uri files 3170→0" claim was MISREAD as a health win — pre-fix a `--full` rebuild zeroed NULL-uri files by DELETING the specifier-path import stubs (cleanup at update.py:285-299), which cascade-deleted ALL import edges, leaving the file-to-file import graph EMPTY (imports edges 0). The `scan`/incremental path conversely kept 3003 NULL-uri stubs + ~5600 all-unresolved import edges; the two results did not actually contradict — both reflected the same unresolved-specifier bug, one via deletion, one via accumulation. nsr fixed it: a new `resolve.resolve_file_imports` pass repoints in-repo import specifiers to real file nodes BEFORE the full-mode cleanup (DERIVER_VERSION 3→4), plus a conservative single-candidate cross-kind call/export fallback (resolves only on EXACTLY ONE graph-wide name match — bare-name collisions stay unresolved, so the false-positive risk flagged above is avoided). Post-fix live re-audit of mono-repo-live: **full** build → imports edges 822 ALL exact-resolved, NULL-uri files 0 (idempotent across repeat full + incremental); **fresh scan (full=False)** → 822 in-repo specifiers exact-resolved, 4168 genuinely-external (react/@electron-forge/bare scoped pkgs) correctly unresolved, 2176 NULL-uri stubs retained (still referenced by their unresolved edges — not orphans). Both prior open questions (scan-vs-full reconciliation; cross-kind safety) are now resolved.

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
| 260530-hxy | Fix graph build repo resolution to match scan — `_resolve_paths` (graph.py) now delegates to `resolve_wiki_and_repo` instead of `config.resolve`, so the source repo is discovered from cwd (`_find_repo_root(Path.cwd())`) like `scan`, not from the workspace dir (which broke repo≠workspace with `fatal: ambiguous argument 'HEAD'`). Also made `resolve_wiki_and_repo`'s explicit-workspace branch honor a `repo-directory:` pin so the documented workaround works for both commands. TDD (RED/GREEN ×2), 10 new tests green. Out of scope: duplicate `_resolve_paths` in propose_domains.py (follow-up). | 2026-05-30 | 3857235 | [260530-hxy-fix-graph-build-repo-resolution-to-match](./quick/260530-hxy-fix-graph-build-repo-resolution-to-match/) |
| 260530-iqo | Force graph rebuild when derivation logic changes — added `schema.DERIVER_VERSION` constant; `update.run()` now compares the stored `metadata.deriver_version` against the current constant and, on mismatch with an existing graph (`prev is not None`), forces `full=True` so derivation-logic changes (classify(), app_kind precedence, derived edges) propagate without a manual `--full`. Stamp written to metadata on every run. Surgical: schema.py + update.py only. 482 graph-io tests green; 2 new tests prove a version bump forces a rebuild at unchanged HEAD. Ran concurrently (parallel-batch worktree). | 2026-05-30 | 23a8369 | [260530-iqo-force-graph-rebuild-when-derivation-logi](./quick/260530-iqo-force-graph-rebuild-when-derivation-logi/) |
| 260530-iqp | Remove legacy container folders from bootstrap scaffolding — dropped `dependencies` from `FIXED_VAULT_DIRS` and removed the `structural_dirs` mkdir loop, so bootstrap no longer creates `apps/`/`packages/`/`domains/`/`dependencies/` (remnants from before the single `entities/` folder). Container-detection metadata (`containers` in the manifest) preserved intact — only the folder mkdir was removed. Surgical: init_vault.py + test only. wiki-io suite green; new regression test asserts legacy folders not created, canonical dirs still are. Ran concurrently (parallel-batch worktree). | 2026-05-30 | 45bac22 | [260530-iqp-remove-legacy-container-folders-from-boo](./quick/260530-iqp-remove-legacy-container-folders-from-boo/) |
| 260530-iqq | Scope gitignore entry to workspace dir on bootstrap — `_ensure_gitignore_entry(workspace, repo_root)` now applies a containment gate: writes `.graph-wiki.local.yaml` to `<workspace>/.gitignore` only when repo_root has a real `.git` and the workspace is strictly under it; skips entirely otherwise (standalone workspaces already get their own `git init`). Stops mutating the repo-root `.gitignore`. Surgical: workspace-io init.py + test only. 87 workspace-io tests green (3 stale repo-root tests replaced with 4 covering contained/outside). Ran concurrently (parallel-batch worktree). | 2026-05-30 | fdac537 | [260530-iqq-scope-gitignore-entry-to-workspace-dir-o](./quick/260530-iqq-scope-gitignore-entry-to-workspace-dir-o/) |
| 260530-iqr | Converge propose_domains _resolve_paths onto shared resolver — extracted the hxy-fixed `_resolve_paths` into a single `graph_wiki_agent/commands/_paths.py`; both graph.py and propose_domains.py now import it (DRY, can't diverge again). Drops the orphaned `resolve_config` import in both. Fixes propose-domains silently writing `domains.proposed.yaml` into the wiki vault on repo≠workspace. Ran concurrently (parallel-batch worktree); worktree was based on a pre-hxy commit so the merge hit a graph.py conflict (resolved in iqr's favor — local def removed, import kept) and the pre-existing `test_propose_domains_e2e.py` fixture needed a `chdir` to match the cwd-based contract (fixed). graph-wiki-agent suite green modulo 2 pre-existing unrelated fails (test_graph_query_output stale snapshot, test_bedrock_iam). | 2026-05-30 | de1cc0b | [260530-iqr-converge-propose-domains-resolve-paths-o](./quick/260530-iqr-converge-propose-domains-resolve-paths-o/) |
| 260530-jap | Stop materializing dist/build import-target file nodes — the defensive backstop for the verified root cause (import edges whose dst is a workspace package's built entry point, e.g. `dist/index.js`, get materialized by `_ensure_node`/`_upsert_edge` which never consult `skip_dirs`, bypassing the walk's dist/build skip). New `resolve.sweep_skip_dir_files(conn, skip_dirs)` runs after `resolve.sweep` in `update.run`: deletes `kind='file' AND uri IS NULL` nodes whose path has a skip-dir component (reuses `_ignore.should_skip`), then drops orphaned edges. Scope deliberately narrow — URI-bearing nodes, non-file nodes, and NULL-uri files outside skip-dirs untouched. `DERIVER_VERSION` bumped 1→2 so existing graphs auto-rebuild (iqo mechanism). TDD: 5 new tests (A–E); full graph-io suite 487 passed. Deeper JS-dependency-resolution fix (stop emitting `dist/` edge targets at the source) is a separate session — this sweep is the intended backstop. | 2026-05-30 | f6766f9 | [260530-jap-stop-materializing-dist-build-import-tar](./quick/260530-jap-stop-materializing-dist-build-import-tar/) |
| 260530-k5y | Fix JS/npm dependency population in graph_io — `refresh()` now runs the dependency-accumulation block for JS manifests (was gated on Python only at packages.py:283, so npm deps were parsed onto package nodes but never produced dependency nodes/edges). `_read_package_json` now returns `dep_specs` (name→raw-spec, runtime wins on collision) and `_runtime_dep_names` for is_dev computation. JS runtime deps → `dependency` nodes (ecosystem=npm, `versions_in_use` from dep_specs) + `used_by` edges (attrs={}). devDependencies-only deps → `used_by` edge with `attrs={"dev": True}`. Internal-workspace JS deps → `depends_on_package` via the existing Phase 55 CLASS-01 cross-ecosystem path. Python dep path byte-identical. `DERIVER_VERSION` 2→3. TDD (RED/GREEN ×2 + integration tests); full graph-io suite 495 passed (8 new). This is the deeper JS-dependency fix flagged as a follow-up in jap's row. | 2026-05-30 | f70fd22 | [260530-k5y-fix-js-npm-dependency-population-in-grap](./quick/260530-k5y-fix-js-npm-dependency-population-in-grap/) |
| 260530-nfj | Add `scripts/graph_health.py` — read-only (`sqlite3 mode=ro`) auditor for a graph-io `code.db`. Reports node/edge completeness by kind (total/no-attrs/no-uri/no-path), edge resolution status (unresolved/exact/ambiguous), function call/export placeholders (path IS NULL) and where their targets actually live (cross-kind: file/method/class/builtin) vs truly-external, and the shape of unresolved import specifiers. Pure stdlib (sqlite3/sys/pathlib), no new deps, NOT wired as a `cg` entry point — standalone dev tool alongside `scripts/{check-brand,drift-diff}.sh`. Byte-identical to the throwaway used to diagnose the live mono-repo scan; executable bit set; verified against the live DB (exit 0, banners print). | 2026-05-30 | 269e1c0 | [260530-nfj-add-graph-health-diagnostic-script-for-g](./quick/260530-nfj-add-graph-health-diagnostic-script-for-g/) |
| 260530-nsr | Fix graph-io file-import resolution (root cause behind nfj's 3003 NULL-uri `file` stubs). `projections/graph.py` emits `imports` edges as dst=("file", name, raw_specifier) and nothing maps the specifier to the real file — so `scan`/incremental left ~5600 all-unresolved import edges + stub nodes, while `--full` let update.py's cleanup DELETE purge the stubs and cascade-delete EVERY import edge (file-import graph → 0; corrects the earlier "3170→0 healthy" misread). FIX: new `resolve.resolve_file_imports` repoints specifier stubs to real file nodes (exact/ambiguous; external left unresolved, never fabricated), wired BEFORE the full-mode cleanup so resolved edges survive; generalized `import_scan` JS-relative + python-dotted resolvers to return a FILE; `dst.name!=dst.path` idempotency guard. PLUS conservative cross-kind call/export fallback (resolves only on EXACTLY ONE graph-wide name match — bare-name collisions stay unresolved). DERIVER_VERSION 3→4. TDD; full graph-io suite 508 passed (3 skip, 1 xfail), +13 tests. Live re-audit mono-repo-live: full → 822 imports ALL exact-resolved, 0 NULL-uri files (idempotent); scan → 822 in-repo resolved + 4168 genuinely-external unresolved. Validated (plan-check PASS + verify 7/7). | 2026-05-30 | 7db81a0 | [260530-nsr-fix-graph-io-file-import-resolution-so-i](./quick/260530-nsr-fix-graph-io-file-import-resolution-so-i/) |

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

Last session: 2026-05-30 — quick task 260530-k5y: JS npm dependency emission in graph_io
Stopped at: Phase 60 (Cost-Frontier Sweep Harness) in progress — harness fixes B–F landed; round-3 judge-signal collapse debugged + fixed (260530-jc1, `f3a9c2e`); JS dep population fixed (k5y); clean full re-run pending

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
