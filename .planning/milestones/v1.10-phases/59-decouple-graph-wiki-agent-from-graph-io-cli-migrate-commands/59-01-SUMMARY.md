---
phase: 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands
plan: 01
subsystem: graph-io
tags: [graph-io, render, formatter, refactor, cli, tdd]

requires:
  - phase: 55-graph-io-dependency-classification
    provides: PackageDescription.internal_dependencies/internal_dependents fields used in format_package

provides:
  - graph_io.render public module with render() + 6 format_<kind>() functions
  - graph_io.cli._format re-export shim preserving 7 existing importers
  - Single source of truth for cg describe output formatting

affects:
  - 59-02 (agent migration — imports graph_io.render directly)
  - any future code that renders describe output

tech-stack:
  added: []
  patterns:
    - "Formatter promotion: move formatter from graph_io.cli to graph_io.render; replace original with re-export shim"
    - "Re-export shim: thin _format.py keeps 7 legacy importers working without changes"
    - "import json as _json alias preserved in render.py so format_* and render() bodies are consistent"

key-files:
  created:
    - packages/graph-io/src/graph_io/render.py
    - packages/graph-io/tests/test_render.py
  modified:
    - packages/graph-io/src/graph_io/cli/_format.py
    - packages/graph-io/src/graph_io/cli/q_describe_package.py
    - packages/graph-io/src/graph_io/cli/q_describe_path.py
    - packages/graph-io/src/graph_io/cli/q_describe_repo.py
    - packages/graph-io/src/graph_io/cli/q_describe_domain.py
    - packages/graph-io/src/graph_io/cli/q_describe_entry_point.py
    - packages/graph-io/src/graph_io/cli/q_describe_suite.py
    - packages/graph-io/src/graph_io/cli/q_find.py

key-decisions:
  - "_format.py converted to re-export shim rather than deleted — 7 cli modules (q_find + q_imported_by/q_exported_by/q_exports/q_imports/q_callers/q_callees) import it and must not break"
  - "render.py uses 'import json as _json' throughout (not plain 'import json') for consistency across the moved render() body and the 6 new format_* functions"
  - "format_domain(desc, packages, subdomains, fmt) signature: packages and subdomains are NOT in DomainDescription, so they are passed as explicit args by the caller"
  - "format_suite uses 'suite:' label not 'test_suite:' — preserved exactly from q_describe_suite.py inline printer (D-03)"

patterns-established:
  - "Public formatter module pattern: graph_io.render is now the single formatting source; cli modules call it rather than owning inline format logic"
  - "Re-export shim pattern: when promoting a module, leave a thin re-export shim in the original location for backward compatibility"

requirements-completed: [SC-03]

duration: 8min
completed: 2026-05-29
---

# Phase 59 Plan 01: Formatter Promotion Summary

**Promoted `graph_io.cli._format` to public `graph_io.render` module, extracted 6 inline `q_describe_*.py` formatters into it, and refactored all 7 cg cli modules to call the single shared renderer — cg test suite remains byte-identical.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-29T17:49:00Z
- **Completed:** 2026-05-29T17:55:10Z
- **Tasks:** 2
- **Files modified:** 9 (1 created, 1 new test, 7 modified)

## Accomplishments
- Created `packages/graph-io/src/graph_io/render.py` with `render()` (promoted verbatim from `_format.py`) plus 6 new `format_<kind>()` functions extracted byte-for-byte from the inline printers in each `q_describe_*.py`
- Replaced `_format.py` body with a thin re-export shim (`from graph_io.render import render, _to_dict, ...`) — preserves the 7 existing importers without any change to those modules
- Refactored all 6 `q_describe_*.py` and `q_find.py` to call `graph_io.render` functions, removing orphaned `import dataclasses` and `import json as _json` from each
- cg byte-identical guard: 57 tests pass (test_cli_format, test_cli_describe, test_cli_describe_entry_point, test_cli_exit_codes, test_cli_anti_regression) + 1 xfailed

## Task Commits

TDD task (Task 1 had three commits per TDD RED/GREEN lifecycle):

