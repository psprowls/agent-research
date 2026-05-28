# Phase 49: Builtin Kind (graph-io) — Patterns

**Phase:** 49 - Builtin Kind (graph-io)
**Source files analyzed:** CONTEXT.md, RESEARCH.md, in-repo source

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog |
|---------------------|------|-----------|----------------|
| `packages/graph-io/src/graph_io/builtins.py` | service (scanner + classifier + emitter) | batch transform | `packages/graph-io/src/graph_io/packages.py` |
| `packages/graph-io/src/graph_io/uri.py` (edit) | utility (URI builder) | transform | `dependency_uri()` in same file |
| `packages/graph-io/src/graph_io/queries.py` (edit) | service (read-only queries) | request-response | `describe_dependency` / `list_dependencies` in same file |
| `packages/graph-io/src/graph_io/update.py` (edit) | controller (orchestrator) | batch | existing `packages.refresh` call site (line 275) |
| `packages/graph-io/src/graph_io/cli/q_list_builtins.py` | controller (CLI handler) | request-response | `packages/graph-io/src/graph_io/cli/q_list_packages.py` |
| `packages/graph-io/src/graph_io/cli/q_describe_builtin.py` | controller (CLI handler) | request-response | `packages/graph-io/src/graph_io/cli/q_describe_dependency.py` |
| `packages/graph-io/src/graph_io/cli/main.py` (edit) | router | dispatch | existing `_SUBCOMMANDS` dict |
| `packages/wiki-io/src/wiki_io/entity_writer.py` (edit) | service (frozenset + annotation) | n/a | existing `ADMITTED_KINDS` docstring |
| `packages/graph-io/tests/test_builtins.py` | test | unit | `packages/graph-io/tests/test_packages.py` |
| `packages/graph-io/tests/integration/test_e2e_builtins.py` | test | integration | `packages/graph-io/tests/integration/` siblings (use `_git_repo.py` helper) |
| `packages/graph-io/tests/test_queries.py` (edit) | test | unit | `test_describe_dependency_*` / `test_list_dependencies_alphabetical` in same file |
| `packages/graph-io/tests/test_cli_describe.py` (edit) | test | CLI integration | `test_cg_describe_dependency_*` in same file |
| `packages/graph-io/tests/test_cli_smoke.py` (edit) | test | CLI smoke | sibling smoke tests in same file |

---

## Pattern Assignments

### `graph_io/builtins.py` (NEW)

**Mirror:** `graph_io/packages.py:132-225` (dedup-and-emit) and `graph_io/import_scan.py:113-150` (file iteration).

**Imports to copy:**
```python
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import sqlite3

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import _ignore, upsert
from graph_io.import_scan import _PYTHON_IMPORT_RE, _JS_IMPORT_RE  # extend or wrap
from graph_io.uri import RepoContext, builtin_uri
```

**Core pattern (accumulator + dedup) — mirror `packages.py:188-220`:**
```python
# packages.py:188-220 — copy this dedup shape for Builtin
dep_edges: list[GraphEdge] = []
seen_edges: set[tuple[str, str]] = set()
for consumer_name, consumer_rel_path, dep_name in used_by_pairs:
    if (consumer_name, dep_name) in seen_edges:
        continue
    seen_edges.add((consumer_name, dep_name))
    dep_edges.append(
        GraphEdge(
            src=("package", consumer_name, consumer_rel_path),
            dst=("dependency", dep_name, None),
            kind="used_by",
            attrs={},
        )
    )
```

