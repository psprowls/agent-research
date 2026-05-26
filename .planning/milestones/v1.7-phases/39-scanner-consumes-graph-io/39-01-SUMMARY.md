---
phase: 39-scanner-consumes-graph-io
plan: 01
subsystem: agent
tags: [scanner, graph-io, decoration, cg-update, fallback]

requires:
  - phase: 38-graph-wiki-agent-graph-subcommand
    provides: _build_namespace, _capture_run, ops_update helpers for in-process cg dispatch
  - phase: 37-librarian-grounding-tools
    provides: read_only_connect lifetime pattern (try/finally) mirrored here
  - phase: 35-wiki-bootstrap-hygiene-burn-down
    provides: _wiki_relative_path_for routing rules (apps/domains/packages)

provides:
  - run_scan() calls `cg update` (incremental, no-trace, no-model) before fan-out
  - workspace dicts gain pkg["uri"] + pkg["domain"] from graph after successful update
  - wiki_relative_path is recomputed when graph domain differs from filesystem default
  - ScanAbortedError hard-aborts on non-recoverable cg failures
  - NOT_INITIALIZED fallback line emitted only on filesystem init-failure stderr patterns
  - Single read-only sqlite conn per scan, closed in finally

affects: [40-ingestor-consumes-graph-io, downstream scan→vault rendering]

tech-stack:
  added: []  # No new third-party deps; uses existing graph_io / workspace_io modules
  patterns:
    - "Pre-action incremental cg update before pipeline fan-out (mirrors librarian's pre-flight)"
    - "Stderr-pattern matcher for distinguishing init-failure (graceful) vs runtime-failure (hard abort)"
    - "Workspace-root vs wiki-dir convention: pass workspace ROOT to ops_update; read DB via graph_dir(wiki.parent)"

key-files:
  created:
    - agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py
    - agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - agents/graph-wiki-agent/tests/unit/test_commands_scan.py
    - agents/graph-wiki-agent/tests/commands/test_scan_parity.py

key-decisions:
  - "Pass workspace ROOT (wiki.parent), not wiki, to ops_update — corrects plan must_have drift; aligns with Phase 38 graph.py + Phase 37 librarian read path"
  - "Use _query_package_uris helper reading nodes.uri column directly — list_packages' NodeRecord doesn't surface uri because upsert.py pops it from attrs"
  - "Gate decoration on queries.list_packages(conn) name set — short-circuits packages absent from graph and satisfies must_have literal"
  - "Init-failure stderr-pattern match is conservative (false positives → fallback; false negatives → hard abort) — both safe-side per RESEARCH §11"

patterns-established:
  - "Try/finally conn lifecycle in async pipelines — wraps the entire body once, conn=None default, closed defensively in finally with bare Exception swallow"
  - "Pre-scan graph refresh via in-process cg helper — no subprocess, no MCP _StdoutGuard violation (Phase 38 D-06 in-process pattern)"

requirements-completed: [SCANNER-01, SCANNER-02, SCANNER-03]

duration: 35 min
completed: 2026-05-26
---

# Phase 39 Plan 01: Scanner Consumes graph-io Summary

**run_scan now dispatches `cg update` before fan-out, decorates every workspace dict with `pkg["uri"]` + `pkg["domain"]` from the graph (recomputing the vault slug on domain change), and enforces a strict error policy with a stderr-pattern-matched filesystem-init fallback.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 5/5 completed (1 pre-condition, 1 TDD test, 1 implementation, 1 e2e integration, 1 regression verification)
- **Files modified:** 5 (1 source, 2 new tests, 2 existing tests retro-fitted to stub the new cg-update path)
- **Commits:** 4 task commits + this metadata commit

## Accomplishments

- **SC#1 satisfied** — `cg update` runs as Step 1.5 in `run_scan` before any fan-out and before `discover_workspaces`; the scan log records `cg update complete: exit_code=0` (verified by unit test `test_cg_update_logs_success` and asserted in the e2e test).
- **SC#2 satisfied** — Decoration step stamps `pkg["uri"]` from `nodes.uri` and `pkg["domain"]` from `belongs_to_domain` for every workspace whose `unscope(name)` is a known graph package node; the wiki_relative_path is recomputed via `_wiki_relative_path_for` only when the graph domain changes the routing.
- **SC#3 satisfied by reference** — Phase 35's `test_bootstrap_e2e_no_broken_links.py` stays green; `git diff packages/wiki-io/` is empty; no scan_monorepo.py modifications.
- **D-07 hard-abort path** — `ScanAbortedError` raised on NOT_IN_GIT_REPO / UPDATE_IN_PROGRESS / SCHEMA_MISMATCH / unknown-GENERIC; pool fan-out is never invoked; no fallback line emitted.
- **D-08 graceful fallback** — GENERIC exit + init-pattern stderr (`Permission denied`, `Read-only file system`, `No space left on device`, `Errno 13/28/30`) emits exactly one `[NOT_INITIALIZED fallback: ...]` line and proceeds with path-based slugs.
- **D-05 conn lifecycle** — Single `read_only_connect` per scan; closed in `finally` even when fan-out raises (proven by `test_conn_closed_on_exception`).

