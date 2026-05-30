---
created: 2026-05-30T18:18:11.237Z
title: Investigate function nodes missing path/line in scan
area: graph
files:
  - packages/graph-io/src/graph_io/upsert.py:62-80
  - packages/graph-io/src/graph_io/resolve.py:30
---

## Problem

Scanning the `mono-repo` repository produces many graph nodes — especially
**functions** — with no `path` or `line` info. Want to understand *why* before
deciding whether it's a bug or expected.

Working hypothesis (Pat): many of these are functions from **dependencies**, not
first-party code. Pat is separately working (another session) on properly
injecting JS dependencies, and this may self-correct once that lands.

## Investigation findings so far

The mechanism is already visible in `packages/graph-io/src/graph_io/upsert.py`:

- `_ensure_node` (lines 62-66) inserts a node with `line=None` and **no path/uri**
  (`_insert_node(conn, key, None, None, None)`) when a node is needed as an **edge
  endpoint** but was never upserted with full source info.
- `_upsert_edge` (lines 69-80) sets `attrs["resolution"] = "unresolved"` whenever
  the edge's destination key has a `None` path (`edge.dst[2] is None`, line 73).

So a function that is **referenced** (e.g. a call edge) but **not defined** in the
scanned source gets materialized as a bare node with no path/line. That is exactly
what dependency functions look like — referenced from first-party code, defined
outside the scanned tree. This corroborates Pat's hypothesis.

Related: `resolve.py:30` stamps `resolution='unresolved'`; queries already filter
unresolved edges (`queries.py:37`, `queries.py:1076`).

## Solution (mostly investigation)

Confirm and decide — not necessarily a code change:

1. **Verify the hypothesis empirically.** Query the `mono-repo` `code.db`: are the
   path/line-less function nodes the destinations of `resolution='unresolved'`
   edges? Cross-check a sample against the actual dependency surface.
2. **Decide expected vs. bug.** If they're genuinely external deps, missing
   path/line is *correct* (no source location exists in-tree). The open question is
   whether they should even surface as bare nodes, or be folded into
   `builtin:`/dependency nodes (see `builtins.py`, `uri.py:59`).
3. **Re-check after JS-dependency injection lands.** Once the other session's JS
   dependency injection is done, re-scan `mono-repo` and see how many of these
   resolve to real path/line. Capture the before/after counts. If a meaningful
   chunk *doesn't* resolve, dig into why (parser coverage? import resolution gaps?).

Defer active work until the JS-dependency-injection effort is merged — this may be
a no-op afterward. Keep as an understand-then-decide task.

## Update 2026-05-30 — related finding: missing URIs are build artifacts

While investigating a sibling question ("why do files/classes/functions/methods
lack URIs?") we ran `SELECT kind, count(*) n, count(uri) with_uri FROM nodes
GROUP BY kind` against the `mono-repo` `code.db`. Two distinct outcomes:

- **class (319), function (3336), method (949) → `with_uri = 0`: by design.**
  `uri.py` defines URI constructors only for entity/structural kinds (repo, pkg,
  app, subpkg, file, entry_point, test_suite, domain, plugin, dependency, builtin).
  There is no class/function/method URI scheme; code symbols are identified by
  `(name, path, line)`. Not a bug.
- **file: 1629 total, 1463 with URI → 166 files have NULL `uri`.** All 166 have a
  non-null `path` (`no_path = 0`), and every path is a **compiled build artifact**:
  `dist/**` bundles, `*.d.ts` declarations, `apps/*/.vite/build/main.js`. Examples:
  `domains/device/device-data-node-ts/dist/index.js`,
  `domains/financial/financial-domain-ts/dist/index.d.ts`.

### Why this happens (hypothesis)

`structural_nodes.emit` only stamps a `file:` URI on **tracked, package-owned**
source files it walks (`structural_nodes.py:560-640`); it never reaches these
`dist/` artifacts. They still appear as file nodes because cross-package imports
resolve to the built entry point (JS/TS `package.json main`/`exports` point at
`dist/index.js`), so the import resolver creates a path-bearing file node for the
compiled output rather than the `src/` source. → path set, no URI, never enriched.

This is the **same JS-dependency root cause** as the path/line-less functions above,
seen from the file angle — and it likely inflates the function/class counts too
(each `dist/` bundle re-declares the `src/` symbols).

### Add to the scope above

4. **Confirm the 166 are import/edge targets** (not strays):
   `SELECT count(*) FROM nodes n WHERE n.kind='file' AND n.uri IS NULL
   AND EXISTS (SELECT 1 FROM edges e WHERE e.dst = n.id);` — expect ~166.
5. **Fix the dist/build leak** — NOTE: `dist`/`build` are *already* in
   `DEFAULT_SKIP_DIRS`; the walk honors them. The leak is `_ensure_node`
   materializing import-edge targets (built `dist/` entry points) without checking
   `skip_dirs`. Tracked as its own actionable todo:
   `2026-05-30-stop-materializing-dist-build-import-targets-as-graph-nodes.md`.
6. **Re-check after JS-dependency injection lands** — verify workspace imports
   resolve to `src/` (or to clean `dependency:` nodes) instead of `dist/` entry
   points, which should drop most of the 166 `dist/` file nodes and the duplicate
   symbol inflation.

## RESOLVED 2026-05-30 — full rebuild against post-sweep deriver (v2)

Ran step 5 properly: backed up `mono-repo-live/.graph/code.db`, then full-rebuilt
against the real source repo `/Users/pat/Personal/mono-repo` via
`update.run(repo, workspace=mono-repo-live, full=True)` — bypassing the broken
workspace→repo resolver (the manifest has no `repo-directory:` pin, so `cg update`
mis-resolves repo_root to the wiki workspace and dies with "ambiguous argument
HEAD"). Deriver bump `None→2` forced the full rebuild as designed.

**Before (stale incremental db) → After (clean rebuild):**

| metric | before | after |
|--------|-------:|------:|
| `file` nodes | 4633 | **1463** |
| file nodes, NULL `uri` | 3170 | **0** |
| dist/build file nodes | 166 | **0** |
| node_modules file nodes | — | **0** |
| **functions w/o path/line** | **2455** | **2455 (unchanged)** |
| path-less funcs that are edge `dst` | 2455/2455 | 2455/2455 |

### Decision — EXPECTED, no code change

1. **Path-less functions (2455): expected, not a bug.** They survive a clean full
   rebuild unchanged, and every one is a call-edge *destination* — referenced but
   never defined in the scanned first-party source (out-of-tree/dependency symbols).
   No in-tree source location exists, so missing `path`/`line` is correct. Queries
   already filter unresolved edges (`queries.py:37`, `:1076`), so they never surface
   in results. The original hypothesis (Pat) is confirmed.

2. **The 3170 NULL-uri *file* nodes were incremental-update cruft, not a defect.**
   The stale db had accumulated junk file nodes under the old deriver (3004 raw
   unresolved import specifiers like `../../../src/config/api` + 166 dist/build).
   The dist/build sweep (todo #2, `resolve.sweep_skip_dir_files`) + the forced full
   rebuild cleared **all** of them → 0. End-to-end validation that the sweep fix and
   the deriver-version-bump→auto-rebuild mechanism both work.

3. **JS-dependency injection (separate session) is now an enhancement, not a fix.**
   It would convert some of the 2455 out-of-tree function targets into proper
   `dependency:` nodes, but they are benign as-is. No action gated on it here.

Closing as understand-then-decide complete. Workspace db left in the improved
clean-rebuilt state; backup at `/tmp/graph_db_backup/code.db.bak` if needed.
