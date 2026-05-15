---
phase: 06-prompt-content-port-divergence-eval
plan: "03"
subsystem: prompts
tags: [prompt-port, fragments, provenance, PORT-01, PORT-06]
dependency_graph:
  requires: [06-01, 06-02]
  provides: [prompts/_fragments/iron_rules.py, prompts/_fragments/page_categories.py, prompts/_fragments/citation_rules.py, prompts/_fragments/frontmatter_rules.py]
  affects: [06-04, 06-05, 06-06, 06-07]
tech_stack:
  added: []
  patterns: [composable-prompt-fragments, provenance-header, import-time-string-constants]
key_files:
  created:
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/__init__.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/__init__.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/iron_rules.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/page_categories.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/citation_rules.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/frontmatter_rules.py
  modified: []
decisions:
  - "Fragment files use `\"\"\"\\ ` (backslash after triple-quote) to avoid leading newline, matching SCANNER_SYSTEM style from scan.py"
  - "Iron rule 3 adapted: `<workspace>/wiki/` replaced with 'the vault path' — preserves the semantic constraint while removing host-specific path"
  - "Page categories table adapted: `<workspace>/wiki/` paths replaced with `vault_path/` placeholder — semantically equivalent, removes lattice-workspace coupling"
  - "frontmatter_rules.py includes both ingestor (source-summary) and scanner (stub) field subsets in one constant — per plan task action"
metrics:
  duration: "1m 49s"
  completed: "2026-05-15T19:50:53Z"
  tasks_completed: 1
  tasks_total: 1
  files_created: 6
  files_modified: 0
---

# Phase 06 Plan 03: Shared Prompt Fragment Files Summary

**One-liner:** Four SCREAMING_SNAKE_CASE string constants ported from lattice-wiki canonical sources into `prompts/_fragments/`, each with a locked 3-line provenance header enabling PORT-06 drift detection.

## What Was Built

Created the `prompts/` and `prompts/_fragments/` Python packages under `code_wiki_agent`, then wrote four shared fragment files:

- **`iron_rules.py`** — 7 canonical iron rules verbatim from `cores/prompt-sources/SKILL.md` §Iron rules (L193-L201). The `<workspace>/wiki/` path reference in rule 3 was adapted to "the vault path" to remove lattice-workspace coupling while preserving the semantic constraint.

- **`page_categories.py`** — 9-row page category table from `cores/prompt-sources/SKILL.md` §Page categories (L143-L155). `<workspace>/wiki/` path references replaced with `vault_path/` neutral placeholder per RESEARCH §Adaptation Map.

- **`citation_rules.py`** — Wikilink/citation rules synthesized from `cores/prompt-sources/agents/librarian.md` §Rules (citation bullets L73-L77) and `cores/prompt-sources/agents/ingestor.md` §Rules "Cite aggressively" (L101). All slash-command and `${CLAUDE_PLUGIN_ROOT}` references removed; `[[wikilink]]` syntax and "cite every claim" invariants preserved verbatim.

- **`frontmatter_rules.py`** — Required-field union from `cores/prompt-sources/agents/ingestor.md` §Workflow step 4 (L50-L58) and `cores/prompt-sources/agents/scanner.md` §Workflow step 3 (L47-L48). Covers both ingestor source-summary fields (`title`, `category`, `page_type`, `target_slug`, `summary`, `tags`) and scanner stub fields (`title`, `category`, `summary`, `package_path`, `language`).

Two `__init__.py` package markers were also created (one for `prompts/`, one for `_fragments/`).

## Verification Results

- `uv run python -c "from code_wiki_agent.prompts._fragments.iron_rules import IRON_RULES; ..."` — all 4 imports OK
- `uv run pytest agents/code-wiki-agent/tests/prompts/test_provenance.py -x -q` — 2 passed (header format + Source path resolution)
- No host-specific references (`CLAUDE_PLUGIN_ROOT`, `/lattice-wiki:`) in any fragment file
- No Python imports from `cores/prompt-sources/` (documentation, not importable Python)

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create prompts package + shared fragment files | 5d99782 | 6 created |

## Deviations from Plan

None — plan executed exactly as written.

Minor adaptation decisions (within plan's allowed scope):
- Iron rule 3: `<workspace>/wiki/` → "the vault path" (per RESEARCH §Adaptation Map: replace `<workspace>/wiki/` with neutral wording about the vault)
- Page categories: `<workspace>/wiki/` → `vault_path/` for all 9 directory entries
- `frontmatter_rules.py` source anchor uses ingestor.md as primary (per plan) with scanner.md fields also covered in the constant body

## Known Stubs

None. All fragment files contain complete canonical content. No placeholder text or TODO items.

## Threat Flags

None. Fragment files are static Python string constants; no new network endpoints, auth paths, or file access patterns introduced.

## Self-Check

### Created files exist:
- FOUND: agents/code-wiki-agent/src/code_wiki_agent/prompts/__init__.py
- FOUND: agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/__init__.py
- FOUND: agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/iron_rules.py
- FOUND: agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/page_categories.py
- FOUND: agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/citation_rules.py
- FOUND: agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/frontmatter_rules.py

### Commits exist:
- FOUND: 5d99782

## Self-Check: PASSED
