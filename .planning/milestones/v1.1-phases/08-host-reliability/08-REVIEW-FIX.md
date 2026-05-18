---
phase: 08-host-reliability
fixed_at: 2026-05-17T00:00:00Z
review_path: .planning/phases/08-host-reliability/08-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 08: Code Review Fix Report

**Fixed at:** 2026-05-17
**Source review:** .planning/phases/08-host-reliability/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (1 BLOCKER + 5 WARNING; INFO findings excluded per `fix_scope=critical_warning`)
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: `test_mcp_cancel.py` patches `make_llm` at the wrong import site

**Files modified:** `agents/code-wiki-agent/tests/integration/test_mcp_cancel.py`
**Commit:** be59f26
**Applied fix:** Changed the `monkeypatch.setattr` target from `model_adapter.loader.make_llm` to `code_wiki_agent.commands.query.make_llm`. The query module imports `make_llm` via `from model_adapter.loader import make_llm` at module-load time, creating a local binding; patching the source module did not redirect the importer's reference, so the 3 s stub `_slow_ainvoke` was never installed. The test now patches the binding inside the importer's namespace, matching the existing convention in `test_query_code_fallback.py` and `test_query_result.py`. Verified: `pytest agents/code-wiki-agent/tests/integration/test_mcp_cancel.py` passes in 3.93 s (consistent with the now-actually-awaited 3 s stub sleep followed by cancellation at 0.05 s); previous runtime was driven by whatever default `make_llm` returned.

### WR-01: `append_log._error` calls `sys.exit(1)` from inside an MCP tool handler

**Files modified:** `cores/vault-io/src/vault_io/append_log.py`, `cores/vault-io/src/vault_io/ingest_work_item.py`, `agents/code-wiki-agent/src/code_wiki_agent/commands/log.py`, `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py`, `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py`
**Commit:** bff47e1 (combined with WR-02)
**Applied fix:** Added a `raise_exception` flag to `_error` (and propagated it through `append_log`'s signature). When `True`, error paths raise `ValueError` instead of calling `sys.exit(1)`, so failures surface as normal exceptions FastMCP's `except Exception` boundary catches. All four library callers (`commands/log.py`, `commands/scan.py`'s three `append_log` calls, `commands/ingest.py`, and `vault_io/ingest_work_item.py`) now pass `raise_exception=True` alongside their existing `silent=True`. The CLI `main()` path is unchanged — it continues to `sys.exit(1)` on hard failures, which is correct for a CLI process. Updated `commands/log.py`'s docstring to document the new `ValueError` surface in place of the never-true "`SystemExit` ... converted upstream" claim. Tests: 29 command unit tests + 70 vault-io tests + 4 cancel/scan-input tests still pass.

### WR-02: `append_log._error` still writes to stdout when `as_json=True`

**Files modified:** `cores/vault-io/src/vault_io/append_log.py`
**Commit:** bff47e1 (combined with WR-01)
**Applied fix:** Routed the `as_json=True` error-path JSON to stderr (`print(..., file=sys.stderr)`). The success-path JSON still goes to stdout (the CLI `--json` contract is preserved), but a hard-failure write can never trip `_StdoutGuard` even if a future caller accidentally enables `as_json=True` from inside the MCP server. This matches the pattern Phase 08 applied to `init_wiki` (which was changed to `logger.error`), restoring consistency across the two error-printing helpers.

### WR-03: `_PAGE_TYPE_DIRS` does not include `"work"` despite docstring claim

**Files modified:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py`
**Commit:** 8668d9c
**Applied fix:** Reconciled the three disagreeing artifacts to a single source of truth. The system prompt (`prompts/ingestor.py`) already lists `source/package/concept/adr` as the four valid `page_type` values, and `_PAGE_TYPE_DIRS` maps exactly those four. The remaining drift was in two places: (1) `IngestResult.page_type`'s docstring listed `package/concept/adr/work`, and (2) `build_ingest_source_prompt`'s human message told the LLM to pick from `(package, concept, or adr)` — omitting `source`. Updated both to align with the system prompt's four reachable values. The docstring now also documents that `run_ingest_work_item` produces `page_type="work"` separately, bypassing `_route_target_path` and filing under `<workspace>/work/` via `file_work_item` — making the source vs work-item split explicit rather than implicit.

### WR-04: E2E test sends `wiki_scan` before `wiki_init` completes — potential ordering race

**Files modified:** `agents/code-wiki-agent/tests/integration/test_mcp_e2e.py`
**Commit:** f2401f0
**Applied fix:** Replaced `_run_server_long` (write-all-then-read) with `_run_server_serial`, which writes the initialize handshake first, then sends each tool-call request one at a time and awaits its matching id in stdout before sending the next. `wiki_init` (id=2) is now guaranteed to complete before `wiki_scan` (id=3) starts, eliminating the FastMCP TaskGroup race that previously let the test pass only because Bedrock latency made the ordering work out by accident. Test still collects (1 test, gated by `INTEGRATION_GATE`, not run in default CI).

### WR-05: `_resolve_wikilinks` walks the full vault on every ingest

**Files modified:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py`
**Commit:** 2004d81
**Applied fix:** Added an early-exit guard at the top of `_resolve_wikilinks`: `if "[[" not in text: return text, []`. The function previously called `wiki.rglob("*.md")` unconditionally on every `run_ingest_source` call, even when the LLM emitted zero wikilinks (the common case for many source types). The fast path returns identical output for any input with no `[[` substring, since `_WIKILINK_RE.sub` would return the text unchanged anyway. Avoids the disk walk for the common case; matters for the cost-frontier eval harness on large vaults. 17 ingest unit tests still pass.

---

_Fixed: 2026-05-17_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
