---
id: T03
parent: S04
milestone: M002
key_files:
  - packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
key_decisions:
  - Classified MCP tool descriptions as active runtime-facing guidance rather than historical references, and updated them to mirror `gw graph ...`.
duration: 
verification_result: passed
completed_at: 2026-05-31T17:06:39.212Z
blocker_discovered: false
---

# T03: Verified the S04 `gw` runtime integration contract and removed stale MCP-facing `graph-wiki-agent` command guidance.

**Verified the S04 `gw` runtime integration contract and removed stale MCP-facing `graph-wiki-agent` command guidance.**

## What Happened

Ran real `gw` help entrypoints through `uv run --package graph-wiki-cli` for `bootstrap`, `ingest source`, and the graph subcommands needed to classify MCP tool descriptions. The focused shim/docs tests and the full `packages/graph-wiki-cli/tests` suite passed. The stale-reference scan over `README.md`, `plugins/graph-wiki`, and `packages/graph-wiki-*` initially found three active MCP tool descriptions that still said they mirrored `graph-wiki-agent graph ...`; those were active user-facing MCP metadata, so I updated them to `gw graph ...`. The final scan has 13 remaining occurrences, all classified as negative tests/guards: CLI boundary assertions reject `graph-wiki-agent` console scripts/imports, runtime-docs regexes detect stale command guidance, and the MCP package-boundary test uses a deliberately stale subprocess string to prevent regression. No remaining active runtime-facing executable guidance to `graph-wiki-agent` was found in S04-owned files.

## Verification

Verified `gw bootstrap --help`, `gw ingest source --help`, and `gw graph {build,describe,query} --help` through real `uv run --package ...` entrypoints. Ran focused shim/docs tests, the full graph-wiki-cli test suite after cleanup, the graph-wiki-mcp package-boundary test, and the final stale-reference scan. All command checks passed; final scan showed only negative-test references.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package graph-wiki-cli gw bootstrap --help && uv run --package graph-wiki-cli gw ingest source --help` | 0 | ✅ pass | 1191ms |
| 2 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py packages/graph-wiki-cli/tests/unit/test_runtime_docs.py` | 0 | ✅ pass, 8 passed | 1246ms |
| 3 | `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests` | 0 | ✅ pass, 86 passed / 12 snapshots passed | 16415ms |
| 4 | `uv run --package graph-wiki-cli gw graph --help && uv run --package graph-wiki-cli gw graph build --help && uv run --package graph-wiki-cli gw graph describe --help && uv run --package graph-wiki-cli gw graph query --help` | 0 | ✅ pass | 2310ms |
| 5 | `python stale-reference scan over README.md, plugins/graph-wiki, packages/graph-wiki-*` | 0 | ✅ pass, 13 remaining matches all classified as negative tests/guards | 89ms |
| 6 | `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests/unit/test_mcp_package_boundary.py` | 0 | ✅ pass, 2 passed | 1225ms |

## Deviations

The stale-reference classification found active MCP tool descriptions that were not listed as expected edits in the task plan; I corrected those runtime-facing descriptions from `graph-wiki-agent graph ...` to `gw graph ...` and verified the relevant CLI/MCP tests.

## Known Issues

None.

## Files Created/Modified

- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
