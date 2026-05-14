---
phase: 05-remaining-commands
plan: "02"
subsystem: vault-io / lint
tags: [lint, port, mechanical, vault-io, wave-2]
dependency_graph:
  requires:
    - vault_io.lint.common (FRONTMATTER_RE, parse_frontmatter, parse_inline_list, FILE_MAP_SECTION_RE, parse_section_entries)
    - vault_io.layout_io.read_layout
    - vault_io.scan_monorepo._git_ls_files
    - vault_io.git_state.changed_files_since
  provides:
    - vault_io.lint.container.check(repo, wiki) -> list[str]
    - vault_io.lint.dependency.check(pages, *, workspaces=None) -> list[str]
    - vault_io.lint.domain.check(pages) -> list[str]
    - vault_io.lint.file_map.check(repo, pages) -> list[str]
    - vault_io.lint.package_sync.check(repo, wiki) -> list[str]
    - vault_io.lint.source_sync.check(repo, wiki) -> list[str]
    - vault_io.lint.workflow_hints.check(pages, vault) -> list[str]
  affects:
    - plan-05-06 (lint command can import all 7 modules directly)
tech_stack:
  added: []
  patterns:
    - Mechanical import swap port: lattice_wiki_core.X -> vault_io.X, no logic changes
    - _git_ls_files used as private-but-acceptable cross-module dep (per RESEARCH Risk 6)
    - Deferred git imports inside check() body for package_sync and source_sync
key_files:
  created:
    - cores/vault-io/src/vault_io/lint/container.py (62 lines)
    - cores/vault-io/src/vault_io/lint/dependency.py (155 lines)
    - cores/vault-io/src/vault_io/lint/domain.py (43 lines)
    - cores/vault-io/src/vault_io/lint/file_map.py (66 lines)
    - cores/vault-io/src/vault_io/lint/package_sync.py (52 lines)
    - cores/vault-io/src/vault_io/lint/source_sync.py (49 lines)
    - cores/vault-io/src/vault_io/lint/workflow_hints.py (58 lines)
  modified:
    - cores/vault-io/tests/test_lint_modules.py (Wave 0 skip-stub replaced with 11 real tests)
decisions:
  - "_git_ls_files imported as private function from vault_io.scan_monorepo (intentional, per plan RESEARCH Risk 6 acceptance)"
  - "domain.py has no vault_io imports — ported verbatim with zero changes"
  - "package_sync.py and source_sync.py use deferred `from vault_io.git_state import changed_files_since` inside check() body — matches upstream pattern exactly"
metrics:
  duration_seconds: 420
  completed_date: "2026-05-14"
  tasks_completed: 2
  tasks_total: 2
  files_created: 7
  files_modified: 1
---

# Phase 05 Plan 02: 7 lint mechanical modules port Summary

Ported all 7 lint mechanical rule modules from lattice-wiki-core into vault_io with import-only rewrites. 485 lines of source code, zero logic changes. Replaced the Wave 0 skip-stub test with 11 real assertions covering importability, GROUP constant uniqueness, and check() return type against fixture vaults.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Port 7 lint mechanical modules with import swaps | 1c4558a | 7 new lint module files |
| 2 | test_lint_modules.py — assertions against fixture vaults | a8bd3a9 | test_lint_modules.py |

## Tests Passing

| File | Tests |
|------|-------|
| cores/vault-io/tests/test_lint_modules.py | 11 passed |
| cores/vault-io/tests/ (full suite) | 25 passed, 2 skipped (ingest stubs, plan-05-03) |

## Exact check() Signatures for plan-05-06

| Module | Signature | GROUP |
|--------|-----------|-------|
| container | `check(repo: Path, wiki: Path) -> list[str]` | `"container"` |
| dependency | `check(pages: dict, *, workspaces: list[dict] \| None = None) -> list[str]` | `"dependency_layer"` |
| domain | `check(pages: dict) -> list[str]` | `"domain"` |
| file_map | `check(repo: Path, pages: dict) -> list[str]` | `"file_map"` |
| package_sync | `check(repo: Path, wiki: Path) -> list[str]` | `"package_sync"` |
| source_sync | `check(repo: Path, wiki: Path) -> list[str]` | `"source_sync"` |
| workflow_hints | `check(pages: dict, vault: Path) -> list[str]` | `"workflow_hints"` |

**Note for plan-05-06:** The `pages` dict shape is `{key: {"fm": dict, "text": str}}` where `key` is the vault-relative path without `.md` extension (e.g., `"packages/foo/foo"`).

## _git_ls_files Export Status

`_git_ls_files` is defined as a private function (`def _git_ls_files(pkg_path: Path) -> list[str] | None:`) in `cores/vault-io/src/vault_io/scan_monorepo.py` at line 274. It is imported with a try/except fallback in `file_map.py`:

```python
try:
    from vault_io.scan_monorepo import _git_ls_files as _scan_git_ls_files
except ImportError:
    _scan_git_ls_files = None
```

No renaming was required. The function accepts a `Path` (package directory) and returns `list[str] | None`.

## Deviations from Plan

None — plan executed exactly as written. All 7 files are byte-for-byte ports with only `lattice_wiki_core` → `vault_io` import substitutions.

## Known Stubs

None — all 7 modules are fully functional. Tests exercise real fixture paths with real module logic.

## Threat Flags

None — no new network endpoints, auth paths, file writes, or schema changes. All 7 modules are read-only file scanners.

## Self-Check: PASSED

Files exist:
- cores/vault-io/src/vault_io/lint/container.py ✓
- cores/vault-io/src/vault_io/lint/dependency.py ✓
- cores/vault-io/src/vault_io/lint/domain.py ✓
- cores/vault-io/src/vault_io/lint/file_map.py ✓
- cores/vault-io/src/vault_io/lint/package_sync.py ✓
- cores/vault-io/src/vault_io/lint/source_sync.py ✓
- cores/vault-io/src/vault_io/lint/workflow_hints.py ✓
- cores/vault-io/tests/test_lint_modules.py ✓

Commits exist:
- 1c4558a ✓
- a8bd3a9 ✓
