---
id: T04
parent: S05
milestone: M002
key_files:
  - pyproject.toml
  - packages/eval-harness/tests/test_models_toml_sweep_candidates.py
  - packages/graph-wiki-core/tests/test_package_boundary.py
  - packages/model-adapter/tests/test_loader.py
  - packages/model-adapter/tests/test_narrator_role.py
key_decisions:
  - Root pytest should ignore local `.claude` worktree artifacts so default-safe workspace verification covers only the active repository.
  - Model tests should assert the documented post-Haiku-purge package defaults rather than pre-purge Haiku defaults.
  - The graph-wiki-core copied-bytecode boundary test should ignore runtime-created `__pycache__` directories and only fail on copied `.pyc` artifacts outside Python cache directories.
duration: 
verification_result: passed
completed_at: 2026-05-31T17:32:26.875Z
blocker_discovered: false
---

# T04: Completed final package-split closeout verification and fixed stale root-test guardrails so the packages-only workspace passes default-safe full pytest.

**Completed final package-split closeout verification and fixed stale root-test guardrails so the packages-only workspace passes default-safe full pytest.**

## What Happened

Ran the planned targeted package-split, integration-gate, workspace-io/wiki-io, brand, package-local, CLI-smoke, stale-reference, and full-workspace checks. Initial full pytest exposed two closeout issues: root pytest was recursing into local `.claude/worktrees` artifacts containing pre-split tests and duplicate eval conftest option hooks, and a few default-safe tests still encoded stale assumptions from before the documented 2026-05-30 Haiku quota purge or treated pytest-generated `__pycache__` directories as copied bytecode. Updated the root pytest recursion guard to exclude `.claude`, aligned model-adapter/eval-harness assertions with the current packaged `models.toml` defaults, and narrowed the bytecode boundary test to copied `.pyc` artifacts outside runtime cache directories. Re-ran focused regressions, stale-reference closeout, brand guardrails, and the full default-safe workspace suite successfully.

## Verification

Verified targeted package-split and integration gates, touched workspace-io/wiki-io tests, brand guardrails, graph-wiki-core/cli/mcp package-local suites, runtime CLI help surfaces, active stale-reference closeout, focused regression tests for fixed failures, full default-safe workspace pytest, and optional live-integration environment classification. Live Bedrock integration was not run because no AWS credential keys or explicit GRAPH_WIKI_RUN_INTEGRATION/cost-acceptance environment variables were present; the default-safe suite reported the expected environment-gated skips.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run python -m pytest tests/test_package_split_workspace.py tests/test_integration_gate.py packages/workspace-io/tests/test_config.py packages/wiki-io/tests/test_ports_importable.py && bash scripts/check-brand.sh` | 0 | ✅ pass | 2887ms |
| 2 | `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests && uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests && uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests` | 0 | ✅ pass | 33045ms |
| 3 | `uv run --package graph-wiki-cli gw --help && uv run --package graph-wiki-cli gw query --help && uv run --package graph-wiki-cli gw graph --help` | 0 | ✅ pass | 1494ms |
| 4 | `active stale-reference assertion over packages/tests/plugins/scripts for graph_wiki_agent namespace and graph-wiki-agent executable guidance` | 0 | ✅ pass | 303ms |
| 5 | `uv run python -m pytest packages/eval-harness/tests/test_models_toml_sweep_candidates.py packages/graph-wiki-core/tests/test_package_boundary.py packages/model-adapter/tests/test_loader.py::test_domain_proposer_role packages/model-adapter/tests/test_narrator_role.py` | 0 | ✅ pass | 2134ms |
| 6 | `uv run python -m pytest` | 0 | ✅ pass: 1700 passed, 43 skipped, 2 xfailed | 127498ms |
| 7 | `optional live integration environment classification` | 0 | ✅ pass: no AWS credential keys or explicit integration/cost-acceptance opt-in present; live Bedrock integration not run | 47ms |
| 8 | `bash scripts/check-brand.sh` | 0 | ✅ pass | 1164ms |

## Deviations

The task was planned as verification-only, but default-safe full pytest revealed stale local-test guardrails and stale model expectations that blocked final verification. I made minimal test/config guardrail updates to make the intended default-safe suite executable and aligned with the documented current `models.toml` behavior.

## Known Issues

Live Bedrock integration remains environment-gated and was not run because no credential or explicit cost-acceptance opt-in environment was present.

## Files Created/Modified

- `pyproject.toml`
- `packages/eval-harness/tests/test_models_toml_sweep_candidates.py`
- `packages/graph-wiki-core/tests/test_package_boundary.py`
- `packages/model-adapter/tests/test_loader.py`
- `packages/model-adapter/tests/test_narrator_role.py`
