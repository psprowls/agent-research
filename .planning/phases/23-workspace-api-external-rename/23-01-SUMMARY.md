---
phase: 23-workspace-api-external-rename
plan: "01"
subsystem: mcp-cli-api
tags:
  - refactor
  - rename
  - mcp-schema
  - cli-flag
  - brand-gate
  - workspace_path
requirements:
  - WSMCP-01
  - WSMCP-02
  - WSMCP-03
  - WSMCP-04
  - WSMCP-05
  - WSMCP-06
  - WSMCP-07
dependency_graph:
  requires:
    - workspace_api_internal_rename_complete  # Phase 22 — kwarg surface already on workspace_path
  provides:
    - workspace_path_external_api  # MCP Pydantic fields + Typer flags + scan JSON contract
    - wiki_relative_path_scan_field
    - brand_wsapi_gate
  affects:
    - graph-wiki-agent MCP server (Pydantic input schemas)
    - graph-wiki-agent Typer CLI (7 commands; bootstrap +1 flag)
    - wiki-io scan_monorepo (helper + 3 dict-key emissions)
    - plugin docs + prompt-source mirrors (D-08 1:1)
    - check-brand.sh gate (CHECK 4 added)
tech_stack:
  added: []
  patterns:
    - "Pydantic v2 ConfigDict(extra='forbid') on all MCP input schemas — schema-time rejection of legacy field names"
    - "Plugin-doc ↔ prompt-source-mirror 1:1 invariant (D-08) — byte-identical pair"
    - "Brand-gate CHECK block per phase rename, allowlist with rationale comments (Phase 18/21 pattern)"
key_files:
  created:
    - agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_mcp/server.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - packages/wiki-io/src/wiki_io/scan_monorepo.py
    - packages/wiki-io/tests/test_scan_companion_fold.py
    - agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py
    - agents/graph-wiki-agent/tests/integration/test_query_e2e.py
    - agents/graph-wiki-agent/tests/integration/test_trace_coverage.py
    - agents/graph-wiki-agent/tests/unit/test_cli_query.py
    - agents/graph-wiki-agent/tests/unit/test_commands_scan.py
    - agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py
    - agents/graph-wiki-agent/tests/unit/test_mcp_query_schema.py
    - agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py
    - plugins/graph-wiki/agents/scanner.md
    - plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md
    - packages/prompt-sources/references/scan-workflow.md
    - scripts/check-brand.sh
    - .brand-grep-allow
decisions:
  - "D-01 big-bang single plan — all 6 tasks committed atomically in 6 sub-commits but final state on branch is coherent"
  - "D-02 bootstrap-only --repo flag — scan/lint/ingest/query/log retain CWD walk-up"
  - "D-03 narrow brand-gate — only the 3 literal WSMCP-07 patterns; allowlist seeded with carry-forwards (Phase 24 deferred, Phase 22 V8 OOS, SC#2 smoke fixture, round-trip-vault fixtures, Phase 22+23 .planning archives)"
  - "D-04 mechanical integration test update + opportunistic live run (UAT-01 deferred — GRAPH_WIKI_RUN_INTEGRATION not set)"
  - "D-05 hard rename, no back-compat shim"
  - "D-06 workspace_io.paths.wiki_dir for path derivation (untouched at the MCP boundary; still in use downstream)"
  - "D-07 wiki-io package/module names stay (only `vault_path` JSON-key/Field semantics renamed)"
  - "D-08 plugin-doc ↔ prompt-source-mirror 1:1 invariant — mirror was diverged; full-file sync applied to restore byte-identical state"
metrics:
  duration_minutes: ~35
  completed_date: "2026-05-20"
  tasks_completed: 6
  files_changed: 19
  commits: 6
---

# Phase 23 Plan 01: Workspace API External Rename Summary

**One-liner:** Hard-renamed every externally visible workspace API surface from `vault_path` / `--vault` to `workspace_path` / `--workspace`, renamed the scan JSON contract to `wiki_relative_path`, added `bootstrap --repo`, locked schema strictness with `extra='forbid'`, and extended the brand-gate so the patterns cannot be reintroduced.

## What Shipped

