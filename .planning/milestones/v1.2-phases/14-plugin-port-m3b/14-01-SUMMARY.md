---
phase: 14-plugin-port-m3b
plan: "01"
subsystem: vault-io
tags: [port, vault-io, lint, brand-rebrand]
requirements: [PLUGIN-04]

dependency_graph:
  requires:
    - vault_io._workspace.resolve_wiki_and_repo
    - vault_io.layout_io.read_layout
    - vault_io.lint.common
    - vault_io.lint.container
    - vault_io.lint.dependency
    - vault_io.lint.domain
    - vault_io.lint.file_map
    - vault_io.lint.package_sync
    - vault_io.lint.source_sync
    - vault_io.lint.workflow_hints
    - vault_io.scan_monorepo.discover_workspaces
  provides:
    - vault_io.lint_wiki.main
    - vault_io.lint_wiki.scan
  affects:
    - Plan 14-03 (plugin shim can now import from vault_io.lint_wiki)

tech_stack:
  added: []
  patterns:
    - Verbatim port with brand-rename table (SR-01 / VP-01 rubric)
    - No provenance headers (in-tree convention)
    - Thin dispatcher over lint/* submodules

key_files:
  created:
    - packages/vault-io/src/vault_io/lint_wiki.py
    - packages/vault-io/tests/test_lint_wiki.py
  modified:
    - .brand-grep-allow

decisions:
  - "_version_check import dropped: not in vault_io scope per VP-01; main() call to check_for_updates also removed"
  - "pytest_cache allowlisted in brand-grep-allow: brand gate scans working tree; gitignored cache files embed test names with upstream lattice strings; this is a generated-artifact allowlist, not a code allowlist"
  - "test uses tmp_path fixture not edge-case-vault: scan() uses wiki.parent as workspace; passing edge-case-vault directly would scan the fixtures/ dir containing all sibling vaults"

metrics:
  duration_seconds: 140
  completed_date: "2026-05-19"
  tasks_completed: 2
  files_changed: 3
---

# Phase 14 Plan 01: vault_io.lint_wiki Port Summary

Verbatim port of `lattice_wiki_core.lint_wiki` (~509 LOC) into `vault_io.lint_wiki` with brand-rename table applied, `_version_check` import dropped, and brand gate cleared without exceptions.

## What Was Built

`packages/vault-io/src/vault_io/lint_wiki.py` is a faithful port of the upstream wiki health-check module. It dispatches to the 7 `vault_io.lint.*` submodules and exposes `scan()` (returns a structured dict with 17 health-check keys) and `main()` (argparse CLI entry) with identical signatures to the upstream.

`packages/vault-io/tests/test_lint_wiki.py` provides importability smoke and a structural smoke test against a minimal tmp_path wiki. Finding-count parity with upstream is explicitly out of Phase 14 scope per VP-02.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1.1 | Port lint_wiki.py from upstream | 70f8d23 | packages/vault-io/src/vault_io/lint_wiki.py, .brand-grep-allow |
| 1.2 | Add structural test for vault_io.lint_wiki | d1215fd | packages/vault-io/tests/test_lint_wiki.py |
| fix | Allowlist .pytest_cache/ in brand-grep-allow | a6de121 | .brand-grep-allow |

## Verification Results

- `uv run --package vault-io pytest packages/vault-io/tests/test_lint_wiki.py`: 2 passed
- `uv run --package vault-io pytest packages/vault-io/tests/`: 73 passed (no regressions)
- `bash scripts/check-brand.sh`: BRAND-04 OK
- `grep -c "lattice" packages/vault-io/src/vault_io/lint_wiki.py`: 0
- `grep -c "_version_check" packages/vault-io/src/vault_io/lint_wiki.py`: 0
- `grep -E "^from vault_io\." packages/vault-io/src/vault_io/lint_wiki.py | wc -l`: 10

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical fix] pytest_cache brand-gate hit after test run**
- **Found during:** Final verification (after Task 1.2 commit)
- **Issue:** `bash scripts/check-brand.sh` failed with 1 hit in `packages/vault-io/.pytest_cache/v/cache/nodeids` which embeds test node IDs including names with "lattice" strings (e.g. `test_no_lattice_wiki_core_imports`). This file is gitignored but the brand gate scans the working tree.
- **Fix:** Added `.pytest_cache/` to `.brand-grep-allow` with rationale comment explaining it is generated/gitignored output. The real source files that produce those test names are already allowlisted.
- **Files modified:** `.brand-grep-allow`
- **Commit:** a6de121

**2. [Rule 1 - Bug] `lattice_` token in test module docstring**
- **Found during:** Task 1.2 acceptance check
- **Issue:** The initial test file docstring referenced `lattice_wiki_core.lint_wiki` which triggered brand gate failure.
- **Fix:** Rewrote the scope-out note to say "the upstream lint_wiki module" without naming the upstream package by its Python identifier.
- **Files modified:** `packages/vault-io/tests/test_lint_wiki.py`
- **Commit:** included in d1215fd (caught before committing)

## Known Stubs

None — `lint_wiki.py` is a functional port; all dispatch paths are wired to real `vault_io.lint.*` submodules.

## Threat Flags

None — this is a read-only verbatim port with no new network endpoints, auth paths, file write paths, or schema changes. Threat model in the plan is unchanged.

## Self-Check: PASSED

- `packages/vault-io/src/vault_io/lint_wiki.py` — FOUND
- `packages/vault-io/tests/test_lint_wiki.py` — FOUND
- `.planning/phases/14-plugin-port-m3b/14-01-SUMMARY.md` — FOUND
- commit 70f8d23 — FOUND
- commit d1215fd — FOUND
- commit a6de121 — FOUND
