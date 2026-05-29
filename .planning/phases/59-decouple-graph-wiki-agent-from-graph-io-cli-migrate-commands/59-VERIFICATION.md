---
phase: 59-decouple-graph-wiki-agent-from-graph-io-cli-migrate-commands
verified: 2026-05-29T20:30:00Z
status: passed
score: 4/4
overrides_applied: 0
re_verification: null
gaps: []
human_verification: []
---

# Phase 59: Decouple graph-wiki-agent from graph_io.cli — Verification Report

**Phase Goal:** `graph-wiki-agent` consumes only the typed `graph_io` library API — nothing in the agent imports `graph_io.cli`. Migrate `commands/graph.py` (and, per sanctioned scope expansion, `mcp/server.py` and `commands/scan.py`) off the in-process `graph_io.cli.*.run(argparse.Namespace)` + captured-stdout shim onto typed functions (`graph_io.queries.*`, `graph_io.update.run`, `graph_io.store.read_only_connect`).

**Verified:** 2026-05-29T20:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No module under `agents/graph-wiki-agent/` imports `graph_io.cli`; `commands/graph.py` calls only typed `graph_io` library functions | VERIFIED | `grep -rn "graph_io.cli" agents/graph-wiki-agent/src/` returns empty. All imports are `from graph_io import exit_codes, queries, render, update` and `from graph_io.store import ...` |
| 2 | `_build_namespace`/`_capture_run` shim removed from `graph.py` in favor of direct typed-function calls | VERIFIED | `grep -nE "_build_namespace\|_capture_run\|argparse" graph.py` returns empty. `run_build`/`run_describe`/`run_query` printing-free core functions present with full implementation |
| 3 | Agent graph command behavior unchanged for all subcommands — byte-identical output and correct not-found stderr messages | VERIFIED | 7 syrupy snapshot tests pass against real DB (all 6 describe kinds + query). WR-01/02/03 messages verified in graph.py: `"error: path not found in graph: {identifier}"`, `"error: not found: {identifier}"` (test_suite), `"error: not found: repository"`. cg regression suite: 55 passed, 1 xfailed |
| 4 | Full test suite passes (`uv run --package graph-wiki-agent pytest`) | VERIFIED | 359 passed, 11 skipped (11 are pre-existing Phase 45 D-08 skip markers, unrelated to this phase) |

**Score:** 4/4 truths verified

---

### Scope Expansion Verification (sanctioned 59-02b)

The original plan context (59-CONTEXT.md) stated `graph.py` was the only consumer. Two additional consumers were discovered mid-phase and migrated via Plan 02b.

