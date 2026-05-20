---
phase: 19-phase-16-code-review-burndown
plan: 01
subsystem: eval-harness/divergence
tags: [eval-harness, regex, divergence-checks, code-review-burndown]
requires: []
provides:
  - "SYN-002 slug-only check covers lowercase/hyphenated wikilink targets"
  - "CR-003 .graph-wiki/ detection catches inline path references (vault/.graph-wiki/foo)"
  - "CR-001 path:line detection accepts bare-filename citations (pool.py:115)"
affects:
  - packages/eval-harness/src/eval_harness/divergence/synthesizer.py
  - packages/eval-harness/src/eval_harness/divergence/code_reader.py
  - packages/eval-harness/tests/test_divergence_checks.py
tech-stack:
  added: []
  patterns:
    - "string-containment check (`'/' not in slug`) replaces narrow regex"
    - "negative lookbehind tightened to exclude only word/hyphen, not the path separator"
key-files:
  created: []
  modified:
    - packages/eval-harness/src/eval_harness/divergence/synthesizer.py
    - packages/eval-harness/src/eval_harness/divergence/code_reader.py
    - packages/eval-harness/tests/test_divergence_checks.py
decisions:
  - "Followed CONTEXT.md D-01/D-02/D-03 patches verbatim — no re-derivation per phase ground rules"
  - "Invoked D-18 exception: added 6 targeted unit assertions (SYN-002 + 2 regex × 2 cases) — prior coverage was zero, so the silent-pass would have re-accumulated"
  - "Removed `_SLUG_ONLY_RE` constant entirely (no other callers) rather than leaving it dead — matches CLAUDE.md hard-cut philosophy"
metrics:
  duration_minutes: ~6
  tasks_completed: 2
  completed_date: 2026-05-19
---

# Phase 19 Plan 01: Divergence Eval Regex Fixes Summary

Three warning-severity false negatives in `packages/eval-harness/src/eval_harness/divergence/` are closed: lowercase/hyphenated slug-only wikilinks now fail SYN-002, inline `.graph-wiki/` references following a path separator now trip CR-003, and bare-filename `path:line` citations now satisfy CR-001.

## Tasks Completed

| Task | Description | Commit | Files |
| ---- | ----------- | ------ | ----- |
| 1 | D-01 (WR-01): replace `_SLUG_ONLY_RE` in synthesizer.py with `"/" not in target` check | `d805829` | synthesizer.py, test_divergence_checks.py |
| 2 | D-02 (WR-02) + D-03 (WR-03): tighten `_GRAPH_WIKI_PREFIX_RE` lookbehind and drop mandatory `/` from `_PATH_LINE_RE` in code_reader.py | `a98ae95` | code_reader.py, test_divergence_checks.py |

## Changes Made

### D-01 (WR-01) — Synthesizer slug-only check

Replaced the PascalCase-only regex `_SLUG_ONLY_RE = re.compile(r"^[A-Z][A-Za-z0-9]+$")` with a string-containment test on the wikilink target. The slug-only branch in `_check_no_slug_only_wikilinks` now keys off `"/" not in slug`. The constant is gone; `re` is still needed elsewhere in the module so no dead-import removal was required.

Behavior change: `[[Bedrock]]`, `[[bedrock]]`, `[[subagent-pool]]`, `[[foo_bar]]` all fail SYN-002. Any target containing `/` (e.g., `[[wiki/bedrock]]`, `[[packages/foo|alias]]`) takes the pass branch.

### D-02 (WR-02) — `.graph-wiki/` prefix lookbehind

Tightened `_GRAPH_WIKI_PREFIX_RE` lookbehind from `(?<![A-Za-z0-9_/-])` to `(?<![A-Za-z0-9_-])` so inline path references like `vault/.graph-wiki/bm25` now match the forbidden-prefix check (`/` is removed from the exclusion set; word/hyphen characters still excluded to avoid false positives on suffixes like `foo.graph-wiki/`).

### D-03 (WR-03) — `path:line` permissiveness

