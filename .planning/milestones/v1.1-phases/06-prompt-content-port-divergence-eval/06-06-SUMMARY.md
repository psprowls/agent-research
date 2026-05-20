---
phase: 06-prompt-content-port-divergence-eval
plan: "06"
subsystem: graph-wiki-agent/prompts
tags: [prompt-port, linter, lint-command, three-group-fanout, PORT-04]
dependency_graph:
  requires: [06-03]
  provides: [prompts/linter.py, LINTER_PAGE_QUALITY_SYSTEM, LINTER_ADR_CHAIN_SYSTEM, LINTER_STALE_CLAIMS_SYSTEM]
  affects: [commands/lint.py]
tech_stack:
  added: []
  patterns:
    - join-based prompt composition (import-time, no runtime templating)
    - syrupy snapshot tests for composed prompt strings
key_files:
  created:
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/linter.py
    - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
decisions:
  - "LINT_PRIORITY_ORDER defined as linter-only local constant (not a shared fragment) per PATTERNS.md — the prioritization rule is linter-specific"
  - "Each group prompt targets <3000 chars (all three within budget: 2469, 2058, 2116 chars)"
  - "LINTER_PAGE_QUALITY_SYSTEM expands prior 5-bullet version to 9 canonical semantic categories from linter.md Pass 2"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-15"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 1
---

# Phase 06 Plan 06: Linter Prompt Port Summary

**One-liner:** 3-group linter system prompts composed from IRON_RULES + linter-local rules, expanding canonical 9-category semantic coverage with report-only invariant in all 3 groups.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Create prompts/linter.py with 3 composed group prompts | d07f016 | prompts/linter.py, tests/prompts/__snapshots__/ |
| 2 | Swap inline LINTER_*_SYSTEM constants for imports in commands/lint.py | 6117919 | commands/lint.py |

## What Was Built

### prompts/linter.py

New module exporting exactly 3 constants built at import time via `"\n\n".join([...])`:

- **`LINTER_PAGE_QUALITY_SYSTEM`** (2469 chars): Covers all 9 canonical semantic check categories from linter.md Pass 2 — vague summaries, missing frontmatter, inconsistent terminology, missing wikilinks, orphaned pages, dead wikilinks, stale claims, missing ADRs for major decisions, missing index entries. Expands the prior 5-bullet version.

- **`LINTER_ADR_CHAIN_SYSTEM`** (2058 chars): Addresses ADR-chain health — broken supersedes references, unsuperseded superseded ADRs, deprecated-without-reason, orphan ADRs, cyclic chains, missing status fields.

- **`LINTER_STALE_CLAIMS_SYSTEM`** (2116 chars): Targets code-drift priority — packages/APIs no longer in code, out-of-date version references, citations to removed source files, factual contradictions, unresolved debt markers.

Each prompt:
- Contains `IRON_RULES` fragment (includes "Iron rules" substring)
- Contains `LINT_PRIORITY_ORDER` ("code drift > contradictions > broken links > orphans > stale > style")
- States the report-only invariant ("Do not include write operations — report only")
- Contains no `CLAUDE_PLUGIN_ROOT`, `/lattice-wiki:`, `lint_wiki.py`, or `graph_analyzer.py` references

### commands/lint.py

Deleted 38 lines of inline triple-quoted constants (3 `LINTER_*_SYSTEM = """\..."""` blocks). Replaced with a 5-line grouped import block. Call site at line ~454 (`semantic_groups` tuple) is unchanged. All 3 constants identity-check as the same object between `commands.lint` and `prompts.linter`.

### Snapshot tests

3 syrupy snapshots recorded on first run in `tests/prompts/__snapshots__/test_prompt_snapshots.ambr`. All 3 pass on subsequent runs without `--snapshot-update`.

## Verification Results

- Import check: `LINTER_PAGE_QUALITY_SYSTEM`, `LINTER_ADR_CHAIN_SYSTEM`, `LINTER_STALE_CLAIMS_SYSTEM` importable from both `prompts.linter` and `commands.lint`
- Identity check: all 3 `commands.lint.LINTER_X is prompts.linter.LINTER_X` pass
- No inline definitions remain in `commands/lint.py` (grep confirms)
- All 3 snapshot tests pass
- All 19 lint-related tests pass (no regressions)
- All prompt lengths within budget (< 3000 chars each)

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The 3 composed prompt strings are immutable at import time. The `noqa: F401` comment on the import block prevents linters from flagging the re-exports as unused — this is intentional and matches the pattern in `commands/lint.py`'s public API docstring.

## Self-Check

- [x] `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/linter.py` exists
- [x] `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` exists (with 3 linter snapshots)
- [x] Commit d07f016 exists in git log
- [x] Commit 6117919 exists in git log
- [x] No inline LINTER_*_SYSTEM definitions in commands/lint.py

## Self-Check: PASSED
