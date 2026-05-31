---
id: T03
parent: S02
milestone: M002
key_files:
  - packages/graph-wiki-cli/tests/unit/test_cli_boundary.py
  - packages/graph-wiki-cli/tests/unit/test_cli_query.py
key_decisions:
  - Kept unresolved-workspace negative coverage in test_cli_query.py rather than duplicating it in the new boundary test file.
duration: 
verification_result: passed
completed_at: 2026-05-31T16:35:21.765Z
blocker_discovered: false
---

# T03: Added graph-wiki-cli boundary tests that lock the gw console script to graph_wiki_cli.cli:app and reject stale graph-wiki-agent CLI dependencies.

**Added graph-wiki-cli boundary tests that lock the gw console script to graph_wiki_cli.cli:app and reject stale graph-wiki-agent CLI dependencies.**

## What Happened

Created packages/graph-wiki-cli/tests/unit/test_cli_boundary.py with package-local assertions for the extracted CLI surface. The new tests verify the graph-wiki-cli distribution is importable, exposes the gw console script pointing at graph_wiki_cli.cli:app, does not expose a graph-wiki-agent console-script alias, imports graph_wiki_cli.cli successfully, exposes a Typer app named gw, and delegates through graph_wiki_core command imports without depending on graph_wiki_agent.cli. I reviewed the existing query tests and confirmed they already cover the unresolved workspace negative path with controlled exit-code/error-message behavior, so no duplicate query test was added.

## Verification

Ran the planned focused boundary test file, the affected query test file containing the unresolved-workspace negative path, and the full package-local CLI unit suite. All checks passed: 3 boundary tests, 8 query tests, and 76 package-local CLI unit tests with 12 snapshots.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` | 0 | ✅ pass — 3 passed | 2199ms |
| 2 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_cli_query.py` | 0 | ✅ pass — 8 passed | 3831ms |
| 3 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit` | 0 | ✅ pass — 76 passed, 12 snapshots passed | 16565ms |

## Deviations

Did not modify packages/graph-wiki-cli/tests/unit/test_cli_query.py because the relocated tests already included the required unresolved-workspace negative command coverage.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_query.py`
