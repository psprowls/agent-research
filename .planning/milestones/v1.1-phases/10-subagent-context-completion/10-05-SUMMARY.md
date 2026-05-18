---
phase: 10-subagent-context-completion
plan: 05
subsystem: prompts
tags: [prompts, wiring, refactor, project-context, fragments]
dependency_graph:
  requires:
    - 10-02 (ARCHITECTURE_OVERVIEW + LOG_FORMAT fragments)
    - 10-03 (STYLE_RULES + CLAUDE_MD_DISAMBIGUATION fragments)
    - 10-04 (project_context module)
  provides:
    - build_scanner_system(project_context) builder + SCANNER_SYSTEM constant
    - build_ingestor_system(project_context) builder + INGESTOR_SYSTEM constant
    - build_linter_page_quality_system(project_context) builder + constant
    - build_linter_adr_chain_system(project_context) builder + constant
    - build_linter_stale_claims_system(project_context) builder + constant
    - build_librarian_system() builder + LIBRARIAN_SYSTEM constant
  affects:
    - 10-06 (command-side wiring will call the new builders with real context)
    - 10-07 (will add project_context variant snapshot tests on top of these builders)
tech_stack:
  added: []
  patterns:
    - "build_X_system(project_context: str = '') -> str + X_SYSTEM = build_X_system() backward-compat alias"
    - "Position-1 insertion: parts.insert(1, project_context) — between role intro and IRON_RULES"
key_files:
  created: []
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/scanner.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/linter.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/librarian.py
    - agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
decisions:
  - "Librarian builder has no project_context kwarg (per CONTEXT.md §Wiring) — it only gains STYLE_RULES"
  - "_NO_CODE_FENCE remains the LAST fragment in INGESTOR_SYSTEM (UAT G1 markdown-fence contract preserved)"
  - "Linter group prompts collapse the three byte-identical output-format blocks into a single shared _OUTPUT_FORMAT_GENERIC constant"
  - "Position-1 insertion (after role intro, before IRON_RULES) chosen so project_context arrives BEFORE the iron rules govern the agent's behavior"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-17T20:13:42Z"
  tasks_completed: 3
  files_changed: 5
  commits: 3
---

# Phase 10 Plan 05: Wire shared fragments into subagent prompt builders Summary

Converted the four subagent prompt modules (scanner, ingestor, linter ×3 groups, librarian) from module-level string constants to `build_X_system(project_context: str = "")` functions, wiring the four new shared fragments (`ARCHITECTURE_OVERVIEW`, `STYLE_RULES`, `LOG_FORMAT`, `CLAUDE_MD_DISAMBIGUATION`) per the CONTEXT.md §Wiring matrix while preserving all backward-compatible module constants.

## What changed

| File | Change |
|------|--------|
| `prompts/scanner.py` | Added `build_scanner_system(project_context)`; wired `ARCHITECTURE_OVERVIEW` + `LOG_FORMAT`. `SCANNER_SYSTEM = build_scanner_system()` retained. |
| `prompts/ingestor.py` | Added `build_ingestor_system(project_context)`; wired `ARCHITECTURE_OVERVIEW` + `STYLE_RULES` + `CLAUDE_MD_DISAMBIGUATION` + `LOG_FORMAT`. `_NO_CODE_FENCE` preserved as final fragment. `INGESTOR_SYSTEM = build_ingestor_system()` retained. |
| `prompts/linter.py` | Extracted role-intro / checks blocks into module-private constants; added three `build_linter_*_system(project_context)` builders; wired `LOG_FORMAT` + `CLAUDE_MD_DISAMBIGUATION`; collapsed the three duplicate output-format blocks into a shared `_OUTPUT_FORMAT_GENERIC`. Three backward-compat constants retained. |
| `prompts/librarian.py` | Added `build_librarian_system()` (no `project_context` kwarg by design); wired `STYLE_RULES`. `LIBRARIAN_SYSTEM = build_librarian_system()` retained. |
| `tests/prompts/__snapshots__/test_prompt_snapshots.ambr` | Regenerated six subagent snapshots (scanner, ingestor, linter ×3, librarian). Synthesizer and code_reader snapshots unchanged. |

## Composition per CONTEXT.md §Wiring matrix

- **scanner**: `[_ROLE_INTRO, IRON_RULES, ARCHITECTURE_OVERVIEW, FRONTMATTER_RULES, LOG_FORMAT, _STUB_SCHEMA, _SCANNER_RULES, _RED_FLAGS, _TOKEN_BUDGET]`
- **ingestor**: `[_ROLE_INTRO, IRON_RULES, ARCHITECTURE_OVERVIEW, PAGE_CATEGORIES, FRONTMATTER_RULES, CITATION_RULES, STYLE_RULES, CLAUDE_MD_DISAMBIGUATION, LOG_FORMAT, _PAGE_TYPE_ROUTING, _INGESTOR_RULES, _RED_FLAGS, _OUTPUT_FORMAT, _NO_CODE_FENCE]`
- **linter (×3)**: `[<group_role_intro>, IRON_RULES, LINT_PRIORITY_ORDER, LOG_FORMAT, CLAUDE_MD_DISAMBIGUATION, <group_checks>, _OUTPUT_FORMAT_GENERIC]`
- **librarian**: `[_ROLE_INTRO, IRON_RULES, PAGE_CATEGORIES, CITATION_RULES, STYLE_RULES, _WORKFLOW, _RED_FLAGS, _OUTPUT_FORMAT]`

