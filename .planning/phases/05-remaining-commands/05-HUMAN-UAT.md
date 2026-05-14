---
status: partial
phase: 05-remaining-commands
source: [05-VERIFICATION.md]
started: 2026-05-14T20:00:00Z
updated: 2026-05-14T20:00:00Z
---

## Current Test

[awaiting human testing / decision]

## Tests

### 1. Live Bedrock smoke test — scan + lint LLM paths
expected: `code-wiki-agent scan` and `code-wiki-agent lint` complete successfully against a real vault with AWS credentials set, SubagentPool fan-out fires real Bedrock calls, and structured results are returned.
result: [pending]

### 2. SC-5 parity baseline scope decision
expected: Developer decides whether fixture-invariant parity tests (structural assertions on fixture vaults) are sufficient for Phase 5 non-LLM commands, or whether lattice-wiki baselines need to be recorded for scan/lint/ingest/log/init.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
