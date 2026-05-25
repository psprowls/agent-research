---
phase: quick-260523-he3
plan: 01
subsystem: wiki-io / graph-wiki plugin
tags: [file-map, lint, emitter, parser, templates, docs]
dependency_graph:
  requires: []
  provides: [new-file-map-table-format]
  affects: [wiki-io.scan_monorepo, wiki-io.lint.common, graph-wiki.scanner, graph-wiki.page-formats]
tech_stack:
  added: []
  patterns: [per-major-folder H3 sections, markdown tables for file map, graceful parser fallback]
key_files:
  created: []
  modified:
    - packages/wiki-io/src/wiki_io/scan_monorepo.py
    - packages/wiki-io/src/wiki_io/lint/common.py
    - packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/app.md
    - packages/wiki-io/tests/test_scan_monorepo.py
    - packages/wiki-io/tests/test_lint_modules.py
    - packages/wiki-io/tests/fixtures/round-trip-vault/.templates/package.md
    - packages/wiki-io/tests/fixtures/round-trip-vault/.templates/package/overview.md
    - plugins/graph-wiki/skills/graph-wiki/references/page-formats.md
    - plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
    - plugins/graph-wiki/agents/scanner.md
decisions:
  - Removed BULLET_RE constant from common.py (now unused after parse_section_entries rewrite)
  - Graceful fallback: old-format bodies return H3-derived dir entries only, no crash, no false-positive file rows
  - No dual-parser; single implementation with a clean no-op path for legacy content
metrics:
  duration: ~45 minutes
  completed: 2026-05-23
  tasks_completed: 6
  files_modified: 11
---

# Phase quick-260523-he3 Plan 01: Revise File Map Format Summary

One-liner: File map block refactored from heading+bullet sub-sections to H2 + per-major-folder H3 markdown tables (Path | Kind | Description) across emitter, parser, templates, and reference docs.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite build_file_map() + templates | 17d1183 | scan_monorepo.py, page-templates/package/overview.md, page-templates/app.md, test_scan_monorepo.py |
| 2 | Rewrite parse_section_entries() | de3e6da | lint/common.py, test_lint_modules.py |
| 3 | Update round-trip vault fixture templates | e34e57c | .templates/package.md, .templates/package/overview.md |
| 4 | Update page-formats.md spec | 9944594 | references/page-formats.md |
| 5 | Update scanner.md + scan-workflow.md | 20b9f7e | agents/scanner.md, references/scan-workflow.md |
| 6 | End-to-end verification | (no commit — all checks passed) | — |

## What Was Built

### Task 1 — build_file_map() emitter (17d1183)

Rewrote `build_file_map()` in `packages/wiki-io/src/wiki_io/scan_monorepo.py`:
- Emits `## File map - <pkg>` H2 + one-line overview paragraph
- Emits a synthetic `### <pkg>/` H3 for root-level files (files only; standard depth-1 dirs get their own H3)
- Emits one `### <pkg>/<sub>/` H3 per depth-1 directory, alphabetically sorted
- Each H3 section: placeholder paragraph + markdown table with `| Path | Kind | Description |` / `|---|---|---|` header
- Nested files (depth ≥ 2) flatten into their depth-1 parent's table
- Dirs deeper than `max_depth` appear as `dir` rows in their depth-1 parent's table
- Truncation marker `> Truncated at N files.` appended after the last table when needed
- Empty package short-circuit preserved (returns legacy `- (no tracked files)` format)
- Returns `None` when `_git_ls_files()` returns `None`

9 new tests in `TestBuildFileMap` class covering all behaviors.

Updated templates: `package/overview.md` and `app.md` both show the new table format with `{{PACKAGE_SLUG}}` variables.

### Task 2 — parse_section_entries() parser (de3e6da)

Rewrote `parse_section_entries()` in `packages/wiki-io/src/wiki_io/lint/common.py`:
- Walks body line by line for H3+ headers (via existing `SECTION_HEADER_RE`)
- For each header, derives `current_path` (strips `pkg_name/` prefix) and records dir entry
- Collects the section block (lines until next H3+), calls `parse_markdown_table()` on it
- For each table row: strips backticks from Path cell, detects trailing `/` or `Kind == dir`, applies brace expansion for file rows
- **Graceful fallback**: when no table is found, returns H3-derived dir entries only (no crash, no false-positive file rows for legacy content)
- Removed `BULLET_RE` constant (orphaned by this change, no other consumers)

