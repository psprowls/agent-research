---
phase: 36-cg-find-parser-ergonomics
plan: 01
subsystem: cli
tags: [argparse, graph-io, cg-find, parser-ergonomics, named-flags]

requires:
  - phase: 35-wiki-bootstrap-hygiene-burn-down
    provides: clean baseline (Pitfall 5 grep-all-callers convention)
provides:
  - "cg find --name X / --kind K / --in-package PKG named-flag UX (AND-combined)"
  - "queries.find(in_package=...) with case-insensitive package-name match"
  - "_format.render(cap=N, on_truncate=cb) opt-in 50-row cap (precedent for Phase 37 LIBTOOLS-02)"
  - "argparse parser.error()-driven D-01 violation message and positional-form rejection"
  - "anti-regression guard (test_find_positional_form_errors) preventing silent positional re-introduction"
affects: [37-librarian-grounding-tools]

tech-stack:
  added: []
  patterns:
    - "argparse choices= for kind validation at parse time"
    - "cap + on_truncate callback for caller-controlled stderr notices"
    - "sub-parser exposed via sp.set_defaults(_parser=sp) for parser.error() calls in run()"

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/cli/q_find.py
    - packages/graph-io/src/graph_io/cli/main.py
    - packages/graph-io/src/graph_io/cli/_format.py
    - packages/graph-io/src/graph_io/queries.py
    - packages/graph-io/tests/test_cli_smoke.py
    - packages/graph-io/tests/test_e2e.py
    - packages/graph-io/tests/test_cli_exit_codes.py
    - packages/graph-io/tests/test_cli_anti_regression.py
    - packages/graph-io/tests/test_queries.py
    - packages/graph-io/tests/test_cli_format.py

key-decisions:
  - "Used RESEARCH §1.1 approach (a): sub-parser handle exposed via sp.set_defaults(_parser=sp); run() calls args._parser.error() to surface argparse's usage + error message + exit 2"
  - "Preserved historical kind-only ORDER BY name in queries.find() to keep test_find_per_kind green"
  - "render() cap is keyword-only and defaults to None — every existing caller (q_callers, q_imports, etc.) is untouched; only q_find opts in via cap=50"
  - "D-07 narrow read confirmed: exit 1 fires ONLY when --in-package is set and matches zero rows; --name X / --kind K zero-result keeps SUCCESS to preserve test_imported_by_symbol_filter and similar callers' expectations"

patterns-established:
  - "Per-handler parser.error() pattern: subparser sets _parser via set_defaults; run() can emit argparse-style usage + error + exit 2 without owning the parser construction"
  - "render(cap, on_truncate) — pure formatter + side-channel callback; render() never writes outside its return value"

requirements-completed:
  - CGFIND-01
  - CGFIND-02
  - CGFIND-03

duration: 35min
completed: 2026-05-26
---

# Phase 36: `cg find` Parser Ergonomics — Plan 01 Summary

**`cg find` migrated from positional-first to named-flag-only UX (--name / --kind / --in-package), with --in-package as a new package-scoped filter, a 50-row cap convention, and an anti-regression guard against silent re-introduction of the positional form.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-05-26
- **Tasks:** 4 of 4
- **Files modified:** 10

## Accomplishments

### Task 1 — `queries.find()` extended (CGFIND-02)
- Added `in_package: str | None = None` keyword-only parameter.
- Replaced the 3-branch if/elif body with a dynamic WHERE-clause builder (lists of `where_parts` + `params`) that AND-combines whichever filters were supplied.
- Containment subquery joins `nodes p ('package') → edges ce ('contains') → nodes f ('file')` and matches via `LOWER(p.name) = LOWER(?)` for D-08 case-insensitive exact-match.
- Preserved the historical kind-only ORDER BY (only when name is None AND in_package is None AND kind is not None) — `test_find_per_kind` still passes unchanged.
- "No filters" guard message updated to name all three filters.
- Four new unit tests added to `test_queries.py`: `test_find_in_package`, `test_find_in_package_case_insensitive`, `test_find_all_three_filters`, `test_find_no_filters_raises`. All pass.

### Task 2 — `_format.render()` cap parameter (D-09; CGFIND-02)
- Signature extended to `render(records, fmt, *, cap=None, on_truncate=None)`.
- When `cap` is set and `total > cap`: rows trimmed to the first `cap`; `on_truncate(cap, total)` is invoked if provided.
- Human format: appends `"... showing {cap} of {total} (truncated)"` trailer line.
- JSON format: silent flat-array truncation (no envelope wrap — preserves JSON consumer stability per RESEARCH §3.2 option 1).
- Cap logic applies to both the importer-batch branch and the general-dataclass branch.
- `cap=None` (the default) is a strict pass-through — every existing caller (`q_callers`, `q_imports`, etc.) is unaffected.
- Four new unit tests added to `test_cli_format.py`. All pass.

