---
phase: 08-host-reliability
reviewed: 2026-05-17T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/init.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/log.py
  - agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
  - agents/code-wiki-agent/src/code_wiki_mcp/server.py
  - agents/code-wiki-agent/tests/integration/test_mcp_cancel.py
  - agents/code-wiki-agent/tests/integration/test_mcp_e2e.py
  - agents/code-wiki-agent/tests/unit/test_wiki_scan_input.py
  - cores/subagent-runtime/src/subagent_runtime/pool.py
  - cores/vault-io/src/vault_io/append_log.py
  - cores/vault-io/src/vault_io/ingest_work_item.py
  - docs/cancellation.md
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-05-17
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 08 wired MCP cancellation through `SubagentPool`, added an E2E subprocess test for all six tools, added a `repo_path` field to `WikiScanInput`, and documented the cancel chain in `docs/cancellation.md`. Auto-fix touches on `commands/init.py`, `commands/log.py`, `commands/scan.py`, `commands/ingest.py`, `vault_io/append_log.py`, and `vault_io/ingest_work_item.py` are intended to make `append_log` silent in MCP mode and to neutralize the `as_json=True` stdout footgun in `init_wiki`.

The cancel machinery in `SubagentPool` (per-item `status: cancelled` records, single batch terminal record, re-raise discipline) is correct and matches the contract documented in `docs/cancellation.md`. The `repo_path` plumbing through `wiki_scan` → `run_scan` is clean, including the deliberate `pinned=None` bypass when the override is supplied.

The one BLOCKER is in `test_mcp_cancel.py`: the test monkeypatches `model_adapter.loader.make_llm`, but `code_wiki_agent.commands.query` does `from model_adapter.loader import make_llm` at import time. That binding is what `run_query` calls. Patching the source module does not redirect the importer's local reference, so the slow stub is never installed and the test does not exercise the path it claims. The fact that the assertions still pass means either the test is racing differently than documented (real Bedrock calls under the hood?) or the trace records are coming from somewhere else — either way, the test does not give the promised guarantee.

Several warnings address residual `sys.exit(...)` / unguarded `print()` paths in `append_log._error` and an inconsistency between the `_PAGE_TYPE_DIRS` route table and the documented `page_type="work"` value in `IngestResult`.

## Critical Issues

### CR-01: `test_mcp_cancel.py` patches `make_llm` at the wrong import site

**File:** `agents/code-wiki-agent/tests/integration/test_mcp_cancel.py:82`
**Issue:** The test does:
```python
monkeypatch.setattr("model_adapter.loader.make_llm", lambda *a, **kw: fake_llm)
```
but `code_wiki_agent.commands.query` imports the symbol at module load:
```python
# query.py:44
from model_adapter.loader import load_role_config, make_llm
```
Python `from X import Y` creates a local binding in the importer's namespace. When `run_query` later calls `make_llm("librarian")` (query.py:856) it resolves against `code_wiki_agent.commands.query.make_llm`, not `model_adapter.loader.make_llm`. The monkeypatch rebinds the source module only, so the `fake_llm` stub is never used by the code under test. All other tests in the repo correctly target the importer (`test_query_code_fallback.py:212`, `test_query_result.py:416`, etc.):
```python
patch("code_wiki_agent.commands.query.make_llm")
```
Consequences:
1. The slow `await asyncio.sleep(3)` stub is never installed. The 0.05 s `asyncio.sleep` before `task.cancel()` is not actually racing a 3 s stub — it's racing whatever `make_llm("librarian")` returns by default, which under `model_adapter.loader` would attempt a real Bedrock invocation if AWS creds are present.
2. If the test "passes," the per-item `cancelled` trace records and `batch_cancelled` summary it asserts on come from cancellation against real (or partially constructed) ChatBedrockConverse instances, which makes the test cost real money on a per-run basis if creds are configured — and makes it non-deterministic if they are not.
3. The test docstring's "stub LLM means zero Bedrock cost" claim is false under this binding.

**Fix:**
```python
# Patch the binding inside code_wiki_agent.commands.query where it is actually used.
monkeypatch.setattr(
    "code_wiki_agent.commands.query.make_llm",
    lambda *a, **kw: fake_llm,
)
```
After fixing the patch site, re-run the test locally without AWS creds in the environment to confirm the slow stub is now exercised and no Bedrock call is attempted.

## Warnings

### WR-01: `append_log._error` calls `sys.exit(1)` from inside an MCP tool handler

