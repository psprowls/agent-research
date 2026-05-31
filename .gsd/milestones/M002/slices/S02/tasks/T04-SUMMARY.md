---
id: T04
parent: S02
milestone: M002
key_files:
  - uv.lock
  - packages/graph-wiki-cli/pyproject.toml
  - packages/graph-wiki-cli/src/graph_wiki_cli/cli.py
  - packages/graph-wiki-cli/tests/unit/test_cli_boundary.py
key_decisions:
  - Allowed `graph_wiki_agent` references only inside graph-wiki-cli boundary tests when they are negative assertions proving the extracted CLI no longer imports or exposes the agent CLI surface.
duration: 
verification_result: passed
completed_at: 2026-05-31T16:37:13.001Z
blocker_discovered: false
---

# T04: Synced the uv workspace and proved the new graph-wiki-cli gw console script launches through the package boundary.

**Synced the uv workspace and proved the new graph-wiki-cli gw console script launches through the package boundary.**

## What Happened

Ran `uv sync` to refresh workspace resolution and lockfile state for the extracted `graph-wiki-cli` package. Verified the import surface by importing `graph_wiki_cli.cli` through `uv run --package graph-wiki-cli` and confirming the Typer app name is `gw`. Exercised the real installed `gw` console script for both root help and `query` command help with plain terminal environment settings. Ran the full package-local CLI test suite and the explicit boundary test module. A raw stale-reference grep surfaced only the boundary test's negative assertions against `graph_wiki_agent`; I followed up with a classified stale-reference check that permits those negative assertions while failing any command-facing stale imports, scripts, help text, or assertions.

## Verification

Verified workspace sync, CLI import smoke, real console-script help, package-local tests, boundary tests, stale-reference classification, and lockfile inclusion. All final verification commands passed: `uv sync`; `uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"` printed `gw`; both `gw --help` and `gw query --help` exited 0; `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests` passed 78 tests and 12 snapshots; `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` passed 3 tests; the classified stale-reference check found no stale command-facing references; and `uv.lock` contains the `graph-wiki-cli` package entry.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv sync` | 0 | ✅ pass | 82ms |
| 2 | `uv run --package graph-wiki-cli python -c "import graph_wiki_cli.cli as c; print(c.app.info.name)"` | 0 | ✅ pass (`gw`) | 1123ms |
| 3 | `NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw --help` | 0 | ✅ pass | 1175ms |
| 4 | `NO_COLOR=1 TERM=dumb COLUMNS=200 uv run --package graph-wiki-cli gw query --help` | 0 | ✅ pass | 1177ms |
| 5 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests` | 0 | ✅ pass (78 passed, 12 snapshots passed) | 16972ms |
| 6 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` | 0 | ✅ pass (3 passed) | 2342ms |
| 7 | `classified stale-reference scan for graph_wiki_agent|graph-wiki-agent under packages/graph-wiki-cli` | 0 | ✅ pass (only allowed negative boundary-test assertions) | 53ms |
| 8 | `python check that uv.lock contains name = "graph-wiki-cli"` | 0 | ✅ pass | 43ms |

## Deviations

Added an explicit classified stale-reference verification after the broad grep found only intended negative boundary-test strings. No code changes were needed.

## Known Issues

None.

## Files Created/Modified

- `uv.lock`
- `packages/graph-wiki-cli/pyproject.toml`
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
