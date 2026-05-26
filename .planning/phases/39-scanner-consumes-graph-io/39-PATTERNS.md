# Phase 39: Scanner Consumes graph-io — Pattern Map

**Mapped:** 2026-05-26
**Purpose:** Pre-locate existing code analogs for each file Phase 39 will create or modify, so executor agents can copy proven patterns rather than reinvent.

---

## Files to be Modified

### `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py`

**Role:** Top-level command — wires monorepo discovery + scanner subagent fan-out.
**Data flow:** Reads filesystem + (NEW) graph DB; writes vault pages + scan log.

**Closest existing analog — `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py`:**

The Phase 37 librarian command at `commands/query.py` is the canonical analog for Phase 39's modifications. It demonstrates all three new patterns Phase 39 needs:

1. **Single-conn open at command entry + close in `finally`** (D-05 mirror). From Phase 37 Plan 02 Task 1, in `commands/query.py`'s `run_query()`:

```python
from graph_io.store import read_only_connect, GraphNotInitializedError
from workspace_io.paths import graph_dir

conn = None
tools: list = []
try:
    try:
        conn = read_only_connect(graph_dir(wiki) / "code.db")
        tools = build_graph_tools(conn)
    except GraphNotInitializedError:
        conn = None
        sys.stderr.write(
            "[graph unavailable: run 'cg update' to enable code-graph grounding tools]\n"
        )
    # ... use conn (or skip if None) ...
finally:
    if conn is not None:
        conn.close()
```

Phase 39 replicates this lifecycle in `run_scan()`. The fallback log line shape and channel (stderr, one line, before fan-out begins) is the same — only the message text differs (per CONTEXT.md D-08 specifics).

2. **In-process cg dispatch via `_capture_run` + `_build_namespace`** (D-01 / D-02). The Phase 38 helpers at `commands/graph.py`:

```python
from graph_wiki_agent.commands.graph import _build_namespace, _capture_run, ops_update

args = _build_namespace(ops_update, repo=repo, workspace=wiki, full=False)
exit_code, stdout, stderr = _capture_run(ops_update, args)
```

Phase 38's `graph_app.command("build")` calls these exact helpers; Phase 39 reuses them with the same `full=False` semantic (D-02).

3. **Scan log entries via `append_log`** (existing pattern, no change). From `commands/scan.py:401-447`:

```python
from wiki_io.append_log import append_log
append_log(wiki, "scan", "<message>", detail=None, silent=True, raise_exception=True)
```

Phase 39 adds new `append_log` calls for the cg-update events (per RESEARCH §7 table).

---

## Files to be Created

### `agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py`

**Role:** Unit tests covering the new graph-integration branches in `run_scan`.
**Closest existing analog — `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` (Phase 38) + `agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py` (Phase 37 Plan 02):**

From Phase 37 Plan 02 (`test_query_graph_tools_wiring.py`), the pattern for mocking the cg layer + asserting NOT_INITIALIZED fallback:

```python
def test_not_initialized_fallback(monkeypatch, capsys, tmp_workspace):
    # Ensure no graph DB exists
    graph_db = tmp_workspace / ".graph-wiki" / "graph" / "code.db"
    assert not graph_db.exists()

    # Run the command
    asyncio.run(run_query(workspace_path=tmp_workspace, ...))

    # Assert exactly one fallback stderr line, no tool calls
    captured = capsys.readouterr()
    assert captured.err.count("[graph unavailable:") == 1
```

From Phase 38 Task 5 (`test_commands_graph.py::test_graph_build_dispatches_to_ops_update`), the pattern for monkeypatching `ops_update.run`:

```python
from unittest.mock import MagicMock, patch
from graph_wiki_agent.commands import graph as graph_module

def test_cg_update_dispatched_before_fanout(monkeypatch, tmp_workspace):
    recorder = MagicMock(return_value=exit_codes.SUCCESS)
    with patch.object(graph_module.ops_update, "run", recorder):
        asyncio.run(run_scan(workspace_path=tmp_workspace))
        assert recorder.call_count == 1
        args = recorder.call_args.args[0]
        assert args.full is False
        assert args._module is graph_module.ops_update
```

Phase 39 tests combine these two patterns: mock `ops_update.run` with various return codes / stderr contents, then assert (a) the call happened with `full=False`, (b) the conn open/close + decoration branches behave as designed, (c) the fallback stderr line is emitted on init-failure pattern but NOT on other failures.

---

### `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py`

**Role:** End-to-end integration with a real fixture monorepo + real cg dispatch.
**Closest existing analog — `packages/graph-io/tests/test_cli_describe_package.py` + `packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py`:**

The Phase 35 bootstrap test demonstrates the e2e fixture pattern for the scanner:

```python
def test_bootstrap_e2e_no_broken_links(tmp_path):
    # Set up a fixture workspace with `.graph-wiki/` + `wiki/CLAUDE.md`
    workspace = _setup_fixture(tmp_path)
    # Run the scanner end-to-end
    result = asyncio.run(run_scan(workspace_path=workspace))
    # Assert vault pages exist at expected paths
    assert (workspace / "wiki" / "packages" / "X" / "overview.md").exists()
    # Assert no broken wikilinks
    ...
```

Phase 39 builds on this: same fixture-construction style, but Phase 39's integration test additionally asserts that `code.db` is created (proving `cg update` ran) and the resulting vault page path matches the graph URI's suffix (proving decoration ran).

For pytest markers, the existing `agents/graph-wiki-agent/pyproject.toml` declares `integration` (verify at execute time; if absent, add it). Mark the new file with `@pytest.mark.integration` at module level.

---

## Re-used Fixtures

| Fixture | Source | Use in Phase 39 |
|---------|--------|------------------|
| `seeded_graph_conn` | `agents/graph-wiki-agent/tests/conftest.py` (added by Phase 37) | Decoration unit tests — provides a populated `sqlite3.Connection` to assert `list_packages` join behavior |
| `tmp_workspace` | Phase 38's `tests/unit/test_commands_graph.py` introduced one inline | Phase 39 extracts to `tests/conftest.py` if reused across files — decision at execute time |
| `sample_monorepo` | `packages/graph-io/tests/fixtures/sample_monorepo/` | Integration test's fixture monorepo (executor verifies it has a `packages/`-style layout) |

---

## Anti-patterns to Avoid

- **Per-workspace `read_only_connect` calls** — violates D-05 / Pitfall 4. Open once at scan entry.
- **Mutating `_wiki_relative_path_for` in `wiki_io/scan_monorepo.py`** — D-04 forbids. wiki-io stays graph-unaware.
- **Adding `--no-graph-update` flag** — CONTEXT.md "Claude's Discretion" — declined.
- **Subprocess `cg update`** — CONTEXT.md Deferred. Use in-process import.
- **Direct `graph_io.cli.ops_update.run` import** — bypasses Phase 38 surface. Always go through `commands/graph.py` helpers (D-01).
- **N+1 SQL queries during decoration** — fetch all packages in one `list_packages` call + one domain-join SQL.
- **Bumping trace schema version** — Phase 39 does not write traces (D-02 disallows `--trace`).

---

*Phase: 39-scanner-consumes-graph-io*
*Pattern mapping completed: 2026-05-26*