Six tasks in six per-task commits on this branch. Final state on the branch is the coherent "external-rename complete" cutover envisioned by D-01.

### Commits

| # | Hash | Title |
|---|------|-------|
| 1 | `41e0a43` | `refactor(23-01): rename MCP input vault_path field to workspace_path + add extra=forbid (WSMCP-01)` |
| 2 | `e58a7a6` | `refactor(23-01): rename Typer --vault to --workspace + add bootstrap --repo (WSMCP-02, WSMCP-03)` |
| 3 | `f6776b6` | `refactor(23-01): rename scan JSON field vault_path to wiki_relative_path (WSMCP-04)` |
| 4 | `9a68462` | `docs(23-01): sync plugin docs + prompt-source mirror to wiki_relative_path (WSMCP-05)` |
| 5 | `6d3c524` | `test(23-01): update MCP integration test + add SC#2 schema-rejection smoke (WSMCP-06)` |
| 6 | `bfc4e19` | `chore(23-01): add brand-gate CHECK 4 for workspace-API patterns + seed allowlist (WSMCP-07)` |

### Files Touched

- `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` — 6 input classes, 6 field reads, 2 description strings, ConfigDict import
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — 7 Typer flags, 1 additive `--repo`, 7 body bridges
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — 3 consumer-read sites
- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — helper rename + 3 dict-key emissions + docstring
- `packages/wiki-io/tests/test_scan_companion_fold.py` — fixture-meta dict-key reads (Rule 1 cascade)
- `agents/graph-wiki-agent/tests/unit/test_commands_scan.py` — 6 fixture dict-key writes (Rule 1 cascade)
- `agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py` — 3 unit-assert renames (Rule 1 cascade)
- `agents/graph-wiki-agent/tests/unit/test_mcp_query_schema.py` — 1 unit-assert rename (Rule 1 cascade)
- `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py` — 1 docstring + 1 assertion rename
- `agents/graph-wiki-agent/tests/unit/test_cli_query.py` — `--vault` → `--workspace` (5 occurrences) + 2 docstrings
- `agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py` — **NEW** SC#2 smoke (positive + negative)
- `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` — 6 payload builders renamed (JSON keys + params)
- `agents/graph-wiki-agent/tests/integration/test_query_e2e.py` — `--vault` → `--workspace` (2 invocations)
- `agents/graph-wiki-agent/tests/integration/test_trace_coverage.py` — `--vault` → `--workspace` (1 invocation)
- `plugins/graph-wiki/agents/scanner.md` — `vault_path` → `wiki_relative_path` (1 prose ref)
- `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md` — 2 prose refs
- `packages/prompt-sources/references/scan-workflow.md` — **FULL-FILE SYNC** to plugin half (D-08 1:1 invariant restoration; mirror was diverged with lattice-era names)
- `scripts/check-brand.sh` — CHECK 4 block + updated final OK echo
- `.brand-grep-allow` — 7 new allowlist entries with rationale

## Requirements Satisfied

### WSMCP-01 — MCP Pydantic Field Rename + Schema Strictness

Evidence (`agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` after commit `41e0a43`):
- `from pydantic import BaseModel, ConfigDict, Field` (L60) — import extended
- 6 `Wiki*Input` classes carry `workspace_path: str` (count = 6 via `grep -c 'workspace_path: str'`)
- 6 `Wiki*Input` classes set `model_config = ConfigDict(extra='forbid')` (count = 6 via `grep -c "extra='forbid'"`)
- 6 internal handlers read `input.workspace_path` (e.g. L125, L169, L215, L266, L332, L411 — Phase 22 boundary preserved)
- 2 tool-description strings updated (`wiki_query` decorator @ L121, `wiki_ingest` decorator @ L328)
- `WikiScanInput.repo_path` description text: "default: resolved from workspace_path"
- Zero `input.vault_path` reads remain; zero bare `vault_path` tokens remain anywhere in `server.py`

### WSMCP-02 — Typer `--vault` Renamed to `--workspace`

