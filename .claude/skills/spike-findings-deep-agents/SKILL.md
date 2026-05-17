---
name: spike-findings-deep-agents
description: Implementation blueprint from spike experiments. Requirements, proven patterns, and verified knowledge for building deep-agents. Auto-loaded during implementation work.
---

<context>
## Project: deep-agents

A Python monorepo (managed with `uv`) of LangChain/deepagents-based AI tooling. The first package, `code-wiki-agent`, is a reimplementation of the existing `lattice-wiki` Claude Code plugin — packaged as both an MCP server and a headless CLI — running on AWS Bedrock with parallel subagents for cost and context savings. Spikes audit gaps between the Python port and the original plugin's runtime behavior.

Spike sessions wrapped: 2026-05-17
</context>

<requirements>
## Requirements

Non-negotiable design decisions that emerged during spiking. Every feature area reference honors these.

- Preserve the existing fragment curation discipline — every shared prompt fragment under `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/` carries the standard `# Source:` / `# Anchor:` / `# Source-commit:` provenance header.
- Stay within the cost-optimization mindset (see [[user_cost_optimization]]). Total added context per fan-out call should justify itself; target < ~1,500 added tokens per role above the current baseline.
- Do not require a deepagents migration to close subagent-context gaps. The dispatch primitive is the custom `cores/subagent-runtime/pool.py::SubagentPool`; migrating to `deepagents.SubAgentMiddleware` is a separate architectural decision.
- Project-specific context (wiki `CLAUDE.md` layout block, container pins, style, log format) must reach the subagents that scan/lint/ingest. Static skill content alone is not enough — the layout differs per project and changes over a project's lifetime.
</requirements>

<findings_index>
## Feature Areas

| Area | Reference | Key Finding |
|------|-----------|-------------|
| Subagent context injection | references/subagent-context-injection.md | Two SKILL.md sections + four wiki/CLAUDE.md sections are absent from subagent SystemMessage today. Closeable via fragment extraction + a project-context renderer at command entry, without a deepagents migration. |

## Source Files

Original spike source files are preserved in `sources/` for complete reference. Spike 001 is analytical (no code source), so only its README is present.
</findings_index>

<metadata>
## Processed Spikes

- 001-subagent-context-audit
</metadata>
