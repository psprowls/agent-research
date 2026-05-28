# Phase 50: App Reclassification (graph-io) — Research

**Researched:** 2026-05-27
**Domain:** graph-io manifest scanning, SQLite node kind mutation, URI rewriting, CLI surfaces
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `attrs_json.app_signals` = sorted list of every matched signal; `attrs_json.app_kind` = derived primary (framework wins over cli; nextjs > expo > spa alphabetical tiebreak).
- **D-02:** Fixed signal mapping — Python `[project.scripts]` non-empty → `cli`; JS `bin` (string or object, non-empty) → `cli`; `dependencies.next` → `nextjs`; `dependencies.expo` → `expo`; `dependencies.vite` + `index.html` at package root → `spa`.
- **D-03:** Zero signals → node stays `kind='package'`; no `app_signals` / `app_kind` emitted.
- **D-04:** New module `classification.py`; pure function `classify(manifest_dict, pkg_dir: Path) → tuple[str, str | None, list[str]]`; called inline from `_discover_manifests` loop at `packages.py:135`.
- **D-05:** `index.html` check is `(pkg_dir / "index.html").exists()` — direct filesystem, no graph query.
- **D-06:** In-place `UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?` when classification flips on re-run. Probe both `(package, name, path)` and `(app, name, path)` before calling `upsert_records`. Preserves row `id` so all inbound edge FKs survive.
- **D-07:** URI prefix flips with kind: `app:org/repo/<name>`. New `app_uri(ctx, name)` in `uri.py`.
- **D-08:** No vault wikilink rewrites, no `*-MIGRATION.md` artifact in Phase 50.
- **D-09:** `cg list-apps` mirrors `cg list-packages` (same JSON-vs-text flag, same row shape + `app_kind` column).
- **D-10:** `cg describe-app <uri>` mirrors `cg describe-package` (same JOIN-back-to-edges output + `app_kind` and `app_signals` in JSON).
- **D-11:** Both handlers live in `packages/graph-io/src/graph_io/cli/` next to package equivalents, same `read_only_connect()` pattern, same exit codes.
- **D-12:** No `SCHEMA_VERSION` bump (stays at 2). Add `"app"` to `_VALID_KINDS`.
- **D-13:** `app_kind` and `app_signals` in `attrs_json`, no new SQL columns.
- **D-14:** `wiki-io` untouched in Phase 50.

### Claude's Discretion

- Whether to add `_VALID_APP_KINDS = frozenset({"cli","nextjs","expo","spa"})` in `queries.py` (planner picks; default yes with a unit test).
- `attrs_json` shape for `app_signals`: sorted list of strings only (no `signals_detail` sub-object). Default: minimal list.
- Existing-row lookup (D-06): per-manifest `SELECT` or batched pre-loop lookup. Default: per-manifest for code-locality.
- `cg describe-app` surfaces `app_signals` always (not behind `--verbose`). Default: always.

### Deferred Ideas (OUT OF SCOPE)

- wiki-io consumer flip (Phase 52)
- Wikilink rewrites (Phase 53)
- `package_family` removal (Phase 51)
- Per-signal metadata / signals_detail
- Additional app frameworks beyond cli/nextjs/expo/spa
- Cross-language CLI signals beyond `[project.scripts]` / `bin`
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APP-01 | Scanner reclassifies Package → App on manifest signals (Python scripts, JS bin, next/expo/vite+index.html) | `classification.py` pure function fed by extended manifest readers; `classify()` called in `packages.refresh` loop |
| APP-02 | App is a graph kind separate from Package; participates in same edges | `_VALID_KINDS` + `"app"` admission; standard `upsert_records` for new App nodes; existing edges survive via D-06 in-place UPDATE |
| APP-03 | No false positives; multi-signal documented precedence | `classify()` returns `kind="package"` when signals list is empty; precedence encoded as ordered check in `classify()` |
| APP-04 | `app_kind` attribute on App nodes | `attrs_json` field; set by `classify()` return value; planner also decides on `_VALID_APP_KINDS` gate |
| APP-05 | `cg list-apps` + `cg describe-app` CLI surfaces | Two new handler modules mirroring package equivalents; `list_apps()` and `describe_app()` in `queries.py` |
| APP-06 | URI rewrite (`pkg:` ↔ `app:`) on classification flip; repeatable | `app_uri()` in `uri.py`; D-06 in-place UPDATE rewrites both `kind` and `uri` column; second run reverts if signal disappears |
</phase_requirements>

---

## Summary

Phase 50 adds `App` as a first-class graph kind in `graph-io`. The implementation is surgery on three existing files (`packages.py`, `queries.py`, `uri.py`) plus two new files (`classification.py`, two CLI handler modules) and a mutation path in the manifest emit loop for kind-flip persistence. Everything builds on the Phase 49 patterns for `Builtin` kind admission and CLI mirroring.

