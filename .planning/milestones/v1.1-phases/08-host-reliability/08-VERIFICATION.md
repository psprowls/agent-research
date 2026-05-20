---
phase: 08-host-reliability
verified: 2026-05-17T00:00:00Z
status: human_needed
score: 6/6 must-haves verified (2 ROADMAP SC deviations need owner acknowledgment)
overrides_applied: 0
gaps: []
human_verification:
  - test: "Confirm SC#1 deviation is acceptable: cancel test does not use a real DeepAgents CLI host"
    expected: "Owner acknowledges that direct-asyncio cancel test + docs/cancellation.md satisfies SC#1 intent, deferring real-DA-CLI verification to v1.2+"
    why_human: "ROADMAP SC#1 says 'under the real DeepAgents CLI host' — test uses direct asyncio with stub LLM. The RESEARCH/PLAN documented this as an intentional scope narrowing. Needs owner sign-off."
  - test: "Confirm SC#2 / MCP-11 deviation is acceptable: cancel test runs without opt-in gate"
    expected: "Owner acknowledges that running test_mcp_cancel.py unconditionally (no GRAPH_WIKI_RUN_INTEGRATION=1 gate) satisfies the zero-cost stub rationale documented in the PLAN"
    why_human: "ROADMAP SC#2 and MCP-11 both say 'opt-in gate consistent with v1.0 integration tests' — test runs unconditionally. PLAN intentionally omitted the gate because the test uses a stub LLM and incurs zero cost. Needs owner sign-off."
---

# Phase 8: Host Reliability Verification Report

**Phase Goal:** MCP cancellation is proven clean under a real DeepAgents CLI host and every MCP tool is exercised by an end-to-end integration test
**Verified:** 2026-05-17
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When the asyncio task running SubagentPool.run_all is cancelled mid-fan-out, each in-flight _run_one writes a per-item trace record with status: cancelled before re-raising CancelledError | VERIFIED | pool.py lines 141-146: `except asyncio.CancelledError` branch before `except Exception`, calls `_write_trace(..., "cancelled", ...)`, then `raise`. Confirmed by passing cancel test. |
| 2 | After CancelledError propagates out of asyncio.gather, run_all writes exactly one terminal trace record with event: batch_cancelled, then re-raises | VERIFIED | pool.py lines 158-169: `except asyncio.CancelledError` around gather, calls `_write_batch_terminal(...)`, then `raise`. Single call site confirmed by grep. |
| 3 | _write_trace and _write_batch_terminal never raise; OSError on write is logged at WARNING and swallowed | VERIFIED | pool.py lines 226-230 (_write_trace) and 259-263 (_write_batch_terminal): both wrap file write in `try / except OSError as exc: logger.warning(...)`. |
| 4 | The cancel test runs unconditionally (no gate) and consumes zero Bedrock cost — make_llm is monkeypatched to a slow stub | VERIFIED | test_mcp_cancel.py has no INTEGRATION_GATE. `monkeypatch.setattr("graph_wiki_agent.commands.query.make_llm", ...)` targets the importer's namespace (CR-01 fix confirmed at line 86). Test passes in 0.41s. |
| 5 | WikiScanInput accepts an explicit repo_path string; wiki_scan handler passes it through to run_scan | VERIFIED | server.py lines 246-249: `repo_path: str = Field("", ...)` added to WikiScanInput. Line 272: `repo_path=Path(input.repo_path).resolve() if input.repo_path else None`. All 3 schema unit tests pass. |
| 6 | A single E2E test launches graph-wiki-mcp as a stdio subprocess and exercises all six tools sequentially against a fresh tmp_path vault | VERIFIED | test_mcp_e2e.py exists with `@INTEGRATION_GATE` decorated `test_all_six_tools_end_to_end`. Uses `_run_server_serial` (WR-04 fix: serial ordering). Skips without gate. All 6 tools exercised with `isError: False` assertions. |

**Score: 6/6 plan truths verified**

### ROADMAP Success Criteria vs Implementation

Two ROADMAP success criteria deviate from what was implemented. Both deviations are documented in the PLAN and RESEARCH with explicit rationale. Neither constitutes missing functionality — they are intentional scope decisions that require owner acknowledgment.

| SC | ROADMAP Wording | Implementation | Gap |
|----|-----------------|----------------|-----|
| SC#1 | "cancel-mid-fan-out under the real DeepAgents CLI host ... no orphaned calls" | Direct-asyncio cancel test with stub LLM. No real DA CLI. No real Bedrock calls cancelled. | PLAN intentionally narrowed: "MCP protocol framing validated by the FastMCP SDK itself" (RESEARCH.md). Orphan-thread behavior documented in docs/cancellation.md §4 as a v1.1 limitation. |
| SC#2 | "automated cancel test ... runs under the standard opt-in gate" | Cancel test runs unconditionally — no GRAPH_WIKI_RUN_INTEGRATION=1 gate. | PLAN intentionally omitted gate because test uses stub LLM (zero Bedrock cost). Gate exists to prevent accidental cost; not applicable to cost-free tests. |

