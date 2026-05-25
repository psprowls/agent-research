---
phase: 08-host-reliability
plan: "02"
subsystem: testing
tags: [e2e-test, mcp, subprocess, json-rpc, wiki-scan, bedrock, integration]

requires:
  - phase: 08-host-reliability
    plan: "01"
    provides: pool.py CancelledError machinery as a clean baseline

provides:
  - WikiScanInput.repo_path field with empty-string default
  - wiki_scan handler passthrough via Path(input.repo_path).resolve() if input.repo_path else None
  - test_wiki_scan_input.py: 3 schema unit tests covering default/explicit/regression
  - test_mcp_e2e.py: INTEGRATION_GATE-gated subprocess E2E test exercising all 6 MCP tools

affects:
  - 08-03-cancellation-docs (wiki_scan, wiki_ingest, wiki_log now stdout-safe)
  - phase-09 (test_mcp_e2e.py serves as v1.1 regression gate for all 6 tools)

tech-stack:
  added: []
  patterns:
    - "stdin-open subprocess pattern: keep proc.stdin open until all expected IDs received, then close"
    - "append_log(silent=True) for all MCP-layer callers to avoid _StdoutGuard trips"
    - "append_log.py silent=False default preserves CLI behavior unchanged"

key-files:
  created:
    - agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py
    - agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_mcp/server.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py
    - cores/vault-io/src/vault_io/append_log.py
    - cores/vault-io/src/vault_io/ingest_work_item.py

key-decisions:
  - "stdin-open test helper: mcp 1.27.1 lowlevel/server.py:690 cancels in-flight handlers on stdin EOF; keeping stdin open until all responses received is required for Bedrock-calling tools"
  - "append_log silent=False default: preserves CLI behavior; only MCP callers pass silent=True"
  - "commands/init.py as_json=False: original as_json=True was a misuse — it ENABLES print(json.dumps(...)) not suppresses it"
  - "TDD RED/GREEN for Task 1: confirmed repo_path absent before implementation, verified all 3 tests fail, then pass"

patterns-established:
  - "stdin-open subprocess pattern for long-running MCP tool tests"
  - "MCP safety pattern: all vault_io functions called from MCP handlers must suppress stdout"

requirements-completed:
  - DACLI-01
  - DACLI-02
  - DACLI-03

duration: 13min
completed: 2026-05-17T17:06:48Z
---

# Phase 8 Plan 02: E2E Test Summary

**WikiScanInput.repo_path field + six-tool subprocess E2E integration test with stdin-open pattern for Bedrock-calling tools, plus MCP stdout safety fixes across vault_io callers**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-05-17T16:54:07Z
- **Completed:** 2026-05-17T17:06:48Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

### Task 1: WikiScanInput.repo_path + unit tests

- Added `repo_path: str = Field("", description="Override repo root for scanner (default: resolved from vault_path). Use for testing.")` to `WikiScanInput` at **server.py lines 246-249**.
- Modified `wiki_scan` handler at **server.py line 272**: `repo_path=Path(input.repo_path).resolve() if input.repo_path else None` — exact `Path(...) if X else None` idiom from lines 125, 169, 215.
- Created `test_wiki_scan_input.py` with 3 tests: default empty-string, explicit path, regression guard on existing fields. All green.
- TDD RED phase confirmed: `AttributeError: 'WikiScanInput' object has no attribute 'repo_path'` before implementation.
- All 141 existing unit tests still pass.

### Task 2: Six-tool subprocess E2E test

- Created `test_mcp_e2e.py` with one `@INTEGRATION_GATE`-decorated `test_all_six_tools_end_to_end` function.
- Seed: minimal uv workspace at `tmp_path` with `packages/alpha` package (`sample.py` with `hello()` function).
- Tools exercised in order: `wiki_init` → `wiki_scan` → `wiki_ingest` → `wiki_query` → `wiki_lint` → `wiki_log`.
- `wiki_scan` passes `repo_path=str(tmp_path)` so scanner walks `tmp_path` not the live monorepo (DACLI-02 / Pitfall 4).
- All 6 tools returned `isError: False` responses in 6.10s wall-clock time (well under 180s budget).

## server.py diff summary

**WikiScanInput** (lines 242-251 post-edit):
```python
class WikiScanInput(BaseModel):
    vault_path: str = Field("", description="Vault path (default: GRAPH_WIKI_REAL_VAULT_PATH env var)")
    no_file_map: bool = Field(False, description="Skip per-package file-map generation")
    max_depth: int = Field(3, description="Max directory depth for file map headers")
    repo_path: str = Field(
        "",
        description="Override repo root for scanner (default: resolved from vault_path). Use for testing.",
    )
```

**wiki_scan handler** (line 272 post-edit):
```python
repo_path=Path(input.repo_path).resolve() if input.repo_path else None,
```

## Seed fixture layout

```
tmp_path/
  pyproject.toml          # [tool.uv.workspace] members = ["packages/alpha"]
  packages/alpha/
    pyproject.toml
    src/alpha/sample.py   # def hello() -> str: return "alpha"
  wiki/                   # created by wiki_init
    .graph-wiki/
    index.md
    log.md
```

## Observed wiki_scan output

From the direct asyncio test run:
```
added=['alpha', 'e2e-test-root'], updated=[], deleted=[]
```
Confirms scan walked `tmp_path` (found 2 new packages: `alpha` and `e2e-test-root`), NOT the agent-research monorepo.