The primary complication is the **in-place UPDATE path (D-06)**: when a `Package` node gains app signals on re-run, the existing row must be mutated (kind, uri, attrs_json) rather than inserted anew, to preserve inbound edge FK pointers. `_node_id(conn, key)` is the existing lookup function and can be called twice (once with `kind="package"`, once with `kind="app"`) to detect and rewrite the "other-kind" row. The standard `_upsert_node` path handles the happy-path (new node or same-kind repeat run).

The second complication is a **manifest reader gap**: `_read_package_json` currently strips `bin` from the returned dict (it only returns `name`, `version`, `dependencies`, `language`). The `bin` field must be added to the returned info dict for `classification.py` to consume it without re-parsing the manifest. Similarly, `_read_pyproject` must add a `scripts_present: bool` field (or the raw `scripts` dict) so `classify()` can detect non-empty `[project.scripts]` without re-opening the TOML file.

**Primary recommendation:** Implement in this order: (1) extend manifest readers → (2) write `classification.py` → (3) add `_VALID_KINDS` + `_VALID_APP_KINDS` + `app_uri` → (4) wire classify into `packages.refresh` with D-06 flip detection → (5) add `list_apps` / `describe_app` query functions → (6) add CLI handlers → (7) register in `main.py`.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Signal detection | `classification.py` (new pure module) | `packages.py` (calls classify) | Signal detection is a pure function of manifest dict + filesystem; belongs in its own module |
| Manifest reader extension | `packages.py` (`_read_pyproject`, `_read_package_json`) | — | Readers own the info dict shape; adding fields here keeps classification.py IO-free |
| Kind/URI/attrs write | `packages.py` emit loop (via `upsert.py`) | — | All node mutation goes through `upsert_records` or the explicit D-06 UPDATE |
| In-place kind-flip | `packages.py` emit loop (explicit SELECT + UPDATE) | `upsert.py._node_id` (lookup helper) | Flip logic belongs adjacent to the upsert call so it is trivially visible |
| Kind admission | `queries.py` (`_VALID_KINDS`) | — | Python-side gate; no DDL change needed |
| URI composition | `uri.py` (`app_uri`) | — | All URI builders live here |
| Read-only queries | `queries.py` (`list_apps`, `describe_app`) | — | Mirrors `list_packages` / `describe_package` |
| CLI surface | `cli/q_list_apps.py`, `cli/q_describe_app.py` | `cli/main.py` (registration) | Mirror pattern from package handlers |

---

## Standard Stack

No new external packages introduced. Phase 50 is pure internal graph-io surgery.

### Core (already in graph-io)

| Module | Role | Notes |
|--------|------|-------|
| `sqlite3` (stdlib) | DB reads/writes | No new usage patterns |
| `tomllib` (stdlib, 3.11+) | TOML parse in `_read_pyproject` | Already in `packages.py` |
| `json` (stdlib) | JSON parse in `_read_package_json` | Already in `packages.py` |
| `pathlib.Path` | `index.html` filesystem check (D-05) | Already imported |
| `source_parser.projections.graph` | `GraphNode`, `GraphEdge`, `GraphRecords` | Already in `packages.py` |

### Package Legitimacy Audit

No external packages to audit. All dependencies are either stdlib or in-repo workspace members.

---

## Architecture Patterns

### System Architecture Diagram

```
pyproject.toml / package.json
           │
           ▼
  _read_pyproject()            _read_package_json()
  _read_pyproject()  ──────▶  info dict (name, version, dependencies,
  [adds scripts_present]       language, bin_present, scripts_present)
           │
           ▼
  classification.classify(info, pkg_dir)
           │
           ├──▶ signals=[]  ──▶  kind="package", app_kind=None, app_signals=[]
           │
           └──▶ signals=[...]  ──▶  kind="app", app_kind="cli"|"nextjs"|..., app_signals=[...]
                    │
                    ▼
  packages.refresh emit loop (packages.py:135)
           │
           ├──▶ probe _node_id("package", name, path)  ─────▶  "other-kind" row found?
           │           │                                              │
           │           │ YES (re-run, kind changed)                  │ NO
           │           ▼                                             ▼
           │    UPDATE nodes SET kind=?, uri=?, attrs_json=?   INSERT via _upsert_node
           │    (preserves row id → all inbound edge FKs OK)
           │
           ▼
  upsert.upsert_records(conn, GraphRecords(nodes, edges))
           │
           ▼
  SQLite nodes table  ──▶  queries.list_apps() / describe_app()
                                     │
                                     ▼
                          CLI: cg list-apps / cg describe-app
```

### Recommended Project Structure (new files only)

```
packages/graph-io/src/graph_io/
├── classification.py      # NEW: pure classify() function
├── packages.py            # MODIFIED: manifest readers + emit loop
├── queries.py             # MODIFIED: _VALID_KINDS, list_apps, describe_app
├── uri.py                 # MODIFIED: add app_uri()
└── cli/
    ├── q_list_apps.py     # NEW: mirrors q_list_packages.py
    ├── q_describe_app.py  # NEW: mirrors q_describe_package.py
    └── main.py            # MODIFIED: register list-apps + describe-app
```

