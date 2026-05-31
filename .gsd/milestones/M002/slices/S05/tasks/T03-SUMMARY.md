---
id: T03
parent: S05
milestone: M002
key_files:
  - tests/test_integration_gate.py
  - scripts/check-brand.sh
  - .brand-grep-allow
  - packages/graph-wiki-core/src/graph_wiki_core/config.py
  - packages/graph-wiki-core/tests/unit/test_config.py
key_decisions:
  - Use package-era brand scopes only (`packages/`, `plugins/`, and explicitly listed docs/scripts) rather than continuing to scan or allow deleted `agents/` paths.
  - Keep new brand allowlist entries file-scoped for active `workspace_io` imports and negative-test fixtures so stale command guidance or old workspace paths in other files still fail.
duration: 
verification_result: passed
completed_at: 2026-05-31T17:22:05.574Z
blocker_discovered: false
---

# T03: Refreshed repo guardrails to enforce package-era integration and brand boundaries against live package paths.

**Refreshed repo guardrails to enforce package-era integration and brand boundaries against live package paths.**

## What Happened

Updated the integration gate failure wording so repo layout drift points at package-local `packages/*/tests/integration/*` tests instead of the deleted `agents/graph-wiki-agent` tree. Refreshed `scripts/check-brand.sh` to remove `agents/` from active scan scopes, point CHECK 3 at `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`, and report the live CLI package in success/failure output. Cleaned `.brand-grep-allow` by removing the obsolete `agents/graph-wiki-agent/` allowance, adding file-scoped classifications for canonical `workspace_io` imports in split packages, and documenting the MCP `vault_path` negative-test fixture and plugin identity/provenance allowance narrowly. During verification the brand guard exposed a real active legacy `vault_path` config field in `graph_wiki_core.config`; I renamed it to `workspace_path` and updated its unit tests so CHECK 4 now fails only on intentional negative fixtures or future regressions.

## Verification

Ran the task-required integration meta-test plus brand script successfully. Also ran the package-split boundary test and the graph_wiki_core config unit tests because this task touched package-era guardrails and cleaned a legacy config field surfaced by the brand gate. Final combined verification passed: `uv run python -m pytest packages/graph-wiki-core/tests/unit/test_config.py tests/test_package_split_workspace.py tests/test_integration_gate.py -q && bash scripts/check-brand.sh`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run python -m pytest tests/test_integration_gate.py -q && bash scripts/check-brand.sh` | 0 | ✅ pass | 3025ms |
| 2 | `uv run python -m pytest tests/test_package_split_workspace.py -q` | 0 | ✅ pass | 1381ms |
| 3 | `uv run python -m pytest packages/graph-wiki-core/tests/unit/test_config.py tests/test_package_split_workspace.py tests/test_integration_gate.py -q && bash scripts/check-brand.sh` | 0 | ✅ pass | 3451ms |

## Deviations

The written plan expected only guardrail files to change, but the refreshed brand gate exposed `packages/graph-wiki-core/src/graph_wiki_core/config.py` as an active legacy `vault_path` runtime config surface. I fixed that stale field and updated its tests rather than allowlisting it.

## Known Issues

None.

## Files Created/Modified

- `tests/test_integration_gate.py`
- `scripts/check-brand.sh`
- `.brand-grep-allow`
- `packages/graph-wiki-core/src/graph_wiki_core/config.py`
- `packages/graph-wiki-core/tests/unit/test_config.py`
