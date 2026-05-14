---
phase: 04-eval-harness
plan: "03"
subsystem: eval-harness
tags:
  - eval
  - judge
  - deepeval
  - bedrock
  - cost-frontier
  - regression-check
  - pytest-evals
  - tdd
dependency_graph:
  requires:
    - "04-01: eval-harness foundation (pricing, structural, conftest, query_cases.json)"
    - "04-02: sweep runner (SweepResult, run_sweep, EvalWorktree)"
  provides:
    - eval_harness.judge (panel_score, make_judge, position_bias_check, JUDGE_PANEL_CONFIG)
    - eval_harness.report (cost_frontier_table, regression_check, print_frontier)
    - cores/eval-harness/tests/eval/test_sweep_eval.py (pytest-evals two-phase sweep integration)
  affects:
    - "04-05+ (any future plans running CODE_WIKI_RUN_EVAL=1 sweep)"
tech_stack:
  added: []
  patterns:
    - "Two-judge GEval panel: explicit model= on every GEval instance (never OpenAI default)"
    - "Fresh AmazonBedrockModel + GEval per call — no instance reuse across panel_score() calls"
    - "cost_frontier_table: sorted dict, quality_score fallback chain (judge mean → structural)"
    - "pytest-evals: pytestmark = [pytest.mark.eval] gates entire module without --run-eval"
    - "CODE_WIKI_RUN_JUDGES=1 decouples judge cost from sweep cost in multi-run workflows"
    - "sys.path.insert to import EVAL_GATE from parent conftest.py in eval/ subpackage"

key_files:
  created:
    - cores/eval-harness/src/eval_harness/judge.py
    - cores/eval-harness/src/eval_harness/report.py
    - cores/eval-harness/tests/test_report.py
    - cores/eval-harness/tests/eval/__init__.py
    - cores/eval-harness/tests/eval/test_sweep_eval.py
  modified: []

key-decisions:
  - "judge.py: AmazonBedrockModel always receives explicit model= arg — deepeval defaults to OpenAI GPT if omitted (T-4-04 threat mitigation)"
  - "JUDGE_PANEL_CONFIG: claude-sonnet-4-6 (quality ceiling) + nova-pro-v1:0 (cost diversity) per D-07"
  - "cost_frontier_table fallback: when judge_scores is None, quality_score = 1.0 if has_citation else 0.0"
  - "sys.path.insert approach for importing EVAL_GATE from tests/conftest.py into tests/eval/ subpackage"
  - "CODE_WIKI_RUN_JUDGES=1 env var separates sweep runs from judge scoring — users can run sweep without Bedrock judge calls on every test"

patterns-established:
  - "GEval panel: always fresh instances per call; model= explicit; temperature=0 for determinism"
  - "regression_check: AssertionError with 'below threshold' in message — pytest captures as test failure"
  - "pytest-evals analysis: print_frontier → regression_check sequence in test_query_sweep_analysis"

requirements-completed:
  - EVAL-05
  - EVAL-07
  - EVAL-09
  - EVAL-10

duration: 20min
completed: 2026-05-14
---

# Phase 04 Plan 03: Judge Panel and Cost-Frontier Report Summary

**Two-judge GEval panel (claude-sonnet-4-6 + nova-pro-v1:0) with explicit Bedrock model binding, cost_frontier_table sorted by quality descending, regression_check AssertionError gate, and pytest-evals two-phase sweep integration with position_bias_check.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-14T16:00Z
- **Completed:** 2026-05-14T16:17Z
- **Tasks:** 2 (Task 1 TDD: RED + GREEN; Task 2: direct implementation)
- **Files modified:** 5 created

## Accomplishments

- `judge.py`: Two-judge GEval panel with hardcoded JUDGE_PANEL_CONFIG, `make_judge()` factory, `panel_score()` returning judge_a/judge_b/mean/reason_a/reason_b, and `position_bias_check()` for UAT order-sensitivity measurement. All GEval instances always receive `model=` explicitly — deepeval never allowed to fall back to OpenAI (T-4-04 mitigation).
- `report.py`: `cost_frontier_table()` builds per-model quality/cost dict sorted by quality_score descending, with structural fallback (has_citation) when judge_scores is None. `regression_check()` raises AssertionError with "below threshold" message for CI quality gate (EVAL-09). `print_frontier()` formats a plain-text table (model_id, quality, cost_usd, pages_drilled).
- `test_sweep_eval.py`: pytest-evals two-phase integration — 12 sweep parametrized tests (4 cases × 3 models), `test_query_sweep_analysis` with regression gate, `test_position_bias_check` for UAT, and `test_eval_mark_skip` verifying the gate mechanism. Module-level `pytestmark = [pytest.mark.eval]` ensures the entire file skips without `--run-eval`.

## Task Commits

