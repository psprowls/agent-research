---
phase: 38-graph-wiki-agent-graph-subcommand
plan: 02
status: complete
date: 2026-05-26
---

# Plan 38-02 SUMMARY — MCP tools: `graph_build`, `graph_describe`, `graph_query`

## What shipped

### Modified files
| Path | Change |
|---|---|
| `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` | +199 lines: 3 new `@mcp.tool` registrations + 4 Pydantic models + `_pack_output` helper + `import time` / `import graph_module`, all placed AFTER `_StdoutGuard` install per existing convention |

### New files
| Path | Lines | Purpose |
|---|---|---|
| `agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py` | 244 | 12 unit tests covering registration, input shape, dispatch, stdout-guard safety, error packaging, trace writes |

## Test results

| Suite | Result |
|---|---|
| `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py -q` | **12 passed** |
| `pytest agents/graph-wiki-agent/tests/ -q` | **268 passed, 6 skipped** (was 256 — +12 new, 0 regressions) |
| `python -c "from graph_wiki_agent.mcp.server import mcp, graph_build, graph_describe, graph_query"` | exit 0 (server loads under `_StdoutGuard`) |

## Verification checks

| Check | Result |
|---|---|
| `grep -c '@mcp.tool(' server.py` | 10 (7 wiki_* + 3 graph_*) |
| `grep -c 'name="graph_' server.py` | 3 (exactly) |
| `grep -c 'name="wiki_' server.py` | 7 (regression guard) |
| `_StdoutGuard` triggered during any test? | NO (the explicit `test_stdout_guard_not_tripped` asserts cg's `print()` is captured by `_capture_run`'s `contextlib.redirect_stdout`) |
| Existing `wiki_*` tools importable? | YES (`test_wiki_tools_still_registered` regression guard) |

## Notes / discoveries

1. **`_StdoutGuard` is module-init.** Any test that imports from `mcp.server` triggers the guard install. Since cg modules `print()` via Python-level `sys.stdout.write`, they would normally trip the guard — but `_capture_run` (Plan 01) wraps every cg call in `contextlib.redirect_stdout(StringIO())`, so the guard never sees those writes. The `test_stdout_guard_not_tripped` test is the explicit regression check.

2. **FastMCP 1.27.1 tool registry inspection.** Did not introspect `mcp._tool_manager` — instead used the simpler import-callable + `inspect.iscoroutinefunction` check (matches the plan's suggested fallback in Task 2 notes). If a future plan wants to walk the registry, it can extend `test_three_graph_tools_registered`.

3. **`_write_trace_record` signature.** Plan 02's draft assumed the helper takes a trace _directory_; Plan 01 implemented it taking a trace _file path_. The MCP code calls `_trace_path(workspace, command, shared_stamp)` to build the file path first, then passes it to `_write_trace_record(trace_file, ...)`. This is captured in the Plan 02 action notes (line 339 noted both options; the file-path option was the simpler match for the in-repo implementation).

4. **`asyncio_mode = "auto"`** in `agents/graph-wiki-agent/pyproject.toml` means `async def test_*` functions are auto-detected — no `@pytest.mark.asyncio` decorator needed. Tests omit the decorator accordingly.

5. **Pydantic identifier-validation layering.** `GraphDescribeInput(kind="package")` (identifier=None) parses cleanly at the Pydantic layer. The adapter (the MCP tool body) returns `GraphCommandOutput(status="error", exit_code=2, stderr="identifier required for kind=package", trace_path=None)`. This matches the plan's specification (line 122) — Pydantic enforces structure; the adapter enforces semantic constraints.

6. **Manual end-to-end smoke (verification step 8) NOT executed.** The plan listed it as optional ("before gsd:verify-work"). Skipped because the 12 unit tests cover the same surface — direct in-process invocation of the `@mcp.tool` coroutines validates registration + dispatch without standing up a real MCP transport.

## Done

GRAPHCMD-04 satisfied. SC#4 satisfied: `graph_build`, `graph_describe`, `graph_query` are all registered MCP tools. The MCP path delegates to Plan 01's CLI helpers (no code duplication between CLI and MCP surfaces). Phase 38 SC#1..SC#4 are all green via Plan 01 + Plan 02.
