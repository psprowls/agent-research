---
phase: 45-scanner-integration
plan: 03
subsystem: scanner-integration
tags: [scan_command, run_scan, write_entities, narrator, inject_narrative, generate_index, dual-writer]

requires:
  - phase: 43-entity-writer
    provides: write_entities, ADMITTED_KINDS_V18, _kind_list_fns, encode_slug, EntityWriteResult
  - phase: 44-scanner-generated-index
    provides: generate_index(conn, wiki) -> IndexWriteResult
  - phase: 45-scanner-integration (Plan 01)
    provides: inject_narrative, scanner_frontmatter_for_node, [roles.narrator], update_index surgical change
  - phase: 45-scanner-integration (Plan 02)
    provides: ExistingPages dataclass + entities walk

provides:
  - "ScanResult extended with entities_created/_updated/_deleted/_narrated/entity_errors"
  - "build_entity_narrative_prompt(node, kind, file_map_text, relations) helper"
  - "run_scan Steps 5/7/9a/9b/10/11/12/13 rewired for v1.8 entity workflow"
  - "End-to-end integration test suite (8 tests) covering write_entities + narrator + dual-writer indexes"

affects: [46-inbound-link-migration-cutover]

tech-stack:
  added: []
  patterns:
    - "Step 9 split: synchronous write_entities (Step 9a) + async narrator fan-out (Step 9b) gated on needs_narrative"
    - "Step 12 dual writer: generate_index produces wiki/index.md; update_index produces per-folder sub-indexes"
    - "model_override repurposed for the narrator role (legacy scanner override path removed)"
    - "Pre-scan cg update monkeypatched in integration tests via _capture_run override (sidesteps git/cg dependency)"

key-files:
  created:
    - agents/graph-wiki-agent/tests/unit/test_scan_result_shape.py
    - agents/graph-wiki-agent/tests/unit/test_entity_narrative_prompt.py
    - agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - agents/graph-wiki-agent/tests/test_command_overrides.py
    - agents/graph-wiki-agent/tests/unit/test_commands_scan.py
    - agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py

key-decisions:
  - "D-08 hard cutover: removed the legacy scanner pool (SubagentPool with role='scanner') and the wiki/packages/<n>/<n>.md write loop in Step 10. The v1.7 tests that validated this behavior were marked with `_PHASE_45_LEGACY_REMOVED` (4 tests skipped with rationale)."
  - "model_override semantics under v1.8: now targets the narrator role (the only LLM in run_scan). test_run_scan_model_override updated and the comment block explains the migration."
  - "test_conn_closed_on_exception switched to raise from `write_entities` (Step 9a) instead of the removed scanner pool. Same conn-lifecycle assertion holds."
  - "ExitStack used in test_run_scan_model_override because Python 3.11 caps `with` statements at 20 entries; the test needs ~22 patches under v1.8."
  - "Removed unused imports `build_scanner_system`, `render_project_context`, and the now-unused `project_ctx` local. ChatBedrockConverse retained for `model_override`."

patterns-established:
  - "Narrator pool reuses the existing SubagentPool surface — items are (uri, kind, node) tuples; the per-item task closure resolves relations via scanner_frontmatter_for_node and builds the prompt via build_entity_narrative_prompt."
  - "Step 12 order: regenerate_dependencies_index → generate_index → update_index. The first two only fire when conn is not None (NOT_INITIALIZED fallback skips them); update_index always fires (filesystem-based)."

requirements-completed:
  - SCANINT-01
  - SCANINT-02
  - SCANINT-03
  - SCANINT-04
  - SCANINT-06

duration: ~30min
completed: 2026-05-27
---

# Plan 45-03: run_scan rewiring + ScanResult + narrator pipeline Summary

**run_scan now threads write_entities (Step 9a) + narrator fan-out (Step 9b) + inject_narrative (Step 10) + dual-writer index (Step 12) into the scan pipeline — v1.8 entity workflow shipped end-to-end with 8 integration tests verifying the call graph, gating, and frontmatter integrity.**