8 new tests in `TestParseSectionEntries` covering new format, root section, nested paths, dir rows, old-format fallback, malformed table, brace expansion, and pipe escapes.

### Task 3 — Fixture templates (e34e57c)

Updated `.templates/package.md` and `.templates/package/overview.md` in the round-trip vault fixture to the new table format. The 18+ existing in-vault overview pages were intentionally left in the old bullet format to exercise the graceful fallback.

Suite result: 127 passed (was 110, +17 from Tasks 1+2 new tests).

### Task 4 — page-formats.md (9944594)

Rewrote the "File map convention" section with the new table-based rules, including the legacy graceful fallback note. Replaced the §1 (web-next-ts app) and §2 (common-aws-node-ts package) worked File map examples with the new table format. grep count: 7 `| Path | Kind | Description |` occurrences.

### Task 5 — scanner.md + scan-workflow.md (20b9f7e)

- `scanner.md` §3: updated file_map write description to H2 + H3 sections with tables
- `scanner.md` §5: updated unfilled-template detection rule to table rows + added legacy bullet-block migration note
- `scan-workflow.md`: updated file_map backfill description to match
- `lint-workflow.md`: verified format-agnostic; no change needed

### Task 6 — Verification (no commit)

All checks passed:
- `uv run pytest packages/wiki-io/ -x`: 127 passed, 1 skipped
- `uv run pytest packages/eval-harness/ -k scanner -x`: 9 passed, 1 skipped (integration gate), 177 deselected
- SCN-003 manual logic check: `_FILE_MAP_SECTION = "## File map"` is a substring of the new heading `## File map - <pkg>`, so the check still correctly rejects scanner stubs that include a file_map block
- Fresh `build_file_map(Path("packages/wiki-io"))` confirms: H2, overview paragraph, `### wiki-io/` root section, `### wiki-io/src/` section, nested files flatten correctly, tables are `| Path | Kind | Description |`

Fresh build_file_map() output excerpt (packages/wiki-io):
```
## File map - wiki-io
TODO — overview of this package's tree.

### wiki-io/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `DRIFT-DECISIONS-RAW.md` | file | — TODO |
| `DRIFT-DECISIONS.md` | file | — TODO |
| `pyproject.toml` | file | — TODO |

### wiki-io/src/
TODO — describe what this directory contains.

| Path | Kind | Description |
|---|---|---|
| `wiki_io/__init__.py` | file | — TODO |
| `wiki_io/lint/common.py` | file | — TODO |
| ...
```

## Deviations from Plan

None — plan executed exactly as written.

The one deliberate choice (already in the plan's resolved_open_questions): `eval-harness/divergence/rubrics/scanner.md` line 19 contains `"every bullet description is still the '— TODO' placeholder"` in the SCN-005 rubric prose. This was left unchanged per Karpathy §3 (it's pre-existing, not orphaned by this change, and it's evaluator guidance not live code). Noted here for future reference.

## Known Stubs

None. The `— TODO` description cells are the intended placeholder state; they are not data stubs — they are the defined initial state for the file map format.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check

Files exist:
- `packages/wiki-io/src/wiki_io/scan_monorepo.py`: build_file_map() rewritten ✓
- `packages/wiki-io/src/wiki_io/lint/common.py`: parse_section_entries() rewritten, BULLET_RE removed ✓
- `packages/wiki-io/src/wiki_io/assets/page-templates/package/overview.md`: new table format ✓
- `packages/wiki-io/src/wiki_io/assets/page-templates/app.md`: new table format ✓
- `plugins/graph-wiki/skills/graph-wiki/references/page-formats.md`: updated ✓
- `plugins/graph-wiki/agents/scanner.md`: updated ✓

Commits exist:
- 17d1183: feat(quick-260523-he3): emit file_map as per-major-folder tables ✓
- de3e6da: refactor(quick-260523-he3): rewrite parse_section_entries as table parser ✓
- e34e57c: test(quick-260523-he3): update round-trip vault fixture templates ✓
- 9944594: docs(quick-260523-he3): rewrite page-formats.md File map spec ✓
- 20b9f7e: docs(quick-260523-he3): update scanner.md + scan-workflow.md for table format ✓

## Self-Check: PASSED
