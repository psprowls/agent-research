# Phase 43 — Pattern Map

Concrete code analogs for files Phase 43 creates or modifies. Each entry pairs a target file with the closest existing pattern in the codebase plus the load-bearing code excerpt the executor should replicate.

---

## Targets

### 1. `packages/graph-io/src/graph_io/queries.py` — add 4 helpers + 2 dataclasses + 2 kinds

**Analog:** `describe_package`, `describe_test_suite`, `list_packages`, `_list_by_kind`, `PackageDescription` dataclass — same file, already established.

**Pattern (existing):**

```python
# queries.py:9-22  (current _VALID_KINDS)
_VALID_KINDS = frozenset(
    {
        "function", "class", "method", "file", "package",
        "repository", "subpackage", "entry_point", "test_suite", "domain",
    }
)

# queries.py:103-112 (dataclass shape)
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

# queries.py:522-528 (list_by_kind pattern)
def _list_by_kind(conn: sqlite3.Connection, kind: str) -> list[NodeRecord]:
    rows = conn.execute(
        "SELECT kind, name, path, line, attrs_json FROM nodes "
        "WHERE kind = ? ORDER BY name", (kind,),
    ).fetchall()
    return [_row_to_node(r) for r in rows]

def list_packages(conn: sqlite3.Connection) -> list[NodeRecord]:
    return _list_by_kind(conn, "package")
```

**Phase 43 target:** Add `dependency` and `plugin` to `_VALID_KINDS`, add `DependencyDescription` (fields: `ecosystem: str`, `name: str`, `uri: str`, `versions_in_use: list[str]`, `used_by: list[str]`) and `PluginDescription` (fields: `name: str`, `uri: str`, `ecosystem: str`), and add `describe_dependency(conn, *, ecosystem, name)`, `list_dependencies(conn)`, `describe_plugin(conn, *, name)`, `list_plugins(conn)` mirroring the existing pattern.

---

### 2. `packages/graph-io/src/graph_io/packages.py` — extend `refresh` with dependency ingestion

**Analog:** Existing `refresh()` function in same file — already parses pyproject.toml and emits `package` nodes + `contains` edges.

**Pattern (existing):**

```python
# packages.py:23-39  (_read_pyproject extracts dependencies list)
def _read_pyproject(path: Path) -> dict[str, Any] | None:
    with path.open("rb") as f:
        data = tomllib.load(f)
    project = data.get("project") or {}
    name = project.get("name")
    if not name:
        return None
    return {
        "name": name,
        "version": project.get("version", ""),
        "dependencies": list(project.get("dependencies", [])),
        "language": "python",
    }

# packages.py:107-132  (refresh loop emitting Package nodes + contains edges)
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
        edges.append(GraphEdge(
            src=("package", info["name"], rel_prefix or None),
            dst=("file", file_path, file_path),
            kind="contains",
            attrs={},
        ))
    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
```

**Phase 43 target:** Extend `_read_pyproject` to also extract `[dependency-groups]` entries (PEP 735). In `refresh`, after the existing per-package emission, accumulate a `dict[(ecosystem, name)] -> {"versions_in_use": set, "used_by": set}` across all discovered manifests, then emit one `dependency` node per pair plus `used_by` edges. Helper: `_extract_dep_name(pep508_str) -> str` (regex `^[A-Za-z0-9_.-]+`).

---

### 3. `packages/graph-io/src/graph_io/plugins.py` — NEW module

**Analog:** Existing tiny graph-io modules — `domains.py`, `entry_points.py`, `test_suites.py` — each provides an `emit(conn, *, ...)` function that reads source data and calls `upsert.upsert_records`.

**Pattern (existing — `domains.py` shape):**

```python
def emit(conn: sqlite3.Connection, *, repo_root: Path, ctx: RepoContext, ...) -> None:
    """One-line summary."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    # read source data ...
    # build nodes ...
    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
```

**Phase 43 target:** New `plugins.py` with `emit(conn, *, workspace_root, ctx)` that calls `workspace_io.manifest.read(workspace_root / ".graph-wiki.yaml")`, iterates `manifest.get("plugins", [])`, and emits one `plugin` node per entry with `name`, `attrs={"uri": plugin_uri(name), "ecosystem": "claude-code", "installed_version": ..., "applied_version": ...}`. No edges in v1.8 (D-03).

---

### 4. `packages/graph-io/src/graph_io/structural_nodes.py` — folded subpackage bug fix

**Analog:** Existing `_walk_subpackages` function in the same file.

