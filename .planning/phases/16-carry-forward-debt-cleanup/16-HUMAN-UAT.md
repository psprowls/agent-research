---
status: partial
phase: 16-carry-forward-debt-cleanup
source: [16-VERIFICATION.md]
started: 2026-05-19T00:00:00Z
updated: 2026-05-19T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Run the gated TRACE-FU-01 regression test against real Bedrock
expected: `CODE_WIKI_RUN_INTEGRATION=1 uv run pytest agents/code-wiki-agent/tests/integration/test_trace_coverage.py -x -v` exits 0 and the assertion `tokens_in/tokens_out is not None` holds for every non-error / non-event JSONL record produced by a real fan-out against the round-trip fixture vault.
result: [pending]

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
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
