# Phase 50: App Reclassification (graph-io) - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 10 (6 new, 4 modified)
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `packages/graph-io/src/graph_io/classification.py` | utility (pure function) | transform | `packages/graph-io/src/graph_io/builtins.py` (signal detection logic) | role-match |
| `packages/graph-io/src/graph_io/packages.py` | scanner/service | CRUD + file-I/O | itself (existing) | exact — surgical modification |
| `packages/graph-io/src/graph_io/uri.py` | utility | transform | itself (existing) | exact — one-line addition |
| `packages/graph-io/src/graph_io/queries.py` | repository | CRUD | itself (existing `describe_package`, `list_packages`) | exact — mirror additions |
| `packages/graph-io/src/graph_io/cli/q_list_apps.py` | CLI handler | request-response | `packages/graph-io/src/graph_io/cli/q_list_builtins.py` | exact |
| `packages/graph-io/src/graph_io/cli/q_describe_app.py` | CLI handler | request-response | `packages/graph-io/src/graph_io/cli/q_describe_package.py` | exact |
| `packages/graph-io/src/graph_io/cli/main.py` | CLI registration | — | itself (existing) | exact — two-entry addition |
| `packages/graph-io/tests/test_classification.py` | test (unit) | — | `packages/graph-io/tests/test_builtins.py` | role-match |
| `packages/graph-io/tests/test_packages.py` | test (integration) | — | itself (existing) | exact — add tests to existing file |
| `packages/graph-io/tests/test_cli_smoke.py` | test (smoke/CLI) | — | itself (lines 196–253, builtin smoke pattern) | exact — mirror pattern |

---

## Pattern Assignments

### `packages/graph-io/src/graph_io/classification.py` (utility, transform)

**Analog:** No existing pure-classification module, but `builtins.py` provides the nearest pattern: a module that takes raw data (import names) and emits a classification result, then `packages.py` consumes it. The RESEARCH.md provides the complete implementation as a verified code example.

**Imports pattern** (use this header block):
```python
"""Pure app-signal classification for manifest info dicts."""
from __future__ import annotations
from pathlib import Path
```

**Core pattern** — the complete function (from RESEARCH.md §2, verified against codebase):
```python
_FRAMEWORK_PRECEDENCE = ("nextjs", "expo", "spa")

def classify(
    info: dict,
    pkg_dir: Path,
) -> tuple[str, str | None, list[str]]:
    """Return (kind, app_kind, app_signals) for a manifest info dict.

    kind in {"package", "app"}; app_kind is None when kind="package".
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

    app_kind: str = "cli"
    for framework in _FRAMEWORK_PRECEDENCE:
        if framework in signals:
            app_kind = framework
            break

    return "app", app_kind, signals
```

**No error handling needed** — pure function, no I/O, no exceptions to catch.

---

### `packages/graph-io/src/graph_io/packages.py` — `_read_pyproject` extension (lines 45–68)

**Analog:** Itself. Surgical addition of `scripts_present` field.

**Current return dict** (lines 62–68):
```python
return {
    "name": name,
    "version": project.get("version", ""),
    "dependencies": list(project.get("dependencies", [])),
    "dep_groups": dep_groups,
    "language": "python",
}
```

**Modified return dict** — add one field:
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

---

### `packages/graph-io/src/graph_io/packages.py` — `_read_package_json` extension (lines 71–87)

**Analog:** Itself. Surgical addition of `bin_present` field.

**Current return dict** (lines 80–87):
```python
deps = data.get("dependencies") or {}
return {
    "name": name,
    "version": data.get("version", ""),
    "dependencies": sorted(deps.keys()) if isinstance(deps, dict) else list(deps),
    "language": "javascript",
}
```

