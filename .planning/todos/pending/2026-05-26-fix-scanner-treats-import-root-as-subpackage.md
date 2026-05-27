---
created: 2026-05-26
title: Fix scanner treating package import root as a sub-package
area: graph-io
files:
  - packages/graph-io/src/graph_io/structural_nodes.py:326  # _walk_subpackages
  - packages/graph-io/src/graph_io/structural_nodes.py:496  # _walk_subpackages call site
  - packages/graph-io/src/graph_io/structural_nodes.py:513  # kind="subpackage" emission
  - packages/graph-io/src/graph_io/packages.py:96           # sub-package contains-edge doc
---

## Problem

The graph scanner is generating an extraneous sub-package node for a package's own import root.

**Concrete example:**

Package `workspace-io` (Python project, normal `src/` layout) has:

```
packages/workspace-io/
  pyproject.toml          # declares package "workspace-io"
  src/workspace_io/       # import root for the package
    __init__.py
    foo.py
    bar/                  # legitimate sub-package
      __init__.py
      baz.py
```

Current scanner behavior: creates a `subpackage` node for `workspace_io` (the import root directory).

Expected behavior: the contents of `src/workspace_io/` ARE the `workspace-io` package's contents — files inside should attach directly to the `workspace-io` package node. Only `bar/` (and anything deeper that contains `__init__.py`) should become a `subpackage`.

The rule: **anything below the import root containing `__init__.py` is a sub-package; the import root itself is not.**

## Solution

TBD — likely a small fix in `_walk_subpackages` (or its caller) at `packages/graph-io/src/graph_io/structural_nodes.py:326` to skip the import-root directory and start sub-package detection one level down.

Things to verify before fixing:
- Behavior for the flat layout (`<pkg>/<importable>/` with no `src/`) — same rule applies, the importable dir is the package's content root not a sub-package.
- Existing `contains` edges in `packages.py:96` doc say files inside a sub-package get edges from BOTH the sub-package and the root package. Make sure removing the spurious import-root subpackage doesn't lose any legitimate edges.
- Snapshot tests / canonical graph fixtures will need re-baselining once the fix lands.