### Task 3 — `q_find.py` rewrite + `main.py` sub-parser exposure (CGFIND-01/02/03)
- `main.py`: added `_parser=sp` to the per-subcommand `set_defaults` so subparsers are reachable from `run(args)` as `args._parser`. One-line change.
- `q_find.py`: full rewrite to named-flag form:
  - `--name`, `--kind` (with `choices=sorted(_VALID_KINDS)`), `--in-package` (`dest="in_package"`).
  - D-01: `args._parser.error("cg find requires at least one of --name, --kind, --in-package")` when all three are None — argparse exits 2 with the usage banner + this error string.
  - D-03: argparse `choices=` rejects invalid `--kind` at parse time with the built-in `invalid choice` wording — exit 2.
  - D-04: positional values now hit argparse's default `unrecognized arguments` — exit 2.
  - D-07: zero-result with `--in-package` returns `exit_codes.GENERIC` (1); other zero-result paths keep returning SUCCESS as agreed.
  - D-09: `_format.render(records, fmt=args.fmt, cap=50, on_truncate=_notice)` where `_notice` writes the truncation message to stderr.
- Live verified `cg find --help` lists exactly the three named flags.
- Live verified `cg find foo.py` exits 2 with `unrecognized arguments: foo.py`.
- Live verified `cg find` (no args) exits 2 with stderr naming all three flags.

### Task 4 — Test call-site migration + D-11 anti-regression guard (D-10, D-11; CGFIND-03)
Migrated all 8 positional `cg find` test call sites to named-flag form in the same commit:
- `test_cli_smoke.py:43` `["find", "alpha", "--kind", "function"]` → `["find", "--name", "alpha", "--kind", "function"]`
- `test_cli_smoke.py:49` `["--fmt", "json", "find", "alpha"]` → `["--fmt", "json", "find", "--name", "alpha"]`
- `test_cli_smoke.py:91` `["find", "alpha"]` → `["find", "--name", "alpha"]`
- `test_e2e.py:35` `["--fmt", "json", "find", "alpha"]` → `["--fmt", "json", "find", "--name", "alpha"]`
- `test_cli_exit_codes.py:108` `["find", "x"]` → `["find", "--name", "x"]`
- `test_cli_exit_codes.py:204` `["find", "foo"]` → `["find", "--name", "foo"]`
- `test_cli_anti_regression.py:84` `["--fmt", "json", "find", "main"]` → `["--fmt", "json", "find", "--name", "main"]`
- `test_cli_anti_regression.py:118` `"find": ["find", "main"]` → `"find": ["find", "--name", "main"]`

Added six positive-coverage CLI smoke tests in `test_cli_smoke.py`:
`test_find_with_named_flags`, `test_find_no_filters_errors`, `test_find_invalid_kind_errors`,
`test_find_in_package`, `test_find_in_package_case_insensitive`, `test_find_in_package_unknown_exits_1`.

Added D-11 anti-regression test `test_find_positional_form_errors` in `test_cli_anti_regression.py`
asserting `cg find foo.py` returns non-zero AND stderr contains "unrecognized arguments".

## Deviations / Notes

- **D-10 grep verification — one expected residual hit.** After migration, `git grep -nE '\["find", "[a-zA-Z0-9_.]' packages/graph-io/tests/` returns exactly one line: the D-11 anti-regression test itself, which deliberately invokes `["find", "foo.py"]` to assert the positional form errors. The plan's "zero hits" target was authored before that guard was added; the residual hit is correct-by-design. All eight real caller migrations are complete (verified by source-line inspection).
- **Approach choice for parser.error() (RESEARCH §1.1).** Implemented option (a): `sp.set_defaults(_parser=sp)` exposes the subparser as `args._parser`; `run()` calls `args._parser.error(...)`. One-line change in `main.py` plus the natural `if args.name is None and ...` guard in `q_find.py:run()`.
- **Full pytest workspace run.** `uv run --package graph-io pytest -q` from the workspace root recursively runs the entire monorepo suite (1060 tests). It reports `1 failed, 1060 passed, 33 skipped, 1 xfailed`. The single failure is `tests/test_integration_gate.py::test_integration_test_files_use_canonical_gate` — a pre-existing repo-level meta-test that flags `packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py` (a fixture file, not a real test). Verified pre-existing by re-running on `git stash`'d source: same failure. Not caused by Phase 36; falls outside this plan's `files_modified` scope.
- **Graph-io scope verification.** `uv run --package graph-io pytest packages/graph-io/tests/ -q` exits 0 with `324 passed, 1 skipped, 1 xfailed` — confirming the entire graph-io test suite (the actual surface this plan touches) is green.

## Self-Check

- [x] All four tasks executed and individually verified
- [x] D-10 hard-cut: 8 positional callers migrated atomically
- [x] D-11 guard added and passing
- [x] `cg find --help` shows exactly 3 named flags (live-verified)
- [x] `cg find foo.py` exits 2 with `unrecognized arguments` (live-verified)
- [x] `cg find` (no args) exits 2 with stderr naming all three flags (live-verified)
- [x] Full graph-io test suite green (324 passed)
- [x] Pre-existing repo-level integration_gate failure is unrelated to this plan
- [x] Single-commit hygiene: only files in `files_modified` frontmatter touched