For Builtin, swap `(consumer_name, dep_name)` for `(consumer_name, lang, module_name)` AND merge `imported_symbols` sets (don't drop duplicates — merge symbol sets per edge).

**File iteration pattern — mirror `import_scan.py:130-148`:**
```python
# import_scan.py:130-148 — file-content read + regex match loop
for rel in file_rel_paths:
    fpath = repo_root / rel
    try:
        content = fpath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    ext = Path(rel).suffix
    if ext == ".py":
        for m in _PYTHON_IMPORT_RE.finditer(content):
            ...
    elif ext in _SCAN_EXTENSIONS_JS:
        for m in _JS_IMPORT_RE.finditer(content):
            ...
```

**Public entry point:** `refresh(conn, *, repo_root, workspace, ctx)` — matches `packages.refresh(conn, *, repo_root, ctx)` signature shape. Add `workspace` for cache-dir resolution via `workspace_io.paths.graph_dir`.

---

### `graph_io/uri.py` (EDIT)

**Add after line 53 (`dependency_uri`):**
```python
def builtin_uri(language: str, module_name: str) -> str:
    return f"builtin:{language}/{module_name}"
```

One-line pure function. Same pattern as every other `*_uri` builder. No tests in `test_uri.py` exist today (URI tests are folded into `test_queries.py`/`test_packages.py`); add a small test wherever feels cohesive.

---

### `graph_io/queries.py` (EDIT)

**Edit 1 — `_VALID_KINDS` (line 9-25):** add `"builtin"` to the frozenset.

```python
# queries.py:9-25 — current frozenset (extend with "builtin")
_VALID_KINDS = frozenset(
    {
        "function", "class", "method",
        "file", "package", "repository", "subpackage",
        "entry_point", "test_suite", "domain",
        "dependency", "plugin",
        "builtin",          # ← Phase 49: stdlib module imports
    }
)
```

**Edit 2 — add `BuiltinDescription` dataclass** near other `*Description` dataclasses (search file for `class DependencyDescription`).

**Edit 3 — add `describe_builtin(conn, *, language, module_name)`** — mirror `describe_dependency` at `queries.py:558-595`:
```python
# queries.py:558-595 — describe_dependency pattern to mirror
def describe_dependency(
    conn: sqlite3.Connection, *, ecosystem: str, name: str
) -> DependencyDescription | None:
    row = conn.execute(
        "SELECT id, name, attrs_json, uri FROM nodes "
        "WHERE kind='dependency' AND name = ? "
        "AND json_extract(attrs_json, '$.ecosystem') = ?",
        (name, ecosystem),
    ).fetchone()
    if not row: return None
    dep_id, dep_name, attrs_json, uri = row
    used_by_rows = conn.execute(
        "SELECT p.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "WHERE e.kind='used_by' AND e.dst = ? AND p.kind='package' "
        "ORDER BY p.name",
        (dep_id,),
    ).fetchall()
    used_by = [r[0] for r in used_by_rows]
    ...
```

Swap `'dependency'` → `'builtin'` and `'$.ecosystem'` → `'$.language'`. Return `BuiltinDescription`.

**Edit 4 — add `list_builtins(conn)`** — one-line mirror of `list_dependencies` at line 655:
```python
def list_builtins(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all Builtin nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "builtin")
```

---

### `graph_io/update.py` (EDIT)

**Single-line addition near line 275** — insert `builtins.refresh(...)` immediately after `packages.refresh(...)`. The transaction is already open via `store.transaction(conn)` (line 273); reuse it.

```python
# update.py:275 — current call (insert builtins.refresh AFTER this)
packages.refresh(conn, repo_root=repo_root, ctx=ctx)
builtins.refresh(conn, repo_root=repo_root, workspace=workspace, ctx=ctx)  # ← NEW
```

Add `from graph_io import builtins` to the module imports near `from graph_io import _ignore, packages, resolve, schema, store, upsert`.

---

### `graph_io/cli/q_list_builtins.py` (NEW)

**Mirror verbatim:** `packages/graph-io/src/graph_io/cli/q_list_packages.py` (44 lines total). Substitute:

| `q_list_packages.py` | `q_list_builtins.py` |
|----------------------|----------------------|
| `queries.list_packages(conn)` | `queries.list_builtins(conn)` |
| `"No packages in graph."` | `"No builtins in graph."` |

Everything else (argparse skeleton, read-only connect, exception handling, JSON-vs-human dispatch, exit codes) is identical.

---

### `graph_io/cli/q_describe_builtin.py` (NEW)

**Mirror:** `packages/graph-io/src/graph_io/cli/q_describe_dependency.py` (53 lines total).

**Key difference — argument shape:** success criterion #3 takes a URI (`cg describe-builtin builtin:python/pathlib`). Parse with `str.split(":", 1)` then `str.split("/", 1)`:

```python
# Adapt q_describe_dependency.py:14-19 (add_arguments)
def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("uri", help="builtin URI, e.g. builtin:python/pathlib")

# Adapt q_describe_dependency.py:run() — parse URI before calling describe_builtin
def run(args: argparse.Namespace) -> int:
    if not args.uri.startswith("builtin:"):
        print(f"error: not a builtin URI: {args.uri}", file=sys.stderr)
        return exit_codes.GENERIC
    rest = args.uri.removeprefix("builtin:")
    if "/" not in rest:
        print(f"error: malformed builtin URI: {args.uri}", file=sys.stderr)
        return exit_codes.GENERIC
    language, module_name = rest.split("/", 1)
    # ... read_only_connect + queries.describe_builtin(conn, language=..., module_name=...) ...
```

Print format mirrors `q_describe_dependency.py:54-60` (human form prints labeled lines; JSON prints `dataclasses.asdict(desc)`).

---

### `graph_io/cli/main.py` (EDIT)

**Two additions:**

1. Import row in the alphabetized block at top:
   ```python
   from graph_io.cli import (
       ...,
       q_describe_builtin,
       ...,
       q_list_builtins,
       ...,
   )
   ```

2. Two entries in `_SUBCOMMANDS` dict (line 39-72):
   ```python
   "list-builtins": q_list_builtins,
   "describe-builtin": q_describe_builtin,
   ```

Maintain the existing alphabetical-ish grouping (list-* together, describe-* together).

---

### `wiki_io/entity_writer.py` (EDIT)

**Modify the `ADMITTED_KINDS` docstring/comment** at line 52-66 to explicitly note Builtin's exclusion:

```python
# entity_writer.py:52-56 — current comment (extend)
# v1.8 admitted entity kinds — the 7 graph-derived kinds the wiki materializes
# as standalone pages under `wiki/entities/`. Underscore-form per D-02 matches
# `graph_io.queries._VALID_KINDS` casing.
#
# Phase 49 D-16: `builtin` is intentionally NOT admitted. Stdlib modules
# are inspectable via `cg list-builtins` / `cg describe-builtin` but do
# not get standalone wiki pages — wiki rendering of every stdlib import
# would dilute the entity surface for negligible information value.
ADMITTED_KINDS: frozenset[str] = frozenset(
    {
        "repository", "domain", "package", "package_family",
        "plugin", "dependency", "test_suite",
    }
)
```

The frozenset content does NOT change — only the comment grows. The existing bijection invariant test (`test_entity_templates.py:61-68`) already enforces that the templates and ADMITTED_KINDS stay in sync.

---

### `graph_io/tests/test_builtins.py` (NEW)

**Mirror structure:** `packages/graph-io/tests/test_packages.py` (manifest-fixture helper + per-feature test functions). The integration variant uses a `tmp_path` + minimal Python/JS package fixture (see existing `tests/integration/` style).

**Specific test functions to write** (one per Validation row, plus parametrized variants):
- `test_python_stdlib_emits_builtin_nodes` — fixture writes `from pathlib import Path` and `import os` → 2 Builtin nodes
- `test_node_stdlib_emits_builtin_nodes` — fixture writes `require('fs')` + `import 'node:fs/promises'` → 1 Builtin node (collapse)
- `test_node_spec_normalization` — direct unit test of the normalize-spec helper
- `test_node_dependency_vs_builtin_classification` — `require('express')` stays `dependency`; `require('fs')` becomes `builtin`
- `test_builtin_node_attrs_and_uri` — assert `language`, `module_name`, `uri` keys present
- `test_used_by_edge_dedup_and_symbol_union` — fixture has 2 files in the same package both `from os import getenv` + `from os import environ` → 1 edge with `imported_symbols == ['environ', 'getenv']`
- `test_emit_is_idempotent` — invoke `builtins.refresh()` twice; query node/edge counts unchanged
- `test_node_builtins_cache_lifecycle` — first call writes cache; second call reads cache without re-invoking subprocess (monkeypatch `subprocess.run` and assert call count); third call with different major triggers re-harvest
- `test_silent_skip_when_node_missing` — monkeypatch `subprocess.run` to raise `FileNotFoundError`; assert no exception bubbles, no JS Builtin nodes emitted, no stderr noise

---

### `graph_io/tests/integration/test_e2e_builtins.py` (NEW)

**Mirror:** `tests/integration/` sibling pattern (use `_git_repo.py` helper if present).

End-to-end fixture:
- Repo with one Python package (`pyproject.toml` + `src/demo/__init__.py` importing `pathlib`, `os`)
- AND one JS package (`package.json` + `src/index.js` requiring `fs`, `express`, `node:path`)
- Run `update.run(repo_root, full=True)`
- Assert: `cg list-builtins` returns `fs`, `os`, `path`, `pathlib`; `cg describe-builtin builtin:python/pathlib` shows `demo` in `used_by`; `cg describe-dependency boto3` and `cg describe-dependency express` still work (no regression)
- Second `update.run(repo_root)` (incremental, no diff) — Builtin node count unchanged

---

### `graph_io/tests/test_queries.py` (EDIT)

**Add three test functions near** `test_describe_dependency_*` and `test_list_dependencies_alphabetical` (around line 1074+):

- `test_valid_kinds_includes_builtin` — asserts `"builtin" in queries._VALID_KINDS`
- `test_list_builtins_alphabetical` — upsert 3 Builtin nodes out of order, assert alphabetic return
- `test_describe_builtin_returns_description` — upsert Builtin + Package + used_by edge, assert `BuiltinDescription` shape
- `test_describe_builtin_returns_none_when_missing` — single assertion

Use the fixture pattern from `test_describe_dependency_returns_dependency_description` verbatim (build with `upsert.upsert_records`, query via read-only conn from `conftest`).

---

### `graph_io/tests/test_cli_describe.py` (EDIT)

**Add three test functions near** `test_cg_describe_dependency_*` (line 80+):

- `test_cg_describe_builtin_smoke` — fixture-workspace + assert `"language" in stdout` etc.
- `test_cg_describe_builtin_not_found` — bad URI → `exit_codes.GENERIC`, stderr contains `error:`
- `test_cg_describe_builtin_json` — `--fmt json` → parse stdout JSON, check shape

Reuse the `workspace_with_deps_and_plugin` fixture pattern, extend it (or add a sibling fixture) to seed Python imports of `pathlib`/`os` so Builtin nodes exist.

---

### `graph_io/tests/test_cli_smoke.py` (EDIT)

**Add:** `test_cg_list_builtins_smoke` and `test_cg_list_builtins_json` — mirror existing `list-*` smoke tests in the same file.

---

## Shared Patterns

### Convention: read-only queries

Every read path opens via `store.read_only_connect(db)` inside try/except handling `GraphNotInitializedError` → `exit_codes.NOT_INITIALIZED` and `SchemaMismatchError` → `exit_codes.SCHEMA_MISMATCH`. **Applies to:** `q_list_builtins.py`, `q_describe_builtin.py`. Mirror verbatim from `q_list_packages.py` / `q_describe_dependency.py`.

### Convention: errors → stderr, JSON → stdout

Every CLI handler:
- Errors: `print(f"error: ...", file=sys.stderr); return exit_codes.X`
- Human output: labelled lines to stdout
- JSON output: `print(_json.dumps(dataclasses.asdict(record), default=str))` to stdout

**Applies to:** both new CLI handlers.

### Convention: single transaction per `cg update`

All emit work happens inside the existing `with store.transaction(conn):` block in `update.run()` (line 273). `builtins.refresh` MUST NOT open its own transaction — it reuses the outer one.

**Applies to:** `builtins.py:refresh()` signature receives the already-open connection.

### Convention: subprocess invocations get a timeout

Existing `update.py` `_git()` does not currently set a `timeout=`, but Phase 49 introduces an interactive-environment subprocess (`node -e`) where slow start has been observed in CI environments. Apply `timeout=5` to every `subprocess.run` call in `builtins.py` and handle `subprocess.TimeoutExpired` → D-03 silent skip.

**Applies to:** `builtins.py` `_node_major()` and `_harvest_node_builtins()`.

### Convention: cache path lives under `<workspace>/.graph/`

Use `workspace_io.paths.graph_dir(workspace)` for cache placement. **Applies to:** `builtins.py` cache file location → `graph_dir(workspace) / "cache" / f"node-builtins-{major}.json"`. `cg update --full` semantics already clear `.graph/` content paths by design.

### Convention: alphabetic sort in `list_*` queries

Every `list_*` query in `queries.py` uses `ORDER BY name`. **Applies to:** `list_builtins` — already inherited from `_list_by_kind`.
</content>
</invoke>