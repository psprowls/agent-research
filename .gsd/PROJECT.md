# Project: agent-research

## Current Project Truth

`agent-research` is a Python 3.11+ `uv` workspace for LangChain-primitives-based AI tooling on AWS Bedrock. Its main product surface is `graph-wiki-agent`: a Bedrock-backed reimplementation of the `graph-wiki` wiki-maintenance workflows, exposed both as a local stdio MCP server and as a headless Typer CLI.

The project exists to reproduce the existing `graph-wiki` Claude Code plugin workflows with parallel within-command subagents, lower model cost, and preserved compatibility with existing graph-wiki vault conventions.

## Core Value

Faithfully reproduce `graph-wiki` wiki-maintenance outcomes while running entirely on AWS Bedrock with bounded parallel subagents, so Pat can achieve the same wiki refresh, query, ingest, lint, scan, log, and graph workflows at meaningfully lower cost than the Claude-Code-hosted plugin path.

## Active Source of Truth

`.gsd/` is the active source of truth for current planning, requirements, task execution, and milestone state. New project truth should be recorded in GSD artifacts first.

`.planning/` is archive/reference evidence only. It remains valuable as historical context for shipped v1.0 through v1.11 work, decisions, and verification records, but old phases and deferred items in `.planning/` are not automatically active M001 scope.

## Current Delivery Posture

- The repo is a single-developer Python monorepo managed by `uv` workspaces.
- v1 is Bedrock-only: use `langchain-aws` / `ChatBedrockConverse` through `model-adapter.make_llm(role)` rather than direct Anthropic APIs or raw Bedrock client construction in product code.
- The orchestration layer is intentionally lightweight: `subagent-runtime` provides an asyncio/Semaphore-based `SubagentPool` over LangChain message/tool primitives instead of LangGraph/deepagents orchestration.
- The primary integration surface is MCP over stdio for local hosts, with a headless CLI for direct operation and tests.
- Existing graph-wiki vault format compatibility remains a constraint: frontmatter schema, layout block format, wikilinks, citations, and generated entity/index conventions must be preserved unless a future GSD milestone explicitly changes them.

## Live Workspace Layout

Root `pyproject.toml` declares the workspace as:

- `packages/*`
- `agents/*`

Current workspace members are:

- `agents/graph-wiki-agent` (`graph-wiki-agent`) — AWS Bedrock-powered wiki maintenance agent, shipped as `graph-wiki-agent` CLI and `graph-wiki-mcp` stdio MCP server.
- `packages/eval-harness` (`eval-harness`) — deterministic eval checks, pricing, and cost-frontier sweep runner for graph-wiki-agent.
- `packages/graph-io` (`graph-io`) — SQLite code-graph store, manifest scanning, query layer, graph projection, and `cg` CLI.
- `packages/model-adapter` (`model-adapter`) — Bedrock model loader and guard/normalization layer for role-based LLM construction.
- `packages/source-parser` (`source-parser`) — tree-sitter-backed source parser that emits span-bearing source trees and graph projections.
- `packages/subagent-runtime` (`subagent-runtime`) — async bounded fan-out primitive used by graph-wiki-agent subagent dispatch.
- `packages/wiki-io` (`wiki-io`) — graph-wiki vault/page IO, layout/frontmatter preservation, generated wiki surfaces, and related helpers.
- `packages/workspace-io` (`workspace-io`) — workspace bootstrap, manifest IO, repository/wiki resolution, and graph-wiki config handling.

## Shipped Trajectory Through v1.11

The legacy `.planning/` archive records a shipped v1 line from v1.0 through v1.11:

- **v1.0 graph-wiki-agent parity** shipped the initial uv workspace, Bedrock model adapter, wiki IO, MCP skeleton, hybrid search, query pipeline, eval harness, and the core CLI/MCP command set.
- **v1.1 Quality Improvements** ported graph-wiki prompt content, added divergence evals, validated an early cost-frontier sweep, improved MCP cancellation behavior, and added structured trace/cost rendering.
- **v1.2 Graph-Wiki Port & Debt Cleanup** added `workspace-io`, completed the graph-wiki rebrand, ported the Claude Code plugin as a separate Claude-inference plugin surface, and closed v1.1 carry-forward trace/sweep/config debt.
- **v1.3 Tooling Cleanup** fixed wiki/workspace path issues, renamed the plugin bootstrap command away from `/init`, moved model overrides into `.graph-wiki.yaml`, and completed the mechanical agent package rename.
- **v1.4 Workspace Path Resolution Cleanup** tightened workspace/package classification and removed obsolete upstream prompt-source scaffolding.
- **v1.5 Repo Rename & Foundational Package Additions** captured the repo rename to `agent-research`, final `wiki-io` package rename, and the addition of `graph-io` plus `source-parser` foundations.
- **v1.6 Code Graph Ontology Expansion** landed graph schema v2, URI identity, structural graph nodes, entry points, test suites, domains, derived edges, and expanded `cg` query surfaces.
- **v1.7 graph-io Integration & Wiki Hygiene** made graph-io the agent identity layer for librarian/scanner/ingestor flows and exposed graph operations through the agent CLI/MCP surfaces.
- **v1.8 Wiki Entity Restructure** collapsed generated wiki pages into a URI-keyed `wiki/entities/` model, added deterministic entity writing, scanner-generated index, narrative injection, and domain proposal support.
- **v1.9 Graph Refinements & Wiki Filename Slimdown** added stdlib/builtin handling, app reclassification, short human-readable entity filenames, and removed dormant package-family machinery.
- **v1.10 Wiki Index & Entity Page Enrichment** improved generated wiki readability with app sections, inline summaries, dependency/test-suite nesting, fleshed-out entity templates, internal-dependency fixes, and decoupling from `graph_io.cli` shims.
- **v1.11 TypeScript Type Node Kind** shipped TS `interface` / `type alias` / `enum` projection as a compact `type` node kind with `ts_kind`, fixed exported TS types previously mislabeled as `function`, and added graph-io cross-kind resolution for `type`.

This trajectory is historical context. It should not be treated as an instruction to revive old phase machinery, backfill every archive artifact, or run a new cost-frontier sweep inside M001.

## Current Known Boundaries

M001 is about initializing current GSD truth from the legacy archive, not converting the entire archive. In particular, this project truth does **not** claim:

- wholesale conversion of `.planning/` into `.gsd/`;
- reusable migration tooling for future repositories;
- an active M001 cost-frontier sweep or winner-selection run;
- reactivation of dropped/deferred Phase 60 sweep execution;
- completion of old process debt such as missing historical audits or retroactive validation.

Those items may be planned later, but they are outside this current PROJECT truth artifact unless a future GSD milestone explicitly adopts them.

## Inspection Surface

Future planning agents should start with `.gsd/PROJECT.md`, `.gsd/ROADMAP.md`, `.gsd/REQUIREMENTS.md`, and active milestone artifacts under `.gsd/milestones/`. Use `.planning/` only as reference evidence when current GSD artifacts need historical detail or shipped-background verification.
