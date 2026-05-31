---
id: T03
parent: S01
milestone: M002
key_files:
  - packages/eval-harness/pyproject.toml
  - packages/eval-harness/src/eval_harness/structural.py
  - packages/eval-harness/src/eval_harness/sweep.py
  - packages/eval-harness/src/eval_harness/divergence/synthesizer.py
  - packages/eval-harness/src/eval_harness/divergence/code_reader.py
  - packages/eval-harness/tests/eval_helpers.py
  - packages/eval-harness/tests/test_structural.py
  - packages/eval-harness/tests/test_sweep.py
  - packages/eval-harness/tests/test_role_sweep.py
key_decisions:
  - Made eval-harness depend on graph-wiki-core instead of the executable graph-wiki-agent package.
duration: 
verification_result: passed
completed_at: 2026-05-31T16:08:33.258Z
blocker_discovered: false
---

# T03: Pointed eval-harness package metadata, source, and tests at graph-wiki-core command imports.

**Pointed eval-harness package metadata, source, and tests at graph-wiki-core command imports.**

## What Happened

Changed eval-harness package metadata from graph-wiki-agent to graph-wiki-core in dependencies and tool.uv.sources. Rewrote active eval-harness source and test imports from graph_wiki_agent.commands to graph_wiki_core.commands, leaving historical fixture/vault text untouched as planned. The selected structural and sweep tests remained deterministic and passed without requiring Bedrock credentials.

## Verification

Ran `uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py`; 17 tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py` | 0 | ✅ pass | 25244ms |

## Deviations

The parent executor performed the implementation because the requested `subagent` tool was not available in this harness namespace; the task contract and verification were otherwise followed.

## Known Issues

None.

## Files Created/Modified

- `packages/eval-harness/pyproject.toml`
- `packages/eval-harness/src/eval_harness/structural.py`
- `packages/eval-harness/src/eval_harness/sweep.py`
- `packages/eval-harness/src/eval_harness/divergence/synthesizer.py`
- `packages/eval-harness/src/eval_harness/divergence/code_reader.py`
- `packages/eval-harness/tests/eval_helpers.py`
- `packages/eval-harness/tests/test_structural.py`
- `packages/eval-harness/tests/test_sweep.py`
- `packages/eval-harness/tests/test_role_sweep.py`
