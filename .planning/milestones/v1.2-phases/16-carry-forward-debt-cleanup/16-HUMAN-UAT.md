---
status: complete
phase: 16-carry-forward-debt-cleanup
source: [16-VERIFICATION.md, 16-02-SUMMARY.md]
started: 2026-05-19T00:00:00Z
updated: 2026-05-19T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Run the gated TRACE-FU-01 regression test against real Bedrock
expected: `GRAPH_WIKI_RUN_INTEGRATION=1 uv run pytest agents/graph-wiki-agent/tests/integration/test_trace_coverage.py -x -v` exits 0 and the assertion `tokens_in/tokens_out is not None` holds for every non-error / non-event JSONL record produced by a real fan-out against the round-trip fixture vault.
result: pass
verified: 2026-05-19 (Phase 16-02 closure) — gated Bedrock re-run `1 passed in 14.02s` after TaskResult contract migration of all 4 fan-out callsites (scanner, linter, librarian, code_reader). Sample librarian success records: `concepts/code-wiki-pattern.md` tokens_in=2804 tokens_out=119 cost_usd=$0.003399. Closure documented in 16-02-SUMMARY.md and 16-VERIFICATION.md G-01 entry (status: CLOSED, SC#1 ✓ VERIFIED). Commits: e97ae7f, 629f077, 4df6ace, 68de2ca.

### 2. Confirm acceptance of judgment-driven substitution for SC#2 live model-sweep
expected: Pat confirms (or rejects) that the deterministic SCANNER_CHECKS pass-rate of 65% on the live vault (`~/Personal/graph-wiki/agent-research`) — with 7 SCN-002/SCN-003 failures attributed to a known structural mismatch (rules target raw LLM stub output; on-disk pages contain pipeline-appended `## File map`) — counts as "no regression vs. v1.1 baseline" without running an actual `run_role_sweep` invocation against the live vault.
result: pass
verdict: 2026-05-19 — Pat accepted the D-12 scope-down. The 65% deterministic SCANNER_CHECKS pass-rate on the live vault (`~/Personal/graph-wiki/agent-research`), with 7 SCN-002/SCN-003 failures excused as structural mismatch (rules target raw LLM stub output; on-disk pages carry pipeline-appended `## File map`), is accepted as "no regression vs. v1.1 baseline" in lieu of running `run_role_sweep` live. Operator-acknowledged risk: an LLM-level scanner regression in v1.2 that the deterministic checks miss.

### 3. Confirm that the "fresh re-evaluation date" phrasing in SC#3 is satisfied by the event-driven re-eval trigger in docs/cancellation.md §5
expected: Pat confirms that the event-driven trigger ("Re-evaluate when langchain-aws cuts a release with #663 merged, OR when aioboto3 reaches a named milestone (GA / 1.0)") is acceptable in place of a calendar-date re-evaluation. Per D-09 the calendar phrasing was deliberately removed because v1.1->v1.2 calendar re-checks generated noise without changing the gate outcome.
result: pass
verdict: 2026-05-19 — Pat accepted the D-09 deviation. The event-driven trigger in `docs/cancellation.md §5` (langchain-aws#663 merged OR aioboto3 GA/1.0) is accepted as satisfying the intent of SC#3 ("anchor the deferral to a checkable signal") in place of the literal "re-evaluation date" wording. Rationale stands: calendar re-checks generated noise without changing the gate outcome.

### 4. Confirm SC#2 "code_reader cases produce non-trivial scores" is acceptable as "cases load and tag-validate cleanly + are structured to force code-fallback"
expected: Pat confirms that cases 04-06 of `eval/cases/code_reader_cases.json` (each phrased to force the code-fallback path against post-rebrand surfaces) constitute acceptable evidence in the absence of a real sweep producing actual numeric scores.
result: pass
verdict: 2026-05-19 — Pat accepted the structural evidence in lieu of actual numeric scores. Cases 04-06 (workspace_io.config.resolve, wiki_io.wiki_search BM25, wiki_io.lint_wiki.scan) are each phrased to force the code-fallback path against post-rebrand surfaces; all 6 cases load + tag-validate (`test_code_reader_cases_json_loads` PASS). Acknowledged risk: no actual sweep was run, so no numeric scores exist; if the sweep ever runs, the cases are positioned to exercise the metric correctly.

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

### G-01: librarian fan-out trace records drop usage_metadata (CLOSED 2026-05-19 via Phase 16-02)
status: closed
source_test: 1
evidence: |
  GRAPH_WIKI_RUN_INTEGRATION=1 uv run pytest \
    agents/graph-wiki-agent/tests/integration/test_trace_coverage.py -x -v
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
