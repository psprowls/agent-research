---
title: lattice-curator-core — Context
category: package
summary: Why context curation exists, why it lives as a pure-Python library separate from Claude Code, and how it relates to the wiki and experts knowledge surfaces.
tags: [python, context, rationale]
updated: 2026-05-10
tokens: 1170
---

# lattice-curator-core — Context

## Concepts

### Why this exists

Claude Code does not always invoke a workflow skill before starting work, and even when it does, the right rule pages and wiki pages for the turn are not always loaded. The result is two failure modes:

1. **Quiet drift** — Claude makes a change consistent with what it knows but inconsistent with what the codebase expects (a known anti-pattern documented in `lattice/knowledge/` that never reached the context window).
2. **Context bloat** — when curation is attempted by hand, it tends to over-fetch, dumping whole wiki sections into the turn and crowding out the actual prompt.

The curator runs outside Claude's decision loop. It gates on `UserPromptSubmit`, decides whether to fire heuristically, picks a tight set of catalog entries via a cheap [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] pass, summarizes them via a second Bedrock pass, and prints a compact brief to stdout that Claude Code injects into the turn. The package is the engine for that work.

### Why it's a pure-logic Python library

The package has no Claude Code, hook, or MCP awareness. The plugin ([[wiki/plugins/lattice-curator/lattice-curator]]) owns those surfaces. Three reasons for the split:

1. **Reusability.** CI checks, eval scenarios, and future tooling can consume `gate()` / `retrieve()` / `format_brief()` directly without faking a Claude Code environment.
2. **Testability.** The retriever takes `model` and `sources` as arguments; unit tests inject fakes; integration tests replay recorded Bedrock responses; nothing in the engine knows what `~/.cache/lattice-curator/state.json` is.
3. **Boundary discipline.** Every interesting decision (gate heuristics, stage prompts, schema validation, fail-silent semantics) lives in one place. The plugin is plumbing.

This mirrors the precedent set by [[wiki/packages/lattice-source-parser/lattice-source-parser]] — pure Python library at `packages/`, thin Claude Code wrapper at `plugins/`.

### Why Python (not TypeScript)

Earlier design notes and the original wiki page proposed a TypeScript stack: `@langchain/core`, `@langchain/aws`, `@langchain/langgraph`, `zod`, `gray-matter`, Vitest. The implementation that landed is Python: `langchain-aws`, `langgraph`, `langchain-core`, `pydantic`, `python-frontmatter`, `mcp`, pytest.

Likely reasons for the pivot (inferred from neighbors, not from a written record):

- The rest of `packages/` is Python (`lattice-source-parser`, `lattice-evals`).
- The MCP server (`mcp/server.py`) uses the Python `mcp` SDK with `FastMCP`.
- The plugin hook scripts are Python under `hooks/*.py` invoked through a bash shim (`run-hook.cmd`).

### Knowledge surfaces

Two `Source` adapters ship today:

1. **Wiki** (`wiki_source(vault_dir)`) — pulls catalog entries from any markdown vault with frontmatter. The repo's vault at `lattice/wiki/` is the canonical consumer. See [[wiki/plugins/lattice-wiki/lattice-wiki]].
2. **Knowledge** (`experts_source(rules_dir)`) — pulls from the per-repo `lattice/knowledge/` directory, seeded from the package's bundled rules via the plugin's `/curator:init` command.

The bundled rules under `src/lattice_curator_core/knowledge/` are global tooling — they ship with the package version. Once seeded into a project's `lattice/knowledge/`, they become per-repo data: editable, gitignorable per project, replaceable. See [[wiki/concepts/per-repo-data-vs-global-tooling-tier]] for the broader pattern.

## Decisions

- [[wiki/adrs/0010-lattice-curator-as-fifth-plugin]] — package vs plugin split, outside-the-loop posture.
- [[wiki/adrs/0012-python-bedrock-stack-for-curator]] — Python stack choice for the curator.

Note: An earlier ADR referenced "0025-typescript-bedrock-stack-for-curator" which contradicts the Python implementation. ADR 0012 supersedes it.

## Sources

- Design spec: sources/2026-05-context-curation-agent-design (describes the package boundary, two-pass pipeline, `Source` interface, stage-aware prompts, and fail-silent contract)

## Belongs to domain

Context curation / RAG pipeline

## Used by

- [[wiki/plugins/lattice-curator/lattice-curator]] — the only plugin that wraps this package with Claude Code surfaces (hooks, MCP, `/curator:init` command)

## Related dependencies

- `langchain-aws` — `ChatBedrockConverse` LLM wrapper
- `langgraph` — `StateGraph` for the two-pass retrieval pipeline
- `langchain-core` — structured output schema support
- `pydantic` — config and type validation
- `python-frontmatter` — markdown frontmatter parsing for source adapters
- `mcp` — Python MCP SDK used by the sibling MCP server in the plugin
