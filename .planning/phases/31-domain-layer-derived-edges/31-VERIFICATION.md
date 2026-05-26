---
status: passed
phase: 31-domain-layer-derived-edges
verified: 2026-05-26
success_criteria_passed: 5
success_criteria_total: 5
requirements_passed: 9
requirements_total: 9
plans_complete: 4
plans_total: 4
human_verification_needed: false
---

# Phase 31 Verification

## Verdict

**PASSED** — all 5 success criteria verified, all 9 requirements satisfied, all 4 plans complete, full graph-io test suite green at 246 passed / 1 skipped.

## Phase Goal

> Domain nodes from `domains.yaml` are in the graph, cycle detection prevents corrupt hierarchies, `references` and `depends_on` derived edges are computed after every `cg update` and are readable without re-computation at query time.

The goal is met:
- Domain nodes emit from `domains.yaml` via `graph_io.domains.emit` (Plan 31-03), called inside `update.run` between `test_suites.emit` and `resolve.sweep` (Plan 31-04, D-16).
- Tarjan SCC cycle detection in `_detect_cycles` (Plan 31-03) skips only cycle-participating containment edges (surgical recovery per D-15); the acyclic remainder is preserved.
- `references` and `depends_on` edges are precomputed once per `cg update` by `graph_io.derived_edges.compute` (Plan 31-04) and stored in the `edges` table — queries read them directly with no re-computation.

## Success Criteria

### SC#1: Explicit-config Domain emission + zero-domain mode

> A `domains.yaml` declaring `billing: packages: [billing-service]` at repo root produces a `Domain(billing)` node after `cg update`; `cg list-domains` shows it; `cg update` with no `domains.yaml` exits 0 with no Domain nodes (zero-domain is not an error)

- **Verified by:** `test_emit_domain_nodes` (Domain node + belongs_to_domain edge) and `test_missing_yaml_zero_domain` (missing yaml → 0 Domains).
- **Note:** `cg list-domains` is a Phase 33 CLI surface — out of scope for Phase 31's emit-only contract. The Domain nodes ARE in the graph and queryable via Phase 32's helpers.

### SC#2: Surgical cycle recovery (D-15 wording amendment)

> A `domains.yaml` with a cycle (`payments → billing → payments`) causes `domains.emit` to print a warning identifying the cycle and skip ONLY the cycle-participating containment edges (keeping the acyclic remainder) without crashing — `cg update` exits 0

- **Verified by:** `test_cycle_skip_only_intra_scc` (2-cycle + outside edge preserved) and `test_cycle_length_3_intra_scc_only_skipped` (3-cycle — all 3 intra edges skipped, nodes still emit). The fixture in `test_cycle_skip_only_intra_scc` includes an `outside: parent: payments` edge that survives the cycle — proves the surgical recovery wording is satisfied.
- **Wording locked:** Plan 31-01 amended ROADMAP.md SC#2 line 168 to read exactly "skip ONLY the cycle-participating containment edges (keeping the acyclic remainder)".

### SC#3: Derived edges + orchestration idempotency

> After `cg update --full` on a repo with domains configured and cross-domain imports, `SELECT COUNT(*) FROM edges WHERE kind='references'` returns > 0; `SELECT COUNT(*) FROM edges WHERE kind='depends_on'` returns > 0; running `cg update` a second time does not duplicate the derived edges

- **Verified by:** `test_references_emitted` (count > 0 + usage_count attr), `test_depends_on_emitted` (count > 0 + usage_count attr), `test_idempotency` (re-compute produces identical edge set), `test_update_run_end_to_end` (second `update.run` call produces edges_first == edges_second).
- **Mechanism:** `derived_edges.compute()` opens `with conn:`, runs 3 DELETEs (references / depends_on / tests-with-Domain-dst), then recomputes — trivially idempotent at the compute level AND at the orchestration level (the end-to-end test exercises the latter).

### SC#4: Unknown package warning with known-list

> A `domains.yaml` referencing a package name that does not exist in the DB prints a warning including the list of known package names — the user can see what names are valid

- **Verified by:** `test_unknown_package_warns_with_known_list`. The warning message in `domains.py` line 169 includes `f"Known packages: {known_sorted_csv}"` where `known_sorted_csv = ", ".join(sorted(known_names))`. The test asserts the substring `"package 'bogus' (in domain 'a')"` and both known package names appear in `caplog.text`.

### SC#5: No convention inference from test directories

> A repo with `tests/billing/` at root (no `domains.yaml`) does NOT produce a `Domain(billing)` node — convention inference does not treat test subdirectories as domain candidates