**File:** `cores/vault-io/src/vault_io/append_log.py:39-44`
**Issue:** `_error` is invoked from `append_log` on every validation/IO failure (unknown op, missing wiki, missing log.md, write OSError — lines 71, 76, 84). It calls `sys.exit(1)` unconditionally. From an MCP tool handler (`commands/log.py:59` → `append_log(..., silent=True)`), this raises `SystemExit` rather than a normal Python exception — which `commands/log.py`'s docstring acknowledges ("SystemExit: If append_log calls sys.exit() on validation error (converted upstream)") but nothing in the chain actually converts it. `SystemExit` inherits from `BaseException`, so:
- `asyncio.CancelledError` handlers won't catch it.
- FastMCP's `except Exception` boundary won't catch it.
- The process terminates, killing the stdio MCP server and all subsequent tool calls.

`silent=True` only suppresses the success-path `print` — it does not neutralize `_error`. The fix submitted by Phase 08 (adding `silent=True` everywhere) is necessary but not sufficient.
**Fix:** Either raise a regular exception inside `append_log` when called as a library, or have `_error` branch on a `library_mode` flag:
```python
def _error(message, as_json=False, raise_exception=False):
    if raise_exception:
        raise ValueError(message)
    if as_json:
        print(json.dumps({"status": "error", "message": message}))
    else:
        print(f"[error] {message}", file=sys.stderr)
    sys.exit(1)
```
Then pass `raise_exception=True` from `commands/log.py`/`commands/scan.py`/`commands/ingest.py` / `vault_io/ingest_work_item.py` callers, or simply have `append_log` raise directly on the error paths and reserve `_error` for the CLI `main()` entry point.

### WR-02: `append_log._error` still writes to stdout when `as_json=True`

**File:** `cores/vault-io/src/vault_io/append_log.py:40-41`
**Issue:** Even though all current MCP callers pass `silent=True` and the default `as_json=False`, the `_error` helper unconditionally `print(json.dumps(...))` to stdout when `as_json=True`. A future caller that accidentally enables `as_json=True` from inside the MCP server would trip `_StdoutGuard` on the error path — the very class of bug Phase 08 was designed to prevent. The fact that `init_wiki` (cores/vault-io/src/vault_io/init_vault.py) was patched to log instead of print (line 138, `logger.error("%s", message)`) but `append_log._error` was not is inconsistent.
**Fix:** Route the error-path JSON to stderr or to `logger.error`. The CLI's `--json` contract can still be honored on stdout because `_error` only runs on hard failures, and the CLI is not stdout-sensitive the way the MCP server is.

### WR-03: `_PAGE_TYPE_DIRS` does not include `"work"` despite docstring claim

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:55-79`
**Issue:** `IngestResult.page_type`'s docstring says: `"Page category: package, concept, adr, or work."` But `_PAGE_TYPE_DIRS` (lines 74-79) only maps `package`, `concept`, `adr`, `source`. In `run_ingest_source`, line 428-429:
```python
if page_type not in _PAGE_TYPE_DIRS:
    page_type = "concept"
```
So if the LLM legitimately returns `page_type: work`, it is silently coerced to `concept` and routed into `concepts/`. Work pages are produced by `run_ingest_work_item`, which explicitly sets `page_type="work"` (line 551) but does not go through `_route_target_path` (it uses `file_work_item`, which writes under `<workspace>/work/`). So the dropdown coverage gap matters for the source-ingestion path specifically — an LLM that classifies a source file as a work item silently loses that signal.

A second oddity: `_PAGE_TYPE_DIRS` includes `"source"` (line 78) but the ingestor prompt told the LLM to choose only from `(package, concept, or adr)` (line 339-340 of `build_ingest_source_prompt`). The `source` mapping is unreachable from the LLM and the `_route_target_path` fallback skips it. Either the prompt should mention source, or `source` should be dropped from `_PAGE_TYPE_DIRS`.

**Fix:** Either add `"work": "work"` (and add `"source"` mention to the prompt and `IngestResult` docstring), or remove `"source"` from `_PAGE_TYPE_DIRS` and add `work` to either the docstring exclusion or the routing table. Pick a single source of truth.

### WR-04: E2E test sends `wiki_scan` before `wiki_init` completes — potential ordering race

**File:** `agents/code-wiki-agent/tests/integration/test_mcp_e2e.py:277-288`
**Issue:** All six tool calls are queued to stdin in one write (`payloads = [...]`, then `_run_server_long(payloads, ...)`). `_run_server_long` writes the full payload to stdin and only later reads stdout. MCP/FastMCP handlers run concurrently by default (anyio TaskGroup), so:
- `wiki_init` (id=2), `wiki_scan` (id=3), `wiki_ingest` (id=4), `wiki_query` (id=5), `wiki_lint` (id=6), `wiki_log` (id=7) can all start before the vault exists.
- If `wiki_scan` runs first, it will hit `wiki/` not existing and either fail (`isError=True` would fail the assertion) or get a different `state_gate` result than expected.
- The test passes today only because the Bedrock-bound calls have enough latency that the local `wiki_init` finishes first by accident — that ordering is not enforced anywhere.

The comment on line 281 — `# repo_path = tmp_path (NEW FIELD)` — acknowledges that scan depends on `tmp_path`, but the test does not gate `wiki_scan` on `wiki_init` completion.