Relaxed `_PATH_LINE_RE` from `r"`?[A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+\.<ext>:\d+(?:-\d+)?`?"` (mandatory `/` in path) to `r"`?[A-Za-z0-9_./-]*[A-Za-z0-9_-]+\.<ext>:\d+(?:-\d+)?`?"` (per the REVIEW.md suggested patch). Bare-filename citations (`pool.py:115`) now match CR-001 alongside qualified paths.

### Test coverage (D-18 exception)

Pre-fix coverage for synthesizer and code_reader divergence checks was zero in `packages/eval-harness/tests/test_divergence_checks.py` — only librarian, ingestor, linter, and scanner had unit tests. Per the D-18 exception path, six targeted assertions were added to the existing file (no new test file):

- `test_syn002_fails_on_lowercase_and_hyphenated_slug_only_wikilinks` — parametric over four casings.
- `test_syn002_passes_on_path_prefixed_wikilink` — positive control.
- `test_graph_wiki_prefix_re_matches_slash_prefixed_inline_path` — WR-02 positive.
- `test_graph_wiki_prefix_re_still_rejects_identifier_prefixed_match` — WR-02 negative control.
- `test_path_line_re_matches_bare_filename_citation` — WR-03 positive.
- `test_path_line_re_still_matches_qualified_paths` — WR-03 negative control.

## Deviations from Plan

None — all three fixes implemented exactly as CONTEXT.md / 16-REVIEW.md specified. Test additions were the D-18 exception explicitly anticipated in the plan.

One observation (out-of-scope, not modified): `packages/eval-harness/src/eval_harness/divergence/librarian.py:21` still defines its own `_SLUG_ONLY_RE = re.compile(r"^[A-Z][A-Za-z]+$")` for LIB-003. The librarian check has the same PascalCase-only limitation as the pre-fix synthesizer. WR-01 explicitly scopes the fix to the synthesizer; the librarian regex is left alone to honor the plan's "no scope creep onto adjacent code" rule. Logged here for visibility — a future burndown could mirror the fix into librarian.py.

## Authentication Gates

None.

## Verification

- Task 1 gate: `uv run pytest packages/eval-harness/tests/ -m "not integration"` → 160 passed, 22 skipped (was 158 baseline, +2 SYN-002 tests).
- Task 2 gate: `uv run pytest packages/eval-harness/tests/ -m "not integration"` → 164 passed, 22 skipped (+4 regex tests).
- Plan-final gate (success criteria): `uv run pytest packages/eval-harness/tests/ packages/subagent-runtime/tests/ agents/graph-wiki-agent/tests/ -m "not integration"` → **395 passed, 23 skipped, 9 deselected, 19 snapshots passed**. ✓

## Burndown Table Hand-off

Plan 05 (19-REVIEW-BURNDOWN.md) populates the disposition table. Rows for this plan:

| Finding | File | Disposition | Commit |
| ------- | ---- | ----------- | ------ |
| WR-01 | packages/eval-harness/src/eval_harness/divergence/synthesizer.py:19,50-60 | fixed | `d805829` |
| WR-02 | packages/eval-harness/src/eval_harness/divergence/code_reader.py:31,71-82 | fixed | `a98ae95` |
| WR-03 | packages/eval-harness/src/eval_harness/divergence/code_reader.py:21-23,39-53 | fixed | `a98ae95` |

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: packages/eval-harness/src/eval_harness/divergence/synthesizer.py
- FOUND: packages/eval-harness/src/eval_harness/divergence/code_reader.py
- FOUND: packages/eval-harness/tests/test_divergence_checks.py
- FOUND commit: d805829
- FOUND commit: a98ae95
- `grep -n "_SLUG_ONLY_RE" packages/eval-harness/src/eval_harness/divergence/synthesizer.py` returns 0 hits ✓
- `grep -n "/" not in slug` matches at synthesizer.py:55 ✓
- `_GRAPH_WIKI_PREFIX_RE` lookbehind contains `[A-Za-z0-9_-]` (no `/`) ✓
- `_PATH_LINE_RE` no longer has a mandatory interior `/` ✓
