---
phase: 34-brand-sweep
plan: 04
subsystem: graph-io
tags: [brand-sweep, env-var-rename, breaking-change-single-user]

requires:
  - plan: 34-01
    provides: .brand-grep-allow (gate runnable mid-sweep)
provides:
  - GRAPH_WIKI_LOCK_TIMEOUT_MS is the only env var controlling lock timeout
  - Old LATTICE_GRAPH_LOCK_TIMEOUT_MS is silently ignored
affects: [34-05]

tech-stack:
  added: []
  patterns: [straight-rename-no-deprecation-window]

key-files:
  created: []
  modified:
    - packages/graph-io/src/graph_io/update.py
    - packages/graph-io/tests/test_cli_exit_codes.py

key-decisions:
  - "D-09 revised applied: 6-line straight rename in _default_lock_timeout(); no alias, no precedence, no warning."
  - "D-13 applied: test_cli_exit_codes.py line 149 updated to set GRAPH_WIKI_LOCK_TIMEOUT_MS=200."

patterns-established:
  - "Straight-rename pattern for single-user repos: no deprecation alias, no stderr warning, no fallback logic — the old name is just gone."

requirements-completed:
  - BRAND-03

duration: ~5min
---

# Plan 34-04 Summary

Two atomic line-level edits:
- `update.py:154`: `os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")` → `os.environ.get("GRAPH_WIKI_LOCK_TIMEOUT_MS")`
- `test_cli_exit_codes.py:149`: env dict literal renamed to match.

No alias, no precedence logic, no deprecation warning — single-user repo per D-07/D-08/D-09/D-10 revised.

Verified: setting `GRAPH_WIKI_LOCK_TIMEOUT_MS=5000` honors the new value; setting only the old
`LATTICE_GRAPH_LOCK_TIMEOUT_MS=5000` returns the default 30000 (old var is silently ignored).
All 11 test_cli_exit_codes.py tests pass.
