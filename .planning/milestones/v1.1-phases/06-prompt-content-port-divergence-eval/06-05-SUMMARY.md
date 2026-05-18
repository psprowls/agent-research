---
phase: 06-prompt-content-port-divergence-eval
plan: 05
subsystem: prompts
tags: [prompt-port, ingestor, ingest-command, port-03]

requires:
  - phase: 06-03
    provides: shared fragment files (iron_rules, page_categories, frontmatter_rules, citation_rules) and test scaffold (test_prompt_snapshots.py)

provides:
  - "prompts/ingestor.py exporting INGESTOR_SYSTEM composed from 4 fragments + 5 role-local sections"
  - "commands/ingest.py refactored to import INGESTOR_SYSTEM from prompts.ingestor"
  - "Syrupy snapshot for INGESTOR_SYSTEM recorded"

affects:
  - "06-08 (divergence eval ING-003 page-type routing check targets INGESTOR_SYSTEM content)"
  - "commands/ingest.py callers (no behavior change; INGESTOR_SYSTEM identity preserved)"

tech-stack:
  added: []
  patterns:
    - "INGESTOR_SYSTEM composed at import time via join([...]) — no runtime templating"
    - "commands/*.py imports *_SYSTEM from prompts module; no inline definitions"

key-files:
  created:
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py
    - agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr (updated)
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py

key-decisions:
  - "Trimmed role-local prose aggressively to stay under 5000 chars with 3636-char fragment base"
  - "Replaced INGESTOR_SYSTEM inline block with single import line + noqa: F401"
  - "Restored _LIST_ITEM_RE regex that was accidentally deleted during edit (Rule 1 auto-fix)"

patterns-established:
  - "Port pattern for commands/*.py: delete inline *_SYSTEM, add import from prompts module"

requirements-completed: [PORT-03]

duration: 25min
completed: 2026-05-15
---

# Phase 06 Plan 05: Ingestor Prompt Port Summary

**INGESTOR_SYSTEM ported from ingestor.md canonical source into prompts/ingestor.py, composed from 4 shared fragments plus adapted role-local routing/rules/red-flags, with commands/ingest.py swapped to import-based sourcing**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-15T19:35:00Z
- **Completed:** 2026-05-15T20:00:36Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `prompts/ingestor.py` composing IRON_RULES + PAGE_CATEGORIES + FRONTMATTER_RULES + CITATION_RULES + 5 role-local sections (role intro, page-type routing, ingestor rules, red flags, output format)
- Adapted ingestor.md canonical source per RESEARCH §Adaptation Map: removed CLAUDE_PLUGIN_ROOT script calls, /lattice-wiki: slash commands, "Wait for confirmation" interactive loops, obsidian-markdown skill invocations
- Preserved downstream parser contract: "Output ONLY YAML frontmatter followed by a markdown body" instruction and page-type values (package, concept, adr, source)
- Recorded syrupy snapshot for INGESTOR_SYSTEM (4995 chars, under 5000 char budget)
- Deleted 25-line inline INGESTOR_SYSTEM from commands/ingest.py, replaced with single import + noqa: F401
- Verified Python identity: `commands.ingest.INGESTOR_SYSTEM is prompts.ingestor.INGESTOR_SYSTEM`

## Task Commits

1. **Task 1: Create prompts/ingestor.py** - `908bca5` (feat)
2. **Task 2: Swap inline INGESTOR_SYSTEM for import** - `fae1168` (refactor)

## Files Created/Modified

- `agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py` - New file; INGESTOR_SYSTEM composed from 4 fragments + 5 role-local sections
- `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py` - Inline constant removed; import from prompts.ingestor added; docstring updated
- `agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` - Snapshot recorded for test_ingestor_system_snapshot

## Decisions Made

- Kept all 4 fragments (IRON_RULES 652 + PAGE_CATEGORIES 1316 + FRONTMATTER_RULES 1065 + CITATION_RULES 603 = 3636 chars) as mandated by must_haves, leaving only 1348 chars for role-local content to stay under 5000
- Trimmed role-local sections aggressively to fit budget: single-sentence routing bullets, bullet-list rules, inline red flags
- PAGE_CATEGORIES included per plan must_haves despite being large (1316 chars) — it provides context for the ingestor's routing decisions across all page categories

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored accidentally deleted _LIST_ITEM_RE regex constant**
- **Found during:** Task 2 (Swap inline for import)
- **Issue:** When deleting the INGESTOR_SYSTEM block and its surrounding section comment, the `_LIST_ITEM_RE = re.compile(r"^[ \t]+- ")` regex constant that followed the logger line was also deleted. This constant is used in `_parse_ingestor_response()` on line 133 — deletion would cause NameError at runtime.
- **Fix:** Re-added `_LIST_ITEM_RE = re.compile(r"^[ \t]+- ")` immediately after logger initialization, in its original position.
- **Files modified:** agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py
- **Verification:** All 12 ingest-related tests pass
- **Committed in:** fae1168 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Auto-fix was essential for correctness. Without _LIST_ITEM_RE, the YAML frontmatter parser in _parse_ingestor_response() would fail with NameError on every ingest call. No scope creep.

## Issues Encountered

- Token budget constraint (< 5000 chars) was tight given 3636 chars of shared fragments. Required 7 iterations to trim role-local prose to fit. The budget constraint is a planning approximation — the fragments are canonical and cannot be trimmed. Future plans should account for this when specifying budgets with large shared fragments.

## Known Stubs

None - INGESTOR_SYSTEM is a complete string constant; all sections contain substantive content adapted from the canonical source.

## Threat Flags

None - no new network endpoints, auth paths, or trust boundaries introduced. Prompt assembly is immutable at import time (T-06-09 mitigated by snapshot test; T-06-10 mitigated by acceptance criteria assertions).

## Next Phase Readiness

- PORT-03 complete; INGESTOR_SYSTEM ready for divergence check wiring in 06-08 (ING-003 page-type routing check)
- commands/ingest.py call site unchanged; behavior identical to pre-port
- Snapshot frozen; any drift in fragments or role-local sections will be caught by test_ingestor_system_snapshot

---
*Phase: 06-prompt-content-port-divergence-eval*
*Completed: 2026-05-15*
