---
title: lattice-wiki-agent
category: package
summary: LangGraph + Bedrock CLI that runs lattice-wiki operations (init, scan, ingest, lint, query, log) headlessly by importing lattice-wiki-core directly — enabling non-interactive wiki maintenance from CI or automation.
status: active
package_path: packages/lattice-wiki-agent
package_type: library
domain:
language: Python
depends_on:
  - packages/lattice-wiki-core/lattice-wiki-core
tags:
  - python
  - wiki
  - agent
  - bedrock
  - langgraph
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 1163
---

# lattice-wiki-agent

## Purpose

`lattice-wiki-agent` is a Python CLI and library that wraps each [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] operation as an agent — `IngestAgent`, `QueryAgent`, `ScanAgent`, `LintAgent`, `LogAgent`, `InitAgent` — so the same workflows the [[wiki/plugins/lattice-wiki/lattice-wiki]] skill drives interactively can also run headlessly from a script, CI job, or automation pipeline. LLM-powered steps (ingest, query, optional lint semantic pass) are routed through Amazon [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] via `langchain-aws` and orchestrated with `langgraph`; mechanical steps (scan, log, init) reuse the core library directly without any model.

## File map - lattice-wiki-agent

Python package wiring a Click CLI to a set of LangGraph agents that drive [[wiki/packages/lattice-wiki-core/lattice-wiki-core]].

- `pyproject.toml` — Hatchling build config; declares the `lattice-wiki-agent` console script and a path-source dep on `lattice-wiki-core`.
- `uv.lock` — uv-resolved lockfile pinning langchain-aws, langgraph, and click versions.

### lattice-wiki-agent/src/

Wheel source root.

#### lattice-wiki-agent/src/lattice_wiki_agent/

The importable package.

- `__init__.py` — empty package marker.
- `cli.py` — Click group `main` with one subcommand per agent; loads config, decides backend, instantiates an agent, runs it via `asyncio.run`.
- `bedrock.py` — `make_bedrock(BedrockConfig)` factory; matches the `lattice-curator` pattern (model + region with env overrides).
- `config.py` — `Config`, `BedrockConfig`, and `load_config()` reading `.lattice-wiki.json` from the repo root with safe defaults.

##### lattice-wiki-agent/src/lattice_wiki_agent/agents/

One module per wiki operation.

- `__init__.py` — empty package marker.
- `ingest.py` — `IngestAgent` — 6-step LangGraph state machine replicating the `/lattice-wiki:ingest` workflow; the only multi-step LLM workflow.
- `init.py` — `InitAgent` — thin wrapper over `lattice_wiki_core.init_vault.init_wiki` (no LLM).
- `lint.py` — `LintAgent` — `lattice_wiki_core.lint_wiki.scan` + optional structured-output semantic pass.
- `log.py` — `LogAgent` — reads `<vault>/log.md`; no LLM, no model parameter.
- `query.py` — `QueryAgent` — BM25 retrieval + single LLM synthesis using `lattice_wiki_core.wiki_search`.
- `scan.py` — `ScanAgent` — calls `lattice_wiki_core.scan_monorepo.scan`; the `model` parameter is currently unused.

### lattice-wiki-agent/tests/

`pytest` + `pytest-asyncio` with `asyncio_mode = "auto"` (`pyproject.toml:28`).

- `__init__.py` — empty.
- `conftest.py` — shared fixtures (mock model, mock vault directory).
- `test_agents.py` — direct agent invocation tests.
- `test_cli.py` — Click `CliRunner` smoke tests verifying each subcommand registers and accepts its flags.
- `test_ingest.py` — IngestAgent end-to-end tests with a mock Bedrock model.

#### lattice-wiki-agent/tests/fixtures/

Static test data.

##### lattice-wiki-agent/tests/fixtures/mock-vault/

A minimal vault used by the tests.

- `index.md` — fixture index page.
- `log.md` — fixture log.

###### lattice-wiki-agent/tests/fixtures/mock-vault/concepts/

- `example.md` — fixture concept page identified during ingest.

###### lattice-wiki-agent/tests/fixtures/mock-vault/raw/

- `sample.md` — fixture raw source ingested by `test_ingest.py`.

## Sub-pages

- [[wiki/packages/lattice-wiki-agent/api]] — public CLI and Python API surface.
- [[wiki/packages/lattice-wiki-agent/patterns]] — agent-per-operation, structured output, per-command backend selection.
- [[wiki/packages/lattice-wiki-agent/work]] — bugs, gaps, tech debt, and open questions.
- [[wiki/packages/lattice-wiki-agent/context]] — why this package exists alongside lattice-wiki-core and the plugin.
