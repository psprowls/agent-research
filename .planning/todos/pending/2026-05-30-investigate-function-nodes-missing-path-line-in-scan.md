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
