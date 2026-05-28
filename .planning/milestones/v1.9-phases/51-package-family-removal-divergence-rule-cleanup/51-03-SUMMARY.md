---
phase: 51-package-family-removal-divergence-rule-cleanup
plan: 03
subsystem: eval-harness
tags: [cleanup, divergence, librarian, baseline]
requires: [51-02]
provides:
  - "librarian divergence registry without LIB-003 (slug-only wikilink check)"
  - "divergence baseline JSON consistent with post-deletion registry"
affects:
  - packages/eval-harness/src/eval_harness/divergence/librarian.py
  - packages/eval-harness/tests/test_divergence_checks.py
  - packages/eval-harness/tests/test_divergence_baseline.py
  - packages/eval-harness/tests/test_two_gate_scorer.py
  - packages/eval-harness/baselines/divergence-librarian.json
tech-stack:
  added: []
  patterns: []
key-files:
  created: []
  modified:
    - packages/eval-harness/src/eval_harness/divergence/librarian.py
    - packages/eval-harness/tests/test_divergence_checks.py
    - packages/eval-harness/tests/test_divergence_baseline.py
    - packages/eval-harness/tests/test_two_gate_scorer.py
    - packages/eval-harness/baselines/divergence-librarian.json
decisions:
  - "Baseline regeneration: Path B (hand-edit) — no AWS creds in worktree env, per D-05 final clause and RESEARCH.md Pitfall 2 (solo-dev fallback)."
  - "SYN-002 in synthesizer.py (parallel function with `'/' not in slug` logic) retained per RESEARCH.md Pitfall 1 — scope of CLEANUP-01 is librarian role only."
metrics:
  duration_minutes: 8
  tasks_completed: 2
  files_modified: 5
  completed_date: 2026-05-28
---

# Phase 51 Plan 03: Eval-harness Divergence Rule Cleanup Summary

Removed the LIB-003 slug-only-wikilink divergence check from the librarian role end-to-end (regex + function + registry entry + tests + baseline JSON), leaving SYN-002's parallel synthesizer-role check untouched.

## What Changed

**`packages/eval-harness/src/eval_harness/divergence/librarian.py` (commit `f9e0fbd`):**
- Deleted the `_SLUG_ONLY_RE = re.compile(r"^[A-Z][A-Za-z]+$")` regex (was line 53).
- Deleted the `_check_no_slug_only_wikilinks` function (was lines 85-93).
- Removed the `DivergenceCheck(id="LIB-003-no-slug-only-wikilinks", ...)` entry from `LIBRARIAN_CHECKS`. LIB-001, LIB-002, LIB-004 are unchanged.

**Test fixtures (commit `cb90968`):**
- `tests/test_divergence_checks.py`: removed `test_lib003_passes_with_path_wikilink` and `test_lib003_fails_on_slug_only_wikilink`.
- `tests/test_divergence_baseline.py`: removed the `LIB-003-no-slug-only-wikilinks` entry from the `_make_results` helper dict.
- `tests/test_two_gate_scorer.py`: removed `LIB-003-no-slug-only-wikilinks` entries from the `heavy_failures` and `clean_results` dicts in `test_two_gate_librarian_divergence_fail` and `test_two_gate_librarian_quality_fail`. No numeric row-count assertions depended on the dict shape, so no further updates were needed.

**Baseline JSON (commit `cb90968`):**
- `baselines/divergence-librarian.json`: removed the `LIB-003-no-slug-only-wikilinks` block from `checks`. Updated `recorded_at` to `2026-05-28T03:18:18.841160+00:00` and `agent_commit` to `f9e0fbd` (the librarian.py-cleanup commit).

## Baseline Regeneration Path Selection

**Path B: hand-edit, AWS creds absent.**

