---
title: lattice-wiki-agent — Context
category: package
summary: Why a programmatic agent layer exists alongside lattice-wiki-core and the lattice-wiki plugin — enabling non-interactive, CI-driven wiki maintenance.
updated: 2026-05-09
tokens: 1136
---

# lattice-wiki-agent — Context

## Concepts

The [[wiki/plugins/lattice-wiki/lattice-wiki]] plugin drives the wiki interactively from a Claude Code session: a human opens a slash command, a sub-agent reads the source, the sub-agent talks to the user, the sub-agent writes vault pages. That works well for human-in-the-loop maintenance but fails for any scenario where there is no Claude Code session — CI pipelines, scheduled jobs, batch ingestion of a backlog of design docs, scripts that ingest each merged PR.

`lattice-wiki-agent` fills that gap. It exposes the same operations (`init`, `scan`, `lint`, `ingest`, `query`, `log`) as a plain Python library plus a Click CLI, with the LLM calls routed through Amazon [[wiki/concepts/bedrock-langgraph-stack|Bedrock]] instead of a Claude Code session. A cron job can run `lattice-wiki-agent ingest <path>` and get the same vault updates a `/lattice-wiki:ingest` invocation would produce.

[[wiki/packages/lattice-wiki-core/lattice-wiki-core]] is the substrate. It owns the vault layout (`init_vault`, `layout_io`), the mechanical scans (`scan_monorepo`, `lint_wiki`, `update_index`, `append_log`), BM25 search (`wiki_search`), and the page templates and schema files used by every consumer. `lattice-wiki-agent` does not re-implement any of that. Every agent calls into `lattice_wiki_core.*` for the deterministic work and only adds the LLM orchestration — extracting a TLDR, identifying which pages to update, writing a source summary, synthesizing a query answer, optionally summarizing a lint report. The split keeps the core stdlib-only and easy to depend on while the agent layer absorbs the heavier `langchain-*` and `langgraph` deps.

This means the plugin's skill scripts and the agent share a single source of truth. A change to how the index is rendered, how packages are detected, or how log lines are formatted lands in `lattice-wiki-core` once and both consumers pick it up.

What the agent enables that plugin skill scripts don't:

| Capability | Plugin skill | `lattice-wiki-agent` |
|---|---|---|
| Run inside a Claude Code session | yes | yes (as a subprocess) |
| Run from CI / cron / batch | no | yes |
| Use Bedrock instead of the local Claude session | no | yes |
| Ingest a queue of sources programmatically | no | yes — `IngestAgent` is just a class |
| Compose with other Python tools (e.g. `lattice-evals`) | awkward | natural — import and call |
| Cost the operation against an AWS account | no (uses host session) | yes (Bedrock invoice) |

`Config.backend_for(command)` (`config.py:35`) lets each operation independently choose between `"claude"` (mechanical only — scan/lint/log/init can run with no LLM at all) and `"bedrock"` (build a `ChatBedrockConverse` and route the LLM steps through it). `ingest` and `query` have no mechanical-only mode, so the CLI fails fast if `bedrock` isn't selected for those commands. See [[wiki/packages/lattice-wiki-agent/api]] for the gating rules.

## Decisions

- No formal ADR yet exists for "ship the agent as a separate package vs. fold it into `lattice-wiki-core`". The de facto reason is the dependency footprint — `langchain-aws`, `langgraph`, and `langchain-core` would otherwise leak into every consumer of the core library.
- No ADR yet for "Bedrock as the headless LLM backend". The choice mirrors the [[wiki/concepts/lattice-naming-convention]] and the existing `lattice-curator` Bedrock factory.

## Sources

No ingested source documents this package yet — it is one of the newer additions and hasn't been the subject of a design doc, PR review, or article. When that changes, summaries land under `<vault>/sources/` and link back here.

## Belongs to domain

No formal domain page yet; conceptually part of the wiki maintenance toolchain alongside [[wiki/packages/lattice-wiki-core/lattice-wiki-core]].

## Used by

- [[wiki/plugins/lattice-wiki/lattice-wiki]] — sibling automation surface; the plugin drives the same operations interactively while the agent drives them headlessly.

## Related dependencies

- `langchain-aws>=0.2` — `ChatBedrockConverse` client.
- `langgraph>=0.2` — `StateGraph` orchestration for `IngestAgent`.
- `langchain-core>=0.3` — runnable / structured-output primitives.
- `click>=8.1` — CLI.
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — the library every agent delegates to for deterministic work.
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — the lifecycle the agent automates.