---

## Implementation Order (Critical Path)

The following dependency chain determines wave structure:

```
Wave 0 (test scaffolding):
  tests/test_classification.py    ← pure unit, no DB
  tests/test_packages.py          ← add app fixture tests
  tests/test_queries.py           ← add list_apps / describe_app stubs
  tests/test_cli_smoke.py         ← add list-apps / describe-app smoke stubs

Wave 1 (foundation):
  queries.py   → add "app" to _VALID_KINDS (+ optional _VALID_APP_KINDS)
  uri.py       → add app_uri(ctx, name)
  packages.py  → extend _read_pyproject (scripts_present) + _read_package_json (bin_present)

Wave 2 (classification module):
  classification.py  → classify() pure function

Wave 3 (emit loop wiring + D-06 flip):
  packages.py:refresh  → call classify(), build app/package node, D-06 flip logic

Wave 4 (query + CLI):
  queries.py         → list_apps(), describe_app(), AppDescription dataclass
  cli/q_list_apps.py
  cli/q_describe_app.py
  cli/main.py        → register both handlers

Wave 5 (integration):
  verify full cg update → cg list-apps round-trip on graph-wiki-agent
```

**Strict unblocking constraint:** `_VALID_KINDS` must admit `"app"` before any test tries to call `queries.find(kind="app")`. The `classify()` function must exist before the emit loop is wired. `app_uri` must exist before the classification result is built into a `GraphNode`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Node lookup by (kind, name, path) | Custom SELECT | `upsert._node_id(conn, key)` | Already handles NULL path correctly (two branches) |
| Kind-flip UPDATE | Custom migration | Inline UPDATE at emit time using the existing row id from `_node_id` | Keeps the flip reversible on every run; no migration artifact needed |
| CLI arg parsing | Custom argparse | Copy pattern from `q_list_packages.py` / `q_describe_package.py` verbatim | Identical error handling, exit codes, `--fmt` flag |
| DB connection management | Custom context manager | `store.read_only_connect()` / `store.transaction()` | Existing helpers enforce the CLAUDE.md conventions |
| URI composition | String formatting inline | `uri.app_uri(ctx, name)` | URI surface is locked in `uri.py`; inline strings escape the constraint |

**Key insight:** The classification logic is entirely new, but the persistence, query, and CLI layers are near-verbatim copies of existing patterns. The work is mostly wiring, not invention.

---

## Detailed Implementation Notes

### 1. Manifest Reader Extension

**`_read_pyproject` (packages.py:45–68)** — add `scripts_present`:

```python
scripts = project.get("scripts") or {}
return {
    "name": name,
    "version": project.get("version", ""),
    "dependencies": list(project.get("dependencies", [])),
    "dep_groups": dep_groups,
    "language": "python",
    "scripts_present": bool(scripts),   # NEW: non-empty [project.scripts]
}
```

The raw `scripts` dict is NOT needed in `info`; only the boolean is required because `classification.classify` only needs to know presence, not the content (the entry-point emitter separately re-reads the TOML for the content).

**`_read_package_json` (packages.py:71–87)** — add `bin_present` and pass through dependency names for next/expo/vite detection:

```python
bin_val = data.get("bin")
bin_present = bool(bin_val) and (
    (isinstance(bin_val, str) and bin_val) or
    (isinstance(bin_val, dict) and any(bin_val.values()))
)
return {
    "name": name,
    "version": data.get("version", ""),
    "dependencies": sorted(deps.keys()) if isinstance(deps, dict) else list(deps),
    "language": "javascript",
    "bin_present": bin_present,          # NEW: JS bin field signal
}
```

Note: `dependencies` is already a sorted list of names, so `"next" in info["dependencies"]` works directly for the nextjs/expo/vite checks. No additional field needed for those three signals.

[VERIFIED: codebase grep] `_read_package_json` currently returns only `name`, `version`, `dependencies`, `language`. The `bin` field is parsed separately in `entry_points._emit_packagejson_entries`, not in `packages._read_package_json`. This gap must be filled before `classification.py` can use it.

### 2. classification.py

```python
"""Pure app-signal classification for manifest info dicts."""
from __future__ import annotations
from pathlib import Path

_FRAMEWORK_PRECEDENCE = ("nextjs", "expo", "spa")

def classify(
    info: dict,
    pkg_dir: Path,
) -> tuple[str, str | None, list[str]]:
    """Return (kind, app_kind, app_signals) for a manifest info dict.

    kind ∈ {"package", "app"}; app_kind is None when kind="package".
    app_signals is the sorted list of all matched signals.
    """
    signals: list[str] = []
    lang = info.get("language", "")

    if lang == "python":
        if info.get("scripts_present"):
            signals.append("cli")
    elif lang == "javascript":
        if info.get("bin_present"):
            signals.append("cli")
        deps = info.get("dependencies") or []
        if "next" in deps:
            signals.append("nextjs")
        if "expo" in deps:
            signals.append("expo")
        if "vite" in deps and (pkg_dir / "index.html").exists():
            signals.append("spa")

    if not signals:
        return "package", None, []

    signals.sort()

    # Derive primary app_kind: framework wins over cli; precedence nextjs>expo>spa
    app_kind: str = "cli"
    for framework in _FRAMEWORK_PRECEDENCE:
        if framework in signals:
            app_kind = framework
            break

    return "app", app_kind, signals
```