**Modified return dict** — extract bin before return:
```python
deps = data.get("dependencies") or {}
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

---

### `packages/graph-io/src/graph_io/packages.py` — `refresh` emit loop (lines 135–164)

**Analog:** Itself (current hard-coded `kind="package"` emit). The D-06 kind-flip pattern has no prior analog — the RESEARCH.md §3 provides the authoritative pattern.

**Current emit loop** (lines 135–164) — the section to replace:
```python
for pkg_dir, info in _discover_manifests(repo_root, skip_dirs):
    rel_prefix = pkg_dir.resolve().relative_to(repo_root).as_posix()
    if rel_prefix == ".":
        rel_prefix = ""
    nodes = [
        GraphNode(
            kind="package",
            name=info["name"],
            path=rel_prefix or None,
            line=None,
            attrs={
                "version": info["version"],
                "dependencies": info["dependencies"],
                "language": info["language"],
                "uri": pkg_uri(ctx, info["name"]),
            },
        )
    ]
    edges = []
    prefix = f"{rel_prefix}/" if rel_prefix else ""
    for file_path in _file_nodes_under(conn, prefix):
        edges.append(
            GraphEdge(
                src=("package", info["name"], rel_prefix or None),
                dst=("file", file_path, file_path),
                kind="contains",
                attrs={},
            )
        )
    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
```

**Replacement pattern** (from RESEARCH.md §3, incorporating D-04/D-06/D-07):
```python
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

    # D-06: probe for other-kind row and mutate in-place to preserve row id
    other_kind = "package" if new_kind == "app" else "app"
    other_id = upsert._node_id(conn, (other_kind, info["name"], rel_prefix or None))
    if other_id is not None:
        attrs_for_db = {k: v for k, v in attrs.items() if k != "uri"}
        conn.execute(
            "UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?",
            (new_kind, new_uri, json.dumps(attrs_for_db, sort_keys=True), other_id),
        )

    nodes = [GraphNode(
        kind=new_kind,
        name=info["name"],
        path=rel_prefix or None,
        line=None,
        attrs=attrs,
    )]
    edges = []
    prefix = f"{rel_prefix}/" if rel_prefix else ""
    for file_path in _file_nodes_under(conn, prefix):
        edges.append(
            GraphEdge(
                src=(new_kind, info["name"], rel_prefix or None),
                dst=("file", file_path, file_path),
                kind="contains",
                attrs={},
            )
        )
    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
```

**Key:** The `used_by` dep-edge emission block below the loop (lines 166–219) uses `src=("package", consumer_name, consumer_rel_path)` — this will need to use `new_kind` instead of the hard-coded `"package"` string so App nodes emit their dep edges correctly.

---

### `packages/graph-io/src/graph_io/uri.py` (utility, transform)

**Analog:** Itself. `pkg_uri` is the one-line template.

**Existing pattern** (`uri.py` lines 19–20):
```python
def pkg_uri(ctx: RepoContext, name: str) -> str:
    return f"pkg:{ctx.org}/{ctx.repo}/{name}"
```

**New function to add** (after `pkg_uri`, before `subpkg_uri`):
```python
def app_uri(ctx: RepoContext, name: str) -> str:
    return f"app:{ctx.org}/{ctx.repo}/{name}"
```

---

### `packages/graph-io/src/graph_io/queries.py` — `_VALID_KINDS` (line 9)

**Analog:** Itself. Phase 49 established the pattern: add one string to the frozenset plus a comment.

**Current frozenset** (lines 9–27):
```python
_VALID_KINDS = frozenset(
    {
        ...
        # Phase 49 D-14: stdlib module imports
        "builtin",
    }
)
```

**Addition** — append inside the frozenset:
```python
        # Phase 50 D-12: app-classified packages (scanner-derived kind)
        "app",
```

**Optional `_VALID_APP_KINDS`** (Claude's Discretion — default yes, add after `_VALID_KINDS`):
```python
_VALID_APP_KINDS = frozenset({"cli", "expo", "nextjs", "spa"})
```

---

### `packages/graph-io/src/graph_io/queries.py` — `AppDescription` dataclass

**Analog:** `PackageDescription` (lines 108–117) and `BuiltinDescription` (lines 138–144).

**`PackageDescription`** (lines 108–117):
```python
@dataclass(frozen=True)
class PackageDescription:
    name: str
    language: str
    version: str
    files: list[str]
    counts: dict[str, int]
    domains: list[str] = field(default_factory=list)
    entry_points: list[EntryPointDescription] = field(default_factory=list)
    test_suites: list[SuiteDescription] = field(default_factory=list)
