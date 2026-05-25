---
phase: 17-wiki-io-bug-fixes
plan: "02"
subsystem: wiki-io
tags: [wiki-io, bedrock, count-tokens, boto3, python, pytest, integration-test]
dependency_graph:
  requires: []
  provides: [TOK-01, TOK-02]
  affects: [packages/wiki-io/src/wiki_io/update_tokens.py, packages/wiki-io/tests/]
tech_stack:
  added: []
  patterns: [unittest.mock.patch + assert_called_once_with, GRAPH_WIKI_RUN_INTEGRATION gate]
key_files:
  modified:
    - packages/wiki-io/src/wiki_io/update_tokens.py
    - packages/wiki-io/pyproject.toml
  created:
    - packages/wiki-io/tests/test_update_tokens.py
    - packages/wiki-io/tests/integration/__init__.py
    - packages/wiki-io/tests/integration/test_count_tokens_live.py
decisions:
  - "Use input={'converse': {'messages': [...]}} — single Converse shape per D-05 (no model-id branching)"
  - "Response field is inputTokens (not inputTokenCount) per AWS API Reference; CONTEXT.md D-06 was wrong"
  - "Register pytest.mark.integration in wiki-io pyproject.toml to match graph-wiki-agent pattern"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-19"
  tasks_completed: 3
  files_changed: 5
---

# Phase 17 Plan 02: Fix Bedrock CountTokens API Call Shape Summary

**One-liner:** Fixed `count_tokens()` to use the Bedrock Converse input shape and `inputTokens` response field; added mocked unit tests locking both the request payload and response key, plus a gated integration test.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix count_tokens request shape and response field (TOK-01) | 04e6f8a | packages/wiki-io/src/wiki_io/update_tokens.py |
| 2 | Mocked unit tests for count_tokens (TOK-02 mocked) | aa6dd85 | packages/wiki-io/tests/test_update_tokens.py |
| 3 | Gated integration test for real Bedrock count_tokens (TOK-02 live) | 0765a13 | packages/wiki-io/tests/integration/__init__.py, tests/integration/test_count_tokens_live.py, packages/wiki-io/pyproject.toml |

## What Was Built

**Task 1 — count_tokens() fix (TOK-01):**
Replaced two bugs in `update_tokens.py:38-44`:
1. Request shape: `content=[{"text": text}]` → `input={"converse": {"messages": [{"role": "user", "content": [{"text": text}]}]}}`
2. Response field: `response["inputTokenCount"]` → `response["inputTokens"]`

Both bugs compounded each other: the wrong request parameter caused boto3 to reject the call, and (if it had succeeded) the wrong response field would have caused a `KeyError`. Every call to `/graph-wiki:scan` that tried to stamp token counts failed silently.

**Task 2 — mocked unit tests (TOK-02):**
Created `tests/test_update_tokens.py` with two test functions:
- `test_count_tokens_request_shape`: patches `wiki_io.update_tokens.boto3.client`, asserts the exact converse input payload via `assert_called_once_with`
- `test_count_tokens_returns_input_tokens`: asserts function returns the `inputTokens` integer from the mocked response

**Task 3 — gated integration test (TOK-02 live):**
Created `tests/integration/__init__.py` (package marker) and `tests/integration/test_count_tokens_live.py` with the canonical `INTEGRATION_GATE` pattern. Test is skipped by default; exercises real Bedrock when `GRAPH_WIKI_RUN_INTEGRATION=1`.

## Verification Results

- `uv run --package wiki-io pytest -x`: 78 passed, 1 skipped
- `uv run --package wiki-io pytest tests/integration/ -v`: 1 skipped (correct — no env var set)
- All acceptance criteria greps pass:
  - `inputTokens` present in update_tokens.py: 1 match
  - `inputTokenCount` in update_tokens.py: 0 matches
  - `"converse"` in update_tokens.py: 1 match
  - `content=[{"text"` in update_tokens.py: 0 matches
  - Both required test names in test_update_tokens.py: 2 matches
  - `assert_called_once_with` in test_update_tokens.py: 2 matches
  - `inputTokenCount` in test_update_tokens.py: 0 matches

## Deviations from Plan

### Auto-added Missing Configuration

**[Rule 2 - Missing Critical Config] Registered pytest.mark.integration in wiki-io pyproject.toml**
- **Found during:** Task 3
- **Issue:** `pytest.mark.integration` caused `PytestUnknownMarkWarning` because it was not declared in wiki-io's `pyproject.toml`. The graph-wiki-agent package already has this registration at line 36.
- **Fix:** Added `markers = ["integration: requires real Bedrock or subprocess (skipped in CI by default)"]` to `[tool.pytest.ini_options]` in `packages/wiki-io/pyproject.toml`.
- **Files modified:** `packages/wiki-io/pyproject.toml`
- **Commit:** 0765a13 (included with Task 3)

## Known Stubs

None. All functionality is fully implemented. TOK-03 (live re-stamp of wiki pages) is tracked in plan 17-04.

## Threat Flags

None. No new network endpoints, auth paths, or file access patterns introduced beyond what was already in the existing `count_tokens()` function.

## Self-Check: PASSED

Files created/modified:
- [FOUND] packages/wiki-io/src/wiki_io/update_tokens.py
- [FOUND] packages/wiki-io/tests/test_update_tokens.py
- [FOUND] packages/wiki-io/tests/integration/__init__.py
- [FOUND] packages/wiki-io/tests/integration/test_count_tokens_live.py
- [FOUND] packages/wiki-io/pyproject.toml

Commits:
- [FOUND] 04e6f8a — fix(17-02): correct Bedrock CountTokens API call shape
- [FOUND] aa6dd85 — test(17-02): add mocked unit tests locking CountTokens request shape
- [FOUND] 0765a13 — test(17-02): add gated integration test for real Bedrock count_tokens