[ASSUMED] The precedence loop assumes `_FRAMEWORK_PRECEDENCE` iterates in priority order (nextjs first). This is correct because `next > expo > spa` and the tuple is ordered that way.

### 3. The In-Place UPDATE for Kind-Flip (D-06)

This is the trickiest part. The existing `_upsert_node` only mutates nodes of the same `(kind, name, path)` key. When `kind` changes, `_upsert_node` would INSERT a second row, leaving the old-kind row orphaned and all inbound edges pointing at the stale row.

**Concrete plan:**

Before calling `upsert.upsert_records`, probe for the "other-kind" row:

```python
# In packages.refresh emit loop, after classify():
other_kind = "package" if new_kind == "app" else "app"
other_key = (other_kind, info["name"], rel_prefix or None)
other_id = upsert._node_id(conn, other_key)

if other_id is not None:
    # Kind has flipped — mutate the existing row in-place.
    new_uri = app_uri(ctx, info["name"]) if new_kind == "app" else pkg_uri(ctx, info["name"])
    new_attrs = _build_attrs(info, app_kind, app_signals, new_uri)
    conn.execute(
        "UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?",
        (new_kind, new_uri, json.dumps(new_attrs, sort_keys=True), other_id),
    )
    # upsert_records will now find (new_kind, name, path) and UPDATE it (not INSERT)
```

After the in-place mutation, `_upsert_node` will correctly find the row by `(new_kind, name, path)` and update it as normal. No duplicate rows.

**Transaction safety:** This UPDATE runs inside the same `store.transaction(conn)` that wraps all of `packages.refresh` (established in `update.py:273`). No separate transaction needed; atomicity is inherited.

**Edge FK safety:** `ON DELETE CASCADE` is set on both `edges.src` and `edges.dst` (confirmed in `schema.py:32-35`). Because we UPDATE the row (not DELETE + INSERT), the row `id` is preserved and all foreign keys remain valid. The cascade is a safety net, not a mechanism used here.