The executor environment has no `AWS_ACCESS_KEY_ID` and no `AWS_PROFILE` exported, so Path A (live Bedrock regeneration via `GRAPH_WIKI_RUN_EVAL=1 pytest ... --accept-divergence-baseline`) was not runnable. D-05's final clause and RESEARCH.md Pitfall 2 explicitly allow hand-editing for the solo-dev / no-creds case. The hand-edit was a one-row deletion plus metadata bump; the resulting JSON parses cleanly and the regression-check tests (which exercise the `load_baseline`/`write_baseline`/`check_regression` pure code paths against `tmp_path` fixtures) pass green.

## SYN-002 Preservation (RESEARCH.md Pitfall 1)

`packages/eval-harness/src/eval_harness/divergence/synthesizer.py` was NOT modified. It defines a structurally separate `_check_no_slug_only_wikilinks` function that uses different logic (`"/" not in slug`, line 55) and registers SYN-002 in `SYNTHESIZER_CHECKS`. Per the plan and RESEARCH.md, deleting it would break `test_syn002_fails_on_lowercase_and_hyphenated_slug_only_wikilinks` and `test_syn002_passes_on_path_prefixed_wikilink` in `test_divergence_checks.py`. Grep confirms 2 hits in synthesizer.py post-cleanup (function def + registry entry).

## Verification

- `grep -c "_SLUG_ONLY_RE\|_check_no_slug_only_wikilinks\|LIB-003" packages/eval-harness/src/eval_harness/divergence/librarian.py` → **0** (G2 librarian.py clean).
- `grep -rn "_SLUG_ONLY_RE\|LIB-003" packages/eval-harness/` → **zero hits** (G2 phase-level grep gate).
- `grep -c "_check_no_slug_only_wikilinks" packages/eval-harness/src/eval_harness/divergence/synthesizer.py` → **2** (SYN-002 retained).
- `python -c "from eval_harness.divergence.librarian import LIBRARIAN_CHECKS; print([c.id for c in LIBRARIAN_CHECKS])"` → `['LIB-001-wikilink-resolves', 'LIB-002-citation-present', 'LIB-004-code-path-format']`.
- `python -c "import json; json.load(open('packages/eval-harness/baselines/divergence-librarian.json'))"` → parses; keys are LIB-001, LIB-002, LIB-004, LIB-JUDGE.
- `pytest packages/eval-harness/tests/test_divergence_checks.py packages/eval-harness/tests/test_divergence_baseline.py packages/eval-harness/tests/test_two_gate_scorer.py -x` → **56 passed**.
- `pytest packages/eval-harness/tests/ -x` → **163 passed, 22 skipped** (skips are `GRAPH_WIKI_RUN_EVAL=1`-gated live-eval tests — unrelated to this change).

## Deviations from Plan

None — both tasks executed exactly as written. Path B (hand-edit) for the baseline was anticipated by the plan as the no-creds fallback; selection is recorded above per acceptance criteria.

## Commits

| Task | Commit | Description |
| ---- | ------ | ----------- |
| 51-03-01 | `f9e0fbd` | refactor(51-03): remove LIB-003 slug-only wikilink check from librarian |
| 51-03-02 | `cb90968` | test(51-03): drop LIB-003 from divergence tests and baseline |

## Self-Check: PASSED

- File `packages/eval-harness/src/eval_harness/divergence/librarian.py`: FOUND, LIB-003 references confirmed absent.
- File `packages/eval-harness/tests/test_divergence_checks.py`: FOUND, LIB-003 test cases confirmed absent.
- File `packages/eval-harness/tests/test_divergence_baseline.py`: FOUND, LIB-003 helper key confirmed absent.
- File `packages/eval-harness/tests/test_two_gate_scorer.py`: FOUND, LIB-003 dict entries confirmed absent.
- File `packages/eval-harness/baselines/divergence-librarian.json`: FOUND, LIB-003 block confirmed absent, JSON parses.
- Commit `f9e0fbd`: FOUND in `git log`.
- Commit `cb90968`: FOUND in `git log`.
