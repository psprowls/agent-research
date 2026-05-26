---
status: complete
phase: 36-cg-find-parser-ergonomics
source:
  - .planning/phases/36-cg-find-parser-ergonomics/36-01-SUMMARY.md
started: "2026-05-26T20:30:00Z"
updated: "2026-05-26T20:45:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. `cg find --help` shows 3 named flags
expected: Run `cg find --help`. Output lists exactly three options (`--name`, `--kind`, `--in-package`); no positional `name` argument; each flag has a one-line description.
result: pass
note: User's first attempt with global `cg` showed old positional form — stale install. Verified workspace-installed binary (`uv run --package graph-io cg find --help`) shows the correct Phase 36 surface with --name/--kind (choices enum)/--in-package. Phase 36 source is correct; global `cg` needs reinstall (deployment hygiene, not a code defect).

### 2. Named-flag query works
expected: Run `cg find --name SubagentPool --kind class`. Exit code 0 (found) OR 1 (not-found). Never exit 2 (parse error). If found, output shows matching node(s) in human format by default.
result: pass
note: Returned `class SubagentPool packages/subagent-runtime/src/subagent_runtime/pool.py 89 {'language': 'python'}` — exit 0, human format default.

### 3. `--in-package` filter (case-insensitive exact match)
expected: Run `cg find --in-package graph-io` (lowercase). Then `cg find --in-package GRAPH-IO` (uppercase). Both return the same result set. Capped at 50 rows with `... showing 50 of N (truncated)` trailer if the package has more than 50 nodes.
result: pass
note: Lowercase `--in-package graph-io` returned 674-node match capped at 50 with `... showing 50 of 674 (truncated)` trailer on stderr. Human format shows kind/name/path/line/attrs columns cleanly. Case-insensitivity covered by `test_find_in_package_case_insensitive` unit test (verified green in 36-01-SUMMARY.md) — not separately re-tested in UAT.

### 4. Old positional form errors clearly
expected: Run `cg find foo.py` (no `--name`). Exits with code 2. Stderr contains `unrecognized arguments: foo.py` (argparse default error message — D-04 chose default over custom for v1.7).
result: pass
note: `cg: error: unrecognized arguments: foo.py` printed; argparse default; exit 2 implied. Bonus: usage line confirms `describe-entry-point` is now in cg's _SUBCOMMANDS (Phase 38 parity work landed).

### 5. Zero-filter invocation errors with all 3 flags named
expected: Run `cg find` (no args). Exits with code 2. Stderr message names all three flags (`--name`, `--kind`, `--in-package`) so the user knows what filters are available.
result: pass
note: `cg find: error: cg find requires at least one of --name, --kind, --in-package` — names all three flags exactly per D-01.

### 6. Invalid `--kind` value errors cleanly
expected: Run `cg find --kind bogus_not_a_real_kind`. Exits with code 2. Stderr shows argparse's `invalid choice` message listing the valid kinds (D-03 lives at argparse layer via `choices=_VALID_KINDS`).
result: pass
note: `cg find: error: argument --kind: invalid choice: 'bogus_not_a_real_kind' (choose from 'class', 'domain', 'entry_point', 'file', 'function', 'method', 'package', 'repository', 'subpackage', 'test_suite')` — argparse default with full enum list.

### 7. Unknown package returns zero rows
expected: Run `cg find --in-package nonexistent-package-name`. Exits with code 1 (zero matches). Output is empty (or shows only column headers / a "no results" indication, depending on `--fmt` choice). No stack trace, no parse error.
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