## Performance

- **Duration:** ~30 minutes
- **Started:** 2026-05-27T15:00Z
- **Completed:** 2026-05-27T15:30Z
- **Tasks:** 4 (3 commits + 1 final integration commit)
- **Files modified:** 7 (1 src + 6 tests including 3 new test files)

## Accomplishments

- `ScanResult` extended with 5 URI-keyed entity fields per D-15 (test_scan_result_shape locks the field set).
- `build_entity_narrative_prompt(node, kind, file_map_text, relations)` per D-05 — system message bans frontmatter/H1/H2, references `## Narrative` anchor; human message includes URI/kind/name + relations as CSV.
- `run_scan` rewired:
  - Step 5/6/7: unpack `existing_pages.legacy` for downstream `attach_changed_files`/`compute_diff` callers (D-11/D-12).
  - Step 9a: `write_entities(conn, wiki, ADMITTED_KINDS_V18)` runs once when `conn is not None`; logs entity counts and `needs_narrative` size.
  - Step 9b: narrator fan-out gated on `entity_write_result.needs_narrative` — pool not instantiated when set is empty (D-04).
  - Step 10: legacy `wiki/packages/<n>/<n>.md` write block REMOVED (D-08); replaced with per-narrator-success `inject_narrative` calls.
  - Step 11: switched to `existing_pages.legacy.get(...)` (D-09/D-10 unchanged behavior).
  - Step 12: dual writer — `generate_index(conn, wiki)` (Phase 44) FIRST, then `update_index(wiki)` SECOND.
  - Step 13: log line follows the D-16 format with both legacy and entity counts.
- End-to-end integration test suite (`test_scan_entity_integration.py`) — 8 tests against a real on-disk sqlite graph + wiki tree; narrator LLM stubbed (no Bedrock).

## Task Commits

1. **Task 1: Extend ScanResult dataclass + snapshot test** — `cecb40c` (feat)
2. **Task 2: build_entity_narrative_prompt helper + unit tests** — `23512bf` (feat)
3. **Task 3: Rewire Steps 5/9a/9b/10/11 in run_scan** — `63649cd` (feat)
4. **Task 4: End-to-end integration suite (Step 12 was wired in Task 3)** — `af88cc7` (test)

