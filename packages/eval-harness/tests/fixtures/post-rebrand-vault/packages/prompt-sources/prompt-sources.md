---
title: prompt-sources
category: package
summary: Canonical agent role definitions (librarian, ingestor, linter, scanner, code_reader, synthesizer) used by both the Bedrock CLI and the divergence rubrics.
status: active
package_path: packages/prompt-sources
package_type: assets
domain:
language: Markdown
depends_on: []
tags: [prompts, agents]
sources: 0
updated: 2026-05-19
---

# prompt-sources

## Overview

`prompt-sources` is the canonical home for every agent role definition shipped with `deep-agents`. Each role lives at `packages/prompt-sources/agents/<role>.md` and supplies the system prompt, the input/output contract, the Rules section, and the Red flags section. The Phase 16 Bedrock divergence rubrics under `packages/eval-harness/src/eval_harness/divergence/rubrics/` anchor every check back into the matching prompt source.

## Roles

- `agents/librarian.md`
- `agents/ingestor.md`
- `agents/linter.md`
- `agents/scanner.md`
- `agents/code_reader.md` (Phase 16 addition)
- `agents/synthesizer.md` (Phase 16 addition)

## Cross-refs

- Anchored by [[wiki/packages/eval-harness/eval-harness]] divergence rules
- Consumed by [[wiki/agents/graph-wiki-agent/graph-wiki-agent]] command prompts
