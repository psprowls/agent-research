# Phase 40 — Pattern Map

Each file Phase 40 creates or modifies, with the closest existing analog and a concrete excerpt to mirror.

---

## Modified: `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py`

**Role:** Command module. Async entry point invoked from CLI and MCP server.
**Closest analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` (Phase 39 ships the closely-parallel graph-consultation pattern).

### Excerpt — graph-conn lifetime pattern (from Phase 39's plan, target shape)

```python
# After resolve_wiki_and_repo and BEFORE the LLM call:
conn = None
try:
    db_path = graph_dir(workspace) / "code.db"
    try:
        conn = read_only_connect(db_path)
    except GraphNotInitializedError:
        sys.stderr.write(
            "error: graph-io not initialized for this workspace. "
            "Run 'graph-wiki-agent graph build' (or 'cg update') to initialize, then retry.\n"
        )
        raise typer.Exit(code=exit_codes.NOT_INITIALIZED)
    # ... lookup + LLM call + write ...
finally:
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
```

### Excerpt — existing slug rewrite (template for `_set_entity_uri_in_body`)

`commands/ingest.py:116-150` — `_rewrite_target_slug_in_body` is the exact frontmatter-rewriting algorithm to mirror.

---

## NEW: `agents/graph-wiki-agent/src/graph_wiki_agent/uri_slug.py`

**Role:** Pure helper module (no I/O, no graph dependency).
**Closest analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/config.py` (single-purpose helper file in the same package).

### Excerpt — module skeleton style

```python
"""<module docstring>"""
from __future__ import annotations


def slug_from_uri(uri: str) -> str:
    """<docstring>"""
    if not uri:
        raise ValueError("uri must be non-empty")
    # implementation
    return tail
```

(`from __future__ import annotations` is the project convention — see `commands/ingest.py:1`.)

---

## Modified: `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`

**Role:** Typer-based CLI entry. Adds NOT_INITIALIZED-specific exit code on the `ingest source` command.
**Closest analog:** `cli.py:565-580` (`ingest_source` Typer command currently catches `(RuntimeError, ValueError)` → exit 1).

### Excerpt — pattern to extend

```python
@ingest_app.command(name="source")
def ingest_source(...):
    try:
        result = asyncio.run(run_ingest_source(path, workspace_path))
    except IngestorGraphNotInitializedError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=exit_codes.NOT_INITIALIZED)
    except (RuntimeError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
```

(The new exception is raised by `run_ingest_source`; CLI re-raises with exit code 3.)

---

## Modified: `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py`

**Role:** Pydantic schema for MCP tool output.
**Closest analog:** `mcp/server.py:317-326` (current `WikiIngestOutput` model).

### Excerpt — pattern to extend

```python
class WikiIngestOutput(BaseModel):
    status: str
    page_path: str
    slug: str
    title: str
    page_type: str
    source_path: str
    cross_refs_updated: int
    entity_uri: str | None = None  # Phase 40
```

---

## NEW: `agents/graph-wiki-agent/tests/unit/test_uri_slug.py`

**Role:** Pure-function unit tests.
**Closest analog:** `agents/graph-wiki-agent/tests/unit/test_config.py` (pure-module tests, no fixtures).

---

## Modified: `agents/graph-wiki-agent/tests/unit/test_commands_ingest.py`

**Role:** Async unit tests for ingest commands with mocked LLM.
**Closest analog:** `agents/graph-wiki-agent/tests/unit/test_commands_ingest.py:23-69` (existing `test_run_ingest_source_extracts_and_routes` template).

### Excerpt — patch chain pattern

```python
with (
    patch("graph_wiki_agent.commands.ingest.resolve_wiki_and_repo") as mock_resolve,
    patch("graph_wiki_agent.commands.ingest.make_llm") as mock_make_llm,
    patch("graph_wiki_agent.commands.ingest.update_index") as mock_update_index,
    patch("graph_wiki_agent.commands.ingest.append_log") as mock_append_log,
):
    mock_resolve.return_value = (wiki, tmp_path)
    fake_llm = MagicMock()
    fake_llm.ainvoke = AsyncMock(return_value=MagicMock(content=fake_llm_response))
    mock_make_llm.return_value = fake_llm
    result = await run_ingest_source(source_file, wiki)
```

### Graph-seeding helper pattern (from Phase 39 plan, target shape)

```python
def _seed_graph_db(workspace: Path, packages: list[tuple[str, str, str | None]]) -> Path:
    """Create <workspace>/.graph/code.db with package nodes + files.

    packages: list of (name, uri, file_path) tuples.
    """
    from graph_io import schema
    from graph_io.store import connect
    db = workspace / ".graph" / "code.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db, create=True)
    try:
        # insert nodes + edges...
    finally:
        conn.close()
    return db
```

---

## Pattern: SQL via raw `conn.execute`

Both `graph_io.queries.find` and `graph_io.queries.describe_path` use raw SQL through `sqlite3.Connection`. Phase 40's `_lookup_entity_by_path` follows the same idiom (parameterized query, single `.fetchone()`).

**Analog excerpt (`packages/graph-io/src/graph_io/queries.py:290-305`):**

```python
pkg = conn.execute(
    "SELECT attrs_json FROM nodes WHERE kind='package' AND name = ?",
    (name,),
).fetchone()
if not pkg:
    return None
attrs = json.loads(pkg[0]) if pkg[0] else {}
```

Mirror this exact pattern: parameterize all values, parse `attrs_json` with `json.loads`, return `None` on miss.

---

## Pattern: Phase 39 D-04 reuse — `slug_from_uri` extraction policy

Phase 39 does NOT extract this helper today. Phase 40 creates it standalone in `uri_slug.py`. **No source-file conflict** with Phase 39's parallel execution since the file is new and lives in the agent package.

A future Phase 39 refactor MAY route through `slug_from_uri`; document this in the helper's docstring as a non-binding future intent.

---

## Pattern: NOT_INITIALIZED exit code surfacing

`raise typer.Exit(code=exit_codes.NOT_INITIALIZED)` — already imported from `graph_io.exit_codes`.

**Analog:** `packages/graph-io/src/graph_io/cli/ops_status.py:64-90` and `q_find.py:46-70` — every cg query module uses `sys.exit(exit_codes.NOT_INITIALIZED)` on missing DB; the agent CLI uses the Typer equivalent (`raise typer.Exit(code=...)`).
