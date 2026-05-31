# S05: Workspace integration and full verification

**Goal:** Complete the final v1.12 package-split assembly by removing the obsolete agents workspace member, proving the uv workspace is packages-only, cleaning active stale executable guidance, updating repo guardrails, and running full workspace verification without reintroducing graph_wiki_agent shims or graph-wiki-agent console aliases.
**Demo:** Root workspace syncs as packages-only, `agents/` is gone, stale active references are cleaned up, and full tests including integration pass.

## Must-Haves

- Root `pyproject.toml` declares a package-only uv workspace and `uv.lock` no longer contains `graph-wiki-agent` or `agents/graph-wiki-agent` workspace membership.
- The obsolete `agents/` tree is removed from the active checkout.
- Active recovery/runtime guidance outside historical artifacts points users at `gw`, while allowed plugin identity/provenance strings remain explicitly classified.
- Repo guardrails and tests assert the final package split boundaries: no active `graph_wiki_agent` import namespace, no old workspace member, package-owned `gw` and `graph-wiki-mcp` entrypoints, and package-local tests.
- Default-safe full workspace verification passes; live Bedrock integration is either run under `GRAPH_WIKI_RUN_INTEGRATION=1` when credentials/cost acceptance are available or recorded as environment-gated.

## Proof Level

- This slice proves: Final-assembly integration proof. This slice must exercise real uv workspace resolution, real console entrypoints (`gw` and `graph-wiki-mcp` via tests), repo-level boundary tests, package-local suites, and the default full pytest suite. No human/UAT is required; live Bedrock paths are gated by environment and cost.

## Integration Closure

Consumes S02 `graph-wiki-cli`/`gw`, S03 `graph-wiki-mcp`, and S04 runtime shim/docs rewiring. Introduces no new runtime feature wiring; closes the milestone by removing the obsolete package owner and verifying all package boundaries compose in the root workspace. Nothing should remain before the milestone is usable end-to-end except optional live Bedrock integration when credentials are unavailable.

## Verification

- No runtime telemetry is added. Failure visibility is test- and guardrail-based: uv sync failure localizes workspace metadata problems, package-split boundary tests localize stale namespace/entrypoint regressions, brand/runtime docs gates localize stale executable guidance, and full pytest output localizes integration failures.

## Tasks

- [x] **T01: Cut over to a package-only uv workspace** `est:1h`
  ---
  estimated_steps: 7
  estimated_files: 4
  skills_used:
    - uv-package-manager
    - python-testing-patterns
    - verify-before-complete
  ---
  - Files: `pyproject.toml`, `uv.lock`, `agents`, `tests/test_package_split_workspace.py`
  - Verify: uv sync && uv run python -m pytest tests/test_package_split_workspace.py -q

- [x] **T02: Update active recovery guidance to gw** `est:35m`
  ---
  estimated_steps: 5
  estimated_files: 4
  skills_used:
    - python-testing-patterns
    - verify-before-complete
  ---
  - Files: `packages/workspace-io/src/workspace_io/config.py`, `packages/workspace-io/tests/test_config.py`, `packages/wiki-io/src/wiki_io/_workspace.py`, `packages/wiki-io/tests/test_ports_importable.py`, `packages/wiki-io/src/wiki_io/init_vault.py`, `packages/wiki-io/tests/test_init_vault.py`
  - Verify: uv run python -m pytest packages/workspace-io/tests/test_config.py packages/wiki-io/tests/test_ports_importable.py -q

- [x] **T03: Refresh repo guardrails for package-era boundaries** `est:45m`
  ---
  estimated_steps: 6
  estimated_files: 4
  skills_used:
    - uv-package-manager
    - python-testing-patterns
    - verify-before-complete
  ---
  - Files: `tests/test_integration_gate.py`, `scripts/check-brand.sh`, `.brand-grep-allow`, `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
  - Verify: uv run python -m pytest tests/test_integration_gate.py -q && bash scripts/check-brand.sh

- [x] **T04: Run full workspace verification and stale-reference closeout** `est:1h`
  ---
  estimated_steps: 8
  estimated_files: 0
  skills_used:
    - uv-package-manager
    - python-testing-patterns
    - verify-before-complete
  ---
  - Files: `tests/test_package_split_workspace.py`, `tests/test_integration_gate.py`, `packages/workspace-io/tests/test_config.py`, `packages/wiki-io/tests/test_ports_importable.py`, `scripts/check-brand.sh`, `.brand-grep-allow`, `packages/graph-wiki-core/tests`, `packages/graph-wiki-cli/tests`, `packages/graph-wiki-mcp/tests`
  - Verify: uv run python -m pytest

## Files Likely Touched

- pyproject.toml
- uv.lock
- agents
- tests/test_package_split_workspace.py
- packages/workspace-io/src/workspace_io/config.py
- packages/workspace-io/tests/test_config.py
- packages/wiki-io/src/wiki_io/_workspace.py
- packages/wiki-io/tests/test_ports_importable.py
- packages/wiki-io/src/wiki_io/init_vault.py
- packages/wiki-io/tests/test_init_vault.py
- tests/test_integration_gate.py
- scripts/check-brand.sh
- .brand-grep-allow
- packages/graph-wiki-cli/src/graph_wiki_cli/cli.py
- packages/graph-wiki-core/tests
- packages/graph-wiki-cli/tests
- packages/graph-wiki-mcp/tests
