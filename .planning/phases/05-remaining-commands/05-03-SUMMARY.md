---
phase: 05-remaining-commands
plan: "03"
subsystem: vault-io
tags: [ingest, port, library, tdd, wave-2]
dependency_graph:
  requires:
    - vault_io.update_index (update_index function added)
    - vault_io.append_log (append_log)
    - vault_io.layout_io (ensure_subpage)
    - vault_io._workspace (resolve_wiki_and_repo)
    - vault_io.scan_monorepo (compute_state_gate)
  provides:
    - vault_io.ingest_source.slugify
    - vault_io.ingest_source.extract
    - vault_io.ingest_source.guess_source_type
    - vault_io.ingest_source.language_for
    - vault_io.ingest_source.list_folder_files
    - vault_io.ingest_source.pick_representative
    - vault_io.ingest_source.folder_brief
    - vault_io.ingest_source._HTMLTextExtractor
    - vault_io.ingest_work_item._slugify
    - vault_io.ingest_work_item._parse_frontmatter
    - vault_io.ingest_work_item._validate
    - vault_io.ingest_work_item._emit_yaml
    - vault_io.ingest_work_item.file_work_item
    - vault_io.update_index.update_index (new library entry point)
  affects:
    - cores/vault-io/src/vault_io/update_index.py (added update_index() function)
tech_stack:
  added: []
  patterns:
    - TDD RED/GREEN per task
    - Library-only port: no argparse main(), no subprocess calls
    - Direct function import replaces subprocess helper invocation
    - FileExistsError raised instead of sys.exit() for library-safe overwrite guard
key_files:
  created:
    - cores/vault-io/src/vault_io/ingest_source.py
    - cores/vault-io/src/vault_io/ingest_work_item.py
  modified:
    - cores/vault-io/src/vault_io/update_index.py (added update_index() library function)
    - cores/vault-io/tests/test_ingest_source.py (replaced Wave 0 stub with 26 tests)
    - cores/vault-io/tests/test_ingest_work_item.py (replaced Wave 0 stub with 19 tests)
decisions:
  - "update_index(wiki) library function added to update_index.py (Rule 3: required by ingest_work_item port; was absent from existing module which only had main())"
  - "file_work_item() raises FileExistsError instead of sys.exit() on overwrite conflict — library callers should not receive sys.exit(); command layer wraps as needed"
  - "compute_state_gate import kept in ingest_source.py per plan spec (available for callers); not called by library functions since main() was dropped"
metrics:
  duration_seconds: 390
  completed_date: "2026-05-14"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 3
---

# Phase 05 Plan 03: ingest_source + ingest_work_item library ports Summary

Ported `ingest_source.py` and `ingest_work_item.py` from `lattice-wiki-core` into `vault_io` as library modules. The critical change: `_run_helper()` subprocess invocations replaced with direct `update_index(wiki)` / `append_log(wiki, ...)` imports. Both Wave 0 skip stubs replaced with real test suites (45 tests total). Added `update_index(wiki)` as a library entry point to `update_index.py` (required by the port; was absent).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | ingest_source failing tests | 285edb4 | test_ingest_source.py, update_index.py |
| 1 GREEN | ingest_source implementation | 029ee19 | ingest_source.py |
| 2 RED | ingest_work_item failing tests | 13c1581 | test_ingest_work_item.py |
| 2 GREEN | ingest_work_item implementation | 07a3d8f | ingest_work_item.py |

## Tests Passing

| File | Tests |
|------|-------|
| cores/vault-io/tests/test_ingest_source.py | 26 passed |
| cores/vault-io/tests/test_ingest_work_item.py | 19 passed |
| cores/vault-io/tests/ (full suite) | 59 passed, 1 skipped (no regressions) |

## Exported Function Signatures

### vault_io.ingest_source

```python
PREVIEW_CHARS: int = 1200
SLUG_RE: re.Pattern
LANGUAGE_BY_EXT: dict[str, str]
REPRESENTATIVE_INDEX_NAMES: list[str]
LARGE_FILE_BYTES: int = 200 * 1024
WARN_FILE_COUNT: int = 50
ERROR_FILE_COUNT: int = 200

def slugify(text: str) -> str: ...
def extract(path: Path) -> tuple[str, str | None]: ...
def guess_source_type(rel_to_wiki: Path | None, rel_to_repo: Path | None) -> str: ...
def language_for(path: Path) -> str: ...
def list_folder_files(root: Path) -> list[tuple[str, int]]: ...
def pick_representative(root: Path, entries: list[tuple[str, int]]) -> str | None: ...
def folder_brief(root: Path, rel_to_wiki: Path | None) -> dict: ...
class _HTMLTextExtractor(html.parser.HTMLParser): ...
```