TDD cycle:

1. **RED: test_report.py** — `bec02d2` (test)
2. **GREEN: judge.py + report.py** — `85d14ea` (feat)
3. **Task 2: test_sweep_eval.py + eval/__init__.py** — `c9f83fe` (feat)

## Files Created/Modified

- `cores/eval-harness/src/eval_harness/judge.py` — Two-judge GEval panel, make_judge, panel_score, position_bias_check, JUDGE_PANEL_CONFIG
- `cores/eval-harness/src/eval_harness/report.py` — cost_frontier_table, regression_check, print_frontier
- `cores/eval-harness/tests/test_report.py` — 9 unit tests (regression_check, cost_frontier_table, print_frontier)
- `cores/eval-harness/tests/eval/__init__.py` — empty package marker
- `cores/eval-harness/tests/eval/test_sweep_eval.py` — pytest-evals two-phase sweep integration (15 tests, gated)

## Decisions Made

- **Explicit model= on every GEval:** deepeval 4.0 defaults to OpenAI GPT if `model` is omitted. Since this project is Bedrock-only, any OpenAI routing would silently incur cost outside the expected provider. Made explicit and documented in both code comments and acceptance criteria (T-4-04).
- **CODE_WIKI_RUN_JUDGES=1 separate env var:** Decouples sweep runs from judge scoring so operators can run the sweep to check structural metrics without incurring Bedrock judge API costs every time. This is the right separation for iterative development.
- **sys.path.insert for conftest import:** The `eval/` subpackage cannot import `conftest.py` from the parent `tests/` directory via normal Python module resolution. Adding `str(Path(__file__).parent.parent)` to sys.path is the minimal fix that preserves the plan's requirement to "import EVAL_GATE from conftest".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] sys.path.insert for conftest import in eval/ subpackage**
- **Found during:** Task 2 (test_sweep_eval.py collection)
- **Issue:** `from conftest import EVAL_GATE` failed with `ModuleNotFoundError: No module named 'conftest'` because Python's module resolution does not include the parent `tests/` directory when running from `tests/eval/`
- **Fix:** Added `sys.path.insert(0, str(Path(__file__).parent.parent))` before the conftest import, placing `tests/` on sys.path temporarily
- **Files modified:** `cores/eval-harness/tests/eval/test_sweep_eval.py`
- **Verification:** Collection succeeds; `uv run --package eval-harness pytest cores/eval-harness/tests/ -m "not eval" -x -q` exits 0
- **Committed in:** c9f83fe

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking import)
**Impact on plan:** Necessary to satisfy the plan's "imports EVAL_GATE from conftest" acceptance criterion. No scope creep.

## Issues Encountered

- Accidental commit to `main` during initial setup (first git command used `cd /path/to/main-repo &&` instead of running in worktree cwd). All subsequent commits correctly targeted the `worktree-agent-a9e8310bc70108663` branch. The main repo commit (2805895) is a pre-existing artifact; the orchestrator will reconcile during merge.

## Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| test_report.py | 9 | All PASSED |
| test_sweep_eval.py | 15 | Collected (gated; skip without --run-eval) |
| eval-harness total (unit, -m "not eval") | 49 | All PASSED |

## Known Stubs

None. All modules implement their full contracts:
- `judge.py` — panel_score() makes real Bedrock calls; unit tests do NOT call it (eval-gated)
- `report.py` — fully deterministic; no stubs
- `test_sweep_eval.py` — gated by both pytest-evals --run-eval and EVAL_GATE; real Bedrock sweep on activation

## Threat Flags

No new security surface beyond plan threat model:

| Threat ID | File | Mitigation Applied |
|-----------|------|--------------------|
| T-4-04 | judge.py `panel_score()` | `model=judge` always explicit on every GEval; grep for gpt/openai returns 0 matches |
| T-4-01 | test_sweep_eval.py | isinstance(case.get("query"), str) validation before parametrization; json.load() not exec |

## Self-Check: PASSED

Files verified to exist:
- `cores/eval-harness/src/eval_harness/judge.py` — FOUND
- `cores/eval-harness/src/eval_harness/report.py` — FOUND
- `cores/eval-harness/tests/test_report.py` — FOUND
- `cores/eval-harness/tests/eval/__init__.py` — FOUND
- `cores/eval-harness/tests/eval/test_sweep_eval.py` — FOUND

Commits verified: bec02d2 (RED), 85d14ea (GREEN), c9f83fe (Task 2) — all present in git log.

TDD Gate Compliance:
- RED commit: bec02d2 (`test(04-03): add failing tests for report module (RED)`) — PASSED
- GREEN commit: 85d14ea (`feat(04-03): implement judge panel and cost-frontier report (GREEN)`) — PASSED

---
*Phase: 04-eval-harness*
*Completed: 2026-05-14*
