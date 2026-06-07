---
title: prompt-sources
uri: pkg:agent-research/prompt-sources
kind: package
summary: Canonical agent role definitions (librarian, ingestor, linter, scanner, code_reader, synthesizer) used by both the Bedrock CLI and the divergence rubrics.
updated: 2026-05-19
---

# prompt-sources

## Overview

`prompt-sources` is the canonical home for every agent role definition shipped with `agent-research`. Each role lives at `packages/prompt-sources/agents/<role>.md` and supplies the system prompt, the input/output contract, the Rules section, and the Red flags section. The Phase 16 Bedrock divergence rubrics under `packages/eval-harness/src/eval_harness/divergence/rubrics/` anchor every check back into the matching prompt source.

## Roles

- `agents/librarian.md`
- `agents/ingestor.md`
- `agents/linter.md`
- `agents/scanner.md`
- `agents/code_reader.md` (Phase 16 addition)
- `agents/synthesizer.md` (Phase 16 addition)

## Cross-refs

- Anchored by [[entities/pkg_eval-harness]] divergence rules
- Consumed by [[entities/app_graph-wiki-cli]] command prompts
