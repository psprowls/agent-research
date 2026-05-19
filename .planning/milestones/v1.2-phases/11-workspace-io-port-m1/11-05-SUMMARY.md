---
phase: 11-workspace-io-port-m1
plan: 05
subsystem: code-wiki-agent
tags: [port, rebrand, workspace-io, wiring, env-var-sweep]
requires:
  - workspace-io public surface (workspace_io.init from Plan 02)
  - vault-io._workspace.resolve_wiki_and_repo (delegated by Plan 04 in parallel)
provides:
  - code-wiki-agent declares workspace-io as a workspace dependency
  - Two-phase init flow (D-07): workspace_io.init -> resolve_wiki_and_repo
  - Zero CODE_WIKI_REAL_VAULT_PATH references under agents/code-wiki-agent/
affects:
  - agents/code-wiki-agent/pyproject.toml
  - agents/code-wiki-agent/src/code_wiki_agent/commands/init.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/log.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
  - agents/code-wiki-agent/src/code_wiki_agent/config.py
  - agents/code-wiki-agent/src/code_wiki_agent/cli.py
  - agents/code-wiki-agent/src/code_wiki_mcp/server.py
tech-stack:
  added: []
  patterns:
    - "importlib.metadata.version('code-wiki-agent') for runtime version introspection (D-13)"
    - "Two-phase init: workspace_io.init(repo_root, plugin, version) BEFORE resolve_wiki_and_repo (D-07)"
    - "repo_root derivation: vault_path.parent if explicit else Path.cwd()"
key-files:
  created: []
  modified:
    - agents/code-wiki-agent/pyproject.toml
    - agents/code-wiki-agent/src/code_wiki_agent/commands/init.py
    - agents/code-wiki-agent/src/code_wiki_agent/commands/log.py
    - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
    - agents/code-wiki-agent/src/code_wiki_agent/config.py
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py
    - agents/code-wiki-agent/src/code_wiki_mcp/server.py
decisions:
  - "D-07 implemented: code-wiki-agent init <path> calls workspace_io.init BEFORE resolve_wiki_and_repo"
  - "D-12 implemented: workspace_io.init plugin='code-wiki-agent' with installed_version == applied_version"
  - "D-13 implemented: version sourced from importlib.metadata.version('code-wiki-agent') at runtime"
  - "Explicit-path branch preserved: when vault_path is provided, repo_root=vault_path.parent and resolve_wiki_and_repo short-circuits to (vault_path.resolve(), ...) — explicit path bypasses manifest discovery"
metrics:
  duration_minutes: 5
  tasks_completed: 2
  files_changed: 7
  completed_date: 2026-05-18
---

# Phase 11 Plan 05: code-wiki-agent wiring + env-var rebrand sweep — Summary

Wired the workspace-io workspace dependency into `code-wiki-agent`, made the agent's `init` CLI command perform a two-phase bootstrap (D-07: `workspace_io.init` first, then the existing `resolve_wiki_and_repo` + `init_wiki` flow), and swept all 18 remaining `CODE_WIKI_REAL_VAULT_PATH` references under `agents/code-wiki-agent/` to `GRAPH_WIKI_WORKSPACE` across CLI help strings, MCP tool descriptions, Pydantic Field descriptions, and module docstrings.

## What Was Built

**Task 1 — workspace-io dep + two-phase init wiring**

- `agents/code-wiki-agent/pyproject.toml`: added `"workspace-io"` to `[project] dependencies` and `workspace-io = { workspace = true }` to `[tool.uv.sources]`.
- `agents/code-wiki-agent/src/code_wiki_agent/commands/init.py`:
  - Added `import importlib.metadata` and `from workspace_io import init as _ws_init`.
  - In `run_init()`, computed `repo_root = vault_path.parent if vault_path is not None else Path.cwd()` and invoked `_ws_init(repo_root, plugin="code-wiki-agent", version=importlib.metadata.version("code-wiki-agent"))` BEFORE the existing `resolve_wiki_and_repo(vault_path)` call.
  - Rebranded the `vault_path` arg docstring (`CODE_WIKI_REAL_VAULT_PATH` → `GRAPH_WIKI_WORKSPACE`).