**Pattern (existing):**

```python
# structural_nodes.py:326-350
def _walk_subpackages(
    import_root: Path, skip_dirs: frozenset[str], repo_root: Path
) -> Iterator[Path]:
    """Yield each __init__.py-containing subdirectory under import_root.

    Includes import_root itself. Honors skip_dirs via _ignore.should_skip.
    Does not follow symlinks (os.walk default).
    """
    if not (import_root / "__init__.py").exists():
        return
    for dirpath, dirnames, filenames in os.walk(import_root, followlinks=False):
        d = Path(dirpath)
        dirnames[:] = [
            name for name in dirnames
            if not _ignore.should_skip(name, skip_dirs)
        ]
        if "__init__.py" in filenames:
            try:
                rel = d.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            if _ignore.should_skip(rel, skip_dirs):
                continue
            yield d
```

**Phase 43 target:** Update the docstring and yield logic so the import root itself is NOT yielded (`if d == import_root: continue` after the `_init_.py` check). Then update the docstring: "Yield each `__init__.py`-containing subdirectory STRICTLY UNDER `import_root` (excluding `import_root` itself)." Add regression test `test_no_subpackage_node_at_import_root`.

---

### 5. `packages/wiki-io/src/wiki_io/entity_writer.py` — extend with Wave 2 implementation

**Analog A (frontmatter round-trip):** `update_tokens.py:110-195` — read with `frontmatter.loads`, modify, write back.

**Pattern (existing — `update_tokens.py:110-114`):**

```python
try:
    raw = path.read_text(encoding="utf-8")
    post = frontmatter.loads(raw)
except Exception as exc:
    print(f"[warn] skipping {path}: {exc}", file=sys.stderr)
    return ("skipped", 0)
```

**Phase 43 target:** Use the same `frontmatter.loads` + `post.metadata` accessor pattern in `write_entities` when reading existing entity pages. On parse failure, catch the exception and append to `EntityWriteResult.errors` rather than skipping silently (D-21).

**Analog B (deterministic write-if-changed):** `update_tokens.py:155-195` — "existing value already matches → unchanged; else write."

**Pattern (existing — `update_tokens.py:166-167`):**

```python
if existing_value == count:
    return ("unchanged", count)
```

**Phase 43 target:** D-15 write-if-changed: render new content to a string buffer; if `path.exists() and path.read_bytes() == new_content.encode("utf-8")`, mark URI as `unchanged` and skip the write.

**Analog C (JSONL append-log):** v1.7 trace JSONL convention (per CLAUDE.md and arch.md). No exact in-tree analog for append-only JSONL — closest is `wiki_io.append_log.append_log` (different format but same "open in `'a'` mode, write one line, close" idiom).

**Pattern (existing — `append_log.py:102-104`):**

```python
with log_path.open("a", encoding="utf-8") as f:
    f.write(entry_text)
```

**Phase 43 target:** `_append_deletion(log_path, record)` opens in `"a"` mode and writes `json.dumps(record, separators=(",", ":")) + "\n"`. Before the open, call `_rotate_deletions_log(log_path)` which does `if log_path.exists() and log_path.stat().st_size >= 10_000_000: log_path.rename(log_path.with_suffix(".log.1"))` (overwriting any prior `.log.1`).

**Analog D (POSIX advisory lock):** No existing in-tree analog. Pattern is stdlib boilerplate.

**Phase 43 target (write from scratch — D-19):**

```python
from contextlib import contextmanager
import fcntl, os
from pathlib import Path
from typing import Iterator

class WriteLockHeldError(RuntimeError):
    pass

@contextmanager
def _acquire_scan_lock(workspace_root: Path) -> Iterator[None]:
    lock_path = workspace_root / ".graph-wiki" / "scan.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WriteLockHeldError(
                f"another scan in progress for this workspace: {workspace_root}"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
```

**Analog E (dataclass result-bag with per-state lists):** `update_tokens.py:204-222` returns `dict[str, list[str]]` with "updated/unchanged/skipped" buckets.

**Pattern (existing — `update_tokens.py:204-222`):**

```python
result: dict[str, list[str]] = {"updated": [], "unchanged": [], "skipped": []}
# ... populate ...
for bucket in result.values():
    bucket.sort()
return result
```

**Phase 43 target:** Same shape but as a frozen dataclass per D-09:

