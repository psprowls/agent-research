# agent-research

A Python monorepo of AWS Bedrock-focused AI tooling, managed with `uv` workspaces.

**Graph Wiki:** wiki-maintenance workflows that can run either inside the Claude Code `graph-wiki` plugin or through package-scoped Bedrock entry points with parallel subagents, so the same vault outcomes can be achieved at lower cost than a Claude-Code-hosted run.

The current Graph Wiki implementation is split into package-only targets:

- `packages/graph-wiki-core/` — workflow orchestration and command implementations shared by all delivery surfaces.
- `packages/graph-wiki-cli/` — the Bedrock-capable `gw` Typer CLI for headless runtime use and plugin Bedrock shims.
- `packages/graph-wiki-mcp/` — the MCP server surface for hosts that consume Graph Wiki as tools.

## Quickstart

```bash
uv sync
uv run --package graph-wiki-cli gw --help
```

Run a scoped command through the CLI package:

```bash
uv run --package graph-wiki-cli gw scan --workspace /path/to/repo/graph-wiki
uv run --package graph-wiki-cli gw wiki ingest source docs/example.md --workspace /path/to/repo/graph-wiki
uv run --package graph-wiki-cli gw wiki query "Where is auth documented?" --top-k 5
uv run --package graph-wiki-cli gw graph update --full --repo /path/to/repo --mode test
uv run --package graph-wiki-cli gw graph find --name SomeSymbol --repo /path/to/repo --mode test
```

## Workspace Layout

```
packages/
  graph-wiki-core/  # shared Graph Wiki workflow logic
  graph-wiki-cli/   # gw CLI, including Bedrock runtime entry point
  graph-wiki-mcp/   # MCP server surface
  wiki-io/          # vault read/write primitives and Claude-hosted shims
  model-adapter/    # AWS Bedrock model loader + role registry
```

Each workspace member has its own `pyproject.toml` with per-member `testpaths`.
`--package` only picks the uv environment, not the pytest scope — pass the
package's own test path explicitly or it collects the whole workspace suite:

```bash
uv run --package wiki-io pytest packages/wiki-io/tests
uv run --package model-adapter pytest packages/model-adapter/tests
uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests -m "not integration"
```

## Requirements

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) 0.11.14+
- AWS account with Bedrock access (for runtime; not required for `gw --help`)

## License

MIT — see [LICENSE](./LICENSE).
