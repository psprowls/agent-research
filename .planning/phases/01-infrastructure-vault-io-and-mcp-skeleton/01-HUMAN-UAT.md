---
status: partial
phase: 01-infrastructure-vault-io-and-mcp-skeleton
source: [01-VERIFICATION.md]
started: 2026-05-13T18:30:00Z
updated: 2026-05-13T18:30:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. BED-01 live Bedrock invoke

expected: After submitting the Anthropic use case form in AWS Bedrock console for the account/region, run `CODE_WIKI_RUN_INTEGRATION=1 uv run --directory agents/code-wiki-agent pytest tests/integration/test_bedrock_iam.py -x -q`. Expected: 2 passed, non-empty `result.content`.
result: [pending]

### 2. verify_bedrock_iam.py live run

expected: Run `uv run python scripts/verify_bedrock_iam.py`. Expected: stderr shows "Verifying Bedrock IAM (haiku role)..." then "OK:" line; exit 0.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
