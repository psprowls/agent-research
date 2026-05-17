---
title: lattice-curator-core — Work
category: package
summary: Open issues, tech debt, follow-ups, and discrepancies discovered while documenting the package.
tags: [python, work, tech-debt]
updated: 2026-05-10
tokens: 716
---

# lattice-curator-core — Work

## Bugs

(None currently tracked.)

## Tech debt

- **`budgets.*` declared but not enforced.** `Config.budgets.pass1_timeout_ms`, `pass2_timeout_ms`, `minute_budget_seconds` exist in `config.py` and have defaults, but the retriever does not pass them to `asyncio.wait_for` and the hook does not enforce a per-minute cap. Either wire them up or remove them.
- **Token counts are estimates, not measurements.** `pass1_tokens` / `pass2_tokens` in `Brief.diagnostics` use `len(prompt_text) // 4` rather than [[wiki/concepts/bedrock-langgraph-stack|Bedrock]]'s reported usage. Adequate for budget signals; misleading for dollar accounting.
- **Catalog dedup is order-sensitive.** First source wins on path collision (`retriever.py:57`). If the wiki vault and `lattice/knowledge/` ever produce overlapping paths, the order of `sources` in `curator_fire.py` decides which one is visible. Worth documenting or making the merge strategy explicit.
- **`VERSION` lives in two places.** `__init__.py` declares `VERSION = "0.1.0"` while `pyproject.toml` declares `version = "1.0.0"`. Move to one source (likely `pyproject.toml` + `importlib.metadata.version`).
- **README is stale.** Claims TypeScript / pnpm; the source is Python.
- **ADR gap.** An earlier ADR referenced "0025-typescript-bedrock-stack-for-curator" still says "TypeScript Bedrock stack" — it contradicts the Python implementation and has not been updated to reflect the pivot.

## Features

- Per-stage `selection_target` overrides via config.
- A third source adapter for the user's own scratch notes (`~/.lattice/notes/*.md`).
- Cache layer keyed on `(prompt_hash, catalog_hash)` so repeated similar prompts don't re-spend Bedrock budget.

## Open questions

- Should `budgets.pass1_timeout_ms` / `pass2_timeout_ms` / `minute_budget_seconds` be enforced (currently declared but unused)?
- Should `VERSION` in `__init__.py` (`"0.1.0"`) be sourced from `pyproject.toml` (`1.0.0`) instead of duplicated?
- Should `wiki_source` accept a frontmatter key other than `description` for catalog inclusion? Many wiki pages use `summary:` instead.
- Is fail-silent the right posture for the MCP path? Currently `mcp/server.py` propagates exceptions (good — Claude explicitly asked); but malformed config still results in a degraded brief without a clear signal to the caller.
- Should there be a "no-fire" verb list (e.g. "explain", "what is") so reads-only prompts don't trigger curation?

## See also

- [[wiki/packages/lattice-curator-core/lattice-curator-core]] — package overview
- [[work/2026-05-04-plugin-aware-semantic-processing]] — related work item
