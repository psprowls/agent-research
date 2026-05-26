---
phase: 38-graph-wiki-agent-graph-subcommand
plan: 01
status: complete
date: 2026-05-26
---

# Plan 38-01 SUMMARY — Agent-side CLI surface for `graph-wiki-agent graph`

## What shipped

### New files
| Path | Lines | Purpose |
|---|---|---|
| `packages/graph-io/src/graph_io/cli/q_describe_entry_point.py` | 90 | `cg describe-entry-point <name>` CLI module (RESEARCH §3 Option A) |
| `packages/graph-io/tests/test_cli_describe_entry_point.py` | 77 | 2 parity tests against the `mypkg-run` fixture entry-point |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` | 419 | `graph_app` Typer subapp: build/describe/query + 6 describe sub-sub-commands + helpers |
| `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` | 237 | 16 unit tests (11 functions, parametrize ×6) |

### Modified files
| Path | Change |
|---|---|
| `packages/graph-io/src/graph_io/cli/main.py` | +2 lines: `q_describe_entry_point` import + `_SUBCOMMANDS` entry |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` | +3 lines: import `graph_app` + `app.add_typer(graph_app, name="graph")` + comment |

## Verification status

| Verification check | Result |
|---|---|
| `uv sync` | exit 0 |
| `uv run --package graph-io pytest packages/graph-io/tests/test_cli_describe_entry_point.py -q` | **2 passed** |
| `uv run --package graph-io pytest packages/graph-io/tests/ -q` | **326 passed, 1 skipped, 1 xfailed** (no regressions) |
| `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py -q` | **16 passed** |
| `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -q` | **256 passed, 6 skipped** (no regressions) |
| `CliRunner().invoke(app, ['graph', '--help'])` lists build/describe/query | confirmed |
| `CliRunner().invoke(app, ['graph', 'describe', '--help'])` lists 6 kebab kinds | confirmed |
| `grep -c '"event":' graph.py` ≥ 4 | 4 event refs present (`graph_build_start`, `graph_build_complete`, `graph_describe`, `graph_query`) |
| `grep -q 'describe-entry-point' .../cli/main.py` | confirmed |

## Deviations from plan

### 1. `q_describe_entry_point` underlying-query signature mismatch
The plan and RESEARCH §3 described `queries.describe_entry_point(conn, name=...)`. The actual function signature in `packages/graph-io/src/graph_io/queries.py:475` is `(conn, *, package_name: str, entry_name: str)` — it requires BOTH a package name AND the entry-point name (entry-point names are NOT unique across packages).

**Resolution:** The new CLI module accepts a single positional `name` argument that supports two forms:
- **Bare form** (`cg describe-entry-point mypkg-run`): scans all packages, returns the unique match. If multiple packages declare an entry-point with that name, returns `AMBIGUOUS` (exit code 7) and lists the candidate packages.
- **Qualified form** (`cg describe-entry-point mypkg:mypkg-run`): splits on the first `:` and passes both values to the underlying query.

This preserves the agent-side single-identifier dispatch model required by D-09 (`_DESCRIBE_DISPATCH` maps `entry_point → (q_describe_entry_point, "name")`) while satisfying the actual underlying query contract. The deviation is documented in the module docstring for future maintainers.

### 2. `seeded_db` fixture shape vs plan-assumed shape
The plan's Task 2 sketch assumed `seeded_db` yields an object with `.repo` and `.workspace` attributes. In reality `seeded_db` (session-scoped, `packages/graph-io/tests/conftest.py:17`) yields only a `sqlite3.Connection`. The CLI module needs the workspace path to open its own read-only connection via `store.read_only_connect`.

**Resolution:** The test file defines its own function-scoped `workspace_path` fixture that re-creates the seeded workspace (init git → commit → `update.run(repo_root, full=True)`) and returns the resolved workspace path. Marginal extra runtime; clean isolation per test.

### 3. `CliRunner(mix_stderr=False)` not supported on Click 8.3
The plan's Task 5 template used `CliRunner(mix_stderr=False)`. Click 8.2+ removed the `mix_stderr` keyword; in 8.3 stderr is already separated by default and `result.stderr` works out of the box.

**Resolution:** Removed the `mix_stderr=False` argument from the `runner` fixture. `result.stderr` and `result.output` behave as expected.

## Territory respected

- **Phase 35 territory** (`init`/`lint` commands in `cli.py`): only modified — added 1 import line + 1 `app.add_typer(graph_app, name="graph")` line + 1 comment line. No existing imports, commands, or Typer subapps removed or reordered.
- **Phase 37 territory** (`graph_tools.py`, `pyproject.toml`): NOT touched. `mcp/server.py` NOT touched (Plan 02's territory).

## Notes for Plan 02 (MCP tools)

1. **`result.stderr` works in tests.** Click 8.3 separates stdout/stderr by default — Plan 02's MCP tests can use the standard `runner.invoke(...).stderr` pattern.

2. **`_DESCRIBE_DISPATCH`, `_build_namespace`, `_capture_run`, `_write_trace_record`, `_trace_path`, `_iso_utc_timestamp`** are all exposed at module scope in `commands/graph.py` for Plan 02 to import and reuse. The MCP tool bodies should be thin wrappers calling these helpers (no logic duplication).

3. **`q_describe_entry_point` accepts either bare or qualified names.** Plan 02's `graph_describe` MCP tool with `kind='entry_point'` should pass the identifier through unchanged — `_run_describe` already calls into the right module via the dispatch table.

4. **trace files use a per-invocation timestamp.** Each `graph build` / `graph describe` / `graph query` MCP call should compute one `shared_stamp` and write all records for that invocation into the same JSONL file (matches `_write_trace_record` semantics).

5. **The `_capture_run` helper already strips stdout/stderr via `contextlib.redirect_stdout/stderr`** — the MCP path will not trip `_StdoutGuard` as required by SC#4. Plan 02 just needs to populate the `GraphCommandOutput.stdout` and `.stderr` fields from the helper's return triple.

## Done

GRAPHCMD-01, GRAPHCMD-02, GRAPHCMD-03 satisfied at the CLI layer. SC#1 (3 subcommands), SC#2 (correct build flag set), SC#3 (trace records written, OBS-04 schema reused with new event values, proxy commands omit cost fields per D-03) all confirmed by automated tests. Ready for Plan 02.
