---
estimated_steps: 19
estimated_files: 9
skills_used: []
---

# T04: Run full workspace verification and stale-reference closeout

---
estimated_steps: 8
estimated_files: 0
skills_used:
  - uv-package-manager
  - python-testing-patterns
  - verify-before-complete
---

Why: This is the final assembly slice for M002. It must prove that the package-only workspace, package-local suites, runtime entrypoints, and stale-reference guardrails compose in the root environment.

Do:
1. Run targeted verification for the final package split and touched gates: `tests/test_package_split_workspace.py`, `tests/test_integration_gate.py`, touched workspace-io/wiki-io tests, and `scripts/check-brand.sh`.
2. Run package-local suites for `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp` using `uv run --package ... python -m pytest ...`.
3. Run runtime-facing smoke checks for `gw --help`, `gw query --help`, and representative graph command help through `uv run --package graph-wiki-cli`.
4. Run the full default-safe workspace test suite with `uv run python -m pytest`.
5. Run a stale-reference assertion that scans active `packages`, `tests`, `plugins`, and `scripts` Python/text surfaces for old `graph_wiki_agent` import namespace and old `graph-wiki-agent` executable guidance, excluding only explicit negative boundary tests, historical artifacts outside the scan roots, preserved plugin identity strings, and classified provenance comments.
6. If AWS/Bedrock credentials are already present and cost acceptance is clear from the environment, optionally run `GRAPH_WIKI_RUN_INTEGRATION=1 uv run python -m pytest`; otherwise record the existing integration skips as environment-gated rather than a product failure.

Failure modes: `uv sync` failures indicate workspace metadata/lock issues from T01; package-local failures indicate a split-boundary regression in the owning package; full-suite failures indicate cross-package integration problems; live integration failures may be credential/cost/environment-driven and must be classified separately from default-safe test failures.

Load profile: Full pytest is the only high-cost local operation. Live Bedrock integration can incur external cost and should only run when credentials/cost acceptance are already available.

Done when: Default-safe full verification passes, stale-reference closeout has no unclassified active hits, and optional live integration status is recorded honestly.

## Inputs

- `pyproject.toml`
- `uv.lock`
- `tests/test_package_split_workspace.py`
- `tests/test_integration_gate.py`
- `packages/workspace-io/src/workspace_io/config.py`
- `packages/workspace-io/tests/test_config.py`
- `packages/wiki-io/src/wiki_io/_workspace.py`
- `packages/wiki-io/tests/test_ports_importable.py`
- `scripts/check-brand.sh`
- `.brand-grep-allow`
- `packages/graph-wiki-core/tests`
- `packages/graph-wiki-cli/tests`
- `packages/graph-wiki-mcp/tests`

## Expected Output

- `tests/test_package_split_workspace.py`
- `tests/test_integration_gate.py`
- `packages/workspace-io/tests/test_config.py`
- `packages/wiki-io/tests/test_ports_importable.py`
- `scripts/check-brand.sh`
- `.brand-grep-allow`
- `packages/graph-wiki-core/tests`
- `packages/graph-wiki-cli/tests`
- `packages/graph-wiki-mcp/tests`

## Verification

uv run python -m pytest

## Observability Impact

Produces no committed artifact, but closeout commands provide the diagnostic evidence future milestone validation needs: package-local failures identify package ownership issues and full-suite failures identify cross-package integration regressions.
