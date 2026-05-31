# S05: Workspace integration and full verification — UAT

**Milestone:** M002
**Written:** 2026-05-31T18:00:40.852Z

## UAT Type
Automated repository integration UAT; no human/manual UI flow required.

## Preconditions
- Work from the repository root `/Users/pat/Personal/agent-research`.
- Use the default-safe environment with no required live Bedrock credentials.
- Optional live Bedrock integration requires explicit credentials and cost opt-in; absence should result in gated skips, not failure.

## Steps
1. Run `uv sync` from the root.
2. Run the focused package/guardrail gate: `uv run python -m pytest tests/test_package_split_workspace.py tests/test_integration_gate.py packages/workspace-io/tests/test_config.py packages/wiki-io/tests/test_ports_importable.py -q && bash scripts/check-brand.sh`.
3. Run package-local suites: `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests -q`, `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests -q`, and `uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests -q`.
4. Smoke the owned entrypoints: `uv run --package graph-wiki-cli gw --help`, `uv run --package graph-wiki-cli gw query --help`, `uv run --package graph-wiki-cli gw graph --help`, and `uv run --package graph-wiki-mcp graph-wiki-mcp --help`.
5. Run the default-safe full suite: `uv run python -m pytest -q`.
6. Check live integration classification: if AWS credentials plus explicit integration/cost opt-in are absent, live Bedrock tests should be skipped/gated rather than fail.

## Expected Outcomes
- Root workspace sync succeeds with package-only workspace membership.
- `agents/` is absent from the active checkout and stale `graph-wiki-agent` workspace membership is not present in active workspace metadata.
- Active runtime guidance uses `gw`; allowed `graph-wiki-agent` references are limited to classified provenance, plugin identity, historical, or negative-test contexts covered by guardrails.
- `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp` package-local tests pass.
- `gw` and `graph-wiki-mcp` console entrypoints resolve through uv package contexts.
- Full default-safe pytest passes; optional live Bedrock coverage is environment-gated when credentials/cost opt-in are unavailable.

## Edge Cases
- Local worktree artifacts under `.claude` must not be collected by root pytest.
- Runtime-generated `__pycache__` directories must not be mistaken for copied bytecode artifacts.
- Tests should reflect the documented current `models.toml` defaults rather than stale pre-purge Haiku assumptions.

## Operational Readiness
- Health signal: `uv sync`, package-local suites, entrypoint smokes, brand guard, and full pytest provide the operational health gate.
- Failure signal: boundary tests identify stale workspace members/import namespaces; brand guard identifies stale executable guidance; package-local tests identify package ownership regressions; full pytest identifies integration breakage.
- Recovery procedure: inspect the failing focused gate first, update only the owning package/guardrail, then rerun the focused gate and full pytest.
- Monitoring gaps: no runtime telemetry was planned or added; live Bedrock behavior remains validated only when credentials and explicit cost opt-in are supplied.