**SQL statement:** `UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?` — updates three columns. `line` and `path` are unchanged (they don't vary across kind flips).

### 4. `describe_app` Query Design

Mirror `describe_package` (queries.py:326–402) with these deltas:

- Query filters on `kind='app'` instead of `kind='package'`
- The returned dataclass `AppDescription` adds `app_kind: str` and `app_signals: list[str]` fields
- `used_by` lookup from `package` consumer nodes (same `belongs_to_domain`, entry point, test suite joins work identically because edges are keyed by node id, not by kind)
- `describe_app` looks up by URI (not by name), matching the `app:org/repo/<name>` form: `"SELECT ... FROM nodes WHERE kind='app' AND uri = ?"`. Alternatively look up by name — the planner chooses; name is simpler and consistent with `describe_package`.

**Recommended:** Look up by name for `describe_app` (same as `describe_package`) since the test suite already knows the package name. The CLI `cg describe-app <name>` takes a name positional arg mirroring `cg describe-package <name>`.

### 5. CLI Handler Scaffolding

`q_list_apps.py` — verbatim copy of `q_list_packages.py` with:
- `queries.list_packages(conn)` → `queries.list_apps(conn)`
- `"No packages in graph."` → `"No apps in graph."`
- All other boilerplate identical

`q_describe_app.py` — verbatim copy of `q_describe_package.py` with:
- `queries.describe_package(conn, name=args.name)` → `queries.describe_app(conn, name=args.name)`
- `"error: package not found:"` → `"error: app not found:"`
- Human-readable output adds `app_kind` and `app_signals` lines
- All boilerplate identical

`main.py` additions to `_SUBCOMMANDS`:
```python
from graph_io.cli import q_list_apps, q_describe_app

_SUBCOMMANDS = {
    ...
    "list-apps": q_list_apps,
    "describe-app": q_describe_app,
}
```

The `main.py` also imports the new modules — add them to the existing import block.

---

## Common Pitfalls

### Pitfall 1: `_read_package_json` `bin` gap
**What goes wrong:** `classification.classify(info, pkg_dir)` checks `info.get("bin_present")` and always gets `None` / falsy because `_read_package_json` doesn't return `bin`. JS packages with `bin` fields are silently misclassified as `Package`.
**Why it happens:** `entry_points._emit_packagejson_entries` re-reads the raw `package.json` file; `packages._read_package_json` does not expose `bin`.
**How to avoid:** Extend `_read_package_json` to extract and return `bin_present: bool` before writing `classification.py`.
**Warning signs:** Test for JS bin classification passes locally but misses in integration if you test against a re-parsed dict.

### Pitfall 2: Second `_upsert_node` inserts a duplicate row after in-place UPDATE
**What goes wrong:** After the D-06 in-place UPDATE flips the row from `kind="package"` to `kind="app"`, if `_upsert_node` is still called with the NEW GraphNode (which has `kind="app"`), it correctly finds the row because `_node_id("app", name, path)` now returns the row's id. No duplicate. BUT if the in-place UPDATE is not committed before `_upsert_node` runs, `_node_id` won't find the row and inserts a second one.
**Why it happens:** Both the UPDATE and the `upsert_records` call are inside the same transaction; SQLite reads your own uncommitted writes within a transaction, so `_node_id` will correctly find the just-updated row.
**How to avoid:** Keep both the in-place UPDATE and the subsequent `upsert_records` call within the same transaction block (they already are — the transaction wraps the full `refresh`). Do NOT wrap each manifest iteration in a nested `with conn:` block.
**Warning signs:** Duplicate rows in the nodes table (`SELECT COUNT(*) FROM nodes WHERE kind='app' AND name=?` returns 2).

### Pitfall 3: Edge direction confusion on kind-flip
**What goes wrong:** Inbound edges (other nodes pointing TO the package/app node) have `dst = old_id`. The kind-flip UPDATE preserves `id`, so `dst` still resolves. But any code that searches for edges FROM the package/app node (`src = old_id`) is also correct for the same reason. No rewrites needed.
**Why it happens:** Non-issue as long as the UPDATE is in-place and `id` doesn't change. Only becomes a problem if someone accidentally DELETEs + INSERTs.
**How to avoid:** Always use the in-place UPDATE pattern (D-06). Never `DELETE FROM nodes WHERE ... AND kind='package'` in the flip path.

### Pitfall 4: `app_uri` leaks into `attrs_json`
**What goes wrong:** `_upsert_node` pops `"uri"` from `attrs` before serializing `attrs_json` (confirmed in `upsert.py:51`). If the GraphNode is built with `"uri"` in both the `attrs` dict and separately passed, the pop handles it correctly. But tests that directly read `attrs_json` and expect `"uri"` to be absent will fail if the builder accidentally double-stores it.
**How to avoid:** Mirror the exact pattern from `packages.refresh:143–150` — `"uri": app_uri(ctx, info["name"])` inside the `attrs` dict only (upsert pops it out). Never add a separate `uri` keyword argument to `GraphNode`.
**Warning signs:** Test `test_refresh_writes_pkg_uri_on_package_nodes` already guards this for packages; add a parallel test for App nodes.

### Pitfall 5: `scripts_present` vs `scripts` dict in `_read_pyproject`
**What goes wrong:** `classification.classify` needs to know if `[project.scripts]` is non-empty. If `_read_pyproject` returns the full `scripts` dict, classification can check `bool(info["scripts"])`. If it returns `scripts_present: bool`, classification checks `info.get("scripts_present")`. Both work, but mixing them causes a `KeyError`.
**How to avoid:** Decide once in the manifest reader. `scripts_present: bool` is the minimal surface and avoids exposing the dict structure to `classification.py`. The planner should choose one shape and use it consistently.
**Warning signs:** `classify()` called with an `info` dict missing `scripts_present` silently returns no signals for Python CLI apps.

### Pitfall 6: `cg find --kind app` rejected before `_VALID_KINDS` is updated
**What goes wrong:** The `find()` function raises `ValueError` for unknown kinds. If any test calls `cg find --kind app` before `_VALID_KINDS` includes `"app"`, it gets exit code 2 from argparse validation (the `--kind` choices list in `q_find.py` derives from `_VALID_KINDS`).
**How to avoid:** Wave 1 must add `"app"` to `_VALID_KINDS` before any test exercises the kind. This is why `_VALID_KINDS` admission is in Wave 1 (foundation), not Wave 4 (queries).

### Pitfall 7: `describe_app` vs `describe_package` — edge queries filter by `p.kind='package'`
**What goes wrong:** The `describe_package` query for `used_by` consumers filters `p.kind='package'`. If App nodes are also consumers (an App that depends_on another App), this filter would miss them.
**Why it matters for Phase 50:** APP-02 says App nodes participate in all the same edges as packages. If an App's edges are emitted with `src.kind='app'`, then `used_by` queries filtering on `p.kind='package'` will miss app-level consumers.
**How to avoid:** For the `describe_app` query's `used_by` section, broaden the filter to `p.kind IN ('package', 'app')`. Note that in Phase 50, dep edges are only emitted FROM package-kind nodes (the emit loop hasn't been split); revisit if App nodes ever emit their own `used_by` edges.

---

## Code Examples

### `app_uri` in `uri.py`

