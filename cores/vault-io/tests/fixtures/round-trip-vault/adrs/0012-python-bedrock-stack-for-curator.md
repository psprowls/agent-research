---
title: "ADR-0012: Python + Bedrock + LangChain/LangGraph stack for the curator"
category: adr
summary: Build lattice-curator in Python (3.12) with langchain-aws for the Bedrock client, langgraph for pipeline orchestration, and Pydantic for structured output.
adr_id: "0012"
status: accepted
decision_date: 2026-05-09
deciders: [Patrick Sprowls]
supersedes: []
superseded_by:
tags: [adr, lattice-curator, python, bedrock, langchain, langgraph, pydantic, stack]
updated: 2026-05-09
tokens: 745
---

# ADR-0012: Python + Bedrock + LangChain/LangGraph stack for the curator

**Status:** accepted (2026-05-09)

## Context

An earlier decision (ADR-0025, TypeScript Bedrock stack for curator) proposed building the curator package in TypeScript. Before implementation began, the team reconsidered in light of the existing Python uv workspace (see [[wiki/adrs/0009-uv-ruff-python-tooling]]) and the maturity of `langchain-aws` / `langgraph` on the Python side.

## Decision

Adopt the following stack for `packages/lattice-curator-core/`:

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Build | `hatchling` (uv workspace, per [[wiki/adrs/0009-uv-ruff-python-tooling]]) |
| Test runner | `pytest` with `asyncio_mode = "auto"` |
| LLM client | `langchain-aws` `ChatBedrockConverse` via `langchain-core` |
| Pipeline orchestration | `langgraph` `StateGraph` |
| Structured output | Pydantic models with `with_structured_output()` |
| Markdown / frontmatter | `python-frontmatter` |
| Distribution | Path-dep consumed by `plugins/lattice-curator/` |

Hook scripts invoke Python directly via a `run-hook.cmd` bash shim. The MCP server (`mcp/server.py`) is a `FastMCP` Python server. No Node toolchain required.

The test seam at `bedrock.py` is preserved: `retrieve()` accepts a model argument for test injection.

## Consequences

**Positive:**
- Single language tier — no Node toolchain alongside the Python uv workspace.
- Same tooling (`uv`, `ruff`, `pytest`) as `lattice-source-parser` and `lattice-evals`.
- LangGraph `StateGraph` and langchain-aws `ChatBedrockConverse` provide identical orchestration and Bedrock access to their TypeScript counterparts.
- Pydantic `with_structured_output()` is equally robust to Zod for schema-validated LLM responses.

**Negative:**
- Bash shim needed for hook invocation (same as `lattice-workflows`); one level of indirection at the Claude Code boundary.
- `python-frontmatter` replaces `gray-matter`; API is different but equally capable.

## Impact

- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — Python package with `langchain-aws`, `langgraph`, `pydantic`, `python-frontmatter`.
- [[wiki/plugins/lattice-curator/lattice-curator]] — hooks and MCP server are Python; bash shim bridges Claude Code's invocation.
- [[wiki/packages/lattice-evals/lattice-evals]] — curator eval scenarios call into the Python package directly.