```

**New `AppDescription`** — mirrors PackageDescription, adds `app_kind`/`app_signals`:
```python
@dataclass(frozen=True)
class AppDescription:
    """Description of an `app` node (Phase 50 APP-04 / APP-05)."""
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

---

### `packages/graph-io/src/graph_io/queries.py` — `list_apps` + `describe_app`

**Analog:** `list_builtins` (line 708–710) and `describe_package` (lines 337–413).

**`list_apps`** (mirror of `list_builtins` at lines 708–710):
```python
def list_apps(conn: sqlite3.Connection) -> list[NodeRecord]:
    """List all App nodes alphabetically. `conn` must be read-only."""
    return _list_by_kind(conn, "app")
```

**`describe_app`** — mirrors `describe_package` with these substitutions:
- `kind='package'` → `kind='app'` in all SQL filters
- Return type `PackageDescription` → `AppDescription`
- Add `app_kind` and `app_signals` pulled from `attrs_json`
- `used_by` filter for consumers: broaden to `p.kind IN ('package', 'app')` (RESEARCH.md Pitfall 7)

Core SQL lookup pattern (copy from `describe_package` lines 337–344):
```python
def describe_app(conn: sqlite3.Connection, *, name: str) -> AppDescription | None:
    pkg = conn.execute(
        "SELECT attrs_json FROM nodes WHERE kind='app' AND name = ?",
        (name,),
    ).fetchone()
    if not pkg:
        return None
    attrs = json.loads(pkg[0]) if pkg[0] else {}
    # ... files, counts, domains, entry_points, test_suites queries identical
    # but with kind='app' substituted for kind='package' in JOIN conditions
    return AppDescription(
        name=name,
        language=attrs.get("language", ""),
        version=attrs.get("version", ""),
        app_kind=attrs.get("app_kind", ""),
        app_signals=attrs.get("app_signals", []),
        files=file_paths,
        counts=counts,
        domains=domain_names,
        entry_points=entry_points,
        test_suites=test_suites,
    )
```

---

### `packages/graph-io/src/graph_io/cli/q_list_apps.py` (CLI handler, request-response)

**Analog:** `q_list_builtins.py` — exact copy with two substitutions.

**Full file** (`q_list_builtins.py` is 45 lines, verbatim source):
```python
"""cg list-apps — list all App nodes alphabetically."""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def run(args: argparse.Namespace) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        records = queries.list_apps(conn)       # <- changed from list_builtins
    finally:
        conn.close()
    if not records:
        if args.fmt == "json":
            print("[]")
        else:
            print("No apps in graph.", file=sys.stderr)  # <- changed message
        return exit_codes.SUCCESS
    if args.fmt == "json":
        print(_json.dumps([dataclasses.asdict(r) for r in records], default=str))
    else:
        for r in records:
            print(r.name)
    return exit_codes.SUCCESS
```

---

### `packages/graph-io/src/graph_io/cli/q_describe_app.py` (CLI handler, request-response)

**Analog:** `q_describe_package.py` — copy with substitutions for app-specific fields.

**Full file** (`q_describe_package.py` is 45 lines, with additions for app_kind/app_signals):
```python
"""cg describe-app <name>"""

from __future__ import annotations

import argparse
import dataclasses
import json as _json
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, queries, store


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name")


def run(args: argparse.Namespace) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.read_only_connect(db)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        desc = queries.describe_app(conn, name=args.name)  # <- changed
    finally:
        conn.close()
    if desc is None:
        print(f"error: app not found: {args.name}", file=sys.stderr)  # <- changed
        return exit_codes.GENERIC
    if args.fmt == "json":
        print(_json.dumps(dataclasses.asdict(desc), default=str))
    else:
        print(f"app:      {desc.name}")
        print(f"language: {desc.language}")
        print(f"version:  {desc.version}")
        print(f"app_kind: {desc.app_kind}")
        print(f"signals:  {desc.app_signals}")   # <- new lines
        print(f"files:    {len(desc.files)}")
        print(f"counts:   {desc.counts}")
    return exit_codes.SUCCESS
```