```python
# Source: uri.py pattern (verified by reading the file)
def app_uri(ctx: RepoContext, name: str) -> str:
    return f"app:{ctx.org}/{ctx.repo}/{name}"
```

### `classify()` caller in `packages.refresh`

```python
# Inline after _discover_manifests loop entry (packages.py:135)
from graph_io.classification import classify
from graph_io.uri import app_uri

for pkg_dir, info in _discover_manifests(repo_root, skip_dirs):
    rel_prefix = pkg_dir.resolve().relative_to(repo_root).as_posix()
    if rel_prefix == ".":
        rel_prefix = ""

    new_kind, app_kind, app_signals = classify(info, pkg_dir)
    new_uri = (
        app_uri(ctx, info["name"]) if new_kind == "app"
        else pkg_uri(ctx, info["name"])
    )
    attrs = {
        "version": info["version"],
        "dependencies": info["dependencies"],
        "language": info["language"],
        "uri": new_uri,
    }
    if new_kind == "app":
        attrs["app_kind"] = app_kind
        attrs["app_signals"] = app_signals

    # D-06: probe for other-kind row
    other_kind = "package" if new_kind == "app" else "app"
    other_id = upsert._node_id(conn, (other_kind, info["name"], rel_prefix or None))
    if other_id is not None:
        import json as _json
        attrs_for_db = {k: v for k, v in attrs.items() if k != "uri"}
        conn.execute(
            "UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?",
            (new_kind, new_uri, _json.dumps(attrs_for_db, sort_keys=True), other_id),
        )

    nodes = [GraphNode(
        kind=new_kind,
        name=info["name"],
        path=rel_prefix or None,
        line=None,
        attrs=attrs,
    )]
    # ... edges and upsert_records call follow
```

### `describe_app` dataclass

```python
@dataclass(frozen=True)
class AppDescription:
    """Description of an `app` node."""
    name: str
    language: str
    version: str
    app_kind: str
    app_signals: list[str]
    files: list[str]
    counts: dict[str, int]
    domains: list[str] = field(default_factory=list)
    entry_points: list[EntryPointDescription] = field(default_factory=list)
    test_suites: list[SuiteDescription] = field(default_factory=list)
```

### `list_apps` query

```python
def list_apps(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all App nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "app")
```

(Single line — `_list_by_kind` is the existing helper in `queries.py:621-627`.)

---

## Runtime State Inventory

This is a greenfield phase for a new graph kind. No rename or migration of existing runtime state.

The only "runtime state" concern is existing SQLite databases (`code.db`) that currently have `kind='package'` rows for packages that should become `kind='app'`. On first run after upgrade, the D-06 in-place UPDATE handles these automatically — no data migration script, no `cg update --full` required (unlike Phase 49 D-11 which has lingering Symbol nodes). The flip is idempotent on every subsequent run.

**Nothing found in category:** "Stored data" — D-06 handles the mutation; "Live service config" — none; "OS-registered state" — none; "Secrets/env vars" — none; "Build artifacts" — none.

---

## Environment Availability

