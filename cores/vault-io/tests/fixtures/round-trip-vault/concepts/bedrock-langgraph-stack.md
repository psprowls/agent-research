---
title: Bedrock + LangGraph stack
category: concept
summary: The Python AI stack used by lattice-curator and lattice-wiki-agent — AWS Bedrock for LLM inference via langchain-aws, LangGraph StateGraph for pipeline orchestration, and Pydantic for structured output.
tags: [bedrock, langgraph, langchain, python, ai, curator, adr]
updated: 2026-05-09
tokens: 569
---

# Bedrock + LangGraph stack

## Decision

[[wiki/adrs/0012-python-bedrock-stack-for-curator]] records the choice to build AI-powered lattice packages in Python using this stack rather than TypeScript.

## Components

| Component | Role | Package |
|---|---|---|
| `langchain-aws` `ChatBedrockConverse` | LLM inference via AWS Bedrock | `langchain-aws` |
| `langgraph` `StateGraph` | Pipeline orchestration (multi-step retrieval, ingest) | `langgraph` |
| Pydantic `with_structured_output()` | Schema-validated LLM responses | `pydantic` |
| `python-frontmatter` | Read/write vault page frontmatter | `python-frontmatter` |

## Rationale

- Keeps the entire lattice ecosystem in a single language tier (Python uv workspace, per [[wiki/adrs/0009-uv-ruff-python-tooling]]).
- Same tooling (`uv`, `ruff`, `pytest`) as `lattice-source-parser` and `lattice-evals`.
- `langchain-aws` and `langgraph` on Python are mature and match the capability of their TypeScript counterparts.

## Test seam

The `bedrock.py` module preserves a model-injection seam: `retrieve()` accepts a `model` argument so tests can inject a stub without hitting Bedrock.

## Hook invocation

Claude Code invokes plugin hooks as shell commands. A `run-hook.cmd` bash shim bridges Claude Code's invocation boundary to the Python process (same pattern as `lattice-workflows`).

## Where it appears

- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — primary consumer; `langchain-aws` + `langgraph` + `pydantic` are declared dependencies
- [[wiki/packages/lattice-wiki-agent/lattice-wiki-agent]] — uses LangGraph for headless wiki ops (scan, ingest, lint dispatched as graph nodes)
- [[wiki/plugins/lattice-curator/lattice-curator]] — hooks + MCP server are Python; bash shim at the Claude Code boundary

## Related

- [[wiki/adrs/0012-python-bedrock-stack-for-curator]]
- [[wiki/adrs/0009-uv-ruff-python-tooling]]
