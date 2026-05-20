---
phase: 06-prompt-content-port-divergence-eval
plan: "04"
subsystem: graph-wiki-agent/prompts
tags: [prompt-port, librarian, synthesizer, code-reader, query-command, PORT-02, D-14]
requirements: [PORT-02]

dependency-graph:
  requires: [06-03]
  provides: [librarian-system-prompt, synthesizer-system-prompt, code-reader-system-prompt, import-based-query]
  affects: [commands/query.py, prompts/librarian.py, prompts/synthesizer.py, prompts/code_reader.py]

tech-stack:
  added: []
  patterns:
    - Fragment composition via join at import time (D-02, no runtime templating)
    - Verbatim relocation of role prompts to prompts/ module (D-14)
    - Re-export via import for backward compatibility (noqa: F401 pattern)
    - Syrupy snapshot testing for prompt byte-stability

key-files:
  created:
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/synthesizer.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/code_reader.py
    - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py

decisions:
  - "LIBRARIAN_SYSTEM composed as join of 7 sections: _ROLE_INTRO + IRON_RULES + PAGE_CATEGORIES + CITATION_RULES + _WORKFLOW + _RED_FLAGS + _OUTPUT_FORMAT"
  - "Trimmed _WORKFLOW and _OUTPUT_FORMAT to fit <4000-char budget (final: 3901 chars)"
  - "SYNTHESIZER_SYSTEM and CODE_READER_SYSTEM relocated verbatim without provenance header (no canonical lattice source per D-14)"
  - "Import lines use noqa: F401 since constants are re-exported, not directly used in query.py body"

metrics:
  duration: ~15 minutes
  completed: "2026-05-15"
  tasks_completed: 3
  files_modified: 5
---

# Phase 06 Plan 04: Librarian Prompt Port + Relocation Summary

**One-liner:** LIBRARIAN_SYSTEM composed from 3 shared fragments + librarian-local prose (3901 chars); SYNTHESIZER_SYSTEM and CODE_READER_SYSTEM relocated verbatim; commands/query.py refactored to import-based prompt sourcing.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create prompts/synthesizer.py and code_reader.py (verbatim relocation) | 5e80ac8 | prompts/synthesizer.py, prompts/code_reader.py |
| 2 | Create prompts/librarian.py composing fragments + role-local content (PORT-02) | fa199eb | prompts/librarian.py, tests/prompts/__snapshots__/test_prompt_snapshots.ambr |
| 3 | Swap inline constants in commands/query.py for imports | 8138bd5 | commands/query.py |

## Deliverables

### prompts/librarian.py
Composes `LIBRARIAN_SYSTEM` at import time via `"\n\n".join([...])` of 7 sections:
1. `_ROLE_INTRO` — adapted from `cores/prompt-sources/agents/librarian.md §Role`
2. `IRON_RULES` — shared fragment (from 06-03)
3. `PAGE_CATEGORIES` — shared fragment (from 06-03)
4. `CITATION_RULES` — shared fragment (from 06-03)
5. `_WORKFLOW` — adapted from `librarian.md §Workflow`, host-specific refs removed
6. `_RED_FLAGS` — verbatim from `librarian.md §Red flags`
7. `_OUTPUT_FORMAT` — preserves `NO_RELEVANT_CONTENT` sentinel contract

Total composed length: **3901 chars** (budget: <4000 chars).

### prompts/synthesizer.py + prompts/code_reader.py
Verbatim relocations of `SYNTHESIZER_SYSTEM` and `CODE_READER_SYSTEM` from `commands/query.py`. No provenance header (no canonical lattice-wiki source per D-14). Byte-identical to former inline definitions.

### commands/query.py (refactored)
- Removed 3 inline `*_SYSTEM` triple-quoted string blocks (51 lines deleted)
- Added 3 import lines with `# noqa: F401`
- Updated module docstring to note re-export source
- All call sites (`SystemMessage(content=LIBRARIAN_SYSTEM)`) unchanged
- Python identity check: `commands.query.LIBRARIAN_SYSTEM is prompts.librarian.LIBRARIAN_SYSTEM`

## Verification

- `test_librarian_system_snapshot` passes (snapshot recorded and verified)
- 103 tests pass across `agents/graph-wiki-agent/tests/` (3 integration tests skipped — require Bedrock)
- No inline `*_SYSTEM` definitions remain in `commands/query.py`
- Adaptation map honored: no `${CLAUDE_PLUGIN_ROOT}`, `/lattice-wiki:`, `obsidian-markdown`, `Offer to file`, `vote to file` in composed prompt

## Threat Model Compliance

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-06-07: NO_RELEVANT_CONTENT sentinel drift | Substring assertion in verify command; snapshot test freezes composed prompt | Mitigated |
| T-06-08: Host-specific references in prompt | Acceptance criteria assert absence of CLAUDE_PLUGIN_ROOT, /lattice-wiki:, Offer to file | Mitigated |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Budget] Trimmed role-local content to fit <4000 char budget**
- **Found during:** Task 2 (first compose attempt yielded 4825 chars)
- **Issue:** Initial _WORKFLOW (1118 chars) and _OUTPUT_FORMAT (527 chars) were too verbose given shared fragments consume 2571 chars
- **Fix:** Condensed _WORKFLOW to 4 steps (614 chars) and _OUTPUT_FORMAT to 2 paragraphs (375 chars); consolidated redundant citation/no-invention rules already covered by CITATION_RULES and IRON_RULES fragments
- **Files modified:** prompts/librarian.py
- **Final length:** 3901 chars (within budget)

None — plan executed as specified otherwise. SYNTHESIZER_SYSTEM and CODE_READER_SYSTEM passed byte-identity verification on first attempt.

## Known Stubs

None — all prompt constants are complete and wired.

## Self-Check

- [x] `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py` — exists
- [x] `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/synthesizer.py` — exists
- [x] `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/code_reader.py` — exists
- [x] `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` — exists
- [x] Commits 5e80ac8, fa199eb, 8138bd5 — all in git log

## Self-Check: PASSED
