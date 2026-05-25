# agent-research

A Python monorepo of LangChain/deepagents-based AI tooling, managed with `uv`.

**Graph Wiki:** wiki-maintenance workflows running in Claude Code, or
while running entirely on AWS Bedrock with parallel subagents, so the same
outcomes can be achieved at meaningfully lower cost than the current
Claude-Code-hosted plugin.

The first agent, **`graph-wiki-agent`**, is a reimplementation of the existing
`graph-wiki` Claude Code plugin — packaged as both an MCP server (consumed
by the DeepAgents CLI) and a headless CLI that runs the full agent loop.

## Quickstart

```bash
uv sync
uv run graph-wiki-agent --help
```

## Workspace Layout

```
packages/
  vault-io/         # vault read/write primitives (frontmatter, layout, tokens)
  model-adapter/    # AWS Bedrock model loader + role registry
agents/
  graph-wiki-agent/  # MCP server + Typer CLI (the user-facing surface)
```

Each workspace member has its own `pyproject.toml` with per-member `testpaths`.
Run scoped tests with:

```bash
uv run --package vault-io pytest
uv run --package model-adapter pytest
uv run --package graph-wiki-agent pytest -m "not integration"
```

## Requirements

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) 0.11.14+
- AWS account with Bedrock access (for runtime; not required for `--help`)

## License

MIT — see [LICENSE](./LICENSE).
