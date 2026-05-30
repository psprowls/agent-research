---
created: 2026-05-30T18:44:34.009Z
title: Force graph rebuild when derivation logic changes
area: graph
files:
  - packages/graph-io/src/graph_io/update.py:121
  - packages/graph-io/src/graph_io/update.py:270
  - packages/graph-io/src/graph_io/classification.py
---

## Problem

`cg update` is incremental and git-diff-gated, so changes to **derivation logic**
(e.g. `classify()`) silently fail to propagate to an existing graph.

- `_changed_files()` (`update.py:121`) returns all files only when `full or prev is None`;
  otherwise it diffs against the previously-recorded commit.
- `update.run()` short-circuits (`update.py:270`) when `not changed and prev == head and not full`.

So when the source manifests/files are unchanged but the deriver code changed, the existing
graph keeps its **stale** derived values (node kind, app_kind, attrs) until a full rebuild
(`full=True`, or delete `code.db`).

Discovered 2026-05-30: the electron-classification fix (quick task 260530-gqp) did **not**
take effect on a re-scan of an existing graph at the same commit — `app-electron-ts` stayed
`pkg:` until a forced full rebuild flipped it to `app:` / `app_kind=electron`. This is an easy
trap: ship a graph-io derivation fix, re-scan, see no change, conclude the fix is broken.

## Solution

TBD — options to weigh:
1. **Deriver version stamp on the graph** — record a deriver/schema-logic version in graph
   metadata; on update, if the stamp differs from the current code's version, force a full
   rebuild automatically. (Most robust; no human memory required.)
2. At minimum, **document** that classification/derivation-logic changes require
   `graph build --full` (or `code.db` deletion) to take effect, and surface a hint in the
   scan/graph-build output.

Relates to [[fix-graph-build-repo-resolution-to-match-scan]] (both surfaced during the same
260530-gqp verification).