These are NOT gaps in the PLAN artifacts — they are architectural decisions made during research that narrowed the ROADMAP scope. They require human acknowledgment before the phase is marked complete.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cores/subagent-runtime/src/subagent_runtime/pool.py` | CancelledError branch + _write_batch_terminal | VERIFIED | Lines 141-146: except CancelledError before except Exception. Lines 155-169: gather wrapped in try/except CancelledError. Lines 232-263: _write_batch_terminal method. |
| `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py` | Direct-asyncio cancel-mid-fan-out test | VERIFIED | Exists. 169 lines. `test_cancel_mid_fan_out` async function. Correct patch target (`graph_wiki_agent.commands.query.make_llm`). All 4 trace invariants asserted. Passes in 0.41s. |
| `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` | WikiScanInput.repo_path field + wiki_scan passthrough | VERIFIED | Lines 246-249: repo_path field. Line 272: `Path(...).resolve() if input.repo_path else None` idiom. |
| `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py` | Schema unit tests for WikiScanInput.repo_path | VERIFIED | 3 tests: default empty, explicit value, regression guard on existing fields. All pass. |
| `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` | INTEGRATION_GATE-gated 6-tool subprocess E2E test | VERIFIED | 332 lines. Serial subprocess pattern (`_run_server_serial`). All 6 tools in order. INTEGRATION_GATE applied. Skips correctly without gate. |
| `docs/cancellation.md` | v1.1 cancellation reference doc, 100-250 lines | VERIFIED | 210 lines. 5 sections in required order. Contains: batch_cancelled, run_in_executor, boto3, notifications/cancelled. No emojis. Framed as "spec-conformant MCP host." |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_run_one` (pool.py) | `_write_trace` (pool.py) | `status='cancelled'` branch | VERIFIED | pool.py:143-145: `self._write_trace(trace_file, role, model_id, item, "cancelled", latency_ms, None)` |
| `run_all` (pool.py) | `_write_batch_terminal` (pool.py) | `except asyncio.CancelledError` around gather | VERIFIED | pool.py:158-169: single call site at line 160. Grep confirms no other call sites. |
| `test_mcp_cancel.py` | `graph_wiki_agent.commands.query.make_llm` | `monkeypatch.setattr` | VERIFIED | Line 86: `"graph_wiki_agent.commands.query.make_llm"` — correct importer namespace (CR-01 fix). |
| `WikiScanInput.repo_path` | `run_scan(repo_path=...)` | wiki_scan handler passthrough | VERIFIED | server.py:272: `repo_path=Path(input.repo_path).resolve() if input.repo_path else None` |
| `test_mcp_e2e.py` | `graph-wiki-mcp` subprocess | `subprocess.Popen(['uv', 'run', '--package', 'graph-wiki-agent', 'graph-wiki-mcp'])` | VERIFIED | test_mcp_e2e.py:75-80: Popen call with correct args. |
| `test_mcp_e2e.py wiki_scan call` | `tmp_path` | `"repo_path": str(tmp_path)` in tool arguments | VERIFIED | test_mcp_e2e.py:304: `_send_wiki_scan(3, str(vault), str(tmp_path))`. |
| `docs/cancellation.md §3` | pool.py trace shapes | JSON record examples | VERIFIED | Doc §3 shows both record shapes; cross-checked against pool.py `_write_trace` and `_write_batch_terminal` fields in 08-03-SUMMARY.md trace-cross-check table — all fields match. |
| `docs/cancellation.md §4` | CONTEXT.md D-05 orphan-thread caveat | `run_in_executor` + boto3 mechanism | VERIFIED | docs/cancellation.md:161-189: full mechanism documented with `run_in_executor`, ThreadPoolExecutor, botocore no socket-close. |

### Data-Flow Trace (Level 4)

