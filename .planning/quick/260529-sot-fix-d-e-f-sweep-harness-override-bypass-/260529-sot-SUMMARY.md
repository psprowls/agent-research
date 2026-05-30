---
phase: quick-260529-sot
plan: 01
subsystem: eval-harness + graph-wiki-agent commands
tags: [sweep-harness, model-override, gate-1, divergence, judge-scores, fix-d, fix-e, fix-f]
requires:
  - model_adapter.make_llm(role, model_override=...)  # already existed
  - eval_harness.divergence.metric.check_regression
  - eval_harness.two_gate.score_two_gate
  - eval_harness.sweep.run_full_matrix
provides:
  - "All 6 model-override branches route through make_llm -> guarded LLM"
  - "Rate-based Gate 1 regression check"
  - "Empty-output divergence disqualification"
  - "SweepResult.judge_scores populated with role-appropriate quality signal"
affects:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/{query,ingest,lint,scan}.py
  - packages/eval-harness/src/eval_harness/{divergence/metric,two_gate,sweep}.py
key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - agents/graph-wiki-agent/tests/test_command_overrides.py
    - packages/eval-harness/src/eval_harness/divergence/metric.py
    - packages/eval-harness/src/eval_harness/two_gate.py
    - packages/eval-harness/src/eval_harness/sweep.py
    - packages/eval-harness/tests/test_divergence_metric.py
    - packages/eval-harness/tests/test_two_gate_scorer.py
    - packages/eval-harness/tests/test_sweep_full_matrix.py
    - agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py
    - agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py
    - agents/graph-wiki-agent/tests/test_query_trace_unit.py
    - agents/graph-wiki-agent/tests/unit/test_query_code_fallback.py
    - agents/graph-wiki-agent/tests/unit/test_query_graph_tools_wiring.py
    - agents/graph-wiki-agent/tests/unit/test_query_result.py
    - agents/graph-wiki-agent/tests/unit/test_scan_graph_integration.py
decisions:
  - "Structural-role quality == divergence-rubric pass-rate (Fix F DESIGN NOTE — Pat confirms at pared-down run)"
metrics:
  duration: ~15 min
  completed: 2026-05-30
---

# Phase quick Plan 260529-sot: Fix D/E/F Sweep-Harness Override Bypass Summary

Three sweep-harness bugs from the 2026-05-29 live run fixed as atomic, TDD-driven commits: candidate models now flow through the guarded LLM adapter (Fix D), Gate 1 compares failure *rates* and disqualifies zero-output candidates (Fix E), and `SweepResult.judge_scores` carries a real role-appropriate quality signal (Fix F). Full offline suite green: **1420 passed**.

## What Was Built

### Fix D — Route 6 model-override branches through `make_llm` (commit `07c709f`)
Each of the 6 if/else override branches in `query.py` (code_reader, librarian, synthesizer), `ingest.py` (ingestor), `lint.py` (linter), and `scan.py` (narrator) constructed a **raw** `ChatBedrockConverse`, bypassing `_GuardedChatBedrockConverse` — so the Fix-B content normalizer and the `AccessDeniedException → BedrockAccessDenied` guard never applied to swept candidates. Each branch collapsed to a single `make_llm(role, model_override=<override_var>)` call. `make_llm` returns the role default when `model_override` is None, so the `else` branch was redundant. All `load_role_config(...)` calls kept (still feed `resolved_*` trace fields). Orphaned `from langchain_aws import ChatBedrockConverse` imports removed from ingest/lint/scan; `query.py` import untouched (still uses `BedrockEmbeddings` + docstring reference).

### Fix E — Rate-based Gate 1 + empty-output disqualification (commit `3dfeae9`)
- `check_regression` (metric.py) now compares failure **rates** (`failures / runs`), not absolute counts. Baselines recorded at runs=4 no longer auto-fail incumbents swept at runs=12 (rate 0.75 == rate 0.75 passes; rate 1.0 fails). Rules with `current_runs == 0` are skipped (no data). Missing-baseline keeps the 0.0-rate floor (`baseline_runs else 0.0`). Soft/`-JUDGE` handling unchanged.
- `score_two_gate` (two_gate.py) guards empty `agent_outputs_by_case` for divergence roles as the *first* check: sets `gate1_passed=None`, `divergence_failures=None`, does NOT call `run_programmatic`. Combined with `panel_mean=None` → existing `both gates None` branch sets `qualified=False`. No other None-vs-False semantics changed.