```python
@dataclass(frozen=True)
class EntityWriteError:
    uri: str
    slug: str
    exception: str  # repr of the caught exception

@dataclass(frozen=True)
class EntityWriteResult:
    created: list[str]
    updated: list[str]
    deleted: list[str]
    unchanged: list[str]
    needs_narrative: set[str]
    errors: list[EntityWriteError]
```

**Analog F (graph read in wiki-io):** None directly — wiki-io currently does not read `graph-io`. But `graph_io.queries` is the read-only surface. Open the conn with `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)`; we don't need this in `write_entities` because the caller (Phase 45 `run_scan`) passes the `conn` in.

---

### 6. `packages/wiki-io/tests/test_entity_writer.py` — extend with Wave 2 unit tests + Hypothesis property tests

**Analog:** Phase 42 Plan 01 creates this file with Hypothesis-driven encode/decode tests already. Phase 43 extends it.

**Pattern (Phase 42 Plan 01's pattern, expected after Phase 42 ships):**

```python
from hypothesis import given, strategies as st, settings

@given(uri=admitted_uri_strategy())
@settings(max_examples=1000)
def test_slug_round_trip(uri):
    assert decode_slug(encode_slug(uri)) == uri
```

**Phase 43 target additions:**

```python
@given(
    existing=st.dictionaries(...),  # include both whitelist + human keys
    scanner=st.dictionaries(...),   # whitelist keys only
)
def test_merge_preserves_non_whitelist_keys(existing, scanner):
    out = merge_frontmatter(existing, scanner)
    for k, v in existing.items():
        if k not in SCANNER_OWNED_KEYS:
            assert k in out and out[k] == v

def test_scan_lock_raises_on_contention(tmp_path):
    with _acquire_scan_lock(tmp_path):
        with pytest.raises(WriteLockHeldError):
            with _acquire_scan_lock(tmp_path):
                pass
```

---

### 7. `packages/wiki-io/tests/integration/test_entity_writer_integration.py` — NEW integration file

**Analog:** `packages/wiki-io/tests/integration/` — directory exists; check `test_bootstrap_e2e_no_broken_links.py` for the e2e style.

**Phase 43 target:** Build a temp workspace (or use `agent-research` itself), run `graph-io` ingestion (Wave 1's code), then run `write_entities` into a temp wiki directory, then assert against the on-disk state.

Helper fixture shape:

```python
@pytest.fixture
def real_graph_and_wiki(tmp_path):
    """Build a real workspace fixture, ingest with graph-io, return (conn, wiki_root)."""
    # ... copy a minimal pyproject.toml fixture; run packages.refresh + plugins.emit
    # ... return sqlite3.connect(...) + tmp_path/"wiki"
```

---

### 8. `packages/graph-io/src/graph_io/update.py` — wire `plugins.emit` into the pipeline

**Analog:** Existing `update.py` calls `packages.refresh`, `structural_nodes.emit`, `entry_points.emit`, `test_suites.emit`, `domains.emit` in order.

**Phase 43 target:** Add one call after `structural_nodes.emit` (or after `packages.refresh`):

```python
plugins.emit(conn, workspace_root=workspace_root, ctx=ctx)
```

Requires `workspace_root` to be available in `update.py`'s call site — already is via the existing argument plumbing.

---

## Cross-Cutting Patterns

### Pattern: `upsert.upsert_records(conn, GraphRecords(nodes=..., edges=...))`

**Used by every wave-1 graph-io ingestion module.** Wave 1 code MUST go through `upsert.upsert_records` — direct `INSERT` SQL bypasses ID resolution and `ON CONFLICT` handling.

### Pattern: `_VALID_KINDS` enforcement at query boundary

`queries.find` raises `ValueError` when `kind` is not in `_VALID_KINDS`. Wave 1's addition of `dependency`/`plugin` to `_VALID_KINDS` automatically extends acceptance for these kinds in `find`, `describe_*`, etc. Tests must assert this gates correctly.

### Pattern: Frozen dataclasses for projections

`PackageDescription`, `RepoDescription`, etc. all use `@dataclass(frozen=True)`. Wave 1's new `DependencyDescription` and `PluginDescription` follow the same pattern. Wave 2's `EntityWriteResult` and `EntityWriteError` do too.

### Pattern: Tests use `sqlite3.connect(":memory:")` + `schema.create_schema(conn)`

graph-io's existing test files (`test_queries.py`, `test_packages.py`) build in-memory DBs in `conftest.py`. Wave 1 tests reuse this pattern; Wave 2 mock-graph tests use a `MockGraphConn` (not a real sqlite conn) for unit speed.

---

## PATTERN MAPPING COMPLETE
