---
phase: 34-brand-sweep
plan: 01
subsystem: tooling
tags: [brand-sweep, allowlist, brand-grep-gate]

requires: []
provides:
  - .brand-grep-allow at repo root with 9 path-substring entries
  - Runnable BRAND-04 gate (no longer fails with "allowlist missing")
affects: [34-05]

tech-stack:
  added: []
  patterns: [allowlist-as-substring-match]

key-files:
  created:
    - .brand-grep-allow
  modified: []

key-decisions:
  - "D-19 ships the minimal broader-codebase allowlist: workspace-io/, source-parser/, eval-harness/, wiki-io/, model-adapter/, graph-wiki-agent/, plugins/graph-wiki/, .planning/, CLAUDE.md."
  - "Zero entries for packages/graph-io/ — at plan-write time (later extended in 34-05; see SUMMARY there)."

patterns-established:
  - "Allowlist format: path-substring entries, '#' comments, blank lines ignored; matched by `grep -vF -f` against `grep -rEl` output."

requirements-completed:
  - BRAND-04 (gate runnable; full pass deferred to 34-05)

duration: ~5min
---

# Plan 34-01 Summary

Created `.brand-grep-allow` at repo root with 9 broader-codebase carve-outs (workspace_io
package, ported-from comments, fixture vaults, cross-package imports, planning docs, CLAUDE.md).
Did not modify `scripts/check-brand.sh` per D-17.

Wave 1 of Phase 34 — gate becomes runnable so Wave 2 plans can check post-edit cleanliness.
