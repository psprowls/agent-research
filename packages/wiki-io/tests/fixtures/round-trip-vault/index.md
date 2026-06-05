# Index — wiki

_Auto-generated 2026-05-11 • 12 navigation pages_

> Navigation index for `wiki/`. Updated by `scripts/update_index.py`
> or during `/lattice-wiki:scan` / `/lattice-wiki:ingest`.
> Answer queries by reading this file first, then open relevant package/domain pages.

## Package (12)

- [[plugins/lattice-curator/lattice-curator|lattice-curator]] — Claude Code plugin wrapping packages/lattice-curator-core — UserPromptSubmit hook, PreToolUse:Skill stage tracker, /curator:init command, and an MCP server exposing context.fetch.
- [[packages/lattice-curator-core/lattice-curator-core|lattice-curator-core]] — Stage-aware Python context-curation library — gates UserPromptSubmit, runs a two-pass Bedrock retriever over wiki + experts catalogs, returns compact briefs for injection into Claude Code.
- [[packages/lattice-evals/lattice-evals|lattice-evals]] — Reproducible evaluation harness for Lattice Claude Code plugins — runs scenarios × configs × runs to measure plugin uplift via three isolation axes and three verifier kinds. Exposes the `lattice-eval` CLI.
- [[plugins/lattice-graph/lattice-graph|lattice-graph]] — Claude Code plugin shell for the per-repo code graph. Thin shell over `lattice-graph-core` — 13 slash commands wrapping `cg` plus a SessionStart staleness hook (hook config in hooks/hooks.json since v0.2.1). MCP server adapter deferred to v1.1.
- [[packages/lattice-graph-core/lattice-graph-core|lattice-graph-core]] — SQLite-backed code-graph library for the lattice ecosystem — schema, upsert, manifest scanning, cross-file edge resolution, read-only query layer (including imports, exports, exported-by, imported-by), wiki sync, and the `cg` CLI.
- [[packages/lattice-source-parser/lattice-source-parser|lattice-source-parser]] — Tree-sitter-backed Python library that parses source files into a span-bearing SourceTree and projects them into GraphRecords aligned with the lattice-graph SQLite schema.
- [[plugins/lattice-wiki/lattice-wiki|lattice-wiki]] — Claude Code plugin that builds and maintains a persistent, cross-referenced markdown wiki alongside any source-code project — single packages, monorepos, or hybrid shapes.
- [[packages/lattice-wiki-agent/lattice-wiki-agent|lattice-wiki-agent]] — LangGraph + Bedrock CLI that runs lattice-wiki operations (init, scan, ingest, lint, query, log) headlessly by importing lattice-wiki-core directly — enabling non-interactive wiki maintenance from CI or automation.
- [[packages/lattice-wiki-core/lattice-wiki-core|lattice-wiki-core]] — Pure-Python (stdlib-only) library that powers the lattice-wiki plugin — scan, lint, ingest, index, search, and layout IO for an Obsidian-shaped Code Wiki.
- [[plugins/lattice-work/lattice-work|lattice-work]] — Bug / tech-debt / feature lifecycle plugin — lifecycle lint and sidecar generation for the unified work/ namespace.
- [[plugins/lattice-workflows/lattice-workflows|lattice-workflows]] — Engineering-discipline framework for Claude Code — skills, hooks, task gates, and methodology; forked from obra/superpowers via pcvelz/superpowers.
- [[packages/lattice-workspace/lattice-workspace|lattice-workspace]] — Python library (`pyyaml` only) that resolves the lattice workspace directory, reads/writes the v2 `.lattice.yaml` manifest with per-plugin version tracking, exposes typed path accessors, idempotently initializes the workspace, and signals plugin staleness via `warn_if_stale`.

## More

- [[concepts/index]] — Concept (34 pages)
- [[sources/index]] — Source (12 pages)
- [[adrs/index]] — ADR (16 pages)
- [[architecture/index]] — Architecture (0 pages)
- [[dependencies/index]] — Dependency (0 pages)
- [[work/index]] — Work (27 pages)