| Consumer | Status | Evidence |
|----------|--------|----------|
| `mcp/server.py` — 3 graph tools | VERIFIED | `graph_build`/`graph_describe`/`graph_query` call `graph_module.run_build`/`run_describe`/`run_query`; `DESCRIBE_REQUIRES_IDENTIFIER` used for identifier validation. No `graph_io.cli` import |
| `commands/scan.py` — pre-scan build block | VERIFIED | Imports `run_build as _cg_run_build` from `commands.graph`; calls `_cg_run_build(repo, _workspace_root, full=False)`. No `graph_io.cli` import |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/graph.py` | Typed API implementation with `run_build`/`run_describe`/`run_query` core funcs | VERIFIED | 656 lines; `_connect_or_error`, `DESCRIBE_REQUIRES_IDENTIFIER`, all 3 core funcs, `_describe_cli` shared wrapper, 6 describe sub-commands, `graph_build_cmd`, `graph_query_cmd` |
| `packages/graph-io/src/graph_io/render.py` | Public formatter promoted out of `graph_io.cli` | VERIFIED | 244 lines; exports `render`, `format_package`, `format_path`, `format_repo`, `format_domain`, `format_entry_point`, `format_suite`, plus internal helpers |
| `packages/graph-io/src/graph_io/cli/_format.py` | Re-export shim for 6 remaining cli importers | VERIFIED | Shim preserved for backward compatibility with 6 cli modules (`q_imported_by`, `q_exported_by`, `q_exports`, `q_imports`, `q_callers`, `q_callees`). Comment corrected from 7 to 6 importers (IN-01) |
| `agents/graph-wiki-agent/tests/unit/test_commands_graph.py` | Real-DB syrupy snapshots + exit-code branches | VERIFIED | 465 lines; 7 snapshot tests, full exit-code coverage (NOT_INITIALIZED, SCHEMA_MISMATCH, GENERIC, AMBIGUOUS, NOT_IN_GIT_REPO), D-03 cost-omission test, D-07 `--in-package` quirk test |
| `agents/graph-wiki-agent/tests/unit/__snapshots__/test_commands_graph.ambr` | Snapshot baseline with real rendered output | VERIFIED | 75 lines; 7 snapshots all contain real rendered graph output (not placeholders) |
| `agents/graph-wiki-agent/tests/conftest.py` | `seeded_graph_workspace` session fixture | VERIFIED | `seeded_graph_workspace` at line 96; additive, `seeded_graph_conn` unchanged |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `commands/graph.py` | `graph_io.queries.*` | `queries.describe_package`, `describe_path`, `describe_repository`, `describe_domain`, `describe_entry_point`, `describe_test_suite`, `find` | WIRED | Direct calls in `run_describe` and `run_query` |
| `commands/graph.py` | `graph_io.update.run` | `update.run(repo, workspace=workspace, full=full)` inside `run_build` | WIRED | Exception mapping covers `NotInGitRepoError`, `UpdateInProgressError`, `SchemaMismatchError`, catch-all |
| `commands/graph.py` | `graph_io.store.read_only_connect` | `_connect_or_error(workspace)` calls `read_only_connect(db)` | WIRED | Exception mapping covers `GraphNotInitializedError` and `SchemaMismatchError` |
| `commands/graph.py` | `graph_io.render` | `_render.format_*` calls in `run_describe`; `_render.render(...)` in `run_query` | WIRED | All 6 format functions called; `render` called with `cap=50` and `on_truncate` callback |
| `mcp/server.py` | `commands.graph` core funcs | `graph_module.run_build`/`run_describe`/`run_query` + `DESCRIBE_REQUIRES_IDENTIFIER` | WIRED | `from graph_wiki_agent.commands import graph as graph_module` at line 456; called in all 3 MCP graph tool handlers |
| `commands/scan.py` | `commands.graph.run_build` | `from graph_wiki_agent.commands.graph import run_build as _cg_run_build` | WIRED | Called at line ~494 for pre-scan build |
| `packages/graph-io/cli/q_describe_*.py` (6 modules) | `graph_io.render` | `from graph_io import ... render as _render` | WIRED | Verified in `q_describe_package.py`, `q_describe_path.py`, `q_describe_repo.py`, `q_describe_domain.py`, `q_describe_entry_point.py`, `q_describe_suite.py` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `run_describe` in `graph.py` | `desc` (query result) | `queries.describe_*` calls against `read_only_connect` DB | Yes — syrupy snapshots show real data (package counts, file counts, URIs) | FLOWING |
| `run_query` in `graph.py` | `records` | `queries.find(conn, ...)` against live DB | Yes — snapshot shows 4 real package rows from sample_monorepo fixture | FLOWING |
| Snapshot `.ambr` | Human-formatted output | Real DB via `seeded_graph_workspace` fixture built by `update.run(full=True)` | Yes — non-empty, non-placeholder values throughout | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| No `graph_io.cli` import in agent source | `grep -rn "graph_io.cli" agents/graph-wiki-agent/src/` | Empty (no output) | PASS |
| No shim patterns in graph.py | `grep -nE "_build_namespace\|_capture_run\|argparse" graph.py` | Empty (no output) | PASS |
| Agent test suite green | `uv run --package graph-wiki-agent pytest` | 359 passed, 11 skipped | PASS |
| cg regression suite green (byte-identical output guard) | `uv run pytest test_cli_format.py test_cli_describe.py test_cli_exit_codes.py test_cli_anti_regression.py` | 55 passed, 1 xfailed | PASS |
| schema_version=1 preserved (D-07) | `grep "_SCHEMA_VERSION = 1" graph.py` | Line 48: `_SCHEMA_VERSION = 1  # Phase 9 OBS-04 — D-02: do NOT bump` | PASS |
| AMBIGUOUS exit code = 7 (D-05) | `grep "AMBIGUOUS" exit_codes.py` | `AMBIGUOUS = 7` | PASS |
| WR-01 path not-found message | `grep "path not found in graph" graph.py` | Line 227: `f"error: path not found in graph: {identifier}"` — matches `q_describe_path.py` exactly | PASS |
| WR-02 test_suite not-found message | `grep at line 304` | `f"error: not found: {identifier}"` — matches `q_describe_suite.py` `"not found: {name}"` | PASS |
| WR-03 repository not-found message | `grep at line 233` | `"error: not found: repository"` — matches `q_describe_repo.py` exactly | PASS |
| WR-04 None guard in run_describe | `grep "identifier is None" graph.py` | Lines 215-216: guard before kind dispatch | PASS |
| IN-01 _format.py shim comment | `head -9 _format.py` | Says "6 existing cli modules" with note q_find was migrated | PASS |

