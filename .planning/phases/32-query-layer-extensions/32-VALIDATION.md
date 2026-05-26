---
phase: 32
slug: query-layer-extensions
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-25
---

# Phase 32 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (pytest-asyncio 1.x — not needed; sync tests only) |
| **Config file** | `packages/graph-io/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -x` |
| **Full suite command** | `uv run --package graph-io pytest packages/graph-io/tests/` |
| **Estimated runtime** | ~30 seconds (session-scoped seeded_db runs `cg update --full` once) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -x -k <task-id-test-pattern>`
- **After every plan wave:** Run full `test_queries.py` module
- **Before `/gsd:verify-work`:** Full graph-io suite must be green (`uv run --package graph-io pytest packages/graph-io/tests/`)
- **Max feedback latency:** 30 seconds (first run includes the one-time `cg update --full`; subsequent runs reuse the session fixture in ~5 s)

---

## Per-Task Verification Map

> Filled in by the planner during plan composition. Each new helper or
> dataclass extension gets at least one row. The Status column flips to
> ✅ as tests land green during execute-phase.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-01-01 | 01 | 0 | QUERY-01..04 | — | Dataclass field set exact + frozen | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_dataclass_field_shapes -x` | ❌ W0 | ⬜ pending |
| 32-01-02 | 01 | 0 | QUERY-01 | — | find allow-list rejects unknown kinds | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_find_unknown_kind_raises -x` | ❌ W0 | ⬜ pending |
| 32-01-03 | 01 | 0 | QUERY-04 (fixture) | — | sample_monorepo D-15 checklist passes after `cg update --full` | integration | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_seeded_db_fixture_audit -x` | ❌ W0 | ⬜ pending |
| 32-02-01 | 02 | 1 | QUERY-01 | — | find returns rows for each new kind | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_find_per_kind -x` | ❌ W0 | ⬜ pending |
| 32-02-02 | 02 | 1 | QUERY-04 | — | `describe_repository` returns RepoDescription | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_describe_repository -x` | ❌ W0 | ⬜ pending |
| 32-02-03 | 02 | 1 | QUERY-04 | — | `describe_domain` happy + None | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_describe_domain -x` | ❌ W0 | ⬜ pending |
| 32-02-04 | 02 | 1 | QUERY-04 | — | `describe_entry_point` happy + None | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_describe_entry_point -x` | ❌ W0 | ⬜ pending |
| 32-02-05 | 02 | 1 | QUERY-04 | — | `describe_test_suite` happy + None | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_describe_test_suite -x` | ❌ W0 | ⬜ pending |
| 32-02-06 | 02 | 1 | QUERY-04 | — | `list_*` helpers return alphabetically sorted NodeRecords | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -k test_list_ -x` | ❌ W0 | ⬜ pending |
| 32-02-07 | 02 | 1 | QUERY-02 | — | `describe_package` extension fields populated | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_describe_package_extended -x` | ❌ W0 | ⬜ pending |
| 32-02-08 | 02 | 1 | QUERY-03 | — | `describe_path` role_flags dict for File / None for Package | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_describe_path_role_flags -x` | ❌ W0 | ⬜ pending |
| 32-03-01 | 03 | 2 | QUERY-04 | — | `tests_for_domain` UNION direct + inferred branches | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_tests_for_domain_union -x` | ❌ W0 | ⬜ pending |
| 32-03-02 | 03 | 2 | QUERY-04 | — | `domain_references` bubble-up via CTE | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_domain_references_bubble -x` | ❌ W0 | ⬜ pending |
| 32-03-03 | 03 | 2 | QUERY-04 | — | `domain_depends_on` bubble-up, self-loop excluded | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_domain_depends_on_no_self_loop -x` | ❌ W0 | ⬜ pending |
| 32-03-04 | 03 | 2 | QUERY-04 | — | `cross_cutting_packages` ranking + tie-break stable | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_cross_cutting_packages_ranking -x` | ❌ W0 | ⬜ pending |
| 32-03-05 | 03 | 2 | QUERY-04 | — | `entry_points_for_package` + `tests_for_package` | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -k _for_package -x` | ❌ W0 | ⬜ pending |
| 32-03-06 | 03 | 2 | QUERY-04 | — | CTE cycle-safety paranoid test (5s timeout) | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py::test_cte_cycle_safe -x` | ❌ W0 | ⬜ pending |
| 32-03-07 | 03 | 2 | QUERY-01..04 | — | Empty-DB graceful degradation (every helper) | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_queries.py -k empty -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `packages/graph-io/tests/conftest.py` — `seeded_db` session-scoped fixture (D-14)
- [ ] `packages/graph-io/tests/test_queries.py` — extended with new test stubs (file already exists; add new test functions)
- [ ] `tests/fixtures/sample_monorepo/` — fixture audit + back-fills per D-15 checklist (depends on Phase 31 ship)

*Existing infrastructure (pytest, graph-io workspace member, sample_monorepo) covers all other phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Read-only conn enforcement | D-16 | Code review — no runtime check; relies on `mode=ro` URI param + reviewer confirming no INSERT/UPDATE/DELETE in queries.py changes | Reviewer greps Phase 32 queries.py diff for `INSERT INTO\|UPDATE \|DELETE FROM\|CREATE \|DROP `; expects zero matches. |
| ONTOLOGY-SPEC.md not edited | D-11 (deliberate divergence) | Static-text check | `git diff --stat .planning/research/ONTOLOGY-SPEC.md` reports zero changes for any Phase 32 commit |

---

## Cross-Phase Dependency Gate

**Phase 32 tests can only PASS GREEN after Phase 31 ships.** The
session-scoped `seeded_db` fixture runs `cg update --full` which invokes
`domains.emit` and `derived_edges.compute` (Phase 31 deliverables) plus
expects `tests/fixtures/sample_monorepo/domains.yaml` to exist (Phase 31
D-03). Test stubs CAN and MUST be written from Phase 31 CONTEXT.md alone
in Phase 32 plans; SC#4 verification (every helper green) is gated on
Phase 31's ship date.

If Phase 32 is verified before Phase 31 ships, the per-task status column
will show ❌ for every row that exercises `seeded_db` — that's expected
and the verifier should treat it as a "blocked on upstream" state, not
a Phase 32 defect.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`seeded_db` fixture, fixture audit)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
