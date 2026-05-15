---
title: code-wiki-agent
category: package
summary: AWS Bedrock-powered wiki maintenance agent — MCP server and headless CLI that replicates lattice-wiki workflows at lower cost
status: active
package_path: agents/code-wiki-agent
package_type: tool
domain:
language: python
depends_on:
  - vault-io
  - model-adapter
  - subagent-runtime
tags: [agent, mcp, bedrock, cli, wiki]
sources: 0
updated: 2026-05-14
tokens: 0
last_sync_commit:
last_sync_at:
---

# code-wiki-agent

## Purpose

The primary deliverable of the monorepo. Implements the same four wiki workflows as the `lattice-wiki` Claude Code plugin (scan, query, ingest, lint) but runs entirely on AWS Bedrock with async subagent fan-out for cost savings. Exposed as both a **CLI** (`code-wiki-agent`) and an **MCP server** (`code-wiki-mcp`) so it can be consumed by DeepAgents CLI or any MCP host.

## Public API

CLI entry points (defined in `pyproject.toml [project.scripts]`):

- `code-wiki-agent` — `src/code_wiki_agent/cli.py` — Typer app; subcommands: `scan`, `query`, `ingest`, `lint`, `init`, `log`
- `code-wiki-mcp` — `src/code_wiki_mcp/server.py` — FastMCP stdio server exposing the same operations as MCP tools

## File map - code-wiki-agent

Root package wiring `pyproject.toml` workspace sources to the `code_wiki_agent` and `code_wiki_mcp` source trees.

- `pyproject.toml` — package manifest; declares workspace deps and CLI entry points

### code-wiki-agent/src/

#### code-wiki-agent/src/code_wiki_agent/

Core agent package.

- `__init__.py` — package init
- `cli.py` — Typer CLI app; registers subcommands from `commands/`
- `config.py` — loads `wiki-config.toml` and `models-*.toml`; resolves vault and repo paths

##### code-wiki-agent/src/code_wiki_agent/commands/

One module per CLI/MCP operation.

- `__init__.py` — package init
- `scan.py` — scan workflow: monorepo diff → stub page creation
- `query.py` — query workflow: index → page drill → synthesize answer
- `ingest.py` — ingest workflow: source → summary → page updates
- `lint.py` — lint workflow: mechanical + semantic health checks
- `init.py` — vault bootstrap
- `log.py` — append / view log entries

#### code-wiki-agent/src/code_wiki_mcp/

MCP server surface.

- `__init__.py` — package init
- `server.py` — FastMCP stdio server; registers `scan`, `query`, `ingest`, `lint` as MCP tools

### code-wiki-agent/tests/

- `__init__.py` — package init
- `conftest.py` — shared fixtures (fake vault, mock Bedrock responses)

#### code-wiki-agent/tests/commands/

Parity tests against lattice-wiki-core reference implementation.

- `__init__.py` — package init
- `test_scan_parity.py` — compares scan output against lattice-wiki-core baseline
- `test_lint_parity.py` — compares lint output against lattice-wiki-core baseline

#### code-wiki-agent/tests/integration/

Live Bedrock and MCP integration tests (marked `integration`, skipped in CI by default).

- `__init__.py` — package init
- `test_bedrock_iam.py` — verifies IAM credentials and Bedrock connectivity
- `test_mcp_stdio.py` — spawns MCP server subprocess and exercises tool calls
- `test_query_e2e.py` — end-to-end query against a real vault

#### code-wiki-agent/tests/unit/

Fast unit tests with mocked Bedrock.

- `__init__.py` — package init
- `test_cli_help.py` — smoke-tests all `--help` outputs
- `test_cli_query.py` — CLI query subcommand output formatting
- `test_commands_scan.py` — scan command logic
- `test_commands_query.py` — query command logic (index read, page drill, synthesis)
- `test_commands_ingest.py` — ingest command logic
- `test_commands_lint.py` — lint command logic
- `test_commands_init.py` — vault init command
- `test_commands_log.py` — log append / view
- `test_config.py` — config loading from TOML
- `test_mcp_query_schema.py` — MCP tool schema validation
- `test_mcp_new_tools.py` — additional MCP tool registration
- `test_query_result.py` — query result formatting
- `test_query_search.py` — BM25 search integration
- `test_stdout_guard.py` — ensures MCP server never writes to stdout outside tool responses
- `test_trace_viewer.py` — trace file parsing

## Key patterns

- All commands resolve vault + repo via `config.py → vault_io._workspace`
- Heavy work (page reads, LLM calls) fans out through `subagent-runtime.pool`
- BM25 fallback via `bm25s` when the index doesn't have a direct hit
- MCP server is thin: it imports the same command functions as the CLI

## Used by
- [[cores/eval-harness/eval-harness]]

## Related concepts
- [[concepts/bedrock-model-routing]]
- [[concepts/mcp-stdio-transport]]

## Dependencies (external)
- [[dependencies/bm25s]]
- [[dependencies/mcp]]
- [[dependencies/langchain-aws]]
- [[dependencies/typer]]

## Open questions
- Query answer quality vs lattice-wiki baseline — tracked in eval-harness