No external tools required. Pure Python stdlib + in-repo workspace packages.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11 | `tomllib`, typing | ✓ | project floor | — |
| `sqlite3` (stdlib) | DB operations | ✓ | bundled | — |
| `pathlib` (stdlib) | `index.html` check | ✓ | bundled | — |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥8.3 |
| Config file | `packages/graph-io/conftest.py` |
| Quick run command | `uv run --package graph-io pytest packages/graph-io/tests/test_classification.py -x` |
| Full suite command | `uv run --package graph-io pytest packages/graph-io/tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| APP-01 | Python `[project.scripts]` → app node with `app_kind=cli` | unit | `pytest tests/test_classification.py::test_classify_python_scripts_cli -x` | ❌ Wave 0 |
| APP-01 | JS `bin` → app node with `app_kind=cli` | unit | `pytest tests/test_classification.py::test_classify_js_bin_cli -x` | ❌ Wave 0 |
| APP-01 | JS `next` dep → app node with `app_kind=nextjs` | unit | `pytest tests/test_classification.py::test_classify_js_next -x` | ❌ Wave 0 |
| APP-01 | JS `expo` dep → app node with `app_kind=expo` | unit | `pytest tests/test_classification.py::test_classify_js_expo -x` | ❌ Wave 0 |
| APP-01 | JS `vite` + `index.html` → spa; `vite` without `index.html` → no signal | unit | `pytest tests/test_classification.py::test_classify_js_vite_spa -x` | ❌ Wave 0 |
| APP-02 | App node has same edge participation as Package (belongs_to_domain, contains) | integration | `pytest tests/test_packages.py::test_app_node_edges -x` | ❌ Wave 0 |
| APP-03 | No signals → kind="package", no app attrs | unit | `pytest tests/test_classification.py::test_classify_no_signals_stays_package -x` | ❌ Wave 0 |
| APP-03 | Multi-signal: nextjs + cli → app_kind=nextjs, app_signals sorted | unit | `pytest tests/test_classification.py::test_classify_multi_signal_precedence -x` | ❌ Wave 0 |
| APP-04 | `app_kind` in attrs_json, not a column | integration | `pytest tests/test_packages.py::test_app_kind_in_attrs_json -x` | ❌ Wave 0 |
| APP-05 | `list_apps` returns App nodes | unit | `pytest tests/test_queries.py::test_list_apps -x` | ❌ Wave 0 |
| APP-05 | `describe_app` returns AppDescription with app_kind + app_signals | unit | `pytest tests/test_queries.py::test_describe_app -x` | ❌ Wave 0 |
| APP-05 | `cg list-apps` exits 0, lists app nodes | smoke | `pytest tests/test_cli_smoke.py::test_list_apps -x` | ❌ Wave 0 |
| APP-05 | `cg describe-app <name>` exits 0, shows app_kind | smoke | `pytest tests/test_cli_smoke.py::test_describe_app -x` | ❌ Wave 0 |
| APP-06 | Kind-flip: Package→App updates uri column to `app:` prefix | integration | `pytest tests/test_packages.py::test_kind_flip_pkg_to_app -x` | ❌ Wave 0 |
| APP-06 | Kind-flip: App→Package (signal removed) reverts uri to `pkg:` prefix | integration | `pytest tests/test_packages.py::test_kind_flip_app_to_pkg -x` | ❌ Wave 0 |
| APP-06 | Kind-flip preserves inbound edge FKs (row id unchanged) | integration | `pytest tests/test_packages.py::test_kind_flip_preserves_edge_ids -x` | ❌ Wave 0 |

### Test Fixtures Needed

| Fixture | Description | For |
|---------|-------------|-----|
| `tmp_path` + `pyproject.toml` with `[project.scripts]` | Python CLI app | APP-01, APP-06 |
| `tmp_path` + `package.json` with `bin` field | JS CLI app | APP-01 |
| `tmp_path` + `package.json` with `dependencies.next` | Next.js app | APP-01 |
| `tmp_path` + `package.json` with `dependencies.vite` + `index.html` at root | SPA | APP-01 |
| `tmp_path` + `package.json` with `dependencies.vite` but NO `index.html` | SPA false-positive guard | APP-03 |
| `tmp_path` + `package.json` with `next` + `bin` | Multi-signal | APP-03 |
| DB with pre-existing `package` node; second `refresh` with scripts added | Kind-flip pkg→app | APP-06 |
| DB with pre-existing `app` node + inbound edges; third `refresh` with scripts removed | Kind-flip app→pkg, edge survival | APP-06 |

Existing `test_packages.py` fixtures (inline `tmp_path` + `conn`) are the correct pattern. No new conftest-level fixtures needed.

### Sampling Rate

- **Per task commit:** `uv run --package graph-io pytest packages/graph-io/tests/test_classification.py packages/graph-io/tests/test_packages.py -x`
- **Per wave merge:** `uv run --package graph-io pytest packages/graph-io/tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_classification.py` — 8 unit tests covering classify() for all signal types
- [ ] `tests/test_packages.py` — 3 kind-flip integration tests + 2 app-node attribute tests
- [ ] `tests/test_queries.py` — `list_apps` + `describe_app` unit tests (add to existing file)
- [ ] `tests/test_cli_smoke.py` — `test_list_apps`, `test_describe_app` (add to existing file)
- [ ] `tests/test_uri.py` — `test_app_uri` (add to existing file, mirrors existing uri tests)

---

## Security Domain

No authentication, session management, cryptography, or user input to external systems. This phase is a local filesystem scanner with SQLite persistence.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes (minimal) | `_VALID_KINDS` + `_VALID_APP_KINDS` gate at query layer |
| V6 Cryptography | no | — |

The only input validation concern: `app_kind` values written to `attrs_json`. The `_VALID_APP_KINDS` frozenset gate (Claude's Discretion) provides a Python-side check at write time — catching typos before they reach the DB. A unit test confirms the gate rejects unknown values.

---

## Open Questions (RESOLVED)

1. **`describe_app` lookup key: name vs URI**
   - What we know: `describe_package` uses name; the CONTEXT says `cg describe-app <uri>` with the URI form in the CLI description, but D-10 says "mirrors describe-package exactly."
   - What's unclear: The roadmap success criterion says `cg describe-app <uri>` (URI form), but D-10 says "mirrors exactly" (name form).
   - Recommendation: Use name for consistency with `describe_package`. If URI lookup is later needed, add a `--uri` flag.

2. **`_VALID_APP_KINDS` at write time vs query time**
   - What we know: The gate prevents `app_kind` typos. The frozenset would live in `queries.py` (consistent with `_VALID_KINDS` location).
   - What's unclear: Whether to validate at write time (in `classification.py` return) or query time (in `describe_app`).
   - Recommendation: Validate at classification return time (`classification.py` raises `ValueError` if derived `app_kind` not in frozenset). This catches bugs in the classification logic itself, not just query-layer typos.

3. **Dep accumulation: do App nodes emit `used_by` edges for their dependencies?**
   - What we know: The current emit loop only emits `used_by` edges for Python packages (lines 169–183 in `packages.py`). The loop keys on `info["language"] == "python"`.
   - What's unclear: After reclassification, the node is `kind="app"` but the `used_by` edge emission still uses `src=("package", name, path)` as the edge src key. The `_ensure_node` in `upsert._upsert_edge` will find the now-`app`-kind row by (app, name, path) which is correct. But `describe_dependency` queries filter by `p.kind='package'` — App consumers of a dependency won't show up there.
   - Recommendation: In Phase 50, emit dep `used_by` edges for both Python and JS packages (App or Package) using the actual kind of the node. Add `p.kind IN ('package','app')` to `describe_dependency`'s `used_by` query. Flag this as a known deviation from Phase 43 behavior.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `kind` hard-coded to `"package"` in emit loop | `classify()` determines kind dynamically | Phase 50 | Packages with app signals become `kind='app'` |
| URI always `pkg:org/repo/name` | URI reflects kind: `app:org/repo/name` for apps | Phase 50 | Kind-flip also flips URI |
| No kind-level app distinction | `App` is a first-class kind in `_VALID_KINDS` | Phase 50 | Queries, CLI, wiki rendering can treat apps distinctly |

**No deprecated patterns to remove in Phase 50.** `package_family_uri` in `uri.py` is deferred to Phase 51.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_upsert_node` correctly finds a row after an in-place UPDATE of its `kind` column within the same transaction (SQLite reads own uncommitted writes) | Pitfall 2 | Duplicate rows inserted; DB inconsistency |
| A2 | The `describe_package` JOIN queries (entry_points, test_suites, domains) work unchanged when `kind='app'` because those edges are keyed by node id, not by kind | Code Examples | Missing data in `describe_app` output |
| A3 | `dependencies.next` in `package.json` is a reliable Next.js signal (not a different package named `next`) | classification.py | False-positive nextjs classification |
| A4 | `mypkg` fixture already has `[project.scripts]` (confirmed in test fixture read) — Phase 50 can reuse this fixture for APP-01 integration test | Test fixtures | Missing real-world fixture; tests use artificial data only |
| A5 | `cg describe-app` takes a `name` positional arg (not a URI), mirroring `describe_package` | CLI handlers | CLI UX mismatch with roadmap success criterion wording |