## Task Commits

1. **Task 1: Pre-condition gate** — verification only, no commit (probe printed `ok`; Phase 38 helpers importable).
2. **Task 2: TDD unit tests (RED)** — `ac35c9d` (`test(39-01): add failing scan→graph integration tests`)
3. **Task 3: Modify run_scan (GREEN)** — `9d0aac3` (`feat(39-01): wire run_scan to graph-io via cg update + decoration`) + `cf064a0` (`feat(39-01): use queries.list_packages to gate decoration`)
4. **Task 4: e2e integration test + workspace-arg fix** — `ca830ef` (`test(39-01): add end-to-end integration test + fix cg workspace arg`)
5. **Task 5: SC#3 regression verification** — verification only, no commit (Phase 35 bootstrap test passes; `git diff packages/wiki-io/` empty).

## Files Created/Modified

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — added `ScanAbortedError`, `_INIT_FAILURE_STDERR_PATTERNS`, `_is_init_failure_stderr`, `_query_package_domains`, `_query_package_uris`; restructured `run_scan` with try/finally + Step 1.5 (cg update) + Step 1.6 (conn open) + Step 3.5 (decoration).
- `agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py` — 9 test functions (15 parametrized cases) covering D-01..D-08.
- `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` — real-cg + git-init'd fixture monorepo with stubbed LLM; asserts DB created, log line written, vault pages produced, pkg: URIs in graph.
- `agents/graph-wiki-agent/tests/unit/test_commands_scan.py` — pre-existing tests retro-fitted with `_capture_run` (return SUCCESS) + `read_only_connect` (raise `GraphNotInitializedError`) stubs so their behavior remains unchanged through the new fallback path.
- `agents/graph-wiki-agent/tests/commands/test_scan_parity.py` — same retro-fit pattern.

## Decisions Made

- **Pass workspace ROOT to ops_update, not wiki.** The plan's must_have said `_build_namespace(ops_update, repo=repo, workspace=wiki, full=False)`. Following that literally caused cg to write the DB to `<wiki>/.graph/code.db` while `read_only_connect(graph_dir(wiki.parent) / "code.db")` looks under `<workspace>/.graph/code.db`, sending every scan through the post-update NOT_INITIALIZED fallback. Phase 38 commands/graph.py (`_resolve_paths` → `cfg.workspace`) and Phase 37 commands/query.py (`graph_dir(wiki.parent)`) both use the workspace root. Aligned scan.py with the existing convention; documented inline.
- **`_query_package_uris` reads `nodes.uri` directly.** `queries.list_packages` returns `NodeRecord(attrs=...)` but `upsert._upsert_node` pops `uri` from attrs before serializing into `attrs_json` (storing it in the dedicated `nodes.uri` column). So `NodeRecord.attrs.get("uri")` is always None on package nodes. The helper reads `nodes.uri` directly in one round trip.
- **Gate decoration on `queries.list_packages(conn)` name set.** The plan's must_have literally requires `queries.list_packages(conn)` to appear in the source. Used the result as the membership-gate for decoration (only decorate workspaces whose `unscope(name)` is a known graph package), which both satisfies the must_have and short-circuits the URI/domain lookup loop for non-graph packages.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `workspace=wiki` argument to ops_update writes DB to wrong path**