---

### Decisions Verification (D-01..D-09)

| Decision | Description | Status | Evidence |
|----------|-------------|--------|----------|
| D-01 | Trace file naming `<ISO-Z>-<command>.jsonl` | VERIFIED | `_trace_path` uses `f"{shared_stamp}-{command}.jsonl"` pattern |
| D-02 | `schema_version=1`, do NOT bump | VERIFIED | `_SCHEMA_VERSION = 1` at graph.py line 48 |
| D-03 | Cost fields omitted on proxy commands | VERIFIED | `_write_trace_record` only includes `model_id` when `model_id is not None or event.startswith("graph_build")`; test asserts absence of `model_id`/`tokens_in`/`tokens_out`/`cost_usd` on describe trace |
| D-04 | Shared connect+map helper | VERIFIED | `_connect_or_error(workspace)` is the shared helper; reused by `run_describe` and `run_query`; `_open_graph_conn` wraps it for Typer-facing CLI |
| D-05 | Exit-code contract: `NOT_INITIALIZED(3)`, `SCHEMA_MISMATCH(4)`, `GENERIC(1)`, `AMBIGUOUS(7)`, `SUCCESS(0)` | VERIFIED | All mapped in `run_build`/`run_describe`/`run_query`; tested with mock-based exit-code branch tests |
| D-06 | `graph build` uses `update.run` (raises on error) | VERIFIED | `run_build` calls `update.run(repo, workspace=workspace, full=full)` with exception mapping |
| D-07 | `--in-package` no-match → GENERIC(1) quirk | VERIFIED | `run_query`: `if in_package is not None and not records: return exit_codes.GENERIC, "", ""`; test at line 399 |
| D-08 | Tests: real DB + syrupy snapshots | VERIFIED | 6 describe + 1 query real-DB snapshot tests in `test_commands_graph.py` |
| D-09 | `seeded_graph_workspace` fixture (reuses `sample_monorepo`) | VERIFIED | Session-scoped fixture at `conftest.py:96`; points `GRAPH_WIKI_WORKSPACE` at seeded repo |

---

### Requirements Coverage

No formal requirement IDs mapped (ROADMAP lists "Requirements: TBD"). All 4 Success Criteria verified as part of Observable Truths above.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `commands/scan.py` | 490 | Comment references deleted `_build_namespace/_capture_run` | Info | Commentary only — notes the migration; not a code reference |

No `TBD`, `FIXME`, or `XXX` markers found in any phase-modified files.

---

### Human Verification Required

None. All phase behaviors have automated verification coverage:
- SC#1/SC#2: static grep verified clean
- SC#3: syrupy snapshots + byte-identical stderr assertions + cg regression suite
- SC#4: full suite 359 passed

---

### Gaps Summary

No gaps. All 4 Success Criteria are verified in the codebase.

**Scope expansion (sanctioned):** `mcp/server.py` and `commands/scan.py` were discovered as additional `graph_io.cli` consumers during Plan 02b and fully migrated. Both are verified decoupled. This was a sanctioned in-flight scope expansion documented in 59-02b-SUMMARY.md.

**Code review findings (WR-01..WR-04, IN-01):** All addressed in commit `c624c6c` before this verification ran. The not-found stderr messages are byte-identical with the cg CLI, the `identifier=None` guard is in place, and the `_format.py` shim comment is corrected.

---

_Verified: 2026-05-29T20:30:00Z_
_Verifier: Claude (gsd-verifier)_
