# S04: Runtime docs and graph-wiki workflow rewiring — UAT

**Milestone:** M002
**Written:** 2026-05-31T17:08:56.040Z

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S04 changes the local runtime subprocess contract and user-facing command guidance, not live AWS Bedrock behavior. Package-local tests fake Bedrock/subprocess boundaries where appropriate, and real `gw ... --help` entrypoint checks prove command availability through the installed graph-wiki-cli package.

## Preconditions

- Workspace dependencies are available through `uv`.
- The `graph-wiki-cli` package is a workspace member and exposes the `gw` console script from S02.
- No live AWS Bedrock credentials are required for this UAT.

## Smoke Test

Run `uv run --package graph-wiki-cli gw bootstrap --help` and confirm it exits 0. This proves the new CLI executable is available for a runtime-facing command used by the plugin shims/docs.

## Test Cases

### 1. Bedrock plugin shims dispatch to current `gw` command shapes

1. Run `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py`.
2. Inspect the test result.
3. **Expected:** The test exits 0 with five shim argv-mapping cases passing, covering `scan`, `bootstrap`, `ingest source`, `lint`, and `query`.

### 2. Runtime docs reject stale executable guidance

1. Run `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests/unit/test_runtime_docs.py`.
2. **Expected:** The test exits 0 and confirms current docs describe `gw`/v1.12 usage without stale `graph-wiki-agent` executable guidance in the guarded docs scope.

### 3. Current CLI package remains internally coherent

1. Run `uv run --package graph-wiki-cli python -m pytest packages/graph-wiki-cli/tests`.
2. **Expected:** The package-local graph-wiki-cli test suite exits 0; closeout evidence showed 86 tests and 12 snapshots passing.

### 4. Real entrypoint help works for runtime-facing commands

1. Run `uv run --package graph-wiki-cli gw bootstrap --help`.
2. Run `uv run --package graph-wiki-cli gw ingest source --help`.
3. Run `uv run --package graph-wiki-cli gw graph build --help`, `gw graph describe --help`, and `gw graph query --help` through the same package entrypoint.
4. **Expected:** Each command exits 0, proving the docs/shim/MCP guidance points at commands that the package can actually resolve.

## Edge Cases

### Plugin identity strings are not executable guidance

1. Review `plugins/graph-wiki/.claude-plugin/plugin.json` and plugin docs in the guarded scope.
2. **Expected:** Allowed plugin identity strings are preserved where required, but executable instructions and runtime subprocess mappings use `gw`.

### MCP tool descriptions are runtime-facing guidance

1. Review `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py` tool descriptions for graph command examples.
2. **Expected:** Examples use `gw graph ...`, not `graph-wiki-agent graph ...`.

## Failure Signals

- Any Bedrock shim argv test expects or emits `graph-wiki-agent`.
- Docs guard tests find stale `graph-wiki-agent` executable guidance in current runtime-facing docs.
- `gw bootstrap --help`, `gw ingest source --help`, or `gw graph ... --help` exits non-zero.
- S04 runtime-facing scope scan finds `graph-wiki-agent` in edited docs, shim scripts, or MCP command guidance.

## Not Proven By This UAT

- Live AWS Bedrock execution succeeds end-to-end; this slice intentionally proves the local runtime subprocess boundary without requiring cloud credentials.
- Full package-only workspace cleanup, deletion of obsolete `agents/`, root sync, and full integration verification; those remain S05 responsibilities.
- MCP stdio end-to-end runtime behavior beyond command guidance text; S03 covered MCP package extraction and S05 owns full integration.

## Notes for Tester

Treat `graph-wiki-agent` mentions in historical artifacts, explicit negative tests, or allowed plugin identity fields differently from runtime executable guidance. For S04, a failure is stale guidance that would lead a user, shim, or MCP-hosted workflow to execute `graph-wiki-agent` instead of `gw`.
