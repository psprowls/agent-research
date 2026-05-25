---
phase: 22-workspace-api-internal-rename
plan: "01"
subsystem: workspace-path-resolution
tags:
  - refactor
  - rename
  - vault_path
  - workspace_path
  - internal-api
dependency_graph:
  requires: []
  provides:
    - WSAPI-01
    - WSAPI-02
    - WSAPI-03
    - WSAPI-04
    - WSAPI-05
    - WSAPI-06
  affects:
    - packages/wiki-io/src/wiki_io/_workspace.py
    - packages/workspace-io/src/workspace_io/config.py
    - packages/workspace-io/src/workspace_io/init.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/
    - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
    - agents/graph-wiki-agent/src/graph_wiki_mcp/server.py
tech_stack:
  added: []
  patterns:
    - "workspace_path: Path | None = None kwarg in all run_* signatures"
    - "resolve_workspace(repo_root) as public function in workspace_io.config"
    - "WORKSPACE_DIRECTORY_KEY = workspace-directory in .graph-wiki.local.yaml"
key_files:
  created: []
  modified:
    - packages/wiki-io/src/wiki_io/_workspace.py
    - packages/workspace-io/src/workspace_io/config.py
    - packages/workspace-io/src/workspace_io/init.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
    - agents/graph-wiki-agent/src/graph_wiki_mcp/server.py
    - 17 test files (unit, integration, commands, eval-harness)
decisions:
  - "D-02: replaced f-string hack with _ws_paths.wiki_dir(workspace_path)"
  - "D-05: repo discovery walks up from Path.cwd() when repo_path omitted"
  - "D-06: exact signature resolve_wiki_and_repo(workspace_path, repo_path)"
  - "D-07: hard rename, no back-compat shim"
  - "D-08: workspace-directory YAML key, old graph-wiki-directory silently ignored"
  - "D-10: wiki-io package directory unchanged"
metrics:
  duration_minutes: 30
  completed_date: "2026-05-20"
  tasks_completed: 7
  files_touched: 28
---

# Phase 22 Plan 01: Workspace API Internal Rename Summary

Hard-renamed the internal Python API from `vault_path` to `workspace_path` across all 6 `run_*` command signatures, `resolve_wiki_and_repo` in wiki-io, CLI/MCP server call sites, and ~30 test kwarg call sites; promoted `resolve_workspace` to public symbol; hard-cut `.graph-wiki.local.yaml` YAML key to `workspace-directory`.

## Files Touched

28 files modified, 0 created (from `git diff --name-only HEAD~7..HEAD`).

## WSAPI Requirements Satisfied

- **WSAPI-01**: `resolve_wiki_and_repo` signature renamed: `(workspace_path: Path | None = None, repo_path: Path | None = None) -> tuple[Path, Path | None]`
- **WSAPI-02**: All 6 `run_*` command signatures renamed: `scan`, `lint`, `ingest` (x2), `query`, `log`, `init`
- **WSAPI-03**: CLI and MCP server internal kwarg calls flipped: `vault_path=` → `workspace_path=`
- **WSAPI-04**: All test file kwarg call sites swept; lambda mock signatures renamed
- **WSAPI-05**: `WORKSPACE_DIRECTORY_KEY = "workspace-directory"` exported; `_resolve_workspace` promoted to `resolve_workspace`
- **WSAPI-06**: `workspace_io.init.init()` now routes default workspace through `resolve_workspace(repo_root=repo_root)`

## Pytest Result

**582 passed, 33 skipped, 6 pre-existing failures** (same 6 failures existed before this phase per stash verification).

Pre-existing failures (NOT caused by Phase 22):
- `test_cli_help.py::test_cli_help_lists_bootstrap_subcommand`
- `test_cli_query.py::test_query_help_exits_zero`
- `test_cli_query.py::test_vault_flag_in_help`
- `test_cli_query.py::test_state_gate_flag_present`
- `test_trace_viewer.py::test_trace_command_has_expand_flag`
- `test_sweep.py::test_run_query_accepts_tmpdir_vault`

## Verification Grep Outputs

**V1** — No f-string hack:
```
grep -n 'f"{workspace_path}"' packages/wiki-io/src/wiki_io/_workspace.py
→ 0 hits
```

**V2** — CWD-based repo walk (D-05):
```
grep -n "_find_repo_root(Path.cwd())" packages/wiki-io/src/wiki_io/_workspace.py
→ 37: return _ws_paths.wiki_dir(workspace_path), repo_path or _find_repo_root(Path.cwd())
```

**V3** — Public symbol importable:
```
python -c "from workspace_io.config import resolve_workspace, WORKSPACE_DIRECTORY_KEY; ..."
→ OK (resolve_workspace: <function>, WORKSPACE_DIRECTORY_KEY: workspace-directory)
```

**V4** — No graph-wiki-directory in config.py:
```
grep -c "graph-wiki-directory" packages/workspace-io/src/workspace_io/config.py
→ 0
```