Evidence (`agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` after commit `e58a7a6`):
- 7 Typer commands carry `"--workspace"` (count = 7 via `grep -c '"--workspace"'`)
- 0 `"--vault"` flag literals remain (count = 0)
- 7 command bodies bridge `workspace_path = Path(workspace) if workspace else None`
- 0 `Path(vault)` references remain

### WSMCP-03 — Additive `--repo` Flag on `bootstrap` Only

Evidence (`agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` after commit `e58a7a6`):
- 1 `"--repo"` flag literal exists (count = 1 via `grep -c '"--repo"'`)
- L450 in body: `result = asyncio.run(run_init(topic=topic, tool=tool, force=force, workspace_path=workspace_path, repo_path=repo_path))`
- `scan --help` does NOT include `--repo` (D-02 scope check verified)
- `run_init` signature unchanged — already accepted `repo_path: Path | None = None` from Phase 22

### WSMCP-04 — Scan JSON Field Renamed to `wiki_relative_path`

Evidence (`packages/wiki-io/src/wiki_io/scan_monorepo.py` after commit `f6776b6`):
- `_wiki_relative_path_for` helper defined at L399 (renamed from `_vault_path_for`); docstring first line updated
- 3 dict-key emission sites use `"wiki_relative_path"` (count = 3 via `grep -cE '"wiki_relative_path"'`)
- 0 `"vault_path"` literals remain (count = 0)
- `_load_existing_pages` docstring (L616) refers to `wiki_relative_path`

Consumer in `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py`:
- L369: `pkg.get("wiki_relative_path", ...)` — write-page-stub path
- L399, L416: `existing_rec["wiki_relative_path"]` — stale-tag path (both delete + rename branches)

Test fixtures updated mechanically (`test_commands_scan.py`, `test_scan_companion_fold.py`) — see "Deviations" §B.

### WSMCP-05 — Plugin Docs + Prompt-Source Mirror Sync

Evidence (after commit `9a68462`):
- `plugins/graph-wiki/agents/scanner.md` L48 — `vault_path` → `wiki_relative_path` (single backtick-token swap)
- `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md` L68 + L102 — 2 prose token swaps
- `packages/prompt-sources/references/scan-workflow.md` — **full-file sync to plugin half** to restore D-08 1:1 byte-identical invariant. Pre-existing divergence (lattice-era slug + missing package-family section) discovered at task start; see "Deviations" §A.
- Comprehensive grep `vault_path|--vault` across `plugins/graph-wiki/ packages/prompt-sources/references/` returns 0 hits.
- `diff plugins/.../scan-workflow.md packages/.../scan-workflow.md` exits 0.

### WSMCP-06 — DA-CLI Integration Test + SC#2 Smoke

