# Phase 49: Builtin Kind (graph-io) — Research

**Researched:** 2026-05-27
**Domain:** graph-io (Python — SQLite-backed code graph, AST/regex import scan, argparse CLI)
**Confidence:** HIGH

## Summary

Phase 49 adds a new node kind `builtin` to `graph-io` so Python (`sys.stdlib_module_names`) and Node.js (`require('module').builtinModules`) standard-library imports are represented as inspectable graph nodes instead of being silently dropped by the resolver. The implementation is almost entirely additive: one new entry in `_VALID_KINDS`, one new URI builder, one new sibling-of-`packages.py` emission pass, two new CLI handlers mirroring `cg describe-dependency`, and a documented exclusion in `wiki_io.entity_writer.ADMITTED_KINDS`.

`SCHEMA_VERSION` does NOT change (D-10). The SQL layer accepts arbitrary kind strings; admission is enforced Python-side in `graph_io.queries._VALID_KINDS`. There are no external package dependencies, no migration, no UI, no AI integration. Risk surface is limited to two areas: (1) the `node -e ... builtinModules` subprocess invocation and its cache file, and (2) the Python import-scan regex extension if D-08's `imported_symbols` is populated at scan time.

**Primary recommendation:** Implement Builtin emission in a new sibling module `packages/graph-io/src/graph_io/builtins.py`, called from `update.run()` immediately after `packages.refresh()` so it shares the manifest-loaded package list. Reuse `_PYTHON_IMPORT_RE` and `_JS_IMPORT_RE` from `import_scan.py` for module-spec capture; extend the regexes (or add a second-pass capture) to harvest `imported_symbols` per D-08. CLI handlers (`q_list_builtins.py`, `q_describe_builtin.py`) replicate the existing `q_list_packages.py` / `q_describe_dependency.py` shapes verbatim.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Stdlib list source & versioning**
- **D-01:** Runtime introspection for both languages. Python: `sys.stdlib_module_names` (3.10+; project floor 3.11). Node: shell out to `node -e 'console.log(JSON.stringify(require("module").builtinModules))'`.
- **D-02:** Cache the Node builtin list to `<workspace>/.graph/cache/node-builtins-<major>.json`. Keyed by Node major version. Invalidate when file missing or `node --version` reports different major.
- **D-03:** When `node` is not on PATH, the cache file is missing, and no JS files were scanned: skip silently. The JS resolver still distinguishes bare names from path imports; bare names just don't get reclassified.
- **D-04:** Scanner runtime is the source of truth for Python stdlib classification. Accept drift across Python versions. No `requires-python` parsing.

**Submodule granularity**
- **D-05:** Top-level only. `from os.path import join` → `builtin:python/os`. One Builtin node per top-level stdlib module.
- **D-06:** Node: collapse `require('fs')`, `import 'node:fs'`, and `import 'node:fs/promises'` to the same `builtin:javascript/fs` node. Strip the `node:` prefix, drop the subpath.

**Symbol-level imports**
- **D-07:** Module-level edges only — no per-symbol Function/Symbol nodes for stdlib calls.
- **D-08:** Edge carries an `imported_symbols` attr on `attrs_json` — the sorted union of all named imports seen across the package.
- **D-09:** One edge per (package, builtin) — file-level granularity is NOT preserved. Matches existing dependency-edge dedup at `packages.py:203-208`.

**Schema version & migration**
- **D-10:** Do NOT bump `SCHEMA_VERSION`. Stays at 2.
- **D-11:** Do not retroactively clean up pre-v1.9 unresolved Symbol nodes for stdlib calls. User opts into `cg update --full` to get clean state.

**CLI surfaces**
- **D-12:** `cg list-builtins` mirrors the `cg list-*` family (output shape, JSON-vs-text flag).
- **D-13:** `cg describe-builtin <uri>` mirrors `cg describe-dependency <uri>`.

**Locked by upstream**
- **D-14:** Add `"builtin"` to `_VALID_KINDS` in `packages/graph-io/src/graph_io/queries.py:9`.
- **D-15:** Builtin nodes carry `language` (`python` | `javascript`) and `module_name` attributes — both required, both inspectable via `cg describe-builtin`.
- **D-16:** Builtin is excluded from `wiki_io.entity_writer.ADMITTED_KINDS` (no wiki page rendering).

### Claude's Discretion
- Exact `attrs_json` schema for `imported_symbols` (key name, optional `usage_count`).
- Implementation point in the scanner pipeline (likely a new sibling module called near `packages.refresh`).
- Import-scanner regex extension vs. switch to AST parsing for Python.
- Whether `node -e` invocation goes through `subprocess.run` directly or behind a small `_node_runtime.py` helper.