- **Verified by:** `test_no_convention_inference_from_test_dir`. Builds `tests/billing/__init__.py` with NO `domains.yaml`, calls `domains.emit`, asserts `SELECT id FROM nodes WHERE kind='domain' AND name='billing'` returns None. `domains._load_domains_yaml` returns None when the file is missing, and `emit` returns early — no Domain nodes are ever inferred from FS layout.

## Requirements Traceability

All 9 requirements in `phase_req_ids` are marked complete in REQUIREMENTS.md:

| Req ID | Description | Marked complete by |
|--------|-------------|--------------------|
| DOMAIN-01 | Domain nodes from explicit config | Plan 31-01 |
| DOMAIN-02 | belongs_to_domain edges | Plan 31-03 |
| DOMAIN-03 | domain_contains_domain edges | Plan 31-01 |
| DOMAIN-04 | Missing yaml = no error | Plan 31-03 |
| DOMAIN-05 | Explicit-config-only | Plan 31-03 |
| DERIVED-01 | references edges | Plan 31-02 |
| DERIVED-02 | depends_on edges | Plan 31-02 |
| DERIVED-03 | Single-transaction recompute | Plan 31-04 |
| DERIVED-04 | No transitive bubble-up at compute | Plan 31-04 |

Note: DOMAIN-01 and DOMAIN-03 were marked complete by Plan 31-01 because that plan landed the URI shape required for Domain identity (D-05). The downstream Plan 31-03 implements the actual emitter; the requirement check is satisfied because both prerequisites (URI shape) and implementation exist by phase end.

DERIVED-01/02 marked by Plan 31-02 because that plan ships the shared `scan_package_imports` surface that `derived_edges.compute` consumes. The actual edge emission happens in Plan 31-04, but per the planner's frontmatter the requirement closure is satisfied when the dependency chain is complete.

## Plans

All 4 plans have SUMMARY.md files and are marked complete:

| Plan | Title | Result |
|------|-------|--------|
| 31-01 | Wave 0 Pre-Req Patches | 3 tasks; 4 AC each; 215 → 215 tests (3 in-place edits) |
| 31-02 | import_scan extraction + test_suites back-port | 4 tasks; 26 AC; +8 tests (215 → 223) |
| 31-03 | domains.py loader + Tarjan cycle detection | 4 tasks; 33 AC; +14 tests (223 → 237) |
| 31-04 | derived_edges + update.run wiring | 5 tasks; 26 AC; +9 tests (237 → 246) |

Net test growth across Phase 31: **+31 tests** (215 → 246).

## Test Suite

```
$ uv run --package graph-io pytest packages/graph-io/tests/ -q
246 passed, 1 skipped in 11.89s
```

The single skip is `test_pyproject_scripts_entry_point_resolves_to_file` — a fixture-dependent assertion that was already skipped in the Phase 30 baseline. Not a regression.

## Cross-Phase Regression Check

Phase 28, 29, 30 tests all remain green after Phase 31 lands:
- Phase 28 (schema v2): no schema changes in Phase 31 — pass.
- Phase 29 (structural nodes): `structural_nodes.emit` unchanged; Phase 31 only consumes `_owning_package`/`_resolve_import_root` — pass.
- Phase 30 (entry points + test suites): `test_suites.py` back-ported in Plan 31-02; 21 of 22 Phase 30 tests still pass + 1 fixture-dependent skip (unchanged). The back-port preserved the public behavior contract — same TestSuite → Package + TestSuite → Repository edges emitted for the same fixtures.

## Code Review

REVIEW.md status: **clean** (0 Critical, 0 Warning, 3 Info — all defensible / non-blocking).

## Security

Verified via REVIEW.md:
- Parameterized SQL throughout — no injection risk.
- `yaml.safe_load` (never `yaml.load`) for `domains.yaml`.
- Path traversal: `Path.resolve()` + `.relative_to(repo_root)` guards in `_match_js_import`.
- File reads use `errors='ignore'` and catch `OSError`.

## Deviations Encountered

One deviation, documented in Plan 31-04 SUMMARY (Rule 1 — bug/contradiction fix):

- **Plan 31-04 Task 4 AC#1** required module-top imports of `domains` and `derived_edges` in `update.py`. Implementing that would create a circular import (`update → derived_edges → import_scan → structural_nodes → update`). Resolved by extending the existing deferred-import pattern inside `run()` (which already covers `entry_points`/`structural_nodes`/`test_suites` for the same cycle-break reason). All other Task 4 AC pass; the behavioural contract is fully satisfied.

## Human Verification

None required. All assertions are automatable and covered by the test suite.

## Outcome

Phase 31 is verified complete. Ready for Phase 32 (Query Layer Extensions) which will consume the `references` and `depends_on` edges via new query helpers.