### Fix F — Populate `SweepResult.judge_scores` with a real quality signal (commit `e9cd8b1`)
`quality_mean` was a `has_citation` proxy (0.000 for structural roles) because `judge_scores` was never assigned. Two new helpers in `sweep.py`, wired into `run_full_matrix`'s second loop:
- **Judge-able roles (librarian/synthesizer):** `_score_and_writeback_judgeable` scores each ok run **once** via `panel_score`, writes the full panel dict onto `r.judge_scores`, and means the per-run `panel["mean"]` values. Eliminates the old double-`panel_score` call (the prior `_panel_mean_for_candidate` discarded per-run scores). Guards mirrored exactly: `GRAPH_WIKI_RUN_JUDGES` set, skip non-ok/empty answers, skip cases with no `expected_answer`.
- **Structural roles (scanner/linter/ingestor/code_reader):** `_writeback_structural_quality` reuses the already-constructed per-role `DivergenceMetric`, runs `run_programmatic` on each ok output, and sets `r.judge_scores = {"mean": pass_rate}` where `pass_rate = 1 - total_failures/total_runs`.
- Judges-off path unchanged (`judge_scores` stays None; `render_role_doc` fallback to has_citation proxy untouched). `_panel_mean_for_candidate` left in place (callable) but no longer on the writeback path. The cosmetic `divergence_failures=None` hardcode at the `render_role_doc` call site was left as-is (out of scope per plan).

## Fix F DESIGN NOTE (Pat to confirm at the pared-down-run checkpoint)

**For structural roles, "quality" == divergence-rubric pass-rate.** This intentionally couples the structural-role quality signal to the *same* checks Gate 1 uses (the divergence rubric). A candidate's structural `quality_mean` is therefore `1 - (failed rule checks / total rule checks)` averaged over its ok outputs. **If the pared-down run shows this does not discriminate sensibly between candidates, that is the explicit discuss-point before the full re-run** — e.g. if all structural candidates cluster at the same pass-rate, the signal is too coarse and an alternative (separate structural quality rubric, or a different aggregation) should be considered.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Widen `make_llm` test fakes to accept `model_override` kwarg**
- **Found during:** Final full-offline-suite gate (after Task 3).
- **Issue:** Fix D made every override branch call `make_llm(role, model_override=...)`. 27 pre-existing tests across 7 files stubbed `make_llm` with a single positional `role` parameter (`lambda role:` / `def _llm_for(role: str):`), raising `TypeError: got an unexpected keyword argument 'model_override'`. Directly caused by Task 1's contract change (in-scope).
- **Fix:** Widened each fake's signature to `(role, *, model_override=None)`. No behavioral assertions changed.
- **Files modified:** test_scan_entity_integration.py, test_scan_graph_end_to_end.py, test_query_trace_unit.py, test_query_code_fallback.py, test_query_graph_tools_wiring.py, test_query_result.py, test_scan_graph_integration.py
- **Commit:** `0798b69` (Fix D follow-up)

### Implementation notes
- Task 3 used the plan's stated preference: **direct unit tests of the new writeback helpers** (`_score_and_writeback_judgeable`, `_writeback_structural_quality`) rather than a full offline `run_full_matrix` drive, which would have been fragile. The existing q8r `run_full_matrix` wiring test still passes unchanged.

## Verification

Per-task verify gates all green. Final orchestrator gate:
```
uv run pytest -q -k "not eval"
→ 1420 passed, 23 skipped, 195 deselected, 2 xfailed
```

## Commits

| Task | Fix | Commit | Subject |
|------|-----|--------|---------|
| 1 | D | `07c709f` | route 6 model-override branches through make_llm |
| — | D follow-up | `0798b69` | widen make_llm test fakes to accept model_override |
| 2 | E | `3dfeae9` | rate-based Gate 1 + empty-output disqualification |
| 3 | F | `e9cd8b1` | populate SweepResult.judge_scores with real quality signal |

## Self-Check: PASSED

- All 4 commits found in `git log`.
- All modified source files present and edited.
- Full offline suite green (1420 passed, 0 failed).