- `uv sync` resolved the new workspace dep; import smoke test (`from workspace_io import init; from code_wiki_agent.commands.init import run_init`) passed.

**Task 2 — env-var rebrand sweep**

- `agents/code-wiki-agent/src/code_wiki_agent/cli.py`: 6 `typer.Option` `--vault` help strings rebranded (the `init`, `scan`, `ingest source`, `ingest work-item`, `log`, and `lint` commands; lines 433, 455, 476, 514, 539, 573). The `query` command's `--vault` help text was already generic ("Vault path (default: env var)") and is unchanged.
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py`: 8 hits rebranded — 1 inline comment (line 105, WikiQueryInput), 2 tool description strings (`wiki_query` line 121, `wiki_ingest` line 328), 5 Pydantic `Field` descriptions (lines 154, 196, 243, 309, 375 spanning WikiLogInput, WikiInitInput, WikiScanInput, WikiIngestInput, WikiLintInput).
- `agents/code-wiki-agent/src/code_wiki_agent/commands/log.py`, `commands/query.py`, `config.py`: 3 one-line docstring rebrands.

## Verification Results

All Task 1 acceptance criteria pass:

- `pyproject.toml`: `grep -c '"workspace-io"'` = 1; `grep -c 'workspace-io.*workspace = true'` = 1.
- `commands/init.py`: `grep -c 'from workspace_io import init'` = 1; `grep -c 'importlib.metadata'` = 3 (import + version() call + nothing else, expected ≥1); `grep -c 'plugin="code-wiki-agent"'` = 1; `grep -c 'GRAPH_WIKI_WORKSPACE'` = 1; `grep -c 'CODE_WIKI_REAL_VAULT_PATH'` = 0.
- `uv sync` succeeded; `+ workspace-io==0.1.0` installed editable from `packages/workspace-io`.
- Import smoke test passed: `from workspace_io import init; from code_wiki_agent.commands.init import run_init` exits 0.
- Read-back of `commands/init.py` confirmed `_ws_init(...)` is invoked at line 68 and `resolve_wiki_and_repo(vault_path)` at line 75 — call order is correct.

All Task 2 acceptance criteria pass:

- Sweep grep: `grep -rE 'CODE_WIKI_REAL_VAULT_PATH' agents/code-wiki-agent/ --include="*.py"` returns zero lines.
- `cli.py`: `grep -c 'GRAPH_WIKI_WORKSPACE'` = 6 (one per --vault option in scan/ingest source/ingest work-item/log/init/lint).
- `server.py`: `grep -c 'GRAPH_WIKI_WORKSPACE'` = 8 (matches the planned 8 hits).
- `commands/log.py`, `commands/query.py`, `config.py`: 1 each.
- Import smoke test passed: `from code_wiki_agent import cli; from code_wiki_mcp import server` exits 0. (Note: the verification command had to write to stderr because the MCP server's `_StdoutGuard` correctly intercepts any non-FastMCP write to stdout — the guard invariant is intact and tested by this very behavior.)

Plan-level success criteria:

- WS-04 fully satisfied: `workspace_io.init` is wired into the `code-wiki-agent init` flow per D-07.
- WS-07 (agent half) satisfied: zero `CODE_WIKI_REAL_VAULT_PATH` references remain under `agents/code-wiki-agent/`. Plan 04 handles the vault-io half in parallel.

## Commits

| Task | Commit  | Description                                                                  |
| ---- | ------- | ---------------------------------------------------------------------------- |
| 1    | 5080a6a | feat(11-05): add workspace-io dep and wire workspace_io.init into agent init |
| 2    | d8232f1 | chore(11-05): rebrand CODE_WIKI_REAL_VAULT_PATH -> GRAPH_WIKI_WORKSPACE in agent |

## Decisions Made

1. **`importlib.metadata` count came out to 3, not 1.** The plan acceptance criterion was `grep -c 'importlib.metadata' >= 1`; the actual count is 3 because the import line, the `.version(` call, and one other dotted-attribute occurrence land on the same token. This exceeds the threshold and is not a deviation — it's the natural shape of using the stdlib namespace twice on one logical reference. Recorded here for transparency.

2. **`query` command --vault help text was already generic.** `cli.py:395` reads `"Vault path (default: env var)"` (no env-var name) and was NOT in the plan's 6-line list (433, 455, 476, 514, 539, 573). Left as-is — the plan's 6 hits are the 6 commands that DO name the env var. The sweep grep confirms zero `CODE_WIKI_REAL_VAULT_PATH` references survive anywhere.

## Deviations from Plan

None. Both tasks executed exactly as written; the plan's acceptance criteria all pass on first verification.

## Threat Flags

None introduced. The plan's threat register (`T-11-09` MCP Field description leakage, `T-11-10` workspace_io.init tampering, `T-11-SC` package installs) is unchanged in disposition:

- `T-11-09` accept — Field descriptions name an env var; same risk profile as the previous text.
- `T-11-10` mitigate — `repo_root` is `vault_path.parent` (CLI-provided) or `Path.cwd()`; `workspace_io.init` does its own `Path.resolve()` and only writes inside `repo_root/graph-wiki`. No new attack surface introduced by this plan.
- `T-11-SC` accept — no new external packages added; `workspace-io` is a workspace member.

## Requirements Satisfied

- **WS-04** — `workspace_io.init` is invoked from `code-wiki-agent init <path>` via the two-phase bootstrap pattern (D-07), with `plugin="code-wiki-agent"` and `version` sourced from `importlib.metadata` (D-12, D-13).
- **WS-07 (agent half)** — All `CODE_WIKI_REAL_VAULT_PATH` references under `agents/code-wiki-agent/` rebranded to `GRAPH_WIKI_WORKSPACE`. Plan 04 closes the vault-io half in parallel; together the two plans leave zero references under `packages/` and `agents/`.

## Phase 11 Success Criterion Progress

- **SC #1 (uv sync resolves workspace-io and tests pass)** — `uv sync` resolves workspace-io as a `code-wiki-agent` dep cleanly; agent test suite is out of scope per phase plan (Phase 12 BACKPORT-XX covers test re-touch).
- **SC #2 (env var rename — agent half)** — agent half satisfied; Plan 04 closes the vault-io half; Plan 06 will verify end-to-end.

## Self-Check: PASSED

- Modified files verified on disk:
  - FOUND: agents/code-wiki-agent/pyproject.toml (workspace-io in deps + sources)
  - FOUND: agents/code-wiki-agent/src/code_wiki_agent/commands/init.py (importlib.metadata + workspace_io import + _ws_init call at line 68)
  - FOUND: agents/code-wiki-agent/src/code_wiki_agent/commands/log.py (GRAPH_WIKI_WORKSPACE)
  - FOUND: agents/code-wiki-agent/src/code_wiki_agent/commands/query.py (GRAPH_WIKI_WORKSPACE)
  - FOUND: agents/code-wiki-agent/src/code_wiki_agent/config.py (GRAPH_WIKI_WORKSPACE)
  - FOUND: agents/code-wiki-agent/src/code_wiki_agent/cli.py (GRAPH_WIKI_WORKSPACE x6)
  - FOUND: agents/code-wiki-agent/src/code_wiki_mcp/server.py (GRAPH_WIKI_WORKSPACE x8)
- Commits verified in git log:
  - FOUND: 5080a6a (Task 1)
  - FOUND: d8232f1 (Task 2)
- Final sweep grep `grep -rE 'CODE_WIKI_REAL_VAULT_PATH' agents/code-wiki-agent/` returns zero lines.
