---
phase: 06-prompt-content-port-divergence-eval
plan: 11
subsystem: eval-harness
tags: [divergence-eval, integration-test, eval-gate, pytest-evals, end-to-end]
dependency_graph:
  requires: [06-10]
  provides: [divergence-eval-gate, eval-12-concrete-examples, eval-13-regression-gate]
  affects: [cores/eval-harness/tests]
tech_stack:
  added: []
  patterns:
    - eval-gate guard on CODE_WIKI_RUN_EVAL=1
    - asyncio.run() wrapping async agent commands for sync test context
    - sys.path.insert for conftest module import in sibling test files
key_files:
  created: []
  modified:
    - cores/eval-harness/tests/conftest.py
    - cores/eval-harness/tests/test_divergence.py
decisions:
  - "_produce_outputs implemented as a plain callable (not a pytest fixture) for direct import from test_divergence.py — matches the pattern used by test_sweep_eval.py which imports from conftest via sys.path.insert"
  - "Scanner corpus uses run_scan() against the vault fixture itself; ingestor corpus uses existing vault .md pages as source documents to re-ingest — both avoid fabricating new fixture data"
  - "asyncio.run() used to invoke async agent commands from the sync test body — no pytest-asyncio mark needed since the test itself is sync (results are collected synchronously)"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-15T20:32:37Z"
  tasks_completed: 2
  files_modified: 2
---

# Phase 06 Plan 11: Eval-Gated Wiring Summary

Wired the divergence metric end-to-end into a single eval-gated pytest test parametrized over the 4 roles (librarian, ingestor, linter, scanner), completing EVAL-12 (per-role divergence counts + concrete examples) and EVAL-13 (regression gate against recorded baseline).

## What Was Built

### Task 1: `_produce_outputs` helper in `conftest.py`

Added `_produce_outputs(role, vault)` as a plain callable to `cores/eval-harness/tests/conftest.py`. It produces `list[tuple[str, AgentOutputProxy, str]]` — the triple expected by `DivergenceMetric.run()` — by invoking the real agent commands:

- **librarian**: calls `run_query()` against each case in `eval/cases/query_cases.json`; wraps `QueryResult.answer` in `AgentOutputProxy`
- **ingestor**: calls `run_ingest_source()` on up to 2 `.md` files from `vault/packages/` or `vault/concepts/`; reads the written page back for the answer; sets `page_type` from `IngestResult`
- **linter**: calls `run_lint()` against the round-trip-vault; returns one output per semantic group (`page_quality`, `adr_chain`, `stale_claims`) with findings joined as the answer
- **scanner**: calls `run_scan()` against the vault and reads the written stub pages for `added + updated` packages

All per-role producers guard on `CODE_WIKI_RUN_EVAL=1` via `pytest.skip`. Missing corpus paths produce skip messages pointing to the expected path.

Existing fixtures (`EVAL_GATE`, `accept_baseline`, `fixture_vault_path`) are preserved unchanged.

### Task 2: `test_divergence.py` production test

Replaced the 06-02 scaffold body with the production test:

```python
@EVAL_GATE
@pytest.mark.parametrize("role", ["librarian", "ingestor", "linter", "scanner"])
def test_divergence_regression(role, fixture_vault_path, accept_baseline, capsys):
    outputs = _produce_outputs(role, fixture_vault_path)
    metric = DivergenceMetric(role=role, checks=ROLE_CHECKS[role], rubric_path=ROLE_RUBRICS[role], vault=fixture_vault_path)
    results = metric.run(outputs)
    # print per-rule counts + first 3 excerpts (EVAL-12)
    ...
    if accept_baseline:
        write_baseline(role, BASELINES_DIR, results, _current_agent_commit())
        return
    baseline = load_baseline(role, BASELINES_DIR)
    check_regression(role, results, baseline)
```

Uses `sys.path.insert(0, str(Path(__file__).parent))` (same pattern as `test_sweep_eval.py`) to import `_produce_outputs` from conftest as a plain module.

## Verification

- Without `CODE_WIKI_RUN_EVAL=1`: `uv run pytest cores/eval-harness/tests/test_divergence.py -x -q` reports **4 skipped, 0 failed** (confirmed)
- Collection: 4 tests collected correctly (confirmed)
- The `BASELINES_DIR` (initial empty baselines from 06-10) remains unchanged — populated on first real Bedrock run with `CODE_WIKI_RUN_EVAL=1 --accept-divergence-baseline`

## Baseline Snapshot (Initial — from 06-10)

The 4 baseline JSON files in `cores/eval-harness/baselines/` have `agent_commit: "initial-empty-baseline"` and all-zero counts. The v1.1 starting counts will be recorded on the first run:

| Role | Rules | Initial failures |
|------|-------|-----------------|
| librarian | LIB-001..LIB-004, LIB-JUDGE | 0 (baseline pending Bedrock run) |
| ingestor | ING-001..ING-004, ING-JUDGE | 0 (baseline pending Bedrock run) |
| linter | LNT-001..LNT-003, LNT-JUDGE | 0 (baseline pending Bedrock run) |
| scanner | SCN-001..SCN-004, SCN-JUDGE | 0 (baseline pending Bedrock run) |

To record the v1.1 starting baseline:
```bash
CODE_WIKI_RUN_EVAL=1 uv run pytest cores/eval-harness/tests/test_divergence.py --accept-divergence-baseline -s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `from conftest import _produce_outputs` fails without sys.path**
- **Found during:** Task 2 verification
- **Issue:** `conftest.py` is not on the Python path when `test_divergence.py` is imported as a module — direct `from conftest import _produce_outputs` raised `ModuleNotFoundError`
- **Fix:** Added `sys.path.insert(0, str(Path(__file__).parent))` to `test_divergence.py`, matching the exact pattern used by `cores/eval-harness/tests/eval/test_sweep_eval.py`
- **Files modified:** `cores/eval-harness/tests/test_divergence.py`
- **Commit:** facb621

None — plan executed as written aside from the sys.path fix.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The only security-relevant boundary is `CODE_WIKI_RUN_EVAL=1` gating Bedrock calls — mitigated by both `EVAL_GATE` mark and the `pytest.skip` guard inside `_produce_outputs` (T-06-24, belt-and-suspenders).

## Self-Check: PASSED

- conftest.py modified: FOUND
- test_divergence.py modified: FOUND
- commit db5e64e (Task 1): FOUND
- commit facb621 (Task 2): FOUND
- 4 tests skip without CODE_WIKI_RUN_EVAL: VERIFIED (4 skipped, 0 failed)
