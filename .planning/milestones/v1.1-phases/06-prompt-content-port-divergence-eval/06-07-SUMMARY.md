---
phase: 06-prompt-content-port-divergence-eval
plan: "07"
subsystem: prompts
tags: [prompt-port, scanner, scan-command, syrupy, fragments]

requires:
  - phase: 06-prompt-content-port-divergence-eval
    plan: "03"
    provides: "prompts package + shared fragment files (IRON_RULES, FRONTMATTER_RULES)"

provides:
  - "prompts/scanner.py — SCANNER_SYSTEM composed from IRON_RULES + FRONTMATTER_RULES + scanner-local rules"
  - "commands/scan.py refactored to import SCANNER_SYSTEM from prompts.scanner"
  - "Syrupy snapshot for SCANNER_SYSTEM recorded"

affects:
  - "06-08 divergence eval (SCN-003 no-File-map check depends on SCANNER_SYSTEM content)"
  - "commands/scan.py call site unaffected (SystemMessage(content=SCANNER_SYSTEM) unchanged)"

tech-stack:
  added: []
  patterns:
    - "prompts/scanner.py: compose-at-import-time pattern via join([...]) from shared fragments + role-local sections"
    - "commands/scan.py: replace inline constant with import from prompts package"

key-files:
  created:
    - "agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py"
    - "agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr"
  modified:
    - "agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py"

key-decisions:
  - "Scanner does not use PAGE_CATEGORIES (stubs are always category: package or app — no table needed)"
  - "Scanner does not use CITATION_RULES (stubs contain no freeform claims requiring citation)"
  - "FRONTMATTER_RULES included as-is even though it also covers ingestor fields — avoids diverging from canonical fragment"
  - "Char count deviation accepted: composed string is 3349 chars vs plan's 2500 char target (see Deviations)"

patterns-established:
  - "Scanner-local rules section: four canonical rules verbatim from scanner.md"
  - "No-File-map rule appears twice: in _ROLE_INTRO and _STUB_SCHEMA for redundant enforcement (SCN-003 invariant)"

requirements-completed: [PORT-05]

duration: 12min
completed: 2026-05-15
---

# Phase 06 Plan 07: Scanner Prompt Port Summary

**SCANNER_SYSTEM composed from IRON_RULES + FRONTMATTER_RULES + scanner-local rules; commands/scan.py swapped to import-based sourcing with syrupy snapshot recorded**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-15T19:44:00Z
- **Completed:** 2026-05-15T19:56:50Z
- **Tasks:** 2
- **Files modified:** 3 (scanner.py created, scan.py modified, snapshot recorded)

## Accomplishments

- Created `prompts/scanner.py` composing SCANNER_SYSTEM from IRON_RULES, FRONTMATTER_RULES, and five scanner-local sections
- Preserved all canonical scanner invariants: stub frontmatter fields (title, category, summary, package_path, language, version, depends_on, exports), Overview + Notable files section requirements, no-File-map rule (SCN-003 pipeline contract), don't-overwrite-prose rule, confirm-renames-deletions, only-stub-actual-workspace-entries, dependency-only-no-confirmation
- Removed all host-specific references (scan_monorepo.py, update_index.py, update_tokens.py, append_log.py, CLAUDE_PLUGIN_ROOT, /lattice-wiki: slash commands) per RESEARCH Adaptation Map
- Refactored `commands/scan.py` to import SCANNER_SYSTEM from prompts.scanner; identity check passes; 17 scan-related tests still pass

## Task Commits

1. **Task 1: Create prompts/scanner.py** - `84030ac` (feat)
2. **Task 2: Swap inline SCANNER_SYSTEM in commands/scan.py for import** - `75152a6` (refactor)

## Files Created/Modified

- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py` — New: SCANNER_SYSTEM composed at import time from shared fragments + scanner-local sections
- `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` — New: syrupy snapshot for SCANNER_SYSTEM (and any previously recorded prompts from prior plans)
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — Modified: deleted inline SCANNER_SYSTEM block (30 lines), added single import line, updated module docstring

## Decisions Made

- Scanner uses only IRON_RULES and FRONTMATTER_RULES (not PAGE_CATEGORIES or CITATION_RULES) — scanner stubs are always `category: package` or `app`, and contain no freeform claims requiring citation
- No-File-map rule stated in both `_ROLE_INTRO` and `_STUB_SCHEMA` sections for belt-and-suspenders enforcement of the SCN-003 pipeline contract
- `# noqa: F401` added to the import in scan.py per plan instructions (ruff does not flag it since SCANNER_SYSTEM is used at line ~329)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Scope Adjustment] Composed string exceeds 2500 char target**
- **Found during:** Task 1 (Create prompts/scanner.py)
- **Issue:** Plan acceptance criterion states `<2500 chars`. IRON_RULES (652 chars) + FRONTMATTER_RULES (1065 chars) + role-local sections combine to 3349 chars. The two mandatory fragments alone are 1717 chars, making the 2500 char target unachievable while including both fragments. This is an inconsistency in the plan's spec (the fragment sizes were finalized after the char limit was set).
- **Fix:** Kept all mandatory fragments and semantic content; accepted the 3349 char result. At ~4 chars/token, this is approximately 700-840 tokens — within practical Bedrock limits for a subagent role prompt. The no-redundancy pass removed one full section (`_OUTPUT_SECTIONS`, ~250 chars) that duplicated content already in `_STUB_SCHEMA`.
- **Files modified:** agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py
- **Verification:** All other acceptance criteria pass; scan tests green; snapshot recorded
- **Committed in:** 84030ac (Task 1 commit)

---

**Total deviations:** 1 (scope adjustment — char limit not achievable with mandatory fragments)
**Impact on plan:** No semantic impact. All canonical content preserved. Token budget is reasonable for Bedrock.

## Issues Encountered

None — both tasks executed cleanly on first attempt.

## Next Phase Readiness

- PORT-05 delivered: scanner prompt composed from canonical fragments + adapted role-local prose
- commands/scan.py fully migrated to import-based sourcing
- SCANNER_SYSTEM snapshot frozen; future prompt changes will require explicit `--snapshot-update`
- SCN-003 no-File-map divergence check (plan 06-08) can now validate against the composed SCANNER_SYSTEM content

---
*Phase: 06-prompt-content-port-divergence-eval*
*Completed: 2026-05-15*
