---
phase: 38
slug: graph-wiki-agent-graph-subcommand
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-26
---

# Phase 38 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (asyncio_mode=auto) |
| **Config file** | `agents/graph-wiki-agent/pyproject.toml` `[tool.pytest.ini_options]` + `packages/graph-io/pyproject.toml` |
| **Quick run command** | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py -q` |
| **Full suite command** | `uv run --package graph-wiki-agent pytest -q && uv run --package graph-io pytest -q` |
| **Estimated runtime** | quick ~5s, full ~45s (excludes `integration` marker) |

---

## Sampling Rate

- **After every task commit:** Run quick command above
- **After every plan wave:** Run `uv run --package graph-wiki-agent pytest -q && uv run --package graph-io pytest -q`
- **Before `/gsd:verify-work`:** Full suite + a `uv sync` check + manual `graph-wiki-agent graph --help` invocation (SC#1)
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 38-01-01 | 01 | 1 | GRAPHCMD-01 | — | `cg describe-entry-point <name>` is registered in `_SUBCOMMANDS` and dispatches to `queries.describe_entry_point` | unit | `uv run --package graph-io pytest packages/graph-io/tests/test_cli_describe_entry_point.py -q` | ✅ W0 | ⬜ pending |
| 38-01-02 | 01 | 1 | GRAPHCMD-01 | — | `graph-wiki-agent graph --help` exits 0 and lists exactly 3 subcommands `build`, `describe`, `query` (no more, no fewer) | unit | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_help_lists_exactly_three_subcommands -q` | ✅ W0 | ⬜ pending |
| 38-01-03 | 01 | 1 | GRAPHCMD-02 | — | `graph-wiki-agent graph build --help` lists only `--full`, `--trace`, `--model`, `--workspace` (no additional flags beyond cg's `--full` + Phase 38's `--trace` + `--model` + the workspace selector) | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_build_help_flags -q` | ✅ W0 | ⬜ pending |
| 38-01-04 | 01 | 1 | GRAPHCMD-02 | — | `graph build` calls `ops_update.run` with a Namespace where `args.full=False` by default; `--full` sets `args.full=True` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_build_dispatches_to_ops_update -q` | ✅ W0 | ⬜ pending |
| 38-01-05 | 01 | 1 | GRAPHCMD-03 (D-01, D-02) | — | `graph build --trace` writes exactly one file matching `.graph-wiki/traces/<ISO-Z>-graph-build.jsonl`; the file contains `event=graph_build_start` and `event=graph_build_complete` records with `schema_version=1`, `command`, `args`, `exit_code`, `duration_ms` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_build_writes_trace -q` | ✅ W0 | ⬜ pending |
| 38-01-06 | 01 | 1 | GRAPHCMD-03 (D-02) | — | `graph build --trace --model <id>` adds `model_id=<id>` to the complete-record but emits a stderr note that the model is not actually invoked in v1.7 | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_build_model_recorded_not_invoked -q` | ✅ W0 | ⬜ pending |
| 38-01-07 | 01 | 1 | GRAPHCMD-01 (D-08) | — | `graph describe --help` lists exactly 6 sub-sub-commands: `package`, `path`, `repository`, `domain`, `entry-point`, `test-suite` (kebab-case at the CLI layer) | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_describe_help_lists_six_kinds -q` | ✅ W0 | ⬜ pending |
| 38-01-08 | 01 | 1 | GRAPHCMD-03 (D-08) | — | each of the 6 describe sub-sub-commands dispatches to the matching `q_describe_*.run` module via the `_DESCRIBE_DISPATCH` table; each constructs a Namespace with the kind-specific identifier attribute (`name`, `path`, or none) | unit (parametrize) | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_describe_dispatch_all_six_kinds -q` | ✅ W0 | ⬜ pending |
| 38-01-09 | 01 | 1 | GRAPHCMD-03 (D-03) | — | `graph describe package <name> --trace` writes a single record with `event=graph_describe`, `command`, `args`, `exit_code`, `duration_ms` AND OMITS `model_id`, `tokens_in`, `tokens_out`, `cost_usd` (D-03's "honest" omission requirement) | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_describe_trace_omits_cost_fields -q` | ✅ W0 | ⬜ pending |
| 38-01-10 | 01 | 1 | GRAPHCMD-03 | — | `graph query --name foo --kind class --in-package pkg` dispatches to `q_find.run` with Namespace containing `args.name="foo"`, `args.kind="class"`, `args.in_package="pkg"` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_dispatch -q` | ✅ W0 | ⬜ pending |
| 38-01-11 | 01 | 1 | GRAPHCMD-03 (D-03) | — | `graph query` with no filters fails at the Typer layer with `typer.Exit(code=2)` and stderr usage message — does NOT reach `q_find.run` (avoids the `args._parser.error` AttributeError path) | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_no_filters_fails_fast -q` | ✅ W0 | ⬜ pending |
| 38-01-12 | 01 | 1 | GRAPHCMD-03 | — | non-zero exit codes from cg modules propagate as `typer.Exit(code=<cg_exit>)`; stderr from cg is echoed to typer stderr | unit | `pytest agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_cg_exit_codes_propagate -q` | ✅ W0 | ⬜ pending |
| 38-02-01 | 02 | 2 | GRAPHCMD-04 | — | exactly 3 new MCP tools registered: `graph_build`, `graph_describe`, `graph_query` — tool registry contains those names; existing `wiki_*` tools remain | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_three_graph_tools_registered -q` | ✅ W0 | ⬜ pending |
| 38-02-02 | 02 | 2 | GRAPHCMD-04 (D-04) | — | `GraphBuildInput` accepts `full: bool`, `trace: bool`, `model: str | None`, `workspace_path: str`; rejects unknown fields (extra='forbid') | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_graph_build_input_shape -q` | ✅ W0 | ⬜ pending |
| 38-02-03 | 02 | 2 | GRAPHCMD-04 (D-09) | — | `GraphDescribeInput.kind` is a Literal over the 6 snake_case kinds; `kind="bogus"` raises Pydantic ValidationError; `kind="repository"` succeeds with `identifier=None` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_graph_describe_input_kind_enum -q` | ✅ W0 | ⬜ pending |
| 38-02-04 | 02 | 2 | GRAPHCMD-04 (D-09) | — | `graph_describe(kind="package", identifier="foo")` dispatches to `q_describe_package.run` via the SAME `_DESCRIBE_DISPATCH` helper as the CLI path | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_graph_describe_mcp_dispatch -q` | ✅ W0 | ⬜ pending |
| 38-02-05 | 02 | 2 | GRAPHCMD-04 | — | calling any of the 3 MCP tools does NOT trip `_StdoutGuard` (no stdout write reaches the guard); all cg `print()` is captured via `contextlib.redirect_stdout` | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_stdout_guard_not_tripped -q` | ✅ W0 | ⬜ pending |
| 38-02-06 | 02 | 2 | GRAPHCMD-04 (D-04) | — | `GraphCommandOutput.exit_code` mirrors the underlying cg module's int return; `stdout` contains the rendered human-format text; `stderr` contains the rendered error text; `trace_path` is non-null iff `trace=True` was passed | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_output_shape_per_tool -q` | ✅ W0 | ⬜ pending |
| 38-02-07 | 02 | 2 | GRAPHCMD-04 | — | invoking `graph_describe(kind="package", identifier="nonexistent")` returns `GraphCommandOutput(status="error", exit_code=<GENERIC>, stderr="error: package not found: nonexistent\n")` without raising | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_describe_missing_entity -q` | ✅ W0 | ⬜ pending |
| 38-02-08 | 02 | 2 | GRAPHCMD-04 | — | invoking `graph_build` against a workspace with no graph DB initialized returns the appropriate cg exit code (NOT_IN_GIT_REPO or NOT_INITIALIZED) packaged in the output; does NOT crash the MCP server | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_graph_build_uninitialized_returns_error -q` | ✅ W0 | ⬜ pending |
| 38-02-09 | 02 | 2 | GRAPHCMD-04 | — | regression: existing `wiki_query`, `wiki_log`, `wiki_bootstrap`, `wiki_scan`, `wiki_ingest`, `wiki_lint` MCP tools are still importable and registered after Phase 38 changes | unit | `pytest agents/graph-wiki-agent/tests/unit/test_mcp_graph_tools.py::test_wiki_tools_still_registered -q` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

All Wave 0 infrastructure already exists on the branch when Phase 38 starts executing:

- ✅ `agents/graph-wiki-agent/tests/unit/` directory and `[tool.pytest.ini_options]` config (pre-existing).
- ✅ `typer.testing.CliRunner` is part of typer's test API (no install needed).
- ✅ Existing analog tests in `tests/unit/test_cli_*.py` and `tests/unit/test_mcp_*.py` (pattern templates).
- ✅ `packages/graph-io/tests/` infrastructure including `seeded_db` fixture (for the new `test_cli_describe_entry_point.py` test).
- ✅ `_StdoutGuard` is already installed at MCP server module init (no test setup needed).

No new framework / fixture / runner installation required.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Trace file readable by existing `graph-wiki-agent trace <file>` renderer (SC#3 lenient consumer test) | GRAPHCMD-03 (D-02) | Cross-feature integration; renderer compatibility check belongs in `gsd:verify-work` not in unit tests | `graph-wiki-agent graph build --trace --workspace <tmp>` then `graph-wiki-agent trace .graph-wiki/traces/<file>.jsonl` — should exit 0 and render the new events in the timeline |
| DeepAgents CLI sees the 3 new MCP tools | GRAPHCMD-04 | Requires running the MCP server under a real DeepAgents host | Start `graph-wiki-mcp` via DeepAgents config; `tools.list` should include `graph_build`, `graph_describe`, `graph_query` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
