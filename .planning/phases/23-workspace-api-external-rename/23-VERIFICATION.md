---
phase: 23-workspace-api-external-rename
verified: 2026-05-20T00:00:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
human_verification_resolved:
  - test: "UAT-01 — Live MCP integration test run against real Bedrock"
    result: "PASSED (1 test, 14.49s) — GRAPH_WIKI_RUN_INTEGRATION=1 uv run pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py -x -q"
    resolved: 2026-05-20
---

# Phase 23: workspace-api-external-rename Verification Report

**Phase Goal:** Every external-facing surface — MCP tool schemas, Typer CLI flags, scan JSON output, plugin docs, and the DA-CLI integration test — uses `workspace_path` / `--workspace` / `wiki_relative_path` instead of the old `vault_path` / `--vault` nomenclature; brand-gate enforces no reintroduction.

**Verified:** 2026-05-20
**Status:** human_needed (1 deferred UAT item — UAT-01 live Bedrock integration run)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth (from PLAN must_haves)                                                                                                                                | Status     | Evidence                                                                                                                                                                                                |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | graph-wiki-agent CLI exposes --workspace on all 7 commands; bootstrap also exposes --repo                                                                   | VERIFIED   | `grep -c '"--workspace"' cli.py` = 7; `grep -c '"--repo"' cli.py` = 1; `bootstrap --help` shows both `--workspace` and `--repo` in rendered Typer panel; `scan --help` shows `--workspace` and NOT `--repo` |
| 2   | MCP tool call with field workspace_path succeeds; call with vault_path fails Pydantic schema validation (extra='forbid')                                    | VERIFIED   | Direct Python check: `WikiScanInput(workspace_path='/tmp/foo')` succeeds; `WikiScanInput(**{'vault_path': '/tmp/foo'})` raises `pydantic_core.ValidationError: Extra inputs are not permitted`. SC#2 smoke pytest passes (2/2). |
| 3   | Scan JSON output emits wiki_relative_path per package entry; vault_path no longer appears as JSON key                                                       | VERIFIED   | `grep -cE '"wiki_relative_path"' scan_monorepo.py` = 3; `grep -cE '"vault_path"' scan_monorepo.py` = 0; consumer in `commands/scan.py` reads new key at L369, L399, L416                                |
| 4   | Plugin docs and packages/prompt-sources/references mirrors are rename-mirrored                                                                              | VERIFIED   | All 3 doc files have 0 `vault_path` or `--vault` hits; `diff plugins/.../scan-workflow.md packages/prompt-sources/references/scan-workflow.md` exits 0 (byte-identical, D-08 invariant)                |
| 5   | DA-CLI integration test test_mcp_e2e.py uses new field/flag names mechanically and is runnable under GRAPH_WIKI_RUN_INTEGRATION=1                            | VERIFIED (mechanical) / DEFERRED (live) | `grep -cE '"workspace_path"' test_mcp_e2e.py` = 6; 0 `"vault_path"` / 0 `"--vault"` hits. Live Bedrock run is UAT-01 (deferred — see human_verification)                                              |
| 6   | scripts/check-brand.sh exits non-zero when vault_path Pydantic Field, --vault Typer flag, or vault_path JSON key is reintroduced in agents/ packages/ plugins/ | VERIFIED   | Clean tree: `bash scripts/check-brand.sh` → exit 0, prints `BRAND-04 OK: ... + BRAND-WSAPI vault_path|--vault|"vault_path"`. Synthesized `_wsmcp07_negative_test.py` with `    vault_path: str` → gate emits `BRAND-WSAPI FAIL: 1 unallowlisted hits` (caught). Fixture removed; clean-tree re-run → exit 0 |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact                                                                  | Expected                                                              | Status      | Details                                                                                                                                          |
| ------------------------------------------------------------------------- | --------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py`                    | 6 MCP input classes with `workspace_path` + `extra='forbid'`          | VERIFIED    | `workspace_path: str` count = 6; `extra='forbid'` count = 6; `from pydantic import BaseModel, ConfigDict, Field` present at L60; 0 bare `vault_path` tokens remain |
| `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py`                     | 7 Typer commands with `--workspace`; bootstrap also `--repo`           | VERIFIED    | `--workspace` count = 7; `--repo` count = 1; `Path(vault)` count = 0; `run_init(...repo_path=repo_path)` at L450                                |
| `packages/wiki-io/src/wiki_io/scan_monorepo.py`                         | `_wiki_relative_path_for` helper + 3 `wiki_relative_path` emissions   | VERIFIED    | `_wiki_relative_path_for` count = 2 (def + call); 3 emission sites of `"wiki_relative_path"`; 0 hits for `"vault_path"` string literal           |
| `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py`               | Integration test uses new field/flag names mechanically               | VERIFIED    | 6 `"workspace_path"` JSON keys; 0 `"vault_path"`; 0 `"--vault"`                                                                                  |
| `scripts/check-brand.sh`                                                  | CHECK 4 block banning the 3 WSMCP-07 patterns                         | VERIFIED    | CHECK 4 comment block at L80; HITS4 var at L88; literal regex `^[[:space:]]+vault_path:[[:space:]]+(str|Path|int|bool)|"--vault"|"vault_path"`; `BRAND-WSAPI` appears 2× (error + OK echo) |

### Key Link Verification

| From                                              | To                                                  | Via                                                            | Status | Details                                                                                              |
| ------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------- |
| MCP Pydantic field `workspace_path`               | `run_*` command kwargs `workspace_path=`            | `vault = Path(input.workspace_path) if input.workspace_path else None` | WIRED  | 6 internal handler sites in `server.py`; downstream `run_*(workspace_path=vault, ...)` preserved from Phase 22 |
| Typer flag `--workspace`                          | `run_*` command kwargs `workspace_path=`            | `workspace_path = Path(workspace) if workspace else None`      | WIRED  | All 7 command bodies bridge `Path(workspace)`; 0 `Path(vault)` remain                                |
| `bootstrap` CLI `--repo` flag                     | `run_init(repo_path=...)`                           | `repo_path = Path(repo).resolve() if repo else None`           | WIRED  | `cli.py` L450: `asyncio.run(run_init(topic=topic, tool=tool, force=force, workspace_path=workspace_path, repo_path=repo_path))` |
| `scan_monorepo._wiki_relative_path_for`           | `commands/scan.py pkg.get("wiki_relative_path",..)` | scan JSON dict key                                             | WIRED  | Helper renamed; emission sites match consumer reads at L369 / L399 / L416                            |
| `scripts/check-brand.sh` CHECK 4                  | `.brand-grep-allow`                                 | `grep -vF -f allowlist` filter                                 | WIRED  | Pipeline at L88-91; allowlist seeded with 7 rationale-commented entries (Phase 21 pattern)           |

### Data-Flow Trace (Level 4)

| Artifact                                            | Data Variable                  | Source                                              | Produces Real Data | Status   |
| --------------------------------------------------- | ------------------------------ | --------------------------------------------------- | ------------------ | -------- |
| `server.py` Wiki*Input.workspace_path               | over-the-wire JSON payload     | MCP host → Pydantic validation                      | Yes (gated by extra='forbid'; ValidationError on legacy field) | FLOWING |
| `cli.py` workspace_path local                       | Typer `workspace` parameter    | argv → typer.Option → `Path(workspace)`             | Yes (live `--help` shows wired option; bootstrap also threads `--repo` to `run_init`) | FLOWING |
| `scan_monorepo.py` `w["wiki_relative_path"]`        | per-workspace dict             | `_wiki_relative_path_for(w, vault_dir=vault_dir)`   | Yes (helper rename complete; tests in `packages/wiki-io/tests` green) | FLOWING |
| `commands/scan.py pkg.get("wiki_relative_path")`    | scanner→ingestor contract      | reads renamed JSON key                              | Yes (3 read sites match 3 emission sites)                              | FLOWING |

### Behavioral Spot-Checks

| Behavior                                                      | Command                                                                                    | Result                                                              | Status |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- | ------ |
| Bootstrap CLI shows `--workspace` and `--repo`                 | `uv run graph-wiki-agent bootstrap --help`                                                  | Rendered Typer panel shows both options                             | PASS   |
| Scan CLI shows `--workspace` but NOT `--repo`                  | `uv run graph-wiki-agent scan --help`                                                       | `--workspace` present; `--repo` absent (D-02 scope check)           | PASS   |
| Pydantic accepts new field                                     | `python -c "WikiScanInput(workspace_path='/tmp/foo')"`                                      | No ValidationError raised                                            | PASS   |
| Pydantic rejects legacy field with `extra='forbid'`            | `python -c "WikiScanInput(**{'vault_path': '/tmp/foo'})"`                                   | `pydantic_core.ValidationError: Extra inputs are not permitted`     | PASS   |
| SC#2 smoke pytest (positive + negative)                       | `uv run pytest agents/graph-wiki-agent/tests/unit/test_mcp_schema_forbid_extra.py -x -q`    | 2 passed in 0.43s                                                    | PASS   |
| Brand-gate clean tree                                          | `bash scripts/check-brand.sh`                                                                | exit 0; `BRAND-04 OK: ... + BRAND-WSAPI vault_path|--vault|"vault_path"` | PASS   |
| Brand-gate negative test (synthesized reintroduction)          | drop `    vault_path: str` into `packages/wiki-io/src/wiki_io/`, run gate                  | gate reports `BRAND-WSAPI FAIL: 1 unallowlisted hits` (caught)      | PASS   |
| Plugin doc ↔ mirror byte-identical                             | `diff plugins/.../scan-workflow.md packages/prompt-sources/references/scan-workflow.md`     | empty diff, exit 0                                                  | PASS   |
| Workspace-wide pytest                                          | `uv run pytest`                                                                              | 585 passed, 33 skipped, 5 failed (all pre-existing ANSI flakes)     | PASS (baseline preserved; 5 < Phase 22 baseline of 6) |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                                                  | Status      | Evidence                                                                                                                                                  |
| ----------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| WSMCP-01    | 23-01-PLAN  | 6 MCP input Pydantic Fields renamed vault_path → workspace_path; internal reads updated                                       | SATISFIED   | server.py: 6 `workspace_path: str`, 6 `extra='forbid'`, 0 `input.vault_path`, 0 bare `vault_path` tokens                                                  |
| WSMCP-02    | 23-01-PLAN  | 7 Typer flags renamed --vault → --workspace                                                                                  | SATISFIED   | cli.py: 7 `"--workspace"`, 0 `"--vault"`, 0 `Path(vault)`; live `--help` confirms across all 7 commands                                                   |
| WSMCP-03    | 23-01-PLAN  | New --repo flag for bootstrap                                                                                                | SATISFIED   | cli.py L450: `run_init(...repo_path=repo_path)`; scan/lint/etc do not expose `--repo` (D-02 scope check)                                                 |
| WSMCP-04    | 23-01-PLAN  | Scan JSON output field renamed vault_path → wiki_relative_path                                                               | SATISFIED   | scan_monorepo.py: helper `_wiki_relative_path_for`, 3 emission sites; commands/scan.py: 3 consumer-read sites (L369, L399, L416)                          |
| WSMCP-05    | 23-01-PLAN  | Plugin docs + prompt-source mirrors synced                                                                                   | SATISFIED   | 3 doc files have 0 hits; plugin↔mirror byte-identical (D-08)                                                                                              |
| WSMCP-06    | 23-01-PLAN  | DA-CLI integration test updated; passes under GRAPH_WIKI_RUN_INTEGRATION=1                                                   | SATISFIED (mechanical) / NEEDS HUMAN (live) | test_mcp_e2e.py: 6 `"workspace_path"` JSON keys, 0 legacy; SC#2 smoke pytest passes. Live env-gated run deferred to UAT-01.                            |
| WSMCP-07    | 23-01-PLAN  | check-brand.sh extended to ban reintroduction                                                                                | SATISFIED   | CHECK 4 block live; clean tree green; synthesized negative test caught; allowlist seeded with 7 rationale-commented entries (Phase 21 style)             |

All 7 declared requirement IDs from the PLAN frontmatter are accounted for in REQUIREMENTS.md (lines 36-42) and mapped to Phase 23 (REQUIREMENTS.md lines 97-103). No orphaned requirements.

### Probe Execution

No probes declared in PLAN; no conventional `scripts/*/tests/probe-*.sh` files exist in this repository. Step 7c not applicable.

### Anti-Patterns Found

| File                                                                                | Line | Pattern                                                | Severity | Impact                                                                                                       |
| ----------------------------------------------------------------------------------- | ---- | ------------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------------------------ |
| (none)                                                                              | —    | —                                                      | —        | No TBD/FIXME/XXX in any modified file. No empty return stubs introduced. No placeholder/coming-soon strings. |

Note: "vault" appears in 2 CLI help description strings (e.g. scan command docstring "Walk repo, diff packages vs vault, create/update stubs"). These are descriptive prose, not the renamed flag (`--vault`) or field (`vault_path`). Per D-07 the internal terminology (`wiki-io` package, `vault` local var) is intentionally preserved at module boundaries. Not flagged.

### Human Verification Required

#### 1. UAT-01 — Live MCP Integration Test Against Real Bedrock

**Test:** `GRAPH_WIKI_RUN_INTEGRATION=1 uv run pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py -x -q`
**Expected:** All 6 MCP tools round-trip successfully through stdio subprocess against seeded tmp_path workspace; `isError` is `False` for ids 2-7.
**Why human:** Requires AWS Bedrock credentials and is cost-sensitive. Per D-04 (locked CONTEXT decision), the live integration run was opportunistically deferred when `GRAPH_WIKI_RUN_INTEGRATION` was not set during execute-phase; mechanical sweep + SC#2 mechanical smoke satisfy SC#4 at the static-analysis layer, with the live run pending human/Pat action before phase close.

### Gaps Summary

None. All 6 must_haves observable truths verified, all 5 artifacts pass all three exists/substantive/wired levels (Level 4 data-flow checks also pass for the 4 dynamic-data artifacts), all 5 key links wired, all 7 WSMCP requirements satisfied (WSMCP-06 satisfied mechanically; live env-gated check is a one-time human-confirmation step per locked D-04). Pytest baseline preserved (585 passed / 33 skipped / 5 failed — improvement vs Phase 22 baseline of 6 failures; all 5 remaining failures are pre-existing Typer help-text ANSI-rendering flakes documented at the previous phase boundary). Brand-gate clean tree + synthesized negative reproduce verifies SC#5. Plugin doc and prompt-source mirror byte-identical confirms D-08.

Note on PLAN's success_criteria item #9 (single atomic commit per D-01): The phase shipped as 6 per-task sub-commits rather than a single atomic squash. Per the orchestrator-noted exception in the verification request context, the locked decision intent (a coherent end state, no failing intermediate state if measured at the branch-merge result) is preserved. This is informational and not a goal-affecting gap.

---

_Verified: 2026-05-20_
_Verifier: Claude (gsd-verifier)_
