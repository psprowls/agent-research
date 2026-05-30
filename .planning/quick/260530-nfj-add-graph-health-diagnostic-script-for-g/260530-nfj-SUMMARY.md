---
phase: quick-260530-nfj
plan: 01
subsystem: dev-tooling
tags: [scripts, graph-io, diagnostics, sqlite]
one_liner: "Read-only graph-io code.db auditor moved from /tmp into scripts/graph_health.py as a permanent stdlib-only dev tool"
requires: []
provides:
  - "scripts/graph_health.py — read-only graph-io code.db completeness/resolution auditor"
affects: [scripts/]
tech-stack:
  added: []
  patterns:
    - "Standalone stdlib-only dev script (sqlite3/sys/pathlib); not a cg console-script entry point"
    - "Read-only sqlite connection via file:...?mode=ro URI"
key-files:
  created:
    - scripts/graph_health.py
  modified: []
decisions:
  - "Kept body byte-for-byte identical to /tmp/graph_health.py; docstring header already matched the repo's `<name> — <purpose>` convention so no tweak was needed"
  - "Not wired as a cg console-script entry point and no pyproject.toml change — it is a standalone dev tool, not part of the graph-io public CLI"
metrics:
  duration: ~1 min
  completed: 2026-05-30
---

# Quick Task 260530-nfj: Add graph-health diagnostic script Summary

Moved the read-only graph-io diagnostic auditor from `/tmp/graph_health.py` into the
repo at `scripts/graph_health.py`, making it a permanent, reusable dev tool alongside
the existing `scripts/drift-diff.sh` and `scripts/check-brand.sh`. The script audits a
graph-io SQLite `code.db` for node/edge completeness by kind, unresolved-edge counts,
function placeholder targets, and unresolved import-specifier shapes.

## What Was Built

- `scripts/graph_health.py` — executable (mode 100755), pure-stdlib Python 3
  (`sqlite3`, `sys`, `pathlib`). Opens the DB read-only via
  `sqlite3.connect("file:{DB}?mode=ro", uri=True)`, takes the db path as `argv[1]`
  (defaults to `.graph/code.db`), and prints `METADATA`, `NODES`, `EDGES`, plus
  function/file placeholder breakdown sections.

## Verification

- `test -x scripts/graph_health.py` → executable bit present (committed as mode 100755).
- `head -1` matches `#!/usr/bin/env python3`.
- `grep -F 'mode=ro'` → read-only connection present.
- `diff /tmp/graph_health.py scripts/graph_health.py` → byte-identical (no docstring
  tweak required; first docstring line already matched the repo convention).
- Ran `python3 scripts/graph_health.py /Users/pat/Personal/graph-wiki/mono-repo-live/.graph/code.db`
  → exit 0; `METADATA` / `NODES` / `EDGES` banner sections all printed
  (e.g. `deriver_version 3`, file/function/method/class/dependency/package node counts).

## Deviations from Plan

None - plan executed exactly as written. The optional one-line docstring header tweak
was not needed because `/tmp/graph_health.py`'s first docstring line already read in the
repo's `<name> — <purpose>` style.

## Commits

- `269e1c0`: feat(quick-260530-nfj): add scripts/graph_health.py graph-io DB auditor

## Self-Check: PASSED

- FOUND: scripts/graph_health.py
- FOUND: commit 269e1c0