When `project_context` is non-empty, it is inserted at index 1 (immediately after the role intro and before `IRON_RULES`) so the project context arrives before any iron-rule behavior governance.

## Tasks executed

| Task | Name | Commit |
|------|------|--------|
| 1 | Refactor scanner.py + ingestor.py to builder functions, add ARCHITECTURE_OVERVIEW / LOG_FORMAT / STYLE_RULES / CLAUDE_MD_DISAMBIGUATION imports per matrix | `1cc94f5` |
| 2 | Refactor linter.py (3 group prompts) + librarian.py to builder functions, add LOG_FORMAT + CLAUDE_MD_DISAMBIGUATION (linter) and STYLE_RULES (librarian) | `01940e0` |
| 3 | Regenerate existing test_prompt_snapshots.py snapshots and run the full snapshot suite | `2d48e0e` |

## Verification

- `pytest agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py agents/code-wiki-agent/tests/prompts/test_provenance.py agents/code-wiki-agent/tests/prompts/test_project_context.py -x` → 14 passed (8 snapshot + 2 provenance + 4 project_context).
- All six backward-compat constants equal their empty-context builder outputs: `SCANNER_SYSTEM == build_scanner_system()`, `INGESTOR_SYSTEM == build_ingestor_system()`, three `LINTER_*_SYSTEM == build_linter_*_system()`, `LIBRARIAN_SYSTEM == build_librarian_system()`.
- Position-1 insertion verified by asserting `'\n\n' + ctx + '\n\n' + IRON_RULES` appears in the rendered prompt for every builder that accepts `project_context`.
- `_NO_CODE_FENCE` is the final fragment of `INGESTOR_SYSTEM` (UAT G1 contract): `INGESTOR_SYSTEM.rstrip().endswith(_NO_CODE_FENCE.rstrip())`.
- Librarian signature has no `project_context` parameter (`inspect.signature(build_librarian_system).parameters` excludes it).

## Scope fences (all held)

- No `pyproject.toml` modifications.
- No `from deepagents` imports added to any prompt module.
- No edits to `synthesizer.py` or `code_reader.py` (out of scope per CONTEXT.md §Phase Boundary).
- No edits under `cores/eval-harness/` or `.planning/phases/06-*/` (Phase-6 divergence baselines untouched).
- No new top-level dependencies.

## Deviations from Plan

The plan's `<verify>` script for Task 1 contained two assertions that were structurally incorrect (not contract failures, just check-script bugs) and had to be substituted with semantically equivalent versions before passing:

**1. [Rule 3 - Verify-script structural bug] Adjusted `_NO_CODE_FENCE`-is-last check**
- **Found during:** Task 1
- **Issue:** Plan's verify asserted `'Frontmatter format (strict)' in INGESTOR_SYSTEM.split('\n\n')[-1]`. But `_NO_CODE_FENCE` itself contains `\n\n`, so splitting by `\n\n` puts the heading in the second-to-last block, not the last. The actual semantic contract — that `_NO_CODE_FENCE` is the FINAL composed fragment — was satisfied; only the assertion's structural form was wrong.
- **Fix:** Asserted the semantic contract directly: `INGESTOR_SYSTEM.rstrip().endswith(_NO_CODE_FENCE.rstrip())`. The composition order in `build_ingestor_system` places `_NO_CODE_FENCE` last in the parts list per the L71-76 UAT G1 comment.
- **Files modified:** None (only the verification approach changed; the implementation matches the plan).
- **Commit:** N/A (verify-only adjustment).

**2. [Rule 3 - Verify-script structural bug] Adjusted position-1 insertion check**
- **Found during:** Task 1
- **Issue:** Plan's verify asserted `parts_sc[1] == ctx` where `parts_sc = sc.split('\n\n')`. But `_ROLE_INTRO` constants in `scanner.py` and `ingestor.py` themselves contain `\n\n`, so the role intro spans multiple split blocks and index 1 is a fragment of the role intro, not the inserted context.
- **Fix:** Asserted the semantic contract directly: the rendered prompt contains the substring `'\n\n' + ctx + '\n\n' + IRON_RULES`, proving the context sits between role intro and IRON_RULES at the composition level. (This matches `parts.insert(1, project_context)` in the actual `parts` list, which is the contract.)
- **Files modified:** None.
- **Commit:** N/A (verify-only adjustment).

Both adjustments preserve the intent of the original acceptance criteria. The implementations match the plan's specification verbatim — only the post-hoc checks were rewritten to test the correct strings.

No other deviations. No auth gates. No checkpoints required.

## Self-Check: PASSED

- `agents/code-wiki-agent/src/code_wiki_agent/prompts/scanner.py` exists with `build_scanner_system` and `SCANNER_SYSTEM = build_scanner_system()`.
- `agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py` exists with `build_ingestor_system` and `INGESTOR_SYSTEM = build_ingestor_system()`.
- `agents/code-wiki-agent/src/code_wiki_agent/prompts/linter.py` exists with three `build_linter_*_system` functions and three backward-compat constants.
- `agents/code-wiki-agent/src/code_wiki_agent/prompts/librarian.py` exists with `build_librarian_system()` (no `project_context`) and `LIBRARIAN_SYSTEM = build_librarian_system()`.
- `agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` regenerated and tests pass against it.
- Commits `1cc94f5`, `01940e0`, `2d48e0e` present in git log.
