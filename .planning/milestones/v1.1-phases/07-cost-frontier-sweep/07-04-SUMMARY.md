---
phase: 07-cost-frontier-sweep
plan: "04"
subsystem: eval-harness
tags: [pre-flight, cost-estimator, bed-01, dry-run]
dependency_graph:
  requires: ["07-01", "07-03"]
  provides: ["eval_harness.preflight", "eval_harness.sweep.preflight-API"]
  affects: ["07-05", "07-06", "07-07"]
tech_stack:
  added: []
  patterns:
    - "Pre-flight cost estimator with conservative per-tier token constants"
    - "Hard cap enforcement via SystemExit before any Bedrock call"
    - "BED-01 live ping wrapped in SystemExit-formatted error"
key_files:
  created:
    - cores/eval-harness/src/eval_harness/preflight.py
    - cores/eval-harness/tests/test_preflight_estimator.py
    - cores/eval-harness/tests/test_preflight_module_red.py
  modified:
    - cores/eval-harness/src/eval_harness/sweep.py
decisions:
  - "HARD_CAP_USD = $25.0 (D-13 recommendation: 4x headroom over ~$6.19 estimated 24-cell matrix)"
  - "Conservative per-tier token constants: cheap-fast=(3000,500), mid=(5000,1000), quality=(8000,2000)"
  - "preflight_check() is the single entry point; skip_bed01 and auto_confirm flags enable dry-run/CI use"
  - "UnknownModelError from pricing.cost_for_usage is silently swallowed (unknown models skipped)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-17"
  tasks_completed: 2
  files_count: 4
---

# Phase 07 Plan 04: Pre-flight Cost Estimator and BED-01 Ping Summary

Pre-flight module with cost estimator, $25 hard cap, and BED-01 Bedrock connectivity ping backed by 8 passing unit tests.

## What Was Built

### `eval_harness.preflight` module (new)

Three callable public API + one constant:

| Name | Type | Purpose |
|------|------|---------|
| `HARD_CAP_USD` | constant | `25.0` — abort threshold before any Bedrock spend |
| `estimate_sweep_cost(role_candidates, n_cases, repeats)` | function | Conservative cost estimate using per-tier token constants × pricing table |
| `preflight_bed01()` | function | Live Bedrock ping via `make_llm("haiku").invoke("ping")` |
| `preflight_check(...)` | function | Orchestrator: estimate → cap check → BED-01 → user confirm |

### 24-cell Matrix Estimate (live function output)

Running `estimate_sweep_cost(_FULL_ROLE_CANDIDATES, n_cases=4, repeats=3)` with the D-03 candidate set:

```
24-cell matrix estimate: $2.9730
Hard cap:                $25.00
Headroom:                8.4x
Under cap:               True
```

The estimate is comfortably within the $25 hard cap with 8.4x headroom.

### Conservative Per-tier Token Constants (D-13)

| Tier | Roles | Tokens In | Tokens Out |
|------|-------|-----------|-----------|
| cheap-fast | scanner, code_reader | 3,000 | 500 |
| mid | linter, ingestor | 5,000 | 1,000 |
| quality | librarian, synthesizer | 8,000 | 2,000 |

### `sweep.py` import wire

Added `from eval_harness.preflight import HARD_CAP_USD, estimate_sweep_cost, preflight_bed01, preflight_check` to make the API discoverable from `eval_harness.sweep`.

## Test Coverage (8 tests, all green)

| Test | Coverage Area | Result |
|------|---------------|--------|
| `test_estimate_24_cell_sweep_within_cap` | Full D-03 matrix stays under cap | PASS |
| `test_estimate_returns_zero_for_empty_candidates` | Empty dict → 0.0 | PASS |
| `test_estimator_skips_unknown_model_ids` | bogus-model silently skipped | PASS |
| `test_estimator_scales_with_repeats` | repeats=3 is ~3x repeats=1 | PASS |
| `test_preflight_check_aborts_above_cap` | SystemExit with "exceeds hard cap"; BED-01 NOT called | PASS |
| `test_preflight_check_prompts_for_confirmation` | n→SystemExit; y→returns estimate | PASS |
| `test_preflight_bed01_systemexit_on_access_denied` | BedrockAccessDenied → SystemExit "BED-01 FAILED:" | PASS |
| `test_preflight_bed01_prints_confirmation_on_success` | capsys captures "[BED-01] Bedrock connectivity confirmed." | PASS |

### Cap Enforcement Test Outcome

`test_preflight_check_aborts_above_cap`: Monkey-patches `cost_for_usage` to return `100.0` per model; confirms `SystemExit` is raised containing "exceeds hard cap"; also confirms `preflight_bed01` was NOT called (cap check runs first, before BED-01 ping).

### BED-01 Mock Test Outcome

`test_preflight_bed01_systemexit_on_access_denied`: Monkey-patches `make_llm` to return a fake whose `.invoke()` raises `BedrockAccessDenied("arn:...")`. Confirms `SystemExit` message starts with `"BED-01 FAILED:"`.

`test_preflight_bed01_prints_confirmation_on_success`: Monkey-patches `make_llm` to return a fake whose `.invoke()` returns `"pong"`. Uses `capsys` to confirm stdout contains `"[BED-01] Bedrock connectivity confirmed."`.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

T-07-06 (Denial of Service via spend exhaustion): Mitigated by `HARD_CAP_USD = 25.0` enforced in `preflight_check()` before any Bedrock call. Test `test_preflight_check_aborts_above_cap` confirms BED-01 is never reached when estimate exceeds cap.

T-07-07 (BedrockAccessDenied ARN in error): `preflight_bed01()` catches `BedrockAccessDenied` and re-raises as `SystemExit` — the ARN detail is visible in the exit message (same surface as today's `make_llm`). Accepted per threat register.

No new threat surface introduced beyond what is in the plan's threat model.

## Self-Check

- [x] `cores/eval-harness/src/eval_harness/preflight.py` — created
- [x] `cores/eval-harness/src/eval_harness/sweep.py` — modified (import added)
- [x] `cores/eval-harness/tests/test_preflight_estimator.py` — 8 tests, all green
- [x] `cores/eval-harness/tests/test_preflight_module_red.py` — RED phase test, also green after impl

## Self-Check: PASSED