## Files Created/Modified

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — ScanResult expansion, build_entity_narrative_prompt helper, run_scan rewire (Steps 5/6/7/9a/9b/10/11/12/13). Imports updated to bring in Phase 43 + 44 + Plan 01/02 surfaces; unused imports removed.
- `agents/graph-wiki-agent/tests/unit/test_scan_result_shape.py` — 4 snapshot tests (field set + types + default + populated construction)
- `agents/graph-wiki-agent/tests/unit/test_entity_narrative_prompt.py` — 12 unit tests (system bans, human field rendering, file-map gating, scalar relations, return shape)
- `agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py` — 8 end-to-end tests against real sqlite graph + wiki tree
- `agents/graph-wiki-agent/tests/test_command_overrides.py` — `test_run_scan_model_override` rewritten to v1.8 narrator-override semantics (ExitStack to bypass Python 3.11's nested-`with` cap)
- `agents/graph-wiki-agent/tests/unit/test_commands_scan.py` — 4 legacy fan-out tests marked `_PHASE_45_LEGACY_REMOVED`; 2 still-valid tests (stale-tag, repo_path override) updated to return `ExistingPages`
- `agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py` — 3 monkeypatch sites updated to return `ExistingPages`; `test_conn_closed_on_exception` switched to raise from `write_entities` instead of the removed scanner pool

## Decisions Made

- Legacy scanner fan-out is fully removed; 4 v1.7 tests skipped with a clear `_PHASE_45_LEGACY_REMOVED` marker pointing to the integration suite as their replacement. (Per the plan: "updating test fixtures that expected the legacy ScanResult shape or the legacy `wiki/packages/<n>/<n>.md` writes".)
- `model_override` now targets the narrator role under v1.8. The override test was rewritten to mock `write_entities` + `_kind_list_fns` so the narrator pool fires; verified `ChatBedrockConverse(model_id=candidate)` is called and `make_llm("narrator")` is NOT.
- Conn-closure-on-exception now exercised via `write_entities` raising (it runs inside the same `try` block).

## Deviations from Plan

- **Task 3 vs Task 4 split:** the plan put Step 12 wiring in Task 4. I included it in the Task 3 commit because the import (`generate_index`) was already added in Task 3 and isolating just the Step 12 call site for a separate commit added no value. Task 4's commit is now purely the integration test suite. Verification criteria unchanged.
- **ExitStack in test_run_scan_model_override:** the plan's example uses nested `with (...)` blocks. Python 3.11 hits a `SyntaxError: too many statically nested blocks` past 20 entries. Substituted `contextlib.ExitStack`; semantics identical.
- **test_conn_closed_on_exception migration:** the plan didn't call out this specific test; the failure surfaced during Task 3 regression runs and was fixed in the same Task 3 commit (raised from `write_entities` instead of the removed scanner pool).

## Issues Encountered

- 9 pre-existing agent tests failed on first run after Step 5 rewire because they mocked `_load_existing_pages` to return `{}`. Fixed per the plan's Task 2 acceptance criterion ("fix by indexing through `.legacy` instead"). 5 tests still validated the legacy fan-out path which no longer exists — those were skipped with `_PHASE_45_LEGACY_REMOVED`.
- Initial integration test fixture passed `workspace_path=wiki` but `resolve_wiki_and_repo(workspace_path)` calls `wiki_dir(workspace_path)` which appends `/wiki`. Fixed by passing `workspace_path=workspace` (the workspace root).

## Self-Check: PASSED

```text
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_scan_result_shape.py -x             → 4 passed
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_entity_narrative_prompt.py -x      → 12 passed
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py -x → 8 passed
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/                                              → 315 passed, 11 skipped
uv run --package wiki-io pytest packages/wiki-io                                                                     → 295 passed, 2 skipped
uv run --package wiki-io pytest packages/wiki-io/tests/test_scan_monorepo.py -x                                       → 29 passed (SCANINT-06 plugin smoke)
uv run python -c "from graph_wiki_agent.commands.scan import run_scan, ScanResult, build_entity_narrative_prompt; print('ok')"
```

Acceptance grep checks:
- `grep -c "page_path.write_text(final_page" scan.py` → 0 (legacy Step 10 write removed)
- `grep -c "write_entities(conn, wiki, ADMITTED_KINDS_V18)" scan.py` → 1
- `grep -c 'make_llm("narrator")' scan.py` → 1
- `grep -c "inject_narrative(entity_page_path" scan.py` → 1
- `grep -c "generate_index(conn, wiki)" scan.py` → 1
- `grep -c "update_index(wiki)" scan.py` → 1

## Next Phase Readiness

Phase 45 ships the agent-side cutover to entity-driven scans:

- `wiki/entities/` is now the only location new graph-derived pages are written.
- `wiki/index.md` is graph-driven (generate_index); per-folder sub-indexes still flow through update_index.
- `wiki/packages/`, `wiki/dependencies/`, `wiki/domain/`, `wiki/plugin/`, `wiki/package-family/` directories may still contain stale legacy pages from prior scans — Phase 46 cutover deletes those.

Phase 46 (Inbound Link Migration + Cutover) can now consume:
- ScanResult.entities_created/_updated/_deleted as the canonical list of admitted entity URIs after a scan
- The dual-writer index as the single source of truth for inbound link rewriting

Plugin smoke regression (SCANINT-06) continues to pass — `plugins/graph-wiki/` stays on legacy layout per D-13 and the v1.8 changes do not bleed into the plugin's code path.

---
*Phase: 45-scanner-integration*
*Completed: 2026-05-27*