The cancel test exercises dynamic trace writes — verified data flows through the full chain.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `test_mcp_cancel.py` | `cancelled` / `batch` trace lines | `_write_trace` / `_write_batch_terminal` in `pool.py` via `run_query` → `SubagentPool.run_all` | Yes — real JSONL writes to tmp_path trace dir; test reads and parses them | FLOWING |
| `test_mcp_e2e.py` | `responses` (JSON-RPC) | Real `graph-wiki-mcp` subprocess via stdio | Yes — gated; SUMMARY confirms 6.1s run with all 6 tools returning `isError: False` | FLOWING (gated) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Cancel test passes (no gate, no cost) | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py -x -v` | 1 passed in 0.41s | PASS |
| WikiScanInput schema tests pass | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py -x -v` | 3 passed in 0.51s | PASS |
| E2E test skips without gate | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py -x -v` | 1 skipped | PASS |
| Full non-integration suite — no regressions | `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/ -x -k "not e2e and not integration"` | 165 passed, 9 deselected in 9.13s | PASS |
| subagent-runtime own suite — no regressions in pool.py | `uv run --package subagent-runtime pytest cores/subagent-runtime/tests/ -x` | 12 passed, 3 skipped in 0.14s | PASS |
| _write_batch_terminal called in exactly one place | `grep -rn "_write_batch_terminal" cores/subagent-runtime/src/` | pool.py:160 (call) and pool.py:232 (definition) | PASS |
| except CancelledError placed before except Exception | `grep -n "except asyncio.CancelledError\|except Exception"` | lines 141, 147 — CancelledError before Exception | PASS |
| cancellation.md has 5 sections, 210 lines, no emojis | `grep -c "^## "` / `wc -l` / emoji grep | 5 sections, 210 lines, no emojis | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| MCP-09 | 08-03 | Mid-fan-out cancel documented | SATISFIED | `docs/cancellation.md` (210 lines, 5 sections); covers protocol, chain, trace shapes, limitations, future work |
| MCP-10 | 08-01 | In-flight SubagentPool invocations terminate cleanly; traces close with cancelled terminal event | SATISFIED | pool.py CancelledError branch + _write_batch_terminal + passing cancel test |
| MCP-11 | 08-01 | Automated cancel test at MCP transport boundary, opt-in gate | PARTIAL — see human verification | Cancel chain tested via direct asyncio (not MCP transport). No opt-in gate (PLAN intentional). Needs owner sign-off. |
| DACLI-01 | 08-02 | E2E test launches graph-wiki-mcp as stdio subprocess | SATISFIED | test_mcp_e2e.py:75-80 Popen. SUMMARY confirms 6.1s run. |
| DACLI-02 | 08-02 | All 6 tools exercised with non-error outcomes | SATISFIED | test_mcp_e2e.py:325-331: asserts non-error for ids 2-7. SUMMARY: all 6 returned isError: False. |
| DACLI-03 | 08-02 | Runs under GRAPH_WIKI_RUN_INTEGRATION=1 gate | SATISFIED | test_mcp_e2e.py:20-23: INTEGRATION_GATE defined and applied at line 285. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No TBD/FIXME/XXX markers found in phase-modified files. No return null/empty stubs found. |

No debt markers, no placeholder stubs, no hardcoded empty returns in any phase-modified file.

### Human Verification Required

#### 1. SC#1 Deviation: Cancel Test Does Not Use Real DeepAgents CLI Host

**Test:** Review ROADMAP.md Phase 8 SC#1 against test_mcp_cancel.py design. Decide whether direct-asyncio test + docs/cancellation.md §4 (orphan-thread caveat) satisfies the SC intent for this phase.

**Expected:** Either (a) owner accepts the deviation and acknowledges that real-DA-CLI cancel verification is deferred to v1.2+ (when aioboto3 enables wire-level cancel), or (b) owner requires a gated subprocess test that sends a real `notifications/cancelled` JSON-RPC notification and asserts the pool.py cancel chain fires.

**Why human:** ROADMAP SC#1 says "under the real DeepAgents CLI host" — the test uses direct asyncio. The RESEARCH explicitly recommended this as adequate ("MCP protocol framing validated by the FastMCP SDK itself"). This is a deliberate architectural scope decision, not an implementation oversight. Only the owner can decide if this satisfies the phase contract.

#### 2. SC#2 / MCP-11 Deviation: Cancel Test Runs Without Opt-In Gate

**Test:** Review ROADMAP.md Phase 8 SC#2 and REQUIREMENTS.md MCP-11 ("opt-in gate consistent with v1.0 integration tests") against the fact that test_mcp_cancel.py runs unconditionally with no GRAPH_WIKI_RUN_INTEGRATION=1 gate.

**Expected:** Either (a) owner accepts the deviation — zero-cost stub test does not need the cost-protection gate — and the gate requirement is interpreted as "applies to tests that incur Bedrock cost," or (b) owner requires adding INTEGRATION_GATE to test_mcp_cancel.py to match MCP-11's literal wording.

**Why human:** MCP-11 says "opt-in gate consistent with v1.0" — the cancel test has no gate. The PLAN justified this explicitly: the gate exists to prevent accidental Bedrock cost; the cancel test incurs zero cost. Whether a zero-cost test nonetheless requires the gate for consistency is a policy decision only the owner can make.

---

## Gaps Summary

No implementation gaps found. All six plan must-haves are verified at all artifact levels (exists, substantive, wired, data-flowing). The two items in human verification are documented architectural scope decisions made during research and planning — they are deviations from ROADMAP SC wording, not missing implementations.

**Pre-existing test failure (excluded from scoring):** `cores/model-adapter/tests/test_loader.py::test_load_role_config_synthesizer_uses_sonnet` — caused by Qwen model config override (project memory: synthesizer now uses qwen3-32b). Pre-dates Phase 8; unrelated.

---

_Verified: 2026-05-17_
_Verifier: Claude (gsd-verifier)_