### Deferred Ideas (OUT OF SCOPE)
- Pre-v1.9 unresolved Symbol cleanup (user runs `cg update --full`).
- Per-Python-version stdlib correctness (union with historical supersets rejected).
- In-repo committed Node-builtins snapshot (per-workspace runtime caching wins).
- Function nodes under Builtin parents (rejected for v1.9).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUILTIN-01 | Classify Python stdlib imports as `Builtin` nodes | `sys.stdlib_module_names` confirmed available (Python ≥3.10; project floor 3.11). Detection sits in new `builtins.py`, called after `packages.refresh()`. |
| BUILTIN-02 | Classify Node/browser stdlib imports as `Builtin` nodes | `require('module').builtinModules` is the canonical list (Node 9.3.0+; project assumes modern Node). Subprocess + JSON cache documented in D-02. |
| BUILTIN-03 | npm packages remain classified as `dependency`; bare names distinguish Node built-ins via Node's documented list | Classifier order is `is_node_builtin(name) → builtin` else fall through to existing dependency emission path. |
| BUILTIN-04 | Builtin nodes carry `language` + `module_name`; URI scheme `builtin:<language>/<module_name>` | `builtin_uri(language, module_name)` follows existing `dependency_uri` pattern in `uri.py`. |
| BUILTIN-05 | Edges use `used_by`; usage count derivable from edge multiplicity. No `requires`/`imports` edges. | One `used_by` edge per (package, builtin), matching `packages.py:203-208` dedup pattern. Multiplicity captured via `imported_symbols` list length, NOT additional edges (per D-09). |
| BUILTIN-06 | `cg list-builtins` and `cg describe-builtin <uri>` | Two new CLI handlers in `packages/graph-io/src/graph_io/cli/`, registered in `main._SUBCOMMANDS`. Reuse `queries.list_dependencies` / `describe_dependency` shape. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Stdlib list resolution | Scanner / Library | — | `sys.stdlib_module_names` is stdlib; Node subprocess is the only out-of-process call. |
| Builtin node + edge emission | Library (graph-io) | Database (SQLite) | Sits alongside `packages.refresh` in the update pipeline; writes via `upsert.upsert_records` under the existing `store.transaction()`. |
| URI composition | Library (graph-io.uri) | — | Pure function, mirrors `dependency_uri`. |
| Kind admission | Library (graph-io.queries) | — | `_VALID_KINDS` frozenset is the Python-side gatekeeper; SQL is text-flexible. |
| Read-only describe / list | Library (graph-io.queries) | — | Reuses `read_only_connect`; mirrors `describe_dependency` / `list_dependencies`. |
| CLI surface | Library (graph-io.cli) | — | `argparse` dispatch in `main.py`; per-handler module mirrors `q_describe_dependency.py`. |
| Wiki exclusion annotation | Library (wiki-io.entity_writer) | — | `ADMITTED_KINDS` frozenset; add docstring annotation explaining `builtin` is intentionally absent. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sys` (stdlib) | Python 3.11+ | `sys.stdlib_module_names` provides the Python stdlib frozenset | Built-in, zero install, exactly the list Python's import system uses. `[VERIFIED: docs.python.org/3/library/sys.html#sys.stdlib_module_names]` |
| `subprocess` (stdlib) | Python 3.11+ | Run `node -e` once per scan to harvest `require('module').builtinModules` | Already used elsewhere in graph-io (e.g., `update.py` for `git` invocations); no new dependency surface. `[CITED: graph-io/src/graph_io/update.py]` |
| `json` (stdlib) | Python 3.11+ | Parse Node JSON output + serialize cache file | Already used throughout `attrs_json` handling. `[CITED: graph-io/src/graph_io/packages.py]` |
| `sqlite3` (stdlib) | Python 3.11+ | Storage backend via `upsert.upsert_records` | Existing graph store. `[CITED: graph-io/src/graph_io/store.py]` |
| `argparse` (stdlib) | Python 3.11+ | CLI dispatch | Project convention — every existing CLI handler under `cli/` uses `argparse`. `[CITED: graph-io/src/graph_io/cli/main.py]` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `graph_io.upsert.upsert_records` | workspace | Insert/update GraphNode + GraphEdge | Every Builtin emit path. |
| `graph_io.uri` | workspace | URI composition (`dependency_uri` pattern) | Add `builtin_uri(language, module_name)`. |
| `workspace_io.paths.graph_dir` | workspace | Resolve `<workspace>/.graph` | Cache path: `graph_dir(workspace) / "cache" / f"node-builtins-{major}.json"`. |
| `source_parser.projections.graph` | workspace | `GraphNode` / `GraphEdge` / `GraphRecords` dataclasses | Same shapes used by `packages.refresh`. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sys.stdlib_module_names` (runtime) | Committed JSON snapshot of stdlib | Rejected by D-04. Snapshot drifts across Python versions; runtime is canonical and zero-maintenance. |
| `node -e` subprocess | Hard-coded Node 20 builtin list | Rejected by D-02. Node adds/removes built-ins across majors (`node:test` added in 18, `node:sqlite` in 22). Cache-per-major is the cheapest correct approach. |
| Extend `_PYTHON_IMPORT_RE` regex for symbols | Switch to `ast.parse` | Regex extension is ~3 LOC and stays within the existing single-pass scanning model. AST is more correct but doubles scan cost on Python files. **Recommendation:** extend the regex; AST is a deferred improvement if false positives surface. |
| New sibling module `builtins.py` | Inline in `packages.py` | Sibling module is cleaner — `packages.py` already pushes 230 LOC and Builtin emission is conceptually distinct (stdlib classification ≠ manifest scanning). |
| Cache at `<workspace>/.graph/cache/` | `$XDG_CACHE_HOME` | Locked by D-02 (workspace-local, self-contained, naturally cleared by `cg update --full`). |

**Installation:** No external packages required. All dependencies are stdlib or existing workspace members.

## Architecture Patterns

### System Architecture Diagram

```
cg update
   │
   ▼
update.run()
   │
   ├─→ store.connect(create=True)
   ├─→ _process_files()                  (parse + project + upsert per-file)
   ├─→ packages.refresh()                (manifest scan → Package nodes + Dependency nodes + used_by edges)
   │       │
   │       └─ accumulator: (consumer_name, dep_name) → dep_acc
   │
   ├─→ builtins.refresh()    ◀── NEW    (called immediately after packages.refresh)
   │       │
   │       ├─ Load stdlib lists:
   │       │     • Python: sys.stdlib_module_names
   │       │     • Node:   load_or_refresh_cache(workspace)
   │       │                   │
   │       │                   ├─ existing cache & major matches → use it
   │       │                   ├─ stale or missing → subprocess "node -e ..."
   │       │                   └─ no node binary + no JS files → silent skip (D-03)
   │       │
   │       ├─ Scan package files (reuse scan_package_imports() shape):
   │       │     • Python: _PYTHON_IMPORT_RE → top-level segment → stdlib? → builtin candidate
   │       │     • JS/TS:  _JS_IMPORT_RE     → strip "node:" prefix + subpath → builtin? → builtin candidate
   │       │     • Capture imported symbols from `from X import a, b` and `import {a, b} from "X"`
   │       │
   │       ├─ Accumulator: (consumer_name, lang, module_name) → {imported_symbols: set[str]}
   │       │
   │       └─ Emit:
   │             • One Builtin node per (lang, module_name) with attrs {language, module_name, uri}
   │             • One `used_by` edge per (package, builtin) with attrs_json.imported_symbols
   │
   ├─→ structural_nodes.emit() / plugins.emit() / ...
   ├─→ resolve.sweep()                   (Builtin emission already happened; resolver still marks remaining unresolved)
   ├─→ derived_edges.compute()
   └─→ commit transaction

cg list-builtins
   ▼
q_list_builtins.run()  ──→  queries.list_builtins(conn)  ──→  print

cg describe-builtin <uri>
   ▼
q_describe_builtin.run()  ──→  queries.describe_builtin(conn, language, module_name)  ──→  print
```

### Recommended Project Structure

```
packages/graph-io/src/graph_io/
├── builtins.py                ◀── NEW: stdlib classification + node-builtins cache + emit
├── packages.py                (unchanged structure; share import-scan utilities)
├── import_scan.py             (extend regex to capture imported symbols, or add second-pass regex)
├── queries.py                 (+_VALID_KINDS adds "builtin"; +list_builtins; +describe_builtin; +BuiltinDescription dataclass)
├── uri.py                     (+builtin_uri)
├── update.py                  (call builtins.refresh() after packages.refresh)
├── cli/
│   ├── q_list_builtins.py     ◀── NEW: mirrors q_list_packages.py
│   ├── q_describe_builtin.py  ◀── NEW: mirrors q_describe_dependency.py
│   └── main.py                (register two new subcommands in _SUBCOMMANDS)

packages/graph-io/tests/
├── test_builtins.py           ◀── NEW: unit tests for classification + cache + emit
├── test_queries.py            (+test_list_builtins_alphabetical, +test_describe_builtin_*)
├── test_cli_describe.py       (+ describe-builtin smoke / not-found / json)
└── test_cli_smoke.py          (+ list-builtins smoke)

packages/wiki-io/src/wiki_io/
└── entity_writer.py           (ADMITTED_KINDS docstring annotation explaining builtin exclusion)
```

### Pattern 1: Dedup-and-Emit (mirrored from packages.py)

**What:** Collect (consumer, target) pairs during the scan, then collapse to one edge per (consumer_name, target_name) at emit time.
**When to use:** Builtin emission — exactly the same shape as the existing dependency-emission code.
**Example:**
```python
# Source: graph-io/src/graph_io/packages.py:203-220 (existing pattern to mirror)
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

For Builtin, the accumulator key is `(consumer_name, lang, module_name)`, and the value is a `set[str]` of imported symbols (so duplicates across files merge). The emit step serializes the sorted symbol list into `attrs_json.imported_symbols`.

### Pattern 2: Mirror-and-Replace CLI Handler

**What:** Copy `q_describe_dependency.py` verbatim, substitute `dependency` → `builtin`, swap argument names.
**When to use:** Every CLI handler in graph-io follows this template — argparse builder, read-only connect, query call, JSON/human format dispatch, exit code.
**Example:**
```python
# Source: graph-io/src/graph_io/cli/q_describe_dependency.py (existing handler to mirror)
def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("uri", help="builtin URI, e.g. builtin:python/pathlib")

def run(args: argparse.Namespace) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr); return exit_codes.NOT_INITIALIZED
    # ... parse uri → (language, module_name) → queries.describe_builtin(...)
```

### Anti-Patterns to Avoid

- **Bumping `SCHEMA_VERSION`:** D-10 locks this. The DDL is unchanged; kinds are text strings. Bumping forces every existing workspace to rebuild for no schema reason.
- **Emitting Function nodes under Builtin parents:** D-07. Stdlib has thousands of callables — even sparse coverage inflates the node table dramatically.
- **Per-file `used_by` edges:** D-09. Existing dependency edges dedup to one per (package, dep); Builtin must mirror this exactly.
- **Hard-coded stdlib lists:** D-04 (Python) + D-02 (Node). Runtime/cached lists, not snapshots.
- **Failing the scan when `node` is missing:** D-03. Silent skip; the cache file's absence + no JS files is the existing-behavior baseline.
- **Stamping each call site to stdlib as `unresolved`:** Builtin emission happens BEFORE `resolve.sweep`; the sweep should treat already-emitted Builtin edges as resolved, not flag them.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Python stdlib detection | A curated list of `os`, `sys`, `pathlib`, etc. | `sys.stdlib_module_names` (frozenset) | Stdlib provides the exact set the import system itself uses; never drifts from the runtime. |
| Node built-ins detection | A curated list of `fs`, `path`, `crypto`, etc. | `require('module').builtinModules` via single `node -e` per scan | Authoritative per Node major; curated lists go stale across Node releases. |
| JSON cache invalidation | mtime/hash comparison | Major-version key in the filename (`node-builtins-20.json`) + presence check | One read, no stat dance; cheap to invalidate by running `node --version`. |
| URI parsing for `cg describe-builtin builtin:python/pathlib` | Custom regex | `str.split(":", 1)` then `str.split("/", 1)` | URI shape is constrained by `builtin_uri()`; split is sufficient and matches `cg describe-dependency`'s implicit shape. |
| Subprocess invocation patterns | Custom wrapper | `subprocess.run(["node", "-e", "..."], capture_output=True, text=True, check=False)` | Already the in-house pattern in `update.py` for `git`. |

**Key insight:** Every primitive Phase 49 needs is already in stdlib or already in the graph-io workspace. The phase is wiring + classification logic, not new infrastructure.

## Runtime State Inventory

Not a rename / refactor phase. Skipped.

## Common Pitfalls

### Pitfall 1: Node-builtin name aliasing (`node:fs` vs `fs` vs `node:fs/promises`)

**What goes wrong:** Three different import specifiers for the same builtin produce three different Builtin nodes.
**Why it happens:** Modern Node added the `node:` prefix as an explicit-stdlib marker; `node:fs/promises` exposes the promise API on a subpath. Naive `js_map[spec]` lookups treat them as distinct.
**How to avoid:** Normalize before lookup. Strip a `node:` prefix; then take the segment before the first `/`. D-06 locks this collapse.
**Warning signs:** Duplicate Builtin nodes for the same module after a scan; `cg list-builtins` shows `fs` and `node:fs` separately.

### Pitfall 2: Scanner-Python-version drift

**What goes wrong:** Code targets Python 3.8 (uses `distutils`), but the scanner runs on Python 3.12 (where `distutils` is removed from stdlib). `distutils` does not classify as Builtin and falls through as an unresolved Symbol.
**Why it happens:** D-04 explicitly accepts this trade — scanner runtime is the source of truth.
**How to avoid:** Document the limitation in the ship note. Surface it again if it produces visible noise in this repo (it currently doesn't — agent-research is Python 3.11+).
**Warning signs:** Unresolved Symbol nodes for modules that are stdlib in older Python versions.

### Pitfall 3: Symbol-capture regex matches comments / strings

**What goes wrong:** A regex extension that captures `import a, b` matches `# from os import getenv` or `"from os import getenv"` inside docstrings.
**Why it happens:** The current `_PYTHON_IMPORT_RE` is anchored with `^\s*` (MULTILINE) and that already handles most comment cases, but multi-line strings can still leak.
**How to avoid:** Re-use the existing `^\s*` anchor; document the known false-positive surface in `builtins.py`. AST is the correct long-term answer; deferred per Claude's-Discretion notes.
**Warning signs:** Builtin nodes appearing for modules that aren't actually imported.

### Pitfall 4: Edge dedup vs symbol union

**What goes wrong:** Plan emits one edge per file with its file's local symbol list; second emit per file overwrites instead of merging.
**Why it happens:** Mirroring the dependency dedup pattern WITHOUT also unioning the symbol sets per-edge.
**How to avoid:** Accumulator value is a `set[str]` keyed by `(consumer_name, lang, module_name)`. Merge via `set.update` while collecting; serialize sorted list at emit time.
**Warning signs:** `attrs_json.imported_symbols` shows only the symbols from the last file scanned; `cg describe-builtin` underreports usage breadth.

### Pitfall 5: `cg update` (incremental) vs `cg update --full` for first run after upgrade

**What goes wrong:** User upgrades to v1.9, runs `cg update` (incremental, only diffs since last commit), and stdlib-importing files that haven't changed still have stale unresolved Symbol nodes.
**Why it happens:** D-11 explicitly chose not to clean these up retroactively.
**How to avoid:** Ship-note documentation: tell users to run `cg update --full` once after upgrading.
**Warning signs:** Lingering Symbol nodes for stdlib modules in pre-upgrade graphs.

### Pitfall 6: `node` subprocess hangs in CI / sandbox environments

**What goes wrong:** `subprocess.run(["node", "-e", "..."])` hangs or fails with no useful error in a restricted environment.
**Why it happens:** Sandbox restricts subprocess; `node` exists but cannot execute arbitrary `-e` strings; or `node` runs but stdout is empty.
**How to avoid:** Always set a small `timeout=` (e.g., 5s), wrap in try/except, on any failure fall through to D-03 "silent skip". Cache file write should be best-effort.
**Warning signs:** `cg update` hangs intermittently; tests fail flakily on sandboxed CI.

## Code Examples

Verified patterns from in-repo sources.

### Python stdlib detection

```python
# Source: stdlib (verified via docs.python.org/3/library/sys.html#sys.stdlib_module_names)
import sys

PYTHON_STDLIB: frozenset[str] = sys.stdlib_module_names  # Python 3.10+

def is_python_stdlib(module_str: str) -> bool:
    """Return True if the top-level segment is a Python stdlib module."""
    top = module_str.split(".", 1)[0]
    return top in PYTHON_STDLIB
```

### Node built-ins detection (cache + subprocess fallback)

```python
# Source: pattern composed from graph_io.update subprocess use + D-02 cache spec
import json
import subprocess
from pathlib import Path

def _node_major() -> str | None:
    try:
        out = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, check=False, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    # "v20.11.0" -> "20"
    v = out.stdout.strip().lstrip("v")
    return v.split(".", 1)[0] if v else None

def _harvest_node_builtins() -> list[str] | None:
    try:
        out = subprocess.run(
            ["node", "-e", 'console.log(JSON.stringify(require("module").builtinModules))'],
            capture_output=True, text=True, check=False, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None

def load_node_builtins(cache_dir: Path) -> frozenset[str]:
    """Return Node built-ins for the current Node major; empty frozenset on failure (D-03)."""
    major = _node_major()
    if major is None:
        return frozenset()
    cache_file = cache_dir / f"node-builtins-{major}.json"
    if cache_file.exists():
        try:
            return frozenset(json.loads(cache_file.read_text()))
        except (OSError, json.JSONDecodeError):
            pass  # fall through to re-harvest
    harvested = _harvest_node_builtins()
    if harvested is None:
        return frozenset()
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        cache_file.write_text(json.dumps(harvested))
    except OSError:
        pass  # cache write is best-effort
    return frozenset(harvested)
```

### Node-spec normalization (D-06)

```python
# Source: D-06 spec; verified against require('module').builtinModules contents
def normalize_node_spec(spec: str) -> str:
    """`node:fs` → `fs`; `node:fs/promises` → `fs`; `fs/promises` → `fs`."""
    s = spec[5:] if spec.startswith("node:") else spec
    return s.split("/", 1)[0]
```

### Builtin URI builder (mirror `dependency_uri`)

```python
# Source: graph-io/src/graph_io/uri.py:53 (dependency_uri pattern)
def builtin_uri(language: str, module_name: str) -> str:
    """builtin:python/pathlib, builtin:javascript/fs."""
    return f"builtin:{language}/{module_name}"
```

### Builtin emit (mirror `packages.refresh` dedup-and-emit tail)

```python
# Source: graph-io/src/graph_io/packages.py:188-220 (existing pattern; adapt key + attrs)
builtin_acc: dict[tuple[str, str], set[str]] = {}        # (lang, module_name) -> seen symbols
edge_acc: dict[tuple[str, str, str], set[str]] = {}      # (pkg_name, lang, module_name) -> symbols
# ... populate during scan ...

builtin_nodes: list[GraphNode] = []
for (lang, module_name), _ in sorted(builtin_acc.items()):
    builtin_nodes.append(
        GraphNode(
            kind="builtin",
            name=module_name,
            path=None,
            line=None,
            attrs={
                "uri": builtin_uri(lang, module_name),
                "language": lang,
                "module_name": module_name,
            },
        )
    )

builtin_edges: list[GraphEdge] = []
for (pkg_name, lang, module_name), symbols in sorted(edge_acc.items()):
    builtin_edges.append(
        GraphEdge(
            src=("package", pkg_name, None),
            dst=("builtin", module_name, None),
            kind="used_by",
            attrs={"imported_symbols": sorted(symbols)},
        )
    )
if builtin_nodes or builtin_edges:
    upsert.upsert_records(conn, GraphRecords(nodes=builtin_nodes, edges=builtin_edges))
```

### Read-only query (mirror `describe_dependency`)

```python
# Source: graph-io/src/graph_io/queries.py:558-595 (describe_dependency)
@dataclass(frozen=True)
class BuiltinDescription:
    language: str
    module_name: str
    uri: str
    used_by: list[str]

def describe_builtin(
    conn: sqlite3.Connection, *, language: str, module_name: str
) -> BuiltinDescription | None:
    row = conn.execute(
        "SELECT id, name, attrs_json, uri FROM nodes "
        "WHERE kind='builtin' AND name = ? "
        "AND json_extract(attrs_json, '$.language') = ?",
        (module_name, language),
    ).fetchone()
    if not row:
        return None
    bid, name, attrs_json, uri = row
    used_by_rows = conn.execute(
        "SELECT p.name FROM edges e "
        "JOIN nodes p ON e.src = p.id "
        "WHERE e.kind='used_by' AND e.dst = ? AND p.kind='package' "
        "ORDER BY p.name",
        (bid,),
    ).fetchall()
    return BuiltinDescription(
        language=language,
        module_name=name,
        uri=uri or "",
        used_by=[r[0] for r in used_by_rows],
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-curated stdlib lists | `sys.stdlib_module_names` (Python 3.10+) | Python 3.10, Oct 2021 | Canonical, drift-free; project floor is 3.11 so always available. |
| Hand-curated Node built-in lists | `require('module').builtinModules` (Node 9.3.0+) | 2017 | Authoritative per-major; one subprocess + small cache file solves the rest. |
| `cg list-dependencies` CLI | Not yet wired — `queries.list_dependencies()` exists but no `q_list_dependencies.py` handler | — | The new `cg list-builtins` will be the first `list-*` handler for a non-Package entity kind. **Implication for planner:** the CLI surface for `list-builtins` is a fresh module, not a copy of an existing `q_list_dependencies.py`. Use `q_list_packages.py` as the template. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `subprocess.run(["node", ...])` timeout of 5s is sufficient on developer machines | Pitfall 6 | If `node` is slow to start on Windows (a known issue), 5s might race. Mitigation: log the failure (stderr), fall through to D-03 silent skip. Acceptable. |
| A2 | Python's `^\s*(?:from\|import)\s+` regex is good-enough for capturing top-level symbols on the same line | Pitfall 3 | Multi-line `from x import (a, b,)` would not be captured by the existing regex's single-line match. The planner should decide whether to extend the regex with optional paren-multi-line capture or accept partial coverage. |
| A3 | `wiki_io.entity_writer.ADMITTED_KINDS` does not already include `builtin` (verified by reading the file) | Architectural map / D-16 | Verified: the frozenset contains 7 entries — `repository`, `domain`, `package`, `package_family`, `plugin`, `dependency`, `test_suite`. **Not assumed — verified.** Phase 49 only needs to add an annotation/comment confirming the exclusion. |
| A4 | The `cg describe-builtin <uri>` argument should be a single URI string parsed into language + module_name | D-13 / CLI shape | Alternative: two positional args (`describe-builtin python pathlib`). URI parsing matches the success criterion #3 example (`cg describe-builtin builtin:python/pathlib`). The planner should confirm. |
| A5 | "Builtin is listed in `_VALID_KINDS` and in `ADMITTED_KINDS`" (ROADMAP success criterion #5) is a documentation slip; CONTEXT D-16 supersedes — `builtin` is EXCLUDED from `ADMITTED_KINDS` | success criterion #5 vs D-16 | If the ROADMAP wording is the real intent (add Builtin to ADMITTED_KINDS), Phase 49 needs to add a wiki template too. **Decision based on CONTEXT precedence (more recent, more specific):** treat success criterion #5 as "Builtin is in `_VALID_KINDS` (added) and is EXPLICITLY ABSENT from `ADMITTED_KINDS` with a code annotation explaining the exclusion." The planner should surface this as a clarification in plan must_haves. |

## Open Questions (RESOLVED)

1. **`cg describe-builtin` argument shape — URI or two positionals?** — RESOLVED: positional URI string (`builtin:python/pathlib`) parsed via `str.split(":", 1)` then `str.split("/", 1)`. Matches success criterion #3 verbatim. Plan 03 Task 2 implements the parse with explicit error handling for malformed URIs.

2. **Multi-line Python `from x import (a, b, c,)` symbol capture** — RESOLVED: accept partial coverage for Phase 49. The existing `_PYTHON_IMPORT_RE` only captures single-line imports; multi-line paren imports may produce incomplete `imported_symbols` lists, but the `used_by` edge itself is still correct (the module-spec match always succeeds). Plan 02 Task 1 documents this limitation in the module docstring. AST migration is flagged as a deferred successor (Assumption A2 in the table above).

3. **`cg list-builtins` JSON output schema** — RESOLVED: raw `NodeRecord` (kind, name, path, line, attrs) via `dataclasses.asdict`, consistent with `q_list_packages.py`. `attrs` already contains `language` and `module_name`. No new dataclass needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Scanner runtime, `sys.stdlib_module_names` | ✓ | Project floor 3.11 (verified via CLAUDE.md) | — |
| `node` (CLI) | BUILTIN-02 (cache refresh) | ✓ on dev machines (assumed) | — | D-03: silent skip if missing |
| `sqlite3` (stdlib) | Graph store | ✓ | Python stdlib | — |
| `subprocess`, `json`, `re` (stdlib) | All paths | ✓ | Python stdlib | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** `node` — explicit silent-skip path (D-03).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 + pytest-asyncio 1.3.0 (per project CLAUDE.md §8) |
| Config file | `packages/graph-io/pyproject.toml` (pytest config) + `packages/graph-io/tests/conftest.py` |
| Quick run command | `uv run --package graph-io pytest tests/test_builtins.py -x` |
| Full suite command | `uv run --package graph-io pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUILTIN-01 | Python stdlib imports → `builtin:python/<name>` nodes | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_python_stdlib_emits_builtin_nodes -x` | ❌ Wave 0 |
| BUILTIN-02 | Node stdlib imports → `builtin:javascript/<name>` nodes | unit + integration | `uv run --package graph-io pytest tests/test_builtins.py::test_node_stdlib_emits_builtin_nodes -x` | ❌ Wave 0 |
| BUILTIN-03 | npm `express` stays `dependency`; Node `fs` becomes `builtin` | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_node_dependency_vs_builtin_classification -x` | ❌ Wave 0 |
| BUILTIN-04 | Builtin nodes have `language` + `module_name`; URI scheme correct | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_builtin_node_attrs_and_uri -x` | ❌ Wave 0 |
| BUILTIN-05 | One `used_by` edge per (package, builtin); `imported_symbols` is sorted union | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_used_by_edge_dedup_and_symbol_union -x` | ❌ Wave 0 |
| BUILTIN-06 | `cg list-builtins` and `cg describe-builtin` CLI surfaces work | CLI integration | `uv run --package graph-io pytest tests/test_cli_describe.py::test_cg_describe_builtin_smoke tests/test_cli_smoke.py::test_cg_list_builtins_smoke -x` | ❌ Wave 0 |
| Schema invariant | `"builtin" in _VALID_KINDS`; `"builtin" not in ADMITTED_KINDS` | unit | `uv run --package graph-io pytest tests/test_queries.py::test_valid_kinds_includes_builtin -x && uv run --package wiki-io pytest tests/test_entity_templates.py -x` | ❌ Wave 0 |
| Idempotency | Second `cg update` produces identical Builtin node + edge set | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_emit_is_idempotent -x` | ❌ Wave 0 |
| Node cache | First scan creates cache file; second scan reuses it; different Node major triggers re-harvest | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_node_builtins_cache_lifecycle -x` | ❌ Wave 0 |
| Silent-skip (D-03) | No node binary + no JS files → no error, no Builtin JS nodes | unit | `uv run --package graph-io pytest tests/test_builtins.py::test_silent_skip_when_node_missing -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run --package graph-io pytest tests/test_builtins.py -x` (~3-5s)
- **Per wave merge:** `uv run --package graph-io pytest tests/ -x` (~30-60s)
- **Phase gate:** Full suite green: `uv run pytest packages/graph-io/tests/ packages/wiki-io/tests/test_entity_templates.py -v`

### Wave 0 Gaps

- [ ] `packages/graph-io/tests/test_builtins.py` — covers BUILTIN-01 through BUILTIN-05 + idempotency + cache + silent-skip
- [ ] Test additions in `packages/graph-io/tests/test_queries.py` — `test_list_builtins_alphabetical`, `test_describe_builtin_returns_description`, `test_describe_builtin_returns_none_when_missing`, `test_valid_kinds_includes_builtin`
- [ ] Test additions in `packages/graph-io/tests/test_cli_describe.py` — `test_cg_describe_builtin_smoke`, `test_cg_describe_builtin_not_found`, `test_cg_describe_builtin_json`
- [ ] Test addition in `packages/graph-io/tests/test_cli_smoke.py` — `test_cg_list_builtins_smoke`
- [ ] Optional cross-cutting check in `packages/wiki-io/tests/test_entity_templates.py` confirming `"builtin" not in ADMITTED_KINDS` (defends D-16 / SC#5 against future regression)

Framework install: already present (project uses pytest); no additional install needed.

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a — internal scanner, no external entry points |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a — runs as developer process |
| V5 Input Validation | yes | `subprocess.run(["node", "-e", "<literal string>"])` — argument is a hardcoded literal, not user input. No injection surface. |
| V6 Cryptography | no | n/a |
| V12 File and Resources | yes | Cache file `<workspace>/.graph/cache/node-builtins-*.json` is written under the workspace tree only. Path is composed from `graph_dir(workspace)`, not user input. |

### Known Threat Patterns for graph-io / Phase 49

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Subprocess argument injection via `node -e` | Tampering | The argument is a hardcoded literal string in source; nothing from user input or scanned files flows into `subprocess.run`'s argv. |
| Symlink traversal via cache file write | Tampering | `cache_dir.mkdir(parents=True, exist_ok=True)` then `cache_file.write_text(...)` under `<workspace>/.graph/cache/`. Workspace ownership is the trust boundary; no traversal surface. |
| Untrusted JSON parsing from `node -e` output | Tampering | `json.loads()` on a stdlib `module.builtinModules` return value. Worst case is a malformed JSON parse that returns an empty frozenset (D-03 silent-skip path). No `eval` or `exec`. |
| Hang/DoS via slow `node` subprocess | Denial of Service | `timeout=5` on every `subprocess.run` call. Failure path silently skips. |

No new external packages → no slopcheck audit needed.

## Sources

### Primary (HIGH confidence)
- `packages/graph-io/src/graph_io/queries.py:9-25` — `_VALID_KINDS` frozenset (needs `"builtin"` added)
- `packages/graph-io/src/graph_io/queries.py:558-595` — `describe_dependency` (pattern for `describe_builtin`)
- `packages/graph-io/src/graph_io/queries.py:655-657` — `list_dependencies` (pattern for `list_builtins`)
- `packages/graph-io/src/graph_io/uri.py:53` — `dependency_uri` (pattern for `builtin_uri`)
- `packages/graph-io/src/graph_io/packages.py:132-220` — manifest scan + dependency emit (pattern for `builtins.refresh`)
- `packages/graph-io/src/graph_io/import_scan.py:20-23, 45-66, 113-150` — regex + scan utilities to reuse
- `packages/graph-io/src/graph_io/cli/main.py` — `_SUBCOMMANDS` dict (registration point)
- `packages/graph-io/src/graph_io/cli/q_describe_dependency.py` — CLI handler template
- `packages/graph-io/src/graph_io/cli/q_list_packages.py` — CLI handler template
- `packages/graph-io/src/graph_io/update.py:265-313` — pipeline ordering (insert `builtins.refresh` after `packages.refresh`)
- `packages/graph-io/src/graph_io/exit_codes.py` — stable exit codes (`SUCCESS`, `GENERIC`, `NOT_INITIALIZED`, `SCHEMA_MISMATCH`)
- `packages/wiki-io/src/wiki_io/entity_writer.py:56-66` — `ADMITTED_KINDS` frozenset (verified: does NOT include `"builtin"`)
- `packages/wiki-io/tests/test_entity_templates.py:38-68` — bijection invariant that defends ADMITTED_KINDS against drift
- `packages/workspace-io/src/workspace_io/paths.py:29-30` — `graph_dir(workspace) → Path` for cache placement
- `packages/graph-io/tests/test_cli_describe.py:1-110` — CLI test fixture pattern
- `packages/graph-io/tests/test_queries.py:1074-1170` — `describe_dependency` / `list_dependencies` test patterns
- `packages/graph-io/CLAUDE.md` — conventions: read-only via `store.read_only_connect`, write inside `store.transaction()`, errors→stderr, JSON→stdout, stable exit codes

### Secondary (MEDIUM confidence)
- Python docs: `sys.stdlib_module_names` (CPython 3.10+ stdlib frozenset) — well-established stdlib API
- Node.js docs: `require('module').builtinModules` (Node 9.3.0+) — stable Node API across all currently-supported major versions

### Tertiary (LOW confidence)
- None — all guidance is grounded in the workspace source or stdlib documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every primitive verified in-source or via stdlib documentation
- Architecture: HIGH — exactly mirrors existing dependency emission pattern
- Pitfalls: HIGH — D-03/D-06/D-09 explicitly call out the named risks; pitfalls 3/5 inferred from the existing import-scan regex + D-11 ship note

**Research date:** 2026-05-27
**Valid until:** ~2026-06-25 (30 days; stable internal scanner work, no fast-moving deps)

## Project Constraints (from CLAUDE.md)

- **`graph-io` conventions** (`packages/graph-io/CLAUDE.md`):
  - Read-only queries via `store.read_only_connect()` (no direct `sqlite3.connect`)
  - All updates inside one `store.transaction()`
  - Errors to stderr, JSON to stdout — never mix
  - Exit codes stable from `exit_codes.py` (no new exit-code values)
- **Python ≥3.11** (project floor) — `sys.stdlib_module_names` always available; modern typing (`str | None`) used throughout
- **GSD workflow** — all edits originate from a GSD command; no out-of-band edits
- **No new external dependencies** — phase is stdlib + workspace-internal only
</content>
</invoke>