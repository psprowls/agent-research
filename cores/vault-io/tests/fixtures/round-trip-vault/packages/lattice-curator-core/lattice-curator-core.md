---
title: lattice-curator-core
category: package
summary: Stage-aware Python context-curation library — gates UserPromptSubmit, runs a two-pass Bedrock retriever over wiki + experts catalogs, returns compact briefs for injection into Claude Code.
status: active
package_path: packages/lattice-curator-core
package_type: library
domain:
language: Python
depends_on:
  - langchain-aws
  - langgraph
  - langchain-core
  - pydantic
  - python-frontmatter
  - mcp
tags:
  - python
  - context-curation
  - rag
  - bedrock
  - langchain
  - langgraph
  - pydantic
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 1496
---

# lattice-curator-core

## Purpose

Pure-logic Python library implementing a stage-aware, two-pass context-curation pipeline. Given `(prompt, transcript_tail, stage, sources, model)`, it returns a `Brief` (or a no-op gate decision) without any awareness of Claude Code, hooks, or MCP. The package is the engine; [[wiki/plugins/lattice-curator/lattice-curator]] is the only piece that touches Claude Code surfaces. The pipeline is a two-pass curation modeled as a LangGraph `StateGraph`: a cheap heuristic gate decides whether to fire; on fire, the retriever walks `build_catalog → pass1_pick → (load_picks → pass2_brief | assemble) → END`. Pass 1 sees a flattened catalog of frontmatter; Pass 2 sees the full text of the picks. Both calls hit a [[wiki/concepts/bedrock-langgraph-stack|Bedrock]]-hosted small model via LangChain's `ChatBedrockConverse` (default `us.anthropic.claude-haiku-4-5-20251001-v1:0`). Knowledge surfaces plug in through the `Source` adapter contract. Stage-aware: `brainstorming`, `writing-plans`, `execute-plan`, `debugging` each have a tuned prompt pair plus a `selection_target {min, max}` budget; `generic` is the fallback.

## File map

- `pyproject.toml` — package manifest; declares `langchain-aws`, `langgraph`, `langchain-core`, `pydantic`, `python-frontmatter`, `mcp`; dev extras for `pytest`, `pytest-asyncio`, `ruff`
- `README.md` — package overview (stale: claims TypeScript / pnpm; the source is Python)

### lattice-curator-core/src/lattice_curator_core/

- `__init__.py` — public exports + `VERSION = "0.1.0"`
- `bedrock.py` — `make_bedrock(config)` LangChain `ChatBedrockConverse` wrapper; reads `LATTICE_CURATOR_MODEL` + AWS creds
- `config.py` — `.lattice-curator.json` loader + bundled defaults; Pydantic-validated; deep-merged
- `format.py` — `format_brief(brief, mode)` renderer; `hybrid` produces excerpts + see-also list, `inline` expands everything
- `gate.py` — pure tier-1 gate; prompt-length floor, debounce, action-verb match, Jaccard topic-shift, `last_skill`-derived stage
- `log.py` — JSONL fire-log appender with size-based rotation
- `retriever.py` — LangGraph `StateGraph` orchestrating the two-pass retrieval
- `seed.py` — `seed_knowledge(dest)` copies bundled rules into the project's `lattice/knowledge/`
- `types.py` — shared types (`Stage`, `Mode`, `Brief`, `BriefExcerpt`, `BriefSeeAlso`, `GateInput`, `GateDecision`, `GateConfig`, `SkillMarker`)

### lattice-curator-core/src/lattice_curator_core/sources/

- `types.py` — `Source` Protocol, `CatalogEntry` dataclass, `walk_md(directory)` helper
- `wiki.py` — adapter for the [[wiki/plugins/lattice-wiki/lattice-wiki]] vault; walks `<vault_dir>/**/*.md`, parses frontmatter, skips files without a `description:`
- `experts.py` — adapter for the experts rule library; emits `{domain, impact}` tags from frontmatter; treats `_shared/` as `domain: shared`

### lattice-curator-core/src/lattice_curator_core/stages/

- `__init__.py` — `_REGISTRY`, `ALL_STAGES`, `get_stage()`
- `brainstorming.py` — high-recall stage; `selection_target {min: 4, max: 8}`; defines the shared `StageDef` dataclass
- `debugging.py` — `selection_target {min: 3, max: 6}`; emphasizes incidents, gotchas, ADRs
- `execute_plan.py` — `selection_target {min: 2, max: 5}`; tightest budget; pulls package overview + cited rules
- `generic.py` — fallback when stage signal is unknown; `{min: 3, max: 6}`
- `writing_plans.py` — `selection_target {min: 3, max: 6}`; pulls package boundaries, file maps, contracts

### lattice-curator-core/src/lattice_curator_core/knowledge/

Bundled expert rules shipped with the package; `seed_knowledge()` copies them into a project's `lattice/knowledge/`. Each `.md` has a frontmatter `description` so the experts source treats it as catalog-eligible.

- `_shared/` — shared section template + rule template
- `expo/` — Expo Router, Image, NativeWind, native data-fetching, etc. (~7 files)
- `react/` — async, bundle, client, JS, patterns, rendering, server, state (~50+ files)
- `react-native/` — animation, list performance, monorepo, navigation, react-compiler, rendering, UI primitives (~30+ files)
- `web-design/` — accessibility, focus states, forms, prefers-reduced-motion, typography (~7 files)

### lattice-curator-core/tests/

Pytest suite (`asyncio_mode = "auto"`). Run with `pytest`.

## Sub-pages

- [[wiki/packages/lattice-curator-core/api]] — public API surface, stage definitions, retrieval pipeline contract
- [[wiki/packages/lattice-curator-core/patterns]] — the gate → retrieve → format pipeline, stage-aware curation, source adapter contract
- [[wiki/packages/lattice-curator-core/work]] — bugs, tech debt, features, open questions
- [[wiki/packages/lattice-curator-core/context]] — concepts, decisions, ADRs, sources, why this exists
