---
status: complete
phase: 05-remaining-commands
source: [05-VERIFICATION.md]
started: 2026-05-14T20:00:00Z
updated: 2026-05-14T21:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Live Bedrock smoke test — scan + lint LLM paths
expected: `code-wiki-agent scan` and `code-wiki-agent lint` complete successfully against a real vault with AWS credentials set, SubagentPool fan-out fires real Bedrock calls, and structured results are returned.
result: pass
evidence: |
  scan: After removing cores/vault-io/vault-io.md from vault, re-running scan produced `added: ["vault-io"]`, scanner role wrote a 2690-byte page with valid frontmatter (title/category/summary/package_path), Overview section, and Notable files section sourced from Bedrock.
  lint: Returned full LintResult JSON with mechanical findings (6 orphans, 9 broken_links, 4 package_sync_drift, code_drift) and semantic_findings populated by Bedrock 3-group fan-out — page_quality: 10 entries, stale_claims: 4 entries, adr_chain: [] (vault has no ADR pages). errors: []. state_gate.allowed=true once worktree was clean and on a branch.

### 2. SC-5 parity baseline scope decision
expected: Developer decides whether fixture-invariant parity tests (structural assertions on fixture vaults) are sufficient for Phase 5 non-LLM commands, or whether lattice-wiki baselines need to be recorded for scan/lint/ingest/log/init.
result: pass
decision: Accept fixture-invariant parity tests as sufficient for Phase 5 non-LLM commands. Recording lattice-wiki baselines for scan/lint/ingest/log/init is deferred to a later eval pass.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
