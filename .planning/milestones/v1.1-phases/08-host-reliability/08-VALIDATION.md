---
phase: 8
slug: host-reliability
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-17
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from RESEARCH.md §"Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest ≥8.3 + pytest-asyncio 1.3.0 |
| **Config file** | `agents/graph-wiki-agent/pyproject.toml` (`asyncio_mode = "auto"`) |
| **Quick run command** | `uv run --package graph-wiki-agent pytest tests/integration/test_mcp_cancel.py -x` |
| **Full suite command** | `uv run --package graph-wiki-agent pytest -x` |
| **Integration suite command** | `GRAPH_WIKI_RUN_INTEGRATION=1 uv run --package graph-wiki-agent pytest -x` |
| **Estimated runtime** | ~5–10s quick (stub cancel); ~60–180s full integration (4/6 tools hit Bedrock) |

---

## Sampling Rate

- **After every task commit:** Run `uv run --package graph-wiki-agent pytest tests/integration/test_mcp_cancel.py -x` (stub cancel test — no Bedrock cost)
- **After every plan wave:** Run `uv run --package graph-wiki-agent pytest -x` (full non-integration suite)
- **Before `/gsd:verify-work`:** `GRAPH_WIKI_RUN_INTEGRATION=1 uv run --package graph-wiki-agent pytest -x` must be green
- **Max feedback latency:** ~10s for per-commit sampling

---

## Per-Task Verification Map

> Task IDs are placeholders until PLAN.md files are authored; the planner backfills them.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 1 | MCP-10 | — | `_run_one` writes per-item `status: cancelled` trace before re-raising CancelledError | unit | `pytest tests/integration/test_mcp_cancel.py::test_cancel_mid_fan_out -x` | ❌ W0 | ⬜ pending |
| 8-01-02 | 01 | 1 | MCP-10 | — | `run_all` writes terminal `event: batch_cancelled` summary line on outer cancel | unit | `pytest tests/integration/test_mcp_cancel.py::test_cancel_mid_fan_out -x` | ❌ W0 | ⬜ pending |
| 8-01-03 | 01 | 1 | MCP-10 / MCP-11 | — | `_write_trace` + `_write_batch_terminal` never raise; OSError logged WARNING | unit | `pytest tests/integration/test_mcp_cancel.py -x` | ❌ W0 | ⬜ pending |
| 8-01-04 | 01 | 1 | MCP-11 | — | Cancel test runs without `GRAPH_WIKI_RUN_INTEGRATION=1` (stub model) | unit | `pytest tests/integration/test_mcp_cancel.py -x` | ❌ W0 | ⬜ pending |
| 8-02-01 | 02 | 2 | DACLI-02 | — | `WikiScanInput` accepts `repo_path`; `wiki_scan` passes it to `run_scan` | unit | `pytest tests/unit/test_wiki_scan_input.py -x` | ❌ W0 | ⬜ pending |
| 8-02-02 | 02 | 2 | DACLI-01 / DACLI-03 | — | Subprocess `graph-wiki-mcp` launches; initialize+initialized handshake succeeds | integration | `GRAPH_WIKI_RUN_INTEGRATION=1 pytest tests/integration/test_mcp_e2e.py::test_all_six_tools_end_to_end -x` | ❌ W0 | ⬜ pending |
| 8-02-03 | 02 | 2 | DACLI-02 | — | All 6 tools (`wiki_init`, `wiki_scan`, `wiki_ingest`, `wiki_query`, `wiki_lint`, `wiki_log`) return non-error JSON-RPC responses against seeded `tmp_path` vault | integration | same as 8-02-02 | ❌ W0 | ⬜ pending |
| 8-03-01 | 03 | 2 | MCP-09 | — | `docs/cancellation.md` covers 5 sections (protocol, chain, trace shapes, limitations, future work) | manual | — | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Invariants

1. `_write_trace` never raises — OSError logged at WARNING, no exception propagates to `_run_one`.
2. `_write_batch_terminal` never raises — same contract.
3. After outer cancel, `run_all` always re-raises `CancelledError` (FastMCP depends on this).
4. Per-item `cancelled` records are written BEFORE the re-raise in `_run_one` (ordering invariant).
5. The `event: batch_cancelled` record is the final record in the trace file when a cancel occurs.

---

## Wave 0 Requirements

- [ ] `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py` — stubs for MCP-10, MCP-11
- [ ] `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` — stubs for DACLI-01, DACLI-02, DACLI-03
- [ ] `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py` — stub for `WikiScanInput.repo_path` (DACLI-02 precondition)

*Existing infrastructure: `tests/conftest.py` already exposes `INTEGRATION_GATE` skip-marker pattern — reuse.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docs/cancellation.md` reads accurately and covers orphan-thread caveat | MCP-09 | Doc quality is subjective; covered in `/gsd:verify-work` review | Read the doc; confirm 5 sections present per D-15; confirm orphan-thread caveat from D-05 is stated |
| Orphan boto3 thread behaves as documented (best-effort cancel) | MCP-09 (docs accuracy) | Asserting thread state is flaky; orphan threads are expected | Optional smoke: `GRAPH_WIKI_RUN_INTEGRATION=1` run a real cancel via direct asyncio, observe asyncio task returns promptly while boto3 thread completes in background |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s for per-commit sampling
- [ ] `nyquist_compliant: true` set in frontmatter (after planner backfills task IDs)

**Approval:** pending