## Observed wall-clock time

**Gated E2E run:** ~6.1s (both `wiki_init` and `wiki_log` need no Bedrock; scanner Bedrock calls for 2 packages complete quickly with small input context)

## Per-tool stderr extracts

No tools flagged errors. All responses were `isError: False`. `wiki_query` showed the expected "First-time index build" log on its first run.

## Task Commits

1. **Task 1: WikiScanInput.repo_path + unit tests** - `83f4c70` (feat)
2. **Task 2: E2E test + stdout safety fixes** - `74fc876` (feat)
3. **Plan metadata:** (this SUMMARY commit)

## Files Created/Modified

- `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` — Added `repo_path` field to WikiScanInput; wired to `run_scan`
- `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py` — New: 3 schema unit tests
- `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` — New: 6-tool sequential E2E test (DACLI-01/02/03)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` — Fixed as_json=True → as_json=False bug
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — append_log calls now use silent=True
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` — append_log call now uses silent=True
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py` — append_log call now uses silent=True
- `cores/vault-io/src/vault_io/append_log.py` — Added silent=False parameter; suppresses stdout when silent=True
- `cores/vault-io/src/vault_io/ingest_work_item.py` — append_log call now uses silent=True

## Decisions Made

### stdin-open subprocess pattern for Bedrock-calling tools

mcp 1.27.1 `lowlevel/server.py:690` cancels all in-flight tool handlers when stdin closes:
```python
tg.cancel_scope.cancel()  # Transport closed: cancel in-flight handlers.
```
The standard `communicate()` approach (send stdin, close pipe, wait for process) cancels Bedrock calls before they complete. Fix: keep `proc.stdin` open, poll `proc.stdout` line-by-line until all expected response IDs are received, then close stdin.

This is a critical pattern for any MCP stdio subprocess test that exercises Bedrock-calling tools.

### append_log stdout safety

`vault_io/append_log.py` always prints to stdout (either human-readable or JSON format). All calls from MCP tool handlers now pass `silent=True`. The `silent` parameter defaults to `False` so CLI callers are unaffected. This is a Rule 2 (missing critical functionality) fix — the MCP server cannot have stdout writes from library code.

### commands/init.py as_json=True bug

The comment "suppress stdout prints — required for MCP safety" was wrong. `as_json=True` in `init_wiki()` ENABLES `print(json.dumps(result, indent=2))`, it doesn't suppress it. Changed to `as_json=False` — the result dict is returned regardless, and `non_interactive=True` already suppresses all interactive prompts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mcp 1.27.1 cancels in-flight handlers on stdin EOF**
- **Found during:** Task 2 (E2E test)
- **Issue:** `communicate()` closes stdin after sending all requests; mcp server then cancels Bedrock calls via `tg.cancel_scope.cancel()`. Tools `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint` never responded.
- **Fix:** Replaced `communicate()` with a stdin-open pattern: write all requests, keep stdin open, poll stdout via `select` until all expected response IDs received, then close stdin.
- **Files modified:** `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py`

**2. [Rule 1 - Bug] append_log prints to stdout unconditionally**
- **Found during:** Task 2 (E2E test debugging)
- **Issue:** `append_log` with default `as_json=False` calls `print(f"[ok] appended to {log_path}")` which trips `_StdoutGuard` in the MCP subprocess, causing FastMCP to swallow the exception and the server to exit without sending the `wiki_scan` response.
- **Fix:** Added `silent=False` parameter to `append_log`; all MCP-layer callers pass `silent=True`. This is additive — CLI callers unaffected.
- **Files modified:** `cores/vault-io/src/vault_io/append_log.py`, all 4 callers in `commands/`

**3. [Rule 1 - Bug] commands/init.py as_json=True misuse**
- **Found during:** Task 2 (first E2E run, id=2 wiki_init showed isError=True)
- **Issue:** `as_json=True` in `init_wiki()` call was intended to "suppress stdout" but actually ENABLES `print(json.dumps(result, indent=2))` (line 265 of init_vault.py), which trips `_StdoutGuard`.
- **Fix:** Changed to `as_json=False`. Result dict is returned regardless; `non_interactive=True` already suppresses interactive prompts.
- **Files modified:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py`

**Total deviations:** 3 auto-fixed Rule 1 bugs — all pre-existing stdout safety issues in vault_io library code that the E2E test surfaced.

## WikiIngestInput shape deviation from plan

The PLAN suggested `{"op": "source", "path": ...}` but actual `WikiIngestInput` uses `type` (not `op`) and `source_path` (not `path`). Verified from server.py lines 299-303. Corrected in test.

## Known Stubs

None — all tool responses contain real data from vault/Bedrock operations.

## Threat Flags

None — no new trust boundaries. The `repo_path` field is plumbed exclusively to the existing `run_scan(repo_path=...)` parameter with `Path(...).resolve()` (same pattern as lines 125, 169, 215). The subprocess harness is test-only. The `silent=True` parameter in `append_log` only suppresses stdout output — no security surface changed.

## Self-Check: PASSED

- FOUND: agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py
- FOUND: agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py
- FOUND: .planning/phases/08-host-reliability/08-02-SUMMARY.md
- FOUND commit: 83f4c70
- FOUND commit: 74fc876