1. **RED: test(59-01)** - `9687245` — failing tests for graph_io.render public module
2. **GREEN: feat(59-01)** - `e100b9e` — create render.py + _format.py re-export shim
3. **refactor(59-01)** - `148b2a4` — migrate 6 q_describe_*.py + q_find.py to call graph_io.render

_Note: Task 2 (migrate cli modules) was committed together with the refactor in step 3 above._

## Files Created/Modified
- `packages/graph-io/src/graph_io/render.py` — new public formatter: `render()` + `format_package/path/repo/domain/entry_point/suite`
- `packages/graph-io/tests/test_render.py` — new tests verifying public module API, shim identity, format_* output shapes
- `packages/graph-io/src/graph_io/cli/_format.py` — replaced with re-export shim from `graph_io.render`
- `packages/graph-io/src/graph_io/cli/q_describe_package.py` — inline format block replaced with `print(_render.format_package(desc, fmt=args.fmt))`
- `packages/graph-io/src/graph_io/cli/q_describe_path.py` — inline format block replaced with `print(_render.format_path(...))`
- `packages/graph-io/src/graph_io/cli/q_describe_repo.py` — inline format block replaced with `print(_render.format_repo(...))`
- `packages/graph-io/src/graph_io/cli/q_describe_domain.py` — SQL queries for packages/subdomains kept; format block replaced with `print(_render.format_domain(desc, packages, subdomains, fmt=args.fmt))`
- `packages/graph-io/src/graph_io/cli/q_describe_entry_point.py` — disambiguation logic unchanged; format block replaced with `print(_render.format_entry_point(...))`
- `packages/graph-io/src/graph_io/cli/q_describe_suite.py` — inline format block replaced with `print(_render.format_suite(...))`
- `packages/graph-io/src/graph_io/cli/q_find.py` — `from graph_io.cli import _format` → `from graph_io import render as _render`; `_format.render(...)` → `_render.render(...)`

## Decisions Made

- **_format.py shim (not deletion):** PATTERNS.md and RESEARCH.md said to delete `_format.py` after the promotion. The audit correction in the plan's `<interfaces>` block identified that 7 modules (not just `q_find`) import `_format`. The shim approach was the correct resolution — keeps all 7 importers working without any change to those modules.
- **`import json as _json` in render.py:** The original `_format.py` used plain `import json` without alias. The 6 new `format_*` functions (extracted from `q_describe_*.py` which used `import json as _json`) needed the alias. Rather than mix aliased and unaliased calls, `render.py` uses `import json as _json` throughout and all calls are `_json.dumps(...)`.
- **format_domain explicit args:** `packages` and `subdomains` are NOT in `DomainDescription`. The function signature `format_domain(desc, packages, subdomains, fmt)` passes them as explicit args from the caller (which runs the two SQL queries).

## Deviations from Plan

None — plan executed exactly as written. The one pre-identified subtlety (shim vs. delete) was already documented in the plan's `<interfaces>` block as "IMPORTANT (audit correction)".

## Issues Encountered

None. The output shapes were extracted exactly from the existing inline printers; the cg test suite confirmed byte-identical output after each change.

## Output-Shape Subtleties Discovered

- `format_package` renders `files: {len(desc.files)}` (count), not the list itself — matching the original `print(f"files:    {len(desc.files)}")`
- `format_domain` human output: when `packages` is empty, renders `  (none)` (two-space indent); same for `subdomains`
- `format_entry_point` has a `source:` field that was `(none)`-defaulted — `desc.source` can be None despite no `| None` annotation on the dataclass (the inline printer already handled this)
- All `format_*` functions return strings without trailing newlines; callers do `print(output)` which adds the final newline — exactly matching the original multi-`print()` behavior

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- `graph_io.render` is now a public, importable module — Plan 02 can `from graph_io import render as _render` to format describe/query output without importing `graph_io.cli`
- Plan 02 (agent migration of `commands/graph.py`) can proceed immediately

---
*Phase: 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands*
*Completed: 2026-05-29*
