---
phase: quick-260529-pf8
plan: "01"
type: quick
one_liner: "Update 14 stale test assertions to match na9 ground truth: global Haiku ARN, qwen3 0.15/0.60 pricing, structural sweep-candidate invariants replacing retired D-03 tier model"
subsystem: test-suite
tags: [test-update, stale-pins, sweep-candidates, model-adapter, eval-harness]
dependency_graph:
  requires: [260529-na9]
  provides: [green-test-suite]
  affects: []
tech_stack:
  added: []
  patterns: []
key_files:
  modified:
    - packages/eval-harness/tests/test_pricing.py
    - packages/eval-harness/tests/test_models_toml_sweep_candidates.py
    - packages/model-adapter/tests/test_loader.py
    - packages/model-adapter/tests/test_narrator_role.py
    - agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py
decisions:
  - "D-03 tier-to-role candidate frozensets retired; tests now assert structural invariants (non-empty list + Haiku present in every in-scope role)"
metrics:
  duration: "~5 minutes"
  completed_date: "2026-05-29"
  tasks_completed: 2
  files_changed: 5
---

# Quick Task 260529-pf8: Update Stale Config-Pinning Tests After na9 Summary

## What Was Done

The na9 sweep-config refresh (commit 60c8d77) changed three things in `models.toml` and `pricing.py` that caused 14 test failures:

1. **Haiku ARN prefix** changed from `us.` to `global.` inference profile for all Haiku-default roles
2. **qwen3-32b pricing** reconciled from $0.40/$1.60 to $0.15/$0.60 per 1M tokens
3. **sweep_candidates** changed from six uniform 4-entry D-03 tier-locked lists to bespoke per-role lists (lengths: 6/8/6/7/6/6)

This quick task updated the five test files with stale assertions to match the new ground truth. No production/source code was touched.

## Task 1: Mechanical Pin Updates (12 failures)

**Commit: 07c81ea**

Files updated:
- `packages/eval-harness/tests/test_pricing.py` — `test_qwen3_cost`: docstring and `pytest.approx(2.0)` → `pytest.approx(0.75)`
- `packages/model-adapter/tests/test_loader.py` — `HAIKU_ARN` constant: `us.` → `global.` (fixes 7 failures: preflight ARN, access-denied message, domain_proposer, librarian, and 3 workspace-fallback tests)
- `packages/model-adapter/tests/test_narrator_role.py` — `HAIKU_ARN` constant: `us.` → `global.` (fixes 3 narrator failures)
- `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py` — `HAIKU_ARN` constant: `us.` → `global.` (fixes 1 IAM mock failure; live test stayed skipped)

## Task 2: Sweep-Candidate Tests — Structural Invariants (2 failures)

**Commit: 0c6a52f**

File updated: `packages/eval-harness/tests/test_models_toml_sweep_candidates.py`

**Approach — why structural invariants:**
The D-03 tier model assigned roles to one of three tiers (QUALITY/MID/CHEAP_FAST), each with a uniform 4-entry candidate frozenset. The na9 refresh retired this model in favor of bespoke per-role lists driven by model capabilities rather than a fixed tier. Re-pinning the exact new 6/7/8-entry lists would create the same brittleness problem — any future sweep-config change would again break the tests. Instead, the tests now assert properties that must hold regardless of which specific models appear in the lists:

- `test_sweep_candidates_present_for_all_six_roles`: `len(candidates) >= 1` (non-empty) instead of `== 4`
- `test_haiku_present_in_every_in_scope_role`: `global.anthropic.claude-haiku-4-5-20251001-v1:0` in every in-scope role's list (Pat's "always include Haiku" rule — verified true for all 6 roles in current toml)

Removed from the file:
- `QUALITY_ROLES`, `MID_ROLES`, `CHEAP_FAST_ROLES` tuples
- `QUALITY_CANDIDATES`, `MID_CANDIDATES`, `CHEAP_FAST_CANDIDATES` frozensets
- `test_tier_to_role_candidate_map` (replaced by `test_haiku_present_in_every_in_scope_role`)
- Sonnet-4-6, nova-pro, nova-micro spot-checks (model-specific, not structural)

Retained untouched:
- `test_no_sweep_candidates_for_judges`
- `test_all_candidates_have_pricing`
- `test_make_llm_still_works_for_all_roles`
- `test_code_reader_cases_json_loads`

## Deviations from Plan

None — plan executed exactly as written. All 14 failures were confirmed as stale assertions (not real bugs before editing).

## Full Suite Result

```
1580 passed, 45 skipped, 2 xfailed, 7 warnings in 173.85s (0:02:53)
```

**0 failed.** Baseline was 14 failed / 1566 passed; target was 0 failed / 1580 passed — contract met.

## Self-Check: PASSED

- All 5 test files modified: confirmed
- No production source files changed: `git diff --name-only HEAD~2 HEAD` shows only `*/tests/*` paths
- HAIKU_ARN constants: all three files use `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- qwen3 cost assertion: `pytest.approx(0.75)`
- Sweep-candidate tests: structural invariants, D-03 tier lists retired
- Live Bedrock test: remained skipped throughout (no spend)