- **Found during:** Task 4 (integration test failed: graph DB not created at expected path; fallback line emitted)
- **Issue:** Plan's must_have said `workspace=wiki`, but `ops_update` interprets `workspace` as the workspace root (per `workspace_io.paths.graph_dir`). Passing `wiki` caused cg to write `<wiki>/.graph/code.db` while `read_only_connect(graph_dir(wiki.parent) / "code.db")` looked under `<workspace>/.graph/code.db`.
- **Fix:** Pass `wiki.parent` (workspace root) as `workspace=` to `_build_namespace`; documented inline with reference to Phase 38 + 37 conventions.
- **Files modified:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py`, `agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py`
- **Verification:** Integration test now creates `<workspace>/.graph/code.db` and the read-only conn opens successfully; unit test `test_cg_update_dispatched_before_fanout` asserts `args.workspace == workspace` (the root) rather than `args.workspace == wiki`.
- **Committed in:** `ca830ef`

**2. [Rule 1 — Missing critical] `NodeRecord.attrs["uri"]` is always None for package nodes**

- **Found during:** Task 2 / Task 3 (reviewing the schema before writing the seed helper)
- **Issue:** Plan's must_have said "decoration step adds `pkg['uri']` from graph `NodeRecord.attrs['uri']`", but `upsert._upsert_node` pops `uri` from attrs before serializing to attrs_json (storing it in the dedicated `nodes.uri` column).
- **Fix:** Added `_query_package_uris(conn)` helper that reads `nodes.uri` directly in one SQL round trip; passes the result through the decoration loop.
- **Files modified:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py`
- **Verification:** `test_decoration_adds_uri_and_domain` asserts `pkg_a["uri"] == "pkg:org/repo/pkg-a"` against a seeded DB; integration test asserts the graph emits `pkg:` URIs after a real cg update.
- **Committed in:** `9d0aac3`

**3. [Rule 2 — Test ergonomics] Pre-existing scan tests don't stub the new cg-update path**

- **Found during:** Task 3 (full agent suite regression check)
- **Issue:** `tests/unit/test_commands_scan.py` (6 tests) + `tests/commands/test_scan_parity.py` (3 tests) called `run_scan` against a tmp_path with no git repo. After Task 3 added the pre-scan cg update, those tests started failing with `ScanAbortedError(exit_code=5, ...)` because cg returned NOT_IN_GIT_REPO.
- **Fix:** Added `patch("graph_wiki_agent.commands.scan._capture_run", return_value=(0, "", ""))` and `patch("graph_wiki_agent.commands.scan.read_only_connect", side_effect=GraphNotInitializedError("test stub"))` to every existing test that uses `run_scan`. This keeps pre-existing assertions intact (no DB seed → decoration is a no-op via the post-update fallback path).
- **Files modified:** `agents/graph-wiki-agent/tests/unit/test_commands_scan.py`, `agents/graph-wiki-agent/tests/commands/test_scan_parity.py`
- **Verification:** Full agent suite now passes 279/279.
- **Committed in:** `9d0aac3`

**Total deviations:** 3 auto-fixed (1 plan-spec bug, 1 missing-critical context, 1 test infrastructure). **Impact:** All deviations are documented inline in source + tests; no must_have semantically broken; all 5 SC verification commands exit 0.

## Issues Encountered

None — all 5 verification commands exit 0, integration test produces the expected scan-log sequence, and the Phase 35 regression test stays green.

## Verification

```bash
# Pre-condition
uv run --package graph-wiki-agent python -c "from graph_wiki_agent.commands.graph import _build_namespace, _capture_run, ops_update; print('ok')"
# → ok

# Unit tests
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py -q
# → 15 passed in 0.36s

# Full agent suite (regression guard)
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -q --ignore=agents/graph-wiki-agent/tests/integration
# → 279 passed in 24.52s

# Integration test (real cg + git-init'd fixture)
uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py -q -m integration
# → 1 passed in 0.30s

# SC#3 regression
uv run --package wiki-io pytest packages/wiki-io/tests/test_bootstrap_e2e_no_broken_links.py -q
# → 1 passed in 0.03s
```

Manual spot-check (integration test scan log):
```
[2026-05-26] scan | cg update (incremental)
[2026-05-26] scan | cg update complete: exit_code=0
[2026-05-26] scan | graph decoration: 2/2 workspaces
[2026-05-26] scan | scan complete: +2 ~0 -0
```

## Self-Check: PASSED

- All `<acceptance_criteria>` from Tasks 1-5 satisfied (verified via grep + pytest runs)
- All `<verification>` commands exit 0
- Phase 35 regression test green; `git diff packages/wiki-io/` empty (SC#3 by-reference satisfaction confirmed)

## Next Phase Readiness

Phase 39 is complete. Phase 40 (`40-ingestor-consumes-graph-io`) is the next phase per ROADMAP.md and is currently in planning (CONTEXT/RESEARCH/PATTERNS/VALIDATION exist; PLAN.md being drafted in parallel). Phase 40 will use the same Phase 38 graph helpers + the URI-derived slug routing this phase established for the ingestor pipeline.
