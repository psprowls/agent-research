# Phase 49: Builtin Kind (graph-io) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-27
**Phase:** 49-Builtin Kind (graph-io)
**Areas discussed:** Stdlib list source & versioning, Submodule granularity, Symbol-level imports, Schema version & migration

---

## Stdlib list source & versioning

### Q1: How should graph-io know what counts as Python/Node stdlib?

| Option | Description | Selected |
|--------|-------------|----------|
| Runtime introspection (Python: sys.stdlib_module_names; Node: shell out) | Always-fresh; reflects scanner's runtime version. Cost: introduces a Node-binary dependency. | ✓ |
| Hardcoded JSON snapshots pinned in graph-io | Deterministic; no extra runtime dep. Drifts when scanner runs on newer Python/Node. | |
| Hybrid: Python via runtime, Node via hardcoded snapshot | Avoids shelling to Node binary but is asymmetric. | |

**User's choice:** Runtime introspection for both.

### Q2: What should the scanner do when `node` isn't on PATH?

| Option | Description | Selected |
|--------|-------------|----------|
| Skip JS builtin detection silently | Log a debug line; bare JS names won't get reclassified. | |
| Skip + warning if JS files were scanned | Stderr warning per `cg update` run. | |
| Cache result to disk on first successful Node invocation | First run requires Node; subsequent runs read the cache. | ✓ |

**User's choice:** Cache to disk on first successful invocation.

### Q3: Where does the cached node-builtins JSON live, and how is it keyed/invalidated?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-workspace under .graph/ (next to the SQLite DB), keyed by Node major version | Lives with the graph DB, nuked with `cg update --full`. | ✓ |
| Global under $XDG_CACHE_HOME/graph-io/, keyed by full Node version | Shared across workspaces; first scan populates for all. | |
| In-repo under packages/graph-io/src/graph_io/_stdlib/ | Committed snapshot; no Node binary in CI. | |

**User's choice:** Per-workspace `.graph/cache/node-builtins-<major>.json`.

### Q4: Scanner Python vs target-repo Python mismatch — how to handle?

| Option | Description | Selected |
|--------|-------------|----------|
| Scanner runtime is the source of truth — accept the drift | Simplest; matches "single-user repo" reality. | ✓ |
| Union with a hardcoded historical superset | Covers older repos cleanly; tiny maintenance burden. | |
| Read target repo's `requires-python` and switch | Most correct; biggest implementation cost. | |

**User's choice:** Scanner runtime is the source of truth.

---

## Submodule granularity

### Q1: For `from os.path import join`, what's the Builtin URI?

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level only — `builtin:python/os` | Single Builtin node per stdlib top-level module. Mirrors Dependency. | ✓ |
| Full dotted — `builtin:python/os/path` | Distinct Builtin per dotted segment. Inflates node count. | |
| Top-level node + edge-level submodule attr | One node, edges carry `imported_as` attr. | |

**User's choice:** Top-level only.

### Q2: Node import flavors — `require('fs')` vs `node:fs` vs `node:fs/promises`. How to map?

| Option | Description | Selected |
|--------|-------------|----------|
| Collapse all three to one node — `builtin:javascript/fs` | Strip prefix, drop subpath. Mirrors Python decision. | ✓ |
| Preserve `node:` prefix as a separate URI form | Treats prefixed imports as a distinct namespace. | |
| Subpath gets its own node — `builtin:javascript/fs/promises` | Diverges from Python; captures API-level distinction. | |

**User's choice:** Collapse all three to one node.

---

## Symbol-level imports vs module imports

### Q1: For `from os import getenv`, what does the graph record?

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level only — one `used_by` edge to `builtin:python/os`, no symbol nodes | Treats `from os import getenv` identically to `import os`. Cheapest; lossy. | |
| Module edge + edge-level `imported_symbols` attr | Single edge with `attrs_json = {"imported_symbols": [...]}`. Queryable; doesn't inflate nodes. | ✓ |
| Emit Function nodes under the Builtin | Most expressive; stdlib has thousands of functions — node table inflation. | |

**User's choice:** Module edge + edge-level `imported_symbols` attr.

### Q2: One package imports from `os` 30 times across files — how many edges?

| Option | Description | Selected |
|--------|-------------|----------|
| One edge per (package, builtin), `imported_symbols` is the union | Matches existing dependency-edge dedup pattern. | ✓ |
| One edge per (file, builtin) — file-level granularity | More precise; inflates edges substantially. | |
| One edge per (package, builtin), with `usage_count` attr only | Cheapest in storage; loses symbol detail. | |

**User's choice:** One edge per (package, builtin), `imported_symbols` is the union.

---

## Schema version & migration

### Q1: SCHEMA_VERSION currently 2. Does Phase 49 warrant a bump?

| Option | Description | Selected |
|--------|-------------|----------|
| Bump SCHEMA_VERSION to 3 — force full rebuild | Aligns with how PKGFAM-01 (Phase 51) plans to handle the parallel removal. | |
| Keep SCHEMA_VERSION at 2 — incremental update works | DDL unchanged; kinds are text. Old unresolved Symbols linger. | ✓ |
| Defer the bump to Phase 51 | Bundle the bump where the real breaking change lands. | |

**User's choice:** Keep SCHEMA_VERSION at 2 (incremental update).

### Q2: How should `cg update` handle pre-v1.9 lingering unresolved Symbol nodes?

| Option | Description | Selected |
|--------|-------------|----------|
| Delete stdlib-shaped unresolved Symbols during update | Targeted cleanup; needs care to avoid false positives. | |
| Leave them — surface via a one-time advisory | One-time stderr warning suggesting `cg update --full`. | |
| Do nothing — a full rebuild is cheap, just let users opt in | Cheapest implementation; ship note tells the user to run `cg update --full`. | ✓ |

**User's choice:** Do nothing; user opts into `cg update --full`.

---

## Claude's Discretion

- Exact `attrs_json` schema for the `imported_symbols` attr (key name, whether to add `usage_count`).
- Implementation point in scanner pipeline (likely alongside dependency emission in `packages.py`).
- Import-scanner regex extension vs AST parsing for capturing named imports.
- Whether `node -e` invocation goes through `subprocess.run` directly or behind a `_node_runtime.py` helper.

## Deferred Ideas

- One-shot migration command to clean up pre-v1.9 unresolved Symbols (deferred — full rebuild is acceptable).
- Per-Python-version stdlib correctness via `requires-python` parsing (deferred — accept drift).
- In-repo committed Node-builtins snapshot (deferred — per-workspace runtime caching chosen).
- Function nodes under Builtin parents (deferred — node-table inflation not justified).
