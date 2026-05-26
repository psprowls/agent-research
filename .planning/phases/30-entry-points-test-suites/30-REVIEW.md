---
phase: 30-entry-points-test-suites
review_type: code-review
depth: standard
status: clean
files_reviewed: 4
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
reviewed_by: gsd-execute-phase (inline, Agent tool unavailable)
reviewed: 2026-05-26
---

# Phase 30 Code Review

## Scope

Production source files changed during Phase 30 (excluding tests and planning artifacts):

- `packages/graph-io/src/graph_io/entry_points.py` (NEW, ~430 lines)
- `packages/graph-io/src/graph_io/test_suites.py` (NEW, ~530 lines)
- `packages/graph-io/src/graph_io/update.py` (MODIFIED — new exception + helper + wiring)
- `packages/graph-io/src/graph_io/structural_nodes.py` (MODIFIED — Plan 30-01 amendment + Plan 30-03 hotfix)

Test files reviewed for assertion quality but not flagged as production code.

## Reviewer Note

The `Agent(subagent_type=\"gsd-code-reviewer\", ...)` tool was unavailable in this runtime
(deferred-tool list did not include `Agent`). Per the execute-phase workflow's
runtime-compatibility note, the orchestrator performed an inline structural review during
implementation, supplemented by:

- TDD discipline: every behavior change was preceded by a failing test commit.
- Full graph-io test suite passing (215 passed + 1 skipped).
- Full workspace test suite passing (730 passed + 27 skipped).
- Phase 29 regression check folded into the run.

This is a "best-effort inline" review, not a full third-party audit. Re-running
`/gsd:code-review 30` once the Agent tool is available will produce a deeper report.

## Findings

**None.** No bugs, security issues, or quality problems identified.

## Notes (non-findings, informational only)

These are observations from the inline review — not findings, but useful for future readers:

1. **`entry_points.py` upsert path-slot encoding.** Conditional exports that share an
   export key (`"."` with `import` vs `require`) are kept distinct in the SQLite
   `(kind, name, path)` upsert key by encoding the condition as `path='condition:<cond>'`.
   The encoding is documented inline at the call site and exercised by
   `test_packagejson_exports_recursive_walk`. If a future query needs the export key
   alone, read `name`; for the condition, read either the `condition` attr (preferred)
   or split the `path` slot on `':'`.

2. **`test_suites.py` JS relative-spec resolution.** The resolver tries a fixed list of
   extensions (`.ts/.js/.tsx/.jsx/.mjs/.cjs`) plus `index.<ext>` variants. This is
   intentionally conservative — a future plan that needs framework-agnostic resolution
   (e.g. matching a TS path-alias) should add a higher-level resolver rather than
   extending this list ad-hoc.

3. **`update.py` `_enforce_strict_tree_invariant` placement.** Runs after `resolve.sweep`
   and before `_set_metadata`. A raise propagates, `store.transaction` rolls back the
   write, and the on-disk DB stays at the previous indexed commit. This is the strictest
   possible failure mode and matches D-20.

4. **`structural_nodes.py` orphan-test-file branch.** Plan 30-03 hotfixed Phase 29's
   D-14 contract (Repository -> File for test files outside Packages). The branch is
   guarded by `_is_test_path` with the post-Plan-30-01 D-01 src-override applied —
   non-test files outside any Package remain skipped exactly as Phase 29 intended.

5. **No new external dependencies.** All Phase 30 code uses stdlib only (tomllib, json,
   re, fnmatch, sqlite3, sys, dataclasses, pathlib) plus the existing graph_io /
   source_parser imports. Verified via `grep -E '^(import|from)' ... | grep -v <whitelist>`
   yielding 0 lines in the plan-level verification of 30-02 and 30-03.

## Self-Check: PASSED

- All Phase 30 production files compile and import cleanly.
- All 215 graph-io tests pass.
- All 730 workspace tests pass (27 skipped — unrelated integration/eval gates).
- No silent excepts, no TODOs / FIXMEs, no bare-except patterns.
- Conventional commit messages on every commit; per-task atomic commits.
- Self-checks per plan SUMMARY all PASSED.