**Fix:** Either send each request in a separate `_run_server_long` call (one request at a time, await response, send next), or pass the full payload but inspect responses in order, fail fast if any earlier ID returns `isError=True`, and tolerate a wiki-missing failure on `wiki_scan` only if it deterministically arrives after `wiki_init`. The simplest correct shape: send `initialize` + `initialized` first, then send each tool call serially, awaiting its response before queuing the next.

### WR-05: `_resolve_wikilinks` walks the full vault on every ingest — O(vault_size) per source page

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py:171-179`
**Issue:** `_resolve_wikilinks` calls `wiki.rglob("*.md")` to build `known_relpaths` and `known_basenames` on every `run_ingest_source` call. The author's own comment acknowledges "rglob is O(vault_size) — acceptable: vaults are <10k files." This is true for current vaults, but the function is invoked unconditionally even when the LLM produced zero `[[wikilinks]]`. A trivial early-exit check before the rglob would avoid the disk walk in the common case.
**Fix:** Scan `text` for any occurrence of `[[` before doing the rglob:
```python
if "[[" not in text:
    return text, []
# ... existing rglob logic ...
```
Note: this is a correctness optimization (avoiding wasted IO), not a performance-only finding — in a large vault the disk walk also takes a non-trivial wallclock slice of the ingest pipeline, which matters for the cost-frontier eval harness.

## Info

### IN-01: Unused `field` import in `commands/init.py`

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/init.py:14`
**Issue:** `from dataclasses import dataclass, field` — `field` is imported but never used (none of the `InitResult` fields use `field(default_factory=...)`).
**Fix:** `from dataclasses import dataclass`

### IN-02: `commands/log.py` docstring mentions `SystemExit` conversion that does not exist

**File:** `agents/code-wiki-agent/src/code_wiki_agent/commands/log.py:53-54`
**Issue:** Docstring says: `"SystemExit: If append_log calls sys.exit() on validation error (converted upstream)."` There is no upstream conversion — `run_log` will propagate `SystemExit` directly into the MCP handler, killing the server. Either fix `append_log` (see WR-01) or update the docstring to be accurate about the failure mode.
**Fix:** Update docstring once WR-01 is addressed.

### IN-03: `_StdoutGuard.write` returns `len(data)` for whitespace-only data

**File:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py:42-45`
**Issue:** The guard returns `len(data)` (not 0) after the strip-check passes. For a write of `"   "` (3 spaces), it claims 3 bytes were written but discarded them. Any caller that reads `n_written` to track buffer position would observe progress despite no IO. Low risk since no realistic caller does this, but it's a subtle invariant lie.
**Fix:** Return 0 when data is stripped to empty:
```python
def write(self, data: str) -> int:
    if data.strip():
        raise RuntimeError(...)
    return 0
```
Or, more strictly, raise on any non-empty write (`if data: raise ...`) since the FastMCP raw stream goes through `buffer` and never through `write`.

### IN-04: `cancel test` 0.05 s race is documented as "deterministic" but depends on the (broken) patch

**File:** `agents/code-wiki-agent/tests/integration/test_mcp_cancel.py:117-122`
**Issue:** The comment claims the 0.05 s yield is deterministic with the 3 s stub sleep (60:1 ratio). Once CR-01 is fixed and the patch actually takes, the 60:1 ratio is sound. But documenting this as deterministic while the stub is not actually wired is misleading to future readers debugging flakiness. After fixing CR-01, re-validate the comment's claim by running the test 100x with `--count=100`.
**Fix:** Resolve CR-01, then verify the ratio holds. No code change needed beyond CR-01.

---

_Reviewed: 2026-05-17_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