---

## Sources

### Primary (HIGH confidence)

- Codebase: `packages/graph-io/src/graph_io/packages.py` — manifest readers, emit loop, dep accumulator — read directly
- Codebase: `packages/graph-io/src/graph_io/upsert.py` — `_node_id`, `_upsert_node`, `_upsert_edge` — read directly
- Codebase: `packages/graph-io/src/graph_io/queries.py` — `_VALID_KINDS`, `describe_package`, `list_packages`, `_list_by_kind` — read directly
- Codebase: `packages/graph-io/src/graph_io/uri.py` — URI builder patterns — read directly
- Codebase: `packages/graph-io/src/graph_io/schema.py` — `SCHEMA_VERSION=2`, DDL (ON DELETE CASCADE confirmed) — read directly
- Codebase: `packages/graph-io/src/graph_io/cli/q_list_packages.py` — CLI handler template — read directly
- Codebase: `packages/graph-io/src/graph_io/cli/q_describe_package.py` — CLI describe template — read directly
- Codebase: `packages/graph-io/src/graph_io/cli/main.py` — `_SUBCOMMANDS` registration — read directly
- Codebase: `packages/graph-io/src/graph_io/entry_points.py:352-369` — bin parsing pattern — read directly
- Codebase: `packages/graph-io/tests/test_packages.py` — existing test patterns and fixtures — read directly
- Codebase: `packages/graph-io/tests/fixtures/sample_monorepo/packages/mypkg/pyproject.toml` — confirmed `[project.scripts]` present in mypkg fixture
- Codebase: `.planning/phases/50-app-reclassification-graph-io/50-CONTEXT.md` — all locked decisions
- Codebase: `.planning/phases/49-builtin-kind-graph-io/49-CONTEXT.md` — Phase 49 conventions D-10/D-12/D-13/D-14/D-15

### Secondary (MEDIUM confidence)

- Phase 49 CONTEXT.md D-12/D-13 — CLI mirror pattern (Phase 49 is planned, not yet executed — conventions inferred from decisions, not from completed code)

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — no new packages; all dependencies directly read from existing code
- Architecture: HIGH — emit loop, upsert helpers, CLI handlers all directly read
- Pitfalls: HIGH — identified from direct code reading (manifest reader gap is a confirmed current limitation)
- Kind-flip SQL: HIGH — schema DDL read; `_node_id` implementation read; transaction boundary read

**Research date:** 2026-05-27
**Valid until:** 2026-06-27 (stable codebase; 30-day horizon)