---

### `packages/graph-io/src/graph_io/cli/main.py` — registration

**Analog:** Itself (lines 1–77). Two entries in the import block and `_SUBCOMMANDS` dict.

**Import block addition** (after line 43, before `_SUBCOMMANDS`):
```python
from graph_io.cli import (
    ...
    q_describe_app,    # NEW
    q_list_apps,       # NEW
    ...
)
```

**`_SUBCOMMANDS` additions** (after `"list-builtins": q_list_builtins` entry):
```python
    "list-apps": q_list_apps,
    "describe-app": q_describe_app,
```

---

## Test Patterns

### `packages/graph-io/tests/test_classification.py` (new unit test file)

**Analog:** `test_builtins.py` for structure; `test_packages.py` for fixture pattern.

**File header and fixture pattern** (copy from `test_packages.py` lines 1–35):
```python
"""Unit tests for graph_io.classification — pure classify() function."""

from __future__ import annotations

from pathlib import Path

import pytest

from graph_io.classification import classify


def test_classify_no_signals_stays_package(tmp_path: Path) -> None:
    info = {"language": "python", "scripts_present": False}
    kind, app_kind, signals = classify(info, tmp_path)
    assert kind == "package"
    assert app_kind is None
    assert signals == []


def test_classify_python_scripts_cli(tmp_path: Path) -> None:
    info = {"language": "python", "scripts_present": True}
    kind, app_kind, signals = classify(info, tmp_path)
    assert kind == "app"
    assert app_kind == "cli"
    assert signals == ["cli"]
```

**`tmp_path` is the pytest builtin fixture** — no custom conftest setup needed for pure function tests. For `index.html` check tests, write the file to `tmp_path` before calling `classify`.

---

### `packages/graph-io/tests/test_packages.py` — kind-flip integration tests

**Analog:** Itself (existing `test_refresh_pyproject` at lines 37–54). The `conn` fixture (lines 19–24) and `_seed_file_node` helper (lines 27–34) are reused without modification.

**Integration test pattern for kind-flip** (copy `test_refresh_pyproject` structure, add second refresh):
```python
def test_kind_flip_pkg_to_app(tmp_path: Path, conn: sqlite3.Connection) -> None:
    pkg_dir = tmp_path / "myapp"
    pkg_dir.mkdir(parents=True)
    # First run: no scripts → kind=package
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    row = conn.execute("SELECT kind, id FROM nodes WHERE name='myapp'").fetchone()
    assert row[0] == "package"
    original_id = row[1]

    # Second run: add [project.scripts] → kind flips to app
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "myapp"\nversion = "0.1.0"\n'
        '[project.scripts]\nmyapp = "myapp:main"\n'
    )
    packages.refresh(conn, repo_root=tmp_path, ctx=_CTX)
    row = conn.execute("SELECT kind, uri, id FROM nodes WHERE name='myapp'").fetchone()
    assert row[0] == "app"
    assert row[1].startswith("app:")
    assert row[2] == original_id  # id preserved → edge FKs intact
```

---

### `packages/graph-io/tests/test_cli_smoke.py` — list-apps / describe-app smoke

**Analog:** Lines 196–253 (`test_cg_list_builtins_smoke` / `test_cg_list_builtins_empty`). The `_cg` helper (lines 15–18) and `populated_repo` fixture (lines 22–39) are reused.

