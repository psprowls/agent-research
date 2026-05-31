---
id: S04
parent: M002
milestone: M002
provides:
  - Plugin Bedrock shims invoke `gw` with current command shapes.
  - Current user-facing/runtime docs describe v1.12 packages and `gw` usage.
  - MCP graph command guidance points at `gw graph ...`.
  - Regression tests guard shim argv mapping and docs-facing stale executable guidance.
requires:
  - slice: S02
    provides: `gw` console script and current graph-wiki-cli command entrypoint used by docs and plugin shims.
affects:
  - S05
key_files:
  - plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py
  - plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py
  - packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py
  - README.md
  - plugins/graph-wiki/README.md
  - plugins/graph-wiki/CLAUDE.md
  - plugins/graph-wiki/.claude-plugin/plugin.json
  - packages/graph-wiki-cli/tests/unit/test_runtime_docs.py
  - packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
key_decisions:
  - MCP tool descriptions are active runtime-facing guidance during CLI command renames and must be updated alongside docs and shim scripts.
patterns_established:
  - Use package-local shim argv tests with fake subprocess execution to prove plugin runtime command mappings without AWS Bedrock.
  - Guard current runtime docs against stale executable names while allowing explicit negative tests, historical artifacts, and preserved plugin identity strings.
observability_surfaces:
  - No new runtime telemetry; package-local tests and real `gw ... --help` checks are the diagnostic surfaces for this slice.
drill_down_paths:
  - .gsd/milestones/M002/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-31T17:08:56.040Z
blocker_discovered: false
---

# S04: Runtime docs and graph-wiki workflow rewiring

**Runtime-facing graph-wiki Bedrock shims, docs, and MCP guidance now invoke the `gw` CLI instead of the removed `graph-wiki-agent` executable.**

## What Happened

S04 consumed S02's `gw` console script and rewired the current runtime-facing graph-wiki surfaces to that command. T01 updated the five plugin Bedrock shim scripts so they dispatch through `gw` using the current CLI command shapes: `scan`, `bootstrap`, `ingest source`, `lint`, and `query`; package-local regression coverage now proves each shim's subprocess argv contract without requiring AWS Bedrock. T02 updated the current user-facing/runtime docs (`README.md`, plugin README, plugin CLAUDE.md, and plugin.json) to describe the v1.12 package layout and `gw` usage while preserving allowed plugin identity strings. T03 performed integration closeout, found that MCP tool descriptions were also active runtime-facing command guidance, and corrected those descriptions from stale `graph-wiki-agent graph ...` examples to `gw graph ...`. The final result is that the slice's runtime-facing scope no longer instructs users or plugin shims to execute `graph-wiki-agent`; remaining broader stale-reference cleanup and package-only workspace integration remain S05-owned.

## Verification

Fresh closeout verification passed through `gsd_exec`. Evidence: `adff0d73-42f2-47b3-a97d-6fe7ce2ac4a7` ran the required package-local checks: `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py` (5 passed), `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_runtime_docs.py` (3 passed), and `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests` (86 passed, 12 snapshots passed). The same verification scanned the S04 runtime-facing scope and found no `graph-wiki-agent` references in edited docs, shim scripts, or MCP server guidance. Evidence `ba81297b-3531-414a-9693-f33b17f7c6b6` separately verified focused real-entrypoint help checks for `gw bootstrap --help`, `gw ingest source --help`, and `gw graph {build,describe,query} --help`; all exited 0.

## Requirements Advanced

- R007 — Provided verified runtime-facing `gw` wiring and package-local CLI test evidence for S05's full workspace verification.

## Requirements Validated

- R005 — S04 closeout verified five Bedrock plugin shims dispatch to `gw`, real `gw` help checks for runtime-facing commands exit 0, and the S04 runtime-facing scope contains no stale `graph-wiki-agent` executable guidance.
- R008 — Runtime docs guard tests passed, edited current docs describe the v1.12 package layout and `gw` usage, and the guarded docs scan found no stale `graph-wiki-agent` executable guidance.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

- None. — 

## Operational Readiness

None.

## Deviations

T03 found active MCP tool descriptions that were not listed in the original S04 file scope. They were correctly classified as runtime-facing guidance, updated from `graph-wiki-agent graph ...` to `gw graph ...`, and covered by focused CLI/MCP verification.

## Known Limitations

No live AWS Bedrock run was performed or required for this slice. S05 still owns full workspace integration, root sync, obsolete `agents/` cleanup, broad stale-reference cleanup outside the S04 runtime-facing scope, and full integration tests.

## Follow-ups

S05 should use the S04 stale-reference classification when doing broad cleanup: distinguish negative tests, historical artifacts, and plugin identity strings from active executable guidance.

## Files Created/Modified

- `plugins/graph-wiki/skills/graph-wiki/scripts/scan_monorepo.py` — Rewired scan shim subprocess invocation to `gw scan`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py` — Rewired bootstrap shim subprocess invocation to `gw bootstrap`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py` — Rewired ingest shim subprocess invocation to `gw ingest source`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py` — Rewired lint shim subprocess invocation to `gw lint`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py` — Rewired query/search shim subprocess invocation to `gw query`.
- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py` — Added regression coverage for all five plugin Bedrock shim argv mappings.
- `README.md` — Updated user-facing package layout and command guidance for v1.12 `gw` usage.
- `plugins/graph-wiki/README.md` — Updated plugin-facing runtime docs to use `gw` command guidance.
- `plugins/graph-wiki/CLAUDE.md` — Updated runtime instructions to point at `gw` while preserving plugin identity boundaries.
- `plugins/graph-wiki/.claude-plugin/plugin.json` — Updated current plugin metadata/docs-facing command guidance while preserving allowed identity strings.
- `packages/graph-wiki-cli/tests/unit/test_runtime_docs.py` — Added docs guard tests against stale `graph-wiki-agent` executable guidance.
- `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` — Updated MCP tool descriptions from stale `graph-wiki-agent graph ...` examples to `gw graph ...`.
