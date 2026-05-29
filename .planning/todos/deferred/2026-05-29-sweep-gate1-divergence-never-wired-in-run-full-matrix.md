---
created: 2026-05-29
title: Sweep Gate-1 (divergence) auto-FAILs — run_full_matrix passes divergence_metric_or_none=None
area: eval-harness
origin: 2026-05-29 live cost-frontier sweep — every candidate in every role came back gate1=FAIL / qualified=NO
files:
  - packages/eval-harness/src/eval_harness/sweep.py        # run_full_matrix score_two_gate call (~line 872): divergence_metric_or_none=None, baselines_dir=None hardcoded
  - packages/eval-harness/src/eval_harness/two_gate.py     # score_two_gate (~line 103-105): metric is None -> gate1_passed=False
  - packages/eval-harness/src/eval_harness/divergence/metric.py  # load_baseline / check_regression — the wiring that is never called
  - eval/baselines/                                        # divergence-{role}.json baselines the metric should load
---

## Problem

In the 2026-05-29 live sweep, **Gate 1 (divergence regression) failed for every
candidate in every role** — including Haiku, the incumbent that should pass — so
all 39 cells reported `qualified=NO`. The `divergence_failures` column is `n/a`
everywhere, meaning divergence never actually ran.

Root cause is a hardcoded `None`, not a model or baseline problem. In
`run_full_matrix` (`sweep.py` ~line 872) the per-candidate scoring call is:

```python
outcome = score_two_gate(
    role=role,
    divergence_metric_or_none=None,   # <-- always None
    agent_outputs_by_case=outputs_by_case,
    baselines_dir=None,               # <-- always None
    panel_mean=panel_means.get(candidate),
    default_panel_mean=default_panel_mean,
    threshold=threshold,
)
```

And in `two_gate.py` (~line 103-105):

```python
if divergence_metric_or_none is None:
    # D-07 role with no metric supplied -> cannot run Gate 1
    gate1_passed = False
```

So for every role that has divergence rubrics (all 6 in-scope after Phase 16
SWEEP-FU-02), Gate 1 is structurally guaranteed to fail because the matrix
driver never constructs or passes the divergence metric + baselines_dir.
Net effect: the "qualified" verdict from the sweep is meaningless — the
cost/quality frontier (Gate 2 + cost) is still informative, but two-gate
qualification is not.

## Solution

Wire the per-role divergence metric into `run_full_matrix` instead of passing
`None`:

- For each role in `ROLES_WITH_DIVERGENCE`, build the divergence metric via
  `divergence.metric.load_baseline(...)` against the role's
  `eval/baselines/divergence-{role}.json` and pass it as
  `divergence_metric_or_none`, plus a real `baselines_dir`.
- Roles without divergence rubrics (D-08) should pass `None` deliberately and
  get `gate1_passed=None` (not False) — confirm `score_two_gate` already
  distinguishes "no rubric -> None/skip" from "rubric exists but metric missing
  -> False". If it conflates them, fix the distinction.
- Confirm the `divergence-{role}.json` baselines exist for all 6 roles; if some
  are missing, decide whether to (re)record them (there is a
  `--accept-divergence-baseline` conftest option) or gate the role.

### Verify before building
- Trace exactly how the standalone divergence tests construct the metric
  (`divergence/check.py`, `divergence/metric.py`, the per-role modules) and
  mirror that wiring in `run_full_matrix`.
- Re-run the matrix and confirm Haiku (incumbent) now PASSES Gate 1 for at least
  the quality-tier roles — that's the smoke test that the wiring is correct.
- Add a unit test that drives `run_full_matrix` (mocked cells) and asserts the
  `score_two_gate` call receives a non-None `divergence_metric_or_none` for a
  divergence-eligible role.

## Related anomalies observed in the same run (may be separate todos)

These surfaced alongside the Gate-1 bug and are worth confirming once Gate 1 is
fixed — they may share a cause or be independent:

- **scanner + linter `quality_mean = 0.000` across ALL candidates** — no quality
  discrimination at all. Both are structural-only (no judge panel); the
  structural scorer appears to return 0 for every candidate against the
  round-trip-vault fixture (scanner had a similar "no real work" problem in the
  prior sweep). Frontier for these two collapses to "cheapest that ran," which
  is not a quality judgment.
- **code_reader `cost = N/A` for 5 of 6 candidates** (only Haiku got a cost) —
  token/usage extraction from traces did not capture for the non-Haiku models,
  so those candidates can't be cost-ranked. The `code_reader.md` Pareto-frontier
  rendering is also buggy (prints `quality=0.00` for rows that scored 0.72-1.00
  in the raw table).

Related: [[cost-frontier-sweep]] (two-gate scoring is the qualification gate),
[[eval-judge-panel-design]] (Gate 2), [[divergence-eval-framework]] (Gate 1).