**Fixture for app smoke tests** (mirrors `builtin_repo` at lines 199–213):
```python
@pytest.fixture()
def app_repo(tmp_path: Path) -> Path:
    """A git repo with a Python CLI app; returns repo root after update."""
    init_repo(tmp_path)
    write_and_commit(
        tmp_path,
        {
            "pyproject.toml": (
                '[project]\nname = "myapp"\nversion = "0.1.0"\n'
                '[project.scripts]\nmyapp = "myapp:main"\n'
            ),
        },
        "init",
    )
    res = _cg(["update", "--full"], tmp_path)
    assert res.returncode == 0, res.stderr
    return tmp_path


def test_cg_list_apps_smoke(app_repo: Path) -> None:
    res = _cg(["list-apps"], app_repo)
    assert res.returncode == 0, res.stderr
    assert "myapp" in res.stdout.splitlines()


def test_cg_list_apps_json(app_repo: Path) -> None:
    res = _cg(["--fmt", "json", "list-apps"], app_repo)
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert all(r["kind"] == "app" for r in data)
```

---

## Shared Patterns

### DB Connection Management
**Source:** `packages/graph-io/src/graph_io/cli/q_list_packages.py` lines 20–32
**Apply to:** Both new CLI handler files (`q_list_apps.py`, `q_describe_app.py`)
```python
db = graph_dir(args.workspace) / "code.db"
try:
    conn = store.read_only_connect(db)
except store.GraphNotInitializedError as exc:
    print(f"error: {exc}", file=sys.stderr)
    return exit_codes.NOT_INITIALIZED
except store.SchemaMismatchError as exc:
    print(f"error: {exc}", file=sys.stderr)
    return exit_codes.SCHEMA_MISMATCH
try:
    records = queries.list_apps(conn)
finally:
    conn.close()
```

### attrs_json Pop Convention
**Source:** `packages/graph-io/src/graph_io/upsert.py` lines 48–59
**Apply to:** `packages.py` emit loop (D-06 UPDATE) and `GraphNode` construction
```python
def _upsert_node(conn: sqlite3.Connection, node: GraphNode) -> int:
    key: NodeKey = (node.kind, node.name, node.path)
    attrs_for_json = dict(node.attrs)
    uri_value = attrs_for_json.pop("uri", None)   # uri is stored in the column, not attrs_json
    ...
```
The `"uri"` key in `attrs` dict is popped by `_upsert_node` before serializing to `attrs_json`. For the D-06 UPDATE, manually exclude `"uri"` from the attrs dict passed to `json.dumps`:
```python
attrs_for_db = {k: v for k, v in attrs.items() if k != "uri"}
conn.execute(
    "UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?",
    (new_kind, new_uri, json.dumps(attrs_for_db, sort_keys=True), other_id),
)
```

### `_node_id` lookup for kind-flip probe
**Source:** `packages/graph-io/src/graph_io/upsert.py` lines 18–30
**Apply to:** `packages.py` D-06 flip detection
```python
def _node_id(conn: sqlite3.Connection, key: NodeKey) -> int | None:
    kind, name, path = key
    if path is None:
        row = conn.execute(
            "SELECT id FROM nodes WHERE kind=? AND name=? AND path IS NULL",
            (kind, name),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM nodes WHERE kind=? AND name=? AND path=?",
            (kind, name, path),
        ).fetchone()
    return row[0] if row else None
```
Call as `upsert._node_id(conn, ("package", info["name"], rel_prefix or None))` — handles the `path IS NULL` branch automatically.

### Exit codes
**Source:** `packages/graph-io/src/graph_io/exit_codes.py`
**Apply to:** Both new CLI handlers
```python
from graph_io import exit_codes
# SUCCESS = 0, GENERIC = 1, NOT_INITIALIZED, SCHEMA_MISMATCH are the values in use
```

---

## No Analog Found

All files have close analogs. No files require falling back to RESEARCH.md-only patterns.

| File | Note |
|------|------|
| `classification.py` | New module with no prior classification analog, but RESEARCH.md §2 provides the complete verified implementation. The FRAMEWORK_PRECEDENCE tuple pattern and signal-list approach are novel to this codebase. |

---

## Metadata

**Analog search scope:** `packages/graph-io/src/graph_io/`, `packages/graph-io/src/graph_io/cli/`, `packages/graph-io/tests/`
**Files scanned:** 14 source files read directly
**Pattern extraction date:** 2026-05-27