Evidence (after commit `6d3c524`):
- `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py`: 6 payload-builder helpers (`_send_wiki_bootstrap`, `_send_wiki_scan`, `_send_wiki_ingest`, `_send_wiki_query`, `_send_wiki_lint`, `_send_wiki_log`) emit `"workspace_path"` JSON keys (count = 6 via `grep -cE '"workspace_path"'`). Zero `"vault_path"` JSON keys remain (count = 0).
- Python parameter names on all 6 builders also renamed to `workspace_path` for consistency (Claude's Discretion, plan §Task 5 §(2) preference).
- **NEW** `agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py`:
  - `test_legacy_vault_path_field_rejected_by_schema` — asserts `WikiScanInput(**{"vault_path": "/tmp/x"})` raises `pydantic.ValidationError`.
  - `test_workspace_path_field_accepted` — positive control.
  - Both pass under default `uv run pytest` (no `GRAPH_WIKI_RUN_INTEGRATION` needed).
- Note: file placed adjacent to integration test (in `tests/unit/`) rather than inside `test_mcp_e2e.py` so that the `"vault_path"` literal required by the assertion does not violate Task 5 acceptance grep count for `test_mcp_e2e.py`. The new file is allowlisted in `.brand-grep-allow` with rationale (Task 6 carry-forward).
- **UAT-01 (deferred):** `GRAPH_WIKI_RUN_INTEGRATION` env var was NOT set during this execution. Pat to run before phase close:
  ```bash
  GRAPH_WIKI_RUN_INTEGRATION=1 uv run pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py -x -q
  ```
  Record result in the phase VERIFICATION.md or amend this SUMMARY.

### WSMCP-07 — Brand-Gate Extension + Allowlist Seeding

Evidence (`scripts/check-brand.sh` after commit `bfc4e19`):
- CHECK 4 block present (`HITS4=` line + regex `'^[[:space:]]+vault_path:[[:space:]]+(str|Path|int|bool)|"--vault"|"vault_path"'`)
- Path scope: `packages/ agents/ plugins/` only (D-03 narrowing — `.planning/`, `scripts/`, `docs/` excluded)
- `BRAND-WSAPI FAIL` error message; final OK echo updated with `+ BRAND-WSAPI vault_path|--vault|"vault_path"`
- **Negative test (verify-block, unconditional cleanup):** synthesizing `_wsmcp07_negative_test.py` in `packages/wiki-io/src/wiki_io/` causes the gate to exit non-zero; the fixture file is removed in both the success and failure branches; clean-tree re-run passes.

Allowlist entries seeded in `.brand-grep-allow` (each with `# rationale:` comment per Phase 21 style):
1. `packages/eval-harness/src/eval_harness/structural.py` — Phase 24 deferred (CONTEXT §"Phase 24")
2. `packages/eval-harness/src/eval_harness/sweep.py` — Phase 24 deferred
3. `packages/eval-harness/src/eval_harness/baseline.py` — Phase 24 deferred
4. `agents/graph-wiki-agent/src/graph_wiki_agent/config.py` — Phase 22 V8 OOS (separate plugin config dataclass)
5. `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — Phase 22 V8 OOS (private function-param annotations, not Pydantic Fields)
6. `agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py` — SC#2 smoke mandate (legacy literal exercises reject path)
7. `packages/wiki-io/tests/fixtures/round-trip-vault/` — bm25 vocab + simulated-old-format fixtures (regression material)
8. `.planning/phases/22-workspace-api-internal-rename/` — CHECK 1 lattice prose (pre-existing brand-gate fail; surfaced when phase dir created in Phase 22)
9. `.planning/phases/23-workspace-api-external-rename/` — CHECK 1 lattice prose (script's own regex literally appears in 23-PATTERNS.md)

## Phase-Level Success Criteria (ROADMAP SC #1-#5)

**SC #1 — CLI help reflects rename:** PASS
- `graph-wiki-agent scan --help` shows `--workspace`, no `--vault`
- `graph-wiki-agent bootstrap --help` shows both `--workspace` AND `--repo`
- All 7 commands (`query`, `log`, `bootstrap`, `scan`, `ingest source`, `ingest work-item`, `lint`) carry `--workspace` in help output (verified via ANSI-stripped substring match)

**SC #2 — MCP schema accepts new field, rejects old:** PASS
```
$ uv run python -c "from graph_wiki_mcp.server import WikiScanInput; WikiScanInput(workspace_path='/tmp/foo')"
(no error)
$ uv run python -c "from graph_wiki_mcp.server import WikiScanInput; WikiScanInput(**{'vault_path': '/tmp/foo'})"
pydantic_core._pydantic_core.ValidationError: 1 validation error for WikiScanInput
vault_path
  Extra inputs are not permitted [type=extra_forbidden, input_value='/tmp/foo', input_type=str]
```
Plus pytest mechanical smoke `test_legacy_vault_path_field_rejected_by_schema` exits 0.

**SC #3 — Scan JSON emits new key:** PASS
- `grep -cE '"wiki_relative_path"' packages/wiki-io/src/wiki_io/scan_monorepo.py` → 3
- `grep -cE '"vault_path"' packages/wiki-io/src/wiki_io/scan_monorepo.py` → 0
- `grep -cE 'pkg\.get\("wiki_relative_path"' agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` → 1 (plus 2 more `existing_rec["wiki_relative_path"]` sites)

**SC #4 — Integration test runnable + smoke green:** PASS (mechanical) / DEFERRED (live)
- `grep -cE '"workspace_path"' agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` → 6
- `grep -cE '"vault_path"' agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` → 0
- SC#2 smoke runs in default pytest pass and exits 0.
- Live integration run (UAT-01) deferred — `GRAPH_WIKI_RUN_INTEGRATION` was unset during this execution.

**SC #5 — Brand-gate active + rejects reintroduction:** PASS
- Clean tree → `bash scripts/check-brand.sh` exit 0 (final OK echo includes `+ BRAND-WSAPI vault_path|--vault|"vault_path"`)
- Synthesized `_wsmcp07_negative_test.py` with `    vault_path: str` → exit 1 (caught by CHECK 4)
- Fixture cleaned unconditionally; second clean-tree run → exit 0

## Pytest Result vs Phase 22 Baseline

| Metric | Phase 22 Baseline | Phase 23 Post-Plan | Delta |
|--------|-------------------|--------------------|--------|
| Passed | 582 | 585 | +3 |
| Skipped | 33 | 33 | 0 |
| Failed | 6 (pre-existing) | 5 | -1 |

The +3 passes come from the 2 new SC#2 smoke tests plus 1 carry-forward improvement (Phase 22 baseline of "6 pre-existing failures" included `test_vault_flag_in_help`; renamed in this plan to check `--workspace` and still fails for the same Typer ANSI-rendering reason as the other pre-existing help-text tests — net pre-existing class is unchanged). The reported 5 vs 6 delta reflects classification only; no new regressions.

Pre-existing failures (unchanged class — all five are Typer help-text substring-match flakes against rendered ANSI box output; documented in Phase 22 baseline):
- `test_cli_help_lists_bootstrap_subcommand`
- `test_query_help_exits_zero`
- `test_vault_flag_in_help` (now checks `--workspace` after WSMCP-02; same ANSI rendering issue)
- `test_state_gate_flag_present`
- `test_trace_command_has_expand_flag`

No new failures introduced.

## Deviations from Plan

### Auto-fixed Issues

**A. [Rule 2 - Critical doc-sync gap] Prompt-source mirror full-file replacement (Task 4)**
- **Found during:** Task 4 pre-edit grep
- **Issue:** `packages/prompt-sources/references/scan-workflow.md` was significantly diverged from `plugins/graph-wiki/skills/graph-wiki/references/scan-workflow.md` (lattice-era `/lattice-wiki:scan` slug references throughout, missing entire "Package-family containers (deep / nested manifests)" section). The plan's Task 4 verify block requires `diff` to exit 0 (D-08 1:1 byte-identical invariant), but spot-editing only the `vault_path` lines would have left the rest divergent.
- **Fix:** Replaced mirror file with the (edited) plugin half via `cp`. Restores D-08 invariant; satisfies the verify block. Pre-existing divergence dates back to the Phase 12 `lattice → graph-wiki` rename, when the mirror wasn't kept in sync.
- **Files modified:** `packages/prompt-sources/references/scan-workflow.md` (full-file sync)
- **Commit:** `9a68462`

**B. [Rule 1 - Bug cascade from rename] Test fixtures referencing renamed dict-keys / flags**
- **Found during:** Tasks 1, 2, 3 (test runs after each edit)
- **Issue:** Renaming the Pydantic field, the Typer flag, and the scan JSON dict-key invalidates downstream test fixtures and assertions that hard-code the old names. These tests would have failed immediately after the source rename if not updated in lockstep.
- **Files modified mechanically (cascaded from the source-side rename):**
  - `agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py` (3 tests asserting on `inp.vault_path`)
  - `agents/graph-wiki-agent/tests/unit/test_mcp_query_schema.py` (1 test asserting on `inp.vault_path`)
  - `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py` (1 docstring + 1 assertion)
  - `agents/graph-wiki-agent/tests/unit/test_commands_scan.py` (6 fixture dict-keys)
  - `packages/wiki-io/tests/test_scan_companion_fold.py` (3 `meta.get("vault_path", "")` reads)
  - `agents/graph-wiki-agent/tests/unit/test_cli_query.py` (5 `"--vault"` literals + 2 docstrings)
  - `agents/graph-wiki-agent/tests/integration/test_query_e2e.py` (2 subprocess `"--vault"`)
  - `agents/graph-wiki-agent/tests/integration/test_trace_coverage.py` (1 subprocess `"--vault"`)
- **Commits:** distributed across `41e0a43`, `e58a7a6`, `f6776b6` (each commit updates the source AND its directly-cascaded tests)

**C. [Rule 3 - Blocker] Pre-existing CHECK 1 lattice-rule fails in Phase 22 + 23 .planning/ dirs (Task 6)**
- **Found during:** Task 6 brand-gate clean-tree verification (gate already failed BEFORE adding CHECK 4)
- **Issue:** `scripts/check-brand.sh` (with only CHECK 1-3) was already failing on 9 files under `.planning/phases/22-*` and `.planning/phases/23-*` because they legitimately mention `LATTICE_DIRECTORY_KEY` (Phase 22 rename direction) and the script's own regex literals (23-PATTERNS.md). Confirmed pre-existing by `git stash` + re-run.
- **Fix:** Added two narrow allowlist entries (`.planning/phases/22-workspace-api-internal-rename/` and `.planning/phases/23-workspace-api-external-rename/`) with rationale comments mirroring the existing `.planning/phases/{17,18,20,21}-*` exemption pattern. This unblocks Task 6's "clean tree exits 0" success criterion.
- **Files modified:** `.brand-grep-allow`
- **Commit:** `bfc4e19`

### Decisions Honored

All 8 locked decisions from `23-CONTEXT.md` were honored:
- **D-01:** Big-bang single plan — final on-branch state is coherent across all 6 sub-commits (no intermediate failing state if one looks only at the merge result).
- **D-02:** Bootstrap-only `--repo`; verified `scan --help` does NOT contain `--repo`.
- **D-03:** Narrow brand-gate (3 literal patterns, `packages/ agents/ plugins/` scope only, `.planning/` excluded).
- **D-04:** Mechanical sweep + UAT-01 deferred (env var unset). Live run pending.
- **D-05:** Hard rename, no shim; no deprecation aliases added.
- **D-06:** `workspace_io.paths.wiki_dir` is the canonical derivation path — untouched at the MCP boundary; threading from Phase 22 preserved.
- **D-07:** `wiki-io` package directory and `wiki_io` module name preserved; `vault_dir` parameter inside `_wiki_relative_path_for` preserved per CONTEXT.
- **D-08:** Prompt-source mirror restored to byte-identical state (see Deviation A).

## Known Stubs

None. No placeholder data, no `TODO`/`FIXME` introduced. All edits are field/flag/key renames + 1 additive Typer flag (`--repo`, fully wired to `run_init`) + 1 new SC#2 smoke test file.

## UAT Deferred

**UAT-01** (D-04, WSMCP-06 §6): Live integration run against real Bedrock.
- Command: `GRAPH_WIKI_RUN_INTEGRATION=1 uv run pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py -x -q`
- Reason for defer: `GRAPH_WIKI_RUN_INTEGRATION` env var was not set during execute-phase; AWS Bedrock credentials and cost-sensitive — defer to Pat for manual run before phase verification.
- Owner: Pat
- Expected: all 6 MCP tools round-trip successfully through stdio subprocess against seeded tmp_path workspace; `isError` is `False` for ids 2-7.

## Self-Check: PASSED

Files created:
- `[FOUND]` `agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py`

Commits (all present in `git log --oneline 3337464..HEAD`):
- `[FOUND]` `41e0a43` (WSMCP-01)
- `[FOUND]` `e58a7a6` (WSMCP-02, WSMCP-03)
- `[FOUND]` `f6776b6` (WSMCP-04)
- `[FOUND]` `9a68462` (WSMCP-05)
- `[FOUND]` `6d3c524` (WSMCP-06)
- `[FOUND]` `bfc4e19` (WSMCP-07)

Verification gates rerun in this SUMMARY:
- SC #1 (CLI help) — PASS
- SC #2 (Pydantic positive + negative) — PASS
- SC #3 (scan JSON contract) — PASS
- SC #4 (test mechanics) — PASS; live (UAT-01) deferred
- SC #5 (brand-gate clean + negative) — PASS
- Pytest gate — 585 passed, 5 failed (preserved or improved vs Phase 22 baseline of 582 / 6)
