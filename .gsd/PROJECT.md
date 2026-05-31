# Project: agent-research

## What This Is

`agent-research` is a Python 3.11+ `uv` workspace for LangChain-primitives-based AI tooling on AWS Bedrock. Its main graph-wiki product is being reshaped in v1.12 from an all-in-one `graph-wiki-agent` executable package into three package surfaces:

- `graph-wiki-core` — shared library implementation for graph-wiki Bedrock workflows.
- `graph-wiki-cli` — Typer CLI package exposing the `gw` command.
- `graph-wiki-mcp` — stdio MCP server package exposing the MCP tool surface.

The project exists so Pat can run graph-wiki wiki-maintenance workflows on AWS Bedrock with bounded parallel subagents, lower model cost, and preserved compatibility with existing graph-wiki vault conventions.

## Core Value

Faithfully reproduce graph-wiki wiki-maintenance outcomes while running entirely on AWS Bedrock with bounded parallel subagents, so Pat can achieve the same wiki refresh, query, ingest, lint, scan, log, and graph workflows at meaningfully lower cost than the Claude-Code-hosted plugin path.

## Project Shape

- **Complexity:** complex
- **Why:** The v1.12 package split touches uv workspace topology, Python import namespaces, console scripts, MCP stdio entrypoints, graph-wiki plugin shims, tests, CI/runtime commands, and current user-facing docs.

## Current State

Before M002 execution, the repo still has `agents/graph-wiki-agent` as a workspace member that owns both CLI and MCP scripts. Root `pyproject.toml` includes both `packages/*` and `agents/*`. Several workspace dependents import `graph_wiki_agent.commands`, plugin shims shell out to `graph-wiki-agent`, and tests are grouped under the old agent package.

M002 plans the v1.12 migration to a package-only workspace under `packages/`, with no backward-compatible old import shims and no old `graph-wiki-agent` console-script alias.

## Architecture / Key Patterns

- `uv` workspace with editable workspace members and one shared lockfile.
- AWS Bedrock only for model provider integration; product code should use `model-adapter.make_llm(role)` rather than direct Anthropic APIs or raw Bedrock construction.
- `subagent-runtime` provides asyncio/Semaphore bounded fan-out over LangChain primitives.
- `graph-wiki-core` owns shared command implementations and reusable runtime code.
- `graph-wiki-cli` and `graph-wiki-mcp` are thin presentation packages depending on `graph-wiki-core`.
- Existing graph-wiki vault semantics remain stable: `.graph-wiki.yaml` plugin identity stays `graph-wiki-agent` for now.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [x] M001: GSD Initialization — Established `.gsd/` as the active project truth from current repo state and selected legacy context.
- [ ] M002: v1.12 Package Split — Split graph-wiki into core, CLI, and MCP packages under `packages/`, rename the CLI to `gw`, update runtime-facing workflows/docs, and prove the full workspace including integration tests still passes.
