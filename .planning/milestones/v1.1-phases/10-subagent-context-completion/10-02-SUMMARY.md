---
phase: 10-subagent-context-completion
plan: 02
subsystem: prompts/_fragments
tags: [fragment, vault-layout, architecture, provenance]
requires: []
provides:
  - "graph_wiki_agent.prompts._fragments.architecture_overview.ARCHITECTURE_OVERVIEW"
affects:
  - "agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/"
tech-stack:
  added: []
  patterns:
    - "3-line provenance header (Source / Anchor / Source-commit)"
    - "Pure-data fragment module (no imports, no functions)"
    - "Triple-quoted string with opening-backslash idiom to avoid leading blank line"
key-files:
  created:
    - "agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py"
  modified: []
decisions:
  - "Heading is `## Vault layout` (not `## Architecture`) — subagents need layout context, not arch theory"
  - "Trimmed the `<workspace>/wiki/` location prose and the `raw/` sub-tree to fit ~546 tokens (target ~600, cap 700)"
  - "Collapsed the `raw/` children into a single inline list — names retained, indentation dropped, to save ~150 tokens without losing the load-bearing fact that `raw/` is immutable"
  - "Preserved `[conditional]` annotations verbatim on `apps/`, `packages/`, `domains/` rows — these are load-bearing per CONTEXT.md"
  - "Preserved the `code is the source of truth` sentence verbatim — iron-rule echo"
  - "No wiring into scanner.py/ingestor.py/etc. — that lands in plan 10-05 per scope fence"
metrics:
  duration_min: 4
  completed: 2026-05-17
  tasks_total: 1
  tasks_completed: 1
  files_changed: 1
  est_tokens: 546
---

# Phase 10 Plan 02: Architecture Overview Fragment Summary

Added the `ARCHITECTURE_OVERVIEW` shared fragment carrying a compact rewrite of `cores/prompt-sources/SKILL.md §Architecture (L34-L69)` so later plans can wire vault-layout context into scanner/ingestor subagent prompts.

## What was built

A single new module `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py`:

- 3-line provenance header pointing to `cores/prompt-sources/SKILL.md`, anchor `## Architecture (L34-L69)`, source-commit `ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030`.
- Module-level constant `ARCHITECTURE_OVERVIEW` (triple-quoted string, opening-backslash idiom matching `iron_rules.py`).
- Content: `## Vault layout` heading + compact vault directory tree + conditional-containers note + code-is-source-of-truth sentence.
- Pure data — no imports, no functions, no `__all__`.

## Verification

All acceptance criteria pass:

| Check | Result |
|---|---|
| File exists at `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py` | PASS |
| First three lines match exact provenance header | PASS |
| `grep -c "^ARCHITECTURE_OVERVIEW = \"\"\""` reports 1 | PASS (1) |
| Import `from graph_wiki_agent.prompts._fragments.architecture_overview import ARCHITECTURE_OVERVIEW` succeeds | PASS |
| `.startswith("## Vault layout")` | PASS |
| Contains `packages/<pkg>/`, `apps/<app>/`, `domains/<domain>/`, `adrs/`, `[conditional]` | PASS |
| Contains "code is the source of truth" | PASS |
| `len(ARCHITECTURE_OVERVIEW) // 4 <= 700` | PASS (546) |
| `pytest agents/graph-wiki-agent/tests/prompts/test_provenance.py -x` exits 0 | PASS (2/2) |
| No `from graph_wiki_agent` imports in the new file | PASS (0) |
| No edits outside the new file | PASS (only file in commit) |

## Deviations from Plan

None — plan executed exactly as written. First draft was 695 tokens (within the 700 cap but uncomfortably near it); trimmed the verbose comment column on the workspace-root rows and collapsed the `raw/` subdirectories into one inline list to land at 546 tokens, which is closer to the ~600 target stated in the plan.

## Token Budget

- char_len: 2187
- est_tokens (char_len // 4): 546
- Target: ~600
- Cap: 700
- Headroom: 154 tokens remaining

## Commits

- `1570c7a`: feat(10-02): add ARCHITECTURE_OVERVIEW fragment for vault layout

## Self-Check: PASSED

- File `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py`: FOUND
- Commit `1570c7a`: FOUND in `git log --oneline --all`
