---
phase: 32-query-layer-extensions
status: passed
score: 4/4
verifier: gsd-execute-phase (inline)
completed: 2026-05-26
---

# Phase 32: Query Layer Extensions — Verification

## Goal

> All new node and edge types are queryable through `queries.py` helpers, existing `describe_package` and `describe_path` output is extended with new fields, and the query layer is validated against a database with all emitters having run at least once.

**Status:** PASSED — all 4 must-haves verified.

## Requirements

| ID | Status | Evidence |
|----|--------|----------|
| QUERY-01 | ✓ | `find()` now accepts `kind='repository' / 'domain' / 'entry_point' / 'test_suite' / 'subpackage'` via the `_VALID_KINDS` allow-list. `find(conn, kind=k)` for each new kind exercised by `test_find_per_kind` (parametrised, 10/10 kinds pass). |
| QUERY-02 | ✓ | `PackageDescription` gained `domains: list[str]`, `entry_points: list[EntryPointDescription]`, `test_suites: list[SuiteDescription]` (all `field(default_factory=list)`). `describe_package` populates all three via SQL joins on `belongs_to_domain`, `declares_entry_point`+`implemented_by`, and `tests`. Test `test_describe_package_extended` against seeded_db. |
| QUERY-03 | ✓ | `PathDescription` gained `role_flags: dict[str, bool] | None`. `describe_path` projects the 7 file role flags (`is_importable`, `has_main`, `is_test`, `is_config`, `is_generated`, `is_type_only`, `is_executable`) into the dict. Test `test_describe_path_role_flags` against seeded_db asserts the exact 7-key set + bool values. |
| QUERY-04 | ✓ | 16 helpers shipped: 4 `describe_*` + 6 `list_*` + 2 `*_for_package` + 4 domain helpers. Every helper has at least one happy-path test against `seeded_db` AND an empty-DB variant. See `packages/graph-io/tests/test_queries.py` Waves 0/1/2 — 48/48 active tests pass (1 graceful skip). |

## Success Criteria

The ROADMAP SC#1–SC#4 reference `cg`-CLI surrogates which are Phase 33's scope. For Phase 32 (Python query layer) the equivalent surrogates pass:

| SC# | Phase-32 Python surrogate | Result |
|-----|--------------------------|--------|
| 1   | `find(seeded_db, kind=k)` for k in {repository, domain, entry_point, test_suite} returns non-empty rows | PASSED (`test_find_per_kind` parametrised) |
| 2   | `describe_package(seeded_db, name=<pkg>).domains / entry_points / test_suites` are populated lists | PASSED (`test_describe_package_extended`) |
| 3   | `describe_path(seeded_db, path=<File>).role_flags` is a dict with exactly 7 keys | PASSED (`test_describe_path_role_flags`) |
| 4   | Every Phase-32 helper has at least one unit test passing against a seeded DB | PASSED (48 net-new tests across 3 waves) |

## Test Suite

- Phase 32 net-new tests: 48 passing, 1 graceful skip (empty-state `depends_on`).
- Full `packages/graph-io/tests/` suite: 295 passing, 1 skip — zero regressions on Phase 29/30/31 functionality.

## Coverage of New Node/Edge Types

| Node kind | Find | Describe | List |
|-----------|------|----------|------|
| `repository` | ✓ | `describe_repository` ✓ | `list_repositories` ✓ |
| `domain` | ✓ | `describe_domain` ✓ | `list_domains` ✓ |
| `entry_point` | ✓ | `describe_entry_point` ✓ | `list_entry_points` ✓ |
| `test_suite` | ✓ | `describe_test_suite` ✓ | `list_test_suites` ✓ |
| `package` (extended) | ✓ (existing) | `describe_package` (+domains/entry_points/test_suites) ✓ | `list_packages` ✓ |
| `subpackage` | ✓ | — | — |
| `file` (extended path) | ✓ (existing) | `describe_path` (+role_flags) ✓ | `list_scripts` (executable subset) ✓ |

| Edge kind queried | Via helper |
|-------------------|------------|
| `belongs_to_domain` | `describe_package`, `cross_cutting_packages` |
| `domain_contains_domain` | `_DOMAIN_DESCENDANTS_CTE` (3 bubble-up helpers) |
| `references` | `domain_references`, `cross_cutting_packages` |
| `depends_on` | `domain_depends_on` |
| `tests` | `tests_for_package`, `tests_for_domain`, `describe_package` |
| `declares_entry_point` | `entry_points_for_package`, `describe_entry_point`, `describe_package` |
| `implemented_by` | `describe_entry_point`, `entry_points_for_package` |
| `physically_contains` | `describe_test_suite` (file_count subquery) |

## human_verification

None required — all verification is automated against the seeded `sample_monorepo` fixture which exercises every emitter (Phase 29 structural, Phase 30 EntryPoint/TestSuite, Phase 31 derived edges).

## Findings

None blocking. Three planning-vs-reality bugs identified and resolved during execution (all documented in plan SUMMARYs):

1. DB path: PLAN used `.graph-wiki/graph/code.db`, actual is `<workspace>/.graph/code.db`.
2. EntryPoint kind attribute: PLAN read `kind`, emitter writes `entry_kind`.
3. `_upsert_node` signature: PLAN used kwargs, actual takes a `GraphNode`.

Each was reconciled in favour of the real emitter / helper signatures.

## Verdict

PASSED.