### vault_io.ingest_work_item

```python
REQUIRED_FIELDS: tuple = ("title", "category", "kind", "status", "summary", "opened", "affects")
ALLOWED_CATEGORY: str = "work"
SLUG_RE: re.Pattern

def _err(msg: str, code: int = 2, as_json: bool = False) -> NoReturn: ...
def _slugify(title: str) -> str: ...
def _parse_frontmatter(yaml_text: str) -> dict: ...
def _validate(fm: dict) -> list[str]: ...
def _emit_yaml(fm: dict) -> str: ...
def file_work_item(
    wiki: Path,
    fm: dict,
    body: str,
    slug: str | None = None,
    force: bool = False,
    pkg_dir: Path | None = None,
    pkg_title: str | None = None,
) -> dict: ...
```

### file_work_item() return dict shape

```python
{
    "status": "ok",           # always "ok" on success
    "page_path": str,         # absolute path to written page (e.g. ".../work/2026-05-14-fix-auth-bug.md")
    "slug": str,              # computed or supplied slug
    "title": str,             # fm["title"] value
}
```

Plan-05-05 `IngestResult` mapping: `page_path` → `page_path`, `slug` → `slug`, `title` → `title`.

### vault_io.update_index (new library entry point)

```python
def update_index(wiki: Path) -> None:
    """Regenerate wiki/index.md and category sub-indexes from vault frontmatter."""
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing `update_index(wiki)` library function**
- **Found during:** Task 2 implementation (before writing code)
- **Issue:** Plan spec says `from vault_io.update_index import update_index`, but `update_index.py` only had a `main()` function — no library entry point. The port would fail to import.
- **Fix:** Added `update_index(wiki: Path) -> None` library wrapper to `update_index.py` that calls `scan_vault()`, `scan_work()`, `render_index()`, writes `index.md` and category sub-indexes. Logic extracted directly from `main()` without argparse/json/dry-run handling.
- **Files modified:** `cores/vault-io/src/vault_io/update_index.py`
- **Commit:** 285edb4 (bundled with RED test commit)

**2. [Rule 1 - Bug] Docstring mentions forbidden strings (`_version_check`, `_run_helper`)**
- **Found during:** GREEN test runs (test_no_lattice_wiki_core_imports, test_no_subprocess_or_lattice_imports)
- **Issue:** Source text searches for forbidden strings caught them in module docstrings.
- **Fix:** Rewrote docstring phrases to avoid the exact strings being tested for.
- **Files modified:** `ingest_source.py`, `ingest_work_item.py`

**3. [Rule 2 - Missing critical functionality] `file_work_item()` raises `FileExistsError` instead of `sys.exit()`**
- **Found during:** Task 2 design
- **Issue:** Original `main()` called `_err(..., code=3)` which calls `sys.exit(3)` when page exists and `force=False`. Library functions must not call `sys.exit()` — callers can't catch it.
- **Fix:** Raise `FileExistsError` instead. Command layer (plan-05-05) will catch and map to appropriate exit code.

## Key-Links Verified

| From | To | Via | Verified |
|------|----|-----|---------|
| ingest_work_item.py | update_index.py | direct import: `from vault_io.update_index import update_index` | yes — import confirmed, test monkeypatch confirms call |
| ingest_work_item.py | append_log.py | direct import: `from vault_io.append_log import append_log` | yes — test_file_work_item_calls_update_index_and_append_log |
| ingest_source.py | layout_io.py | `from vault_io.layout_io import ensure_subpage` | yes — import confirmed |

## Known Stubs

None — both modules are fully implemented. plan-05-05 can immediately import and use all exported functions.

## Threat Flags

None — no new network endpoints, auth paths, or external trust boundaries beyond what the plan's threat model covers. YAML parsing uses hand-rolled scalar parser (no `yaml.load`) for `_parse_frontmatter`.

## Self-Check: PASSED

Files exist:
- cores/vault-io/src/vault_io/ingest_source.py (exists, 211 lines)
- cores/vault-io/src/vault_io/ingest_work_item.py (exists, 183 lines)
- cores/vault-io/tests/test_ingest_source.py (26 tests)
- cores/vault-io/tests/test_ingest_work_item.py (19 tests)

Commits exist:
- 285edb4 (test RED ingest_source)
- 029ee19 (feat GREEN ingest_source)
- 13c1581 (test RED ingest_work_item)
- 07a3d8f (feat GREEN ingest_work_item)

Full vault-io test suite: 59 passed, 1 skipped.