**V5** — No LATTICE_DIRECTORY_KEY or _resolve_workspace in Python modules:
```
grep -rn "LATTICE_DIRECTORY_KEY|_resolve_workspace" packages/ agents/ | grep "\.py:" | grep -v ".pyc"
→ 0 Python source file hits (3 md files in test fixtures contain these strings in content, not as imports)
```

**V6** — CLI flag preservation:
```
grep -c '"--vault"' agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
→ 7 (Phase 23 boundary preserved)
```

**V7** — MCP Pydantic field preservation:
```
grep -c "vault_path.*str.*=.*Field|vault_path.*str.*= \"\"" server.py
→ 6 (Phase 23 boundary preserved)
```

**V8** — vault_path in in-scope source trees (Phase 23-owned allowlist):
All remaining `vault_path` hits in `agents/graph-wiki-agent/src` + `packages/workspace-io/src` are:
- `graph_wiki_mcp/server.py`: Pydantic Field declarations (6×) + `input.vault_path` field accesses (6×) + 2 description strings → Phase 23 owned
- `graph_wiki_agent/commands/query.py`: private helpers `_discover_pages`, `_cosine_search_sqlite`, `_resolve_repo_root`, `bm25_query`, `build_index`, `apply_guardrails` — explicitly out of scope per PATTERNS.md
- `graph_wiki_agent/commands/scan.py`: `pkg.get("vault_path", ...)` — dict data key, not parameter rename scope
- `graph_wiki_agent/config.py`: `WikiConfig.vault_path` field — separate plugin config dataclass, out of scope
- `graph_wiki_agent/prompts/_fragments/page_categories.py`: string literals in prompts — not code

**V9** — Signature check:
```
grep -A3 "def resolve_wiki_and_repo" packages/wiki-io/src/wiki_io/_workspace.py
→ workspace_path: Path | None = None,
→ repo_path: Path | None = None,
→ ) -> tuple[Path, Path | None]:
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_lint_parity.py not in PLAN.md files_modified but uses vault_path= kwarg**
- **Found during:** Task 5
- **Issue:** `tests/commands/test_lint_parity.py` calls `run_lint(vault_path=EDGE_CASE_VAULT)` — not listed in plan's `files_modified` but would cause test failures
- **Fix:** Renamed to `workspace_path=EDGE_CASE_VAULT` in 4 call sites
- **Files modified:** `agents/graph-wiki-agent/tests/commands/test_lint_parity.py`
- **Commit:** 5f082d2

**2. [Rule 1 - Bug] Error message test assertions used old "init" term after WIP "bootstrap" change**
- **Found during:** Task 7 (pytest gate)
- **Issue:** WIP config.py changed error message from "graph-wiki-agent init" to "graph-wiki-agent bootstrap"; 3 tests still matched old string
- **Fix:** Updated assertions in `test_config.py` and `test_ports_importable.py` (2 tests)
- **Files modified:** `packages/workspace-io/tests/test_config.py`, `packages/wiki-io/tests/test_ports_importable.py`
- **Commit:** 97212fd

### Plan Inconsistency (documented, not a bug)

**MUST_HAVES truth #5 vs PATTERNS.md out-of-scope list:**
The plan's `must_haves.truths[4]` states "grep -r 'vault_path' agents/graph-wiki-agent/src packages/workspace-io/src returns 0 hits" — but PATTERNS.md explicitly excludes `query.py` private helpers, `scan.py` dict keys, `config.py` WikiConfig dataclass, and `prompts/` strings from Phase 22 scope. The plan verification step 2 allows Pydantic Field hits and `input.vault_path` but doesn't account for these other out-of-scope occurrences. The Phase 22 rename boundary was honored correctly per PATTERNS.md; the discrepancy is in the plan's verification assertion.

### Phase 23-Owned Surfaces Preserved

The following were intentionally preserved for Phase 23:
- **Typer flag literal `"--vault"`**: 7 occurrences in `cli.py` — unchanged
- **MCP Pydantic Field declarations `vault_path: str = Field(...)`**: 5 `Field()` + 1 plain `= ""` in `server.py` — unchanged
- **Pydantic field access `input.vault_path`**: 6 occurrences in `server.py` handler functions — unchanged

## Known Stubs

None. All wired data, no placeholder values introduced.

## Threat Flags

None. Pure internal Python API rename — no new network surface, auth paths, or schema changes at trust boundaries.

## Self-Check

### Commits Exist

All 7 task commits verified:
- `fb15aba` — Task 1: wiki-io/_workspace.py
- `cc3b028` — Task 2: workspace-io/config.py + init.py
- `a01c461` — Task 3: 6 run_* command signatures
- `a572c00` — Task 4: CLI + MCP server internal calls
- `5f082d2` — Task 5: test file sweep (+ Rule 1 test_lint_parity.py)
- `5455687` — Task 6: test_config.py YAML literals
- `97212fd` — Task 7: pytest gate + Rule 1 error message fixes

### Key Files Exist

All 9 source files verified present (packages/wiki-io, workspace-io, and 7 command files).

## Self-Check: PASSED
