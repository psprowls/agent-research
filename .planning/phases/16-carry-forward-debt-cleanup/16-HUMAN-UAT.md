---
status: partial
phase: 16-carry-forward-debt-cleanup
source: [16-VERIFICATION.md]
started: 2026-05-19T00:00:00Z
updated: 2026-05-19T00:00:00Z
---

## Current Test

Item 1 failed against real Bedrock — librarian fan-out trace records emit `tokens_in: None, tokens_out: None` despite `status: success`. TRACE-FU-01 is partially implemented (synthesizer + ingest call sites only). See Gaps.

## Tests

### 1. Run the gated TRACE-FU-01 regression test against real Bedrock
expected: `CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v` exits 0 and the assertion `tokens_in/tokens_out is not None` holds for every non-error / non-event JSONL record produced by a real fan-out against the round-trip fixture vault.
result: FAILED on 2026-05-19 — librarian record (model `us.anthropic.claude-haiku-4-5-20251001-v1:0`, item `packages/lattice-curator-core/context.md`, status=success, latency=4131ms) has `tokens_in: None, tokens_out: None, cost_usd: None`. Root cause: `drill_page` in `query.py:903-914` returns `resp.content` only; `SubagentPool.run_all` (`pool.py`) writes its own trace record but never sees `usage_metadata` because the task callback discards it.

### 2. Confirm acceptance of judgment-driven substitution for SC#2 live model-sweep
expected: Pat confirms (or rejects) that the deterministic SCANNER_CHECKS pass-rate of 65% on the live vault (`~/Personal/wiki/deep-agents`) — with 7 SCN-002/SCN-003 failures attributed to a known structural mismatch (rules target raw LLM stub output; on-disk pages contain pipeline-appended `## File map`) — counts as "no regression vs. v1.1 baseline" without running an actual `run_role_sweep` invocation against the live vault.
result: [pending]

### 3. Confirm that the "fresh re-evaluation date" phrasing in SC#3 is satisfied by the event-driven re-eval trigger in docs/cancellation.md §5
expected: Pat confirms that the event-driven trigger ("Re-evaluate when langchain-aws cuts a release with #663 merged, OR when aioboto3 reaches a named milestone (GA / 1.0)") is acceptable in place of a calendar-date re-evaluation. Per D-09 the calendar phrasing was deliberately removed because v1.1->v1.2 calendar re-checks generated noise without changing the gate outcome.
result: [pending]

### 4. Confirm SC#2 "code_reader cases produce non-trivial scores" is acceptable as "cases load and tag-validate cleanly + are structured to force code-fallback"
expected: Pat confirms that cases 04-06 of `eval/cases/code_reader_cases.json` (each phrased to force the code-fallback path against post-rebrand surfaces) constitute acceptable evidence in the absence of a real sweep producing actual numeric scores.
result: [pending]

## Summary

total: 4
passed: 0
issues: 1
pending: 3
skipped: 0
blocked: 0

## Gaps

### G-01: librarian fan-out trace records drop usage_metadata
status: failed
source_test: 1
evidence: |
  CODE_WIKI_RUN_INTEGRATION=1 uv run pytest \
    agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v
  -> FAILED on librarian record:
     model=us.anthropic.claude-haiku-4-5-20251001-v1:0
     item=packages/lattice-curator-core/context.md
     status=success latency_ms=4131
     tokens_in=None tokens_out=None cost_usd=None
root_cause: |
  `drill_page` in query.py:903-914 returns `resp.content` only.
  `SubagentPool.run_all` writes per-item trace records in pool.py via
  `write_trace_record`, but the pool only sees the string returned by the
  task callback — `usage_metadata` is discarded before the pool can write it.
remediation_options:
  - Change `drill_page` to return (content, tokens_in, tokens_out); update
    `SubagentPool.run_all` task contract to accept a structured return.
  - Pool-side: pass the response-aware callback through and have the pool
    extract `usage_metadata` itself before logging the trace record.
  - Per-item: have `drill_page` write its own supplementary trace record
    parallel to the pool's, mirroring the synthesizer pattern (synth_*.jsonl).
scope: TRACE-FU-01 (partial — librarian path only; ingest + synthesizer call
       sites are correctly wired and still verified by 16 unit tests).
