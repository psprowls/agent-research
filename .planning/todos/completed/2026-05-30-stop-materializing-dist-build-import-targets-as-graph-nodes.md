---
created: 2026-05-30T18:18:11.237Z
title: Stop materializing dist/build import targets as graph nodes
area: graph
files:
  - packages/graph-io/src/graph_io/upsert.py:40-66
  - packages/graph-io/src/graph_io/_ignore.py:18-33
  - packages/graph-io/src/graph_io/update.py:127-136,304
---

## Problem

Scanning the `mono-repo` graph contains 166 `file` nodes (of 1629) whose paths are
**compiled build artifacts** — `dist/**` bundles, `*.d.ts` declarations,
`apps/*/.vite/build/main.js`. They have a `path` but no `uri` (and feed duplicate
`function`/`class`/`method` nodes that inflate the symbol counts).

**Key correction:** this is NOT a missing-ignore-entry problem. `dist` and `build`
are *already* in `DEFAULT_SKIP_DIRS` (`_ignore.py:18-22`), and both walk stages
honor it — `_process_files` (`update.py:134`) and `structural_nodes.emit`
(`structural_nodes.py:565`). Adding `dist/` to `.cgignore` would be a no-op.

### Actual root cause

These nodes are **import-edge targets**, not walked files. The source parser emits
edges (e.g. `imports`) whose destination is a workspace package's *built* entry
point — because JS/TS `package.json` `main`/`exports` point at `dist/index.js`.
`_upsert_edge` → `_ensure_node` (`upsert.py:62-66`) then materializes that dst via
`_insert_node`, which writes the `path` straight from the edge key
(`upsert.py:40-43`) with `line=NULL, attrs=NULL, uri=NULL`. **`_ensure_node` /
`_upsert_edge` never consult `skip_dirs`**, so the `dist`/`build` skip that the
walk respects is bypassed entirely for edge endpoints.

(Verified mechanism: `count(uri)=0` for all 166; `path IS NULL` is false for all
166; every path is under `dist/`, `build/`, or `.vite/`.)

## Solution

Two non-exclusive directions:

1. **Defensive (graph-io, this todo's scope).** Stop edge-target materialization
   from creating file nodes under skip dirs. Options, simplest first:
   - **Post-pass cleanup sweep** (lowest risk): after enrichment, delete `file`
     nodes whose path has a component in `skip_dirs` AND that have `uri IS NULL`
     (never enriched → not real scanned source), rerouting/dropping their edges
     the way `resolve.sweep` already prunes placeholders (`resolve.py:50-57`).
   - **At insertion**: thread `skip_dirs` into `upsert_records` / `_upsert_edge`
     and refuse to `_ensure_node` a file-kind target whose path is skipped (mark
     the edge `resolution='unresolved'`/external instead). More invasive — touches
     the hot upsert path.

2. **Root cause (the JS-dependency-injection work, other session).** Resolve
   workspace-package imports to the package's `src/` entry, or to a clean
   `pkg:`/`dependency:` node, instead of the literal `dist/index.js`. That makes
   the parser stop emitting `dist/` edge targets in the first place — which also
   collapses the duplicate symbol inflation. The defensive sweep is still worth
   having as a backstop.

## Verification

- Confirm the population: `SELECT count(*) FROM nodes n WHERE n.kind='file'
  AND n.uri IS NULL AND EXISTS (SELECT 1 FROM edges e WHERE e.dst=n.id);` → ~166.
- After the fix, re-scan `mono-repo`: `dist/`/`build/`/`.vite/` file nodes gone
  (or reduced to genuinely-needed externals), `file` `with_uri` ≈ total, and
  `function`/`class` counts drop toward the `src/`-only figure.

## Related

Folded out of `2026-05-30-investigate-function-nodes-missing-path-line-in-scan.md`
(see its 2026-05-30 update) — same JS-dependency root cause, this is the
actionable graph-io fix.
