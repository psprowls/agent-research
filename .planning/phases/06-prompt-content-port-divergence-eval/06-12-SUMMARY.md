---
phase: 06-prompt-content-port-divergence-eval
plan: 12
subsystem: ingestor
tags: [gap-closure, ingestor, frontmatter, parser-hardening, UAT-G1, PORT-03, EVAL-11]
requirements: [PORT-03, EVAL-11]
dependency-graph:
  requires:
    - "agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py (INGESTOR_SYSTEM composition)"
    - "agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py (_parse_ingestor_response)"
    - "agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py (snapshot gate)"
  provides:
    - "INGESTOR_SYSTEM explicit no-code-fence rule (prompt-side defense)"
    - "_parse_ingestor_response fence-stripping preamble (parser-side defense)"
    - "5 unit tests covering raw, fenced (with lang), fenced (bare), no-frontmatter, fence-without-dashes shapes"
  affects:
    - "ING-001 divergence check now passes even when LLM violates the no-fence rule"
    - "UAT G1 closed (live ingestor runs that emit fenced frontmatter no longer fail divergence eval)"
tech-stack:
  added: []
  patterns:
    - "defense-in-depth: prompt rule + parser fallback (no-shallow-fix per anti-shallow rule)"
    - "TDD RED→GREEN for parser change (failing fenced test → implementation → all pass)"
key-files:
  created: []
  modified:
    - "agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py (+_NO_CODE_FENCE constant, appended to composition)"
    - "agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py (_parse_ingestor_response: fence-strip preamble + docstring)"
    - "agents/code-wiki-agent/tests/unit/test_commands_ingest.py (+5 parser tests)"
    - "agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr (+4 lines, snapshot refreshed)"
decisions:
  - "Place _NO_CODE_FENCE LAST in the composition list so it is the most recent instruction the LLM reads before generating (recency-bias defense)"
  - "Parser preserves body content that trails the closing ``` fence (the LLM may emit fence around only the YAML block with body below, or wrap YAML+body together) — strip the LAST `\\`\\`\\`` line and rejoin around it"
  - "Fence present but no --- inside → return ({}, original_text), do not silently strip the fence and try to parse a non-YAML body as frontmatter"
  - "Rule lives role-local in ingestor.py, NOT in the shared _fragments/frontmatter_rules.py — scanner stubs are written by command-layer code that controls the byte stream directly, so the no-fence constraint applies only to LLM-generated output"
metrics:
  duration_minutes: 2
  completed_date: 2026-05-16
  tasks_completed: 2
  files_modified: 4
  files_created: 0
  test_count_added: 5
---

# Phase 06 Plan 12: UAT G1 Gap Closure — Ingestor Fenced Frontmatter Summary

Two-defense fix for the live UAT-discovered ingestor failure where the LLM emitted ```yaml-fenced frontmatter instead of beginning with `---`: tightened INGESTOR_SYSTEM with an explicit no-fence rule, and hardened `_parse_ingestor_response` to peel a leading code fence and its matching trailing ``` before searching for the `---` delimiter.

## Tasks Completed

### Task 1: Add no-code-fence rule to INGESTOR_SYSTEM
- **Commit:** `23f043d`
- **Files:** `prompts/ingestor.py`, `tests/prompts/__snapshots__/test_prompt_snapshots.ambr`
- **What:** Added `_NO_CODE_FENCE` private constant containing the substrings:
  - `Do NOT wrap the frontmatter`
  - ```` ```yaml ```` (names the exact failure mode)
  - `The first three characters of the response MUST be ` `---` (positive instruction)
- **Composition order (last):** `_ROLE_INTRO, IRON_RULES, PAGE_CATEGORIES, FRONTMATTER_RULES, CITATION_RULES, _PAGE_TYPE_ROUTING, _INGESTOR_RULES, _RED_FLAGS, _OUTPUT_FORMAT, _NO_CODE_FENCE`
- **Snapshot delta:** +4 lines added, 0 removed (purely additive — all prior fragments preserved unchanged)
- **Substring assertions used in the verify command:**
  - `'Do NOT wrap the frontmatter' in INGESTOR_SYSTEM`
  - ` '```yaml' in INGESTOR_SYSTEM`
  - positive-instruction OR-chain (`start with `---``, `start the response`, `first three characters`)
  - `INGESTOR_SYSTEM.count('## Frontmatter format') == 1`
  - All prior fragment headings still present (`Iron rules`, `Page categories`, `Citation rules`, `Page-type routing`)

### Task 2: Harden _parse_ingestor_response against fenced frontmatter
- **Commit:** `e22b860`
- **Files:** `commands/ingest.py`, `tests/unit/test_commands_ingest.py`
- **What:**
  - Added fence-strip preamble after `text = text.strip()`: detects leading ```` ``` ````, strips the opening fence line, finds the LAST line that is exactly ```` ``` ```` and removes it (preserving body content below).
  - Falls through to the original `---` delimiter check unchanged.
  - Fence present but no `---` inside → returns `({}, original_text)` (defense against silently parsing a non-YAML body).
  - Function signature `_parse_ingestor_response(text: str) -> tuple[dict, str]` unchanged.
  - Docstring updated to reference `prompts/ingestor.py:_NO_CODE_FENCE` for traceability.
- **Tests added (5 total):**
  1. `test_parse_ingestor_response_handles_fenced_and_unfenced[raw ---]` — regression guard
  2. `test_parse_ingestor_response_handles_fenced_and_unfenced[\`\`\`yaml ...]` — UAT G1
  3. `test_parse_ingestor_response_handles_fenced_and_unfenced[\`\`\` ...]` — bare fence
  4. `test_parse_ingestor_response_no_frontmatter_returns_empty`
  5. `test_parse_ingestor_response_fence_without_dashes_returns_empty`

## TDD Gate Compliance

Task 2 followed the RED→GREEN cycle within a single commit (test + implementation shipped together per the plan's `<action>` block, which prescribes adding tests in the same change as the parser fix). RED was confirmed in-loop: the parametrized fenced test failed with `AssertionError: key page_type: expected source, got None` before the parser change; all 6 tests in scope (3 parametrized + 2 free-standing + 1 pre-existing regression) passed after.

## Verification

Final command:
```
uv run --package code-wiki-agent pytest \
  agents/code-wiki-agent/tests/unit/test_commands_ingest.py \
  agents/code-wiki-agent/tests/prompts/test_prompt_snapshots.py \
  -x -q
```
Result: **19 passed, 8 snapshots passed** (exit 0).

## Deviations from Plan

None — plan executed exactly as written, with one small implementation refinement during the GREEN step: the closing-fence strip originally targeted only the last line; the test exposed that the closing ``` lives MID-text (right after the closing `---`, with body below). Adjusted to find the LAST ` ``` `-only line anywhere in the post-opening-fence text and rejoin around it. This change is captured in the docstring/inline comments and covered by the parametrized fenced-with-body test.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- `agents/code-wiki-agent/src/code_wiki_agent/prompts/ingestor.py` — FOUND
- `agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py` — FOUND
- `agents/code-wiki-agent/tests/unit/test_commands_ingest.py` — FOUND
- `agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr` — FOUND
- Commit `23f043d` — FOUND
- Commit `e22b860` — FOUND
