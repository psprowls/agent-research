---
phase: 04-eval-harness
verified: 2026-05-14T21:00:00Z
status: gaps_found
score: 8/10 must-haves verified
overrides_applied: 0
gaps:
  - truth: "The fixture corpus (2–3 small test repos with pre-built wikis) is committed under tests/fixtures/ covering single-package, monorepo, and edge-case shapes"
    status: failed
    reason: "Only one fixture vault exists (round-trip-vault, monorepo shape). ROADMAP SC1 explicitly requires 2–3 repos covering different shapes (single-package, monorepo, edge-case). EVAL-02 requirement states the same. Plan 01's must_have narrowed EVAL-02 to 'eval/cases/query_cases.json contains 3+ test cases' but per verification rules, PLAN frontmatter cannot reduce ROADMAP SC scope."
    artifacts:
      - path: "cores/vault-io/tests/fixtures/round-trip-vault"
        issue: "Only monorepo shape present; single-package and edge-case fixture vaults are missing"
    missing:
      - "A second fixture vault representing a single-package shape (one package, flat structure)"
      - "A third fixture vault representing an edge-case shape (e.g., truncated frontmatter, missing pages, or unusual structure)"
  - truth: "A model sweep over at least 3 Bedrock models produces a cost-frontier table showing at least 2 models at different quality/cost tradeoffs"
    status: failed
    reason: "No baseline recordings committed (eval/baselines/ is empty); no sweep run results exist in the repo. The infrastructure to produce this table is fully built and working, but ROADMAP SC2 requires observable evidence of an actual sweep producing the table — not just infrastructure readiness."
    artifacts:
      - path: "eval/baselines"
        issue: "Directory does not exist; no baseline JSON files committed"
    missing:
      - "Run baseline recording: CODE_WIKI_RUN_EVAL=1 uv run --package eval-harness python -m eval_harness.baseline --cases eval/cases/query_cases.json --vault <vault> --out eval/baselines/"
      - "Run the model sweep and commit the cost-frontier table output or at minimum a sample result"
human_verification:
  - test: "Confirm position bias < 0.05 threshold"
    expected: "position_bias_check() returns delta < 0.05 when called with two plausible answers to the same query"
    why_human: "Requires real Bedrock API calls to both Claude Sonnet and Nova Pro; cannot be verified without credentials and network access"
  - test: "Full eval sweep produces cost-frontier table with 3 models"
    expected: "CODE_WIKI_RUN_EVAL=1 pytest cores/eval-harness/tests/ --run-eval --run-eval-analysis prints a table with 3 rows (haiku, nova-lite, qwen3)"
    why_human: "Requires real Bedrock credentials and network access; sweep makes live model calls"
---

# Phase 04: Eval Harness Verification Report

**Phase Goal:** Build a cost-gating eval harness that runs a model sweep (query against multiple Bedrock models), grades each result with an LLM judge panel, and produces a cost/quality frontier table — so Pat can pick the cheapest model that still passes quality gates.
**Verified:** 2026-05-14T21:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1   | eval-harness package is importable as a workspace member | ✓ VERIFIED | `uv run --package eval-harness python -c "import eval_harness"` exits 0 |
| 2   | Pricing module returns correct USD costs for all 5 Bedrock model IDs | ✓ VERIFIED | All 5 model IDs in PRICES; nova-micro fallback present; cost_for_usage tested |
| 3   | Structural checker returns all 7 EVAL-06 keys | ✓ VERIFIED | `check_structural()` returns exactly 7 keys; 48 unit tests pass |
| 4   | run_query() accepts librarian_model_override parameter | ✓ VERIFIED | 4 grep matches in query.py; signature confirmed via importlib |
| 5   | pool.py writes real cost_usd via eval_harness.pricing lazy import | ✓ VERIFIED | `_compute_cost_usd()` with lazy import inside try/except present at line 200+ |
| 6   | models.toml judge_b is Nova Pro | ✓ VERIFIED | `[roles.judge_b] model_id = "us.amazon.nova-pro-v1:0"` |
| 7   | eval/cases/query_cases.json contains 3+ test cases | ✓ VERIFIED | 4 valid cases with case_id, query, expected_answer, tags |
| 8   | EvalWorktree, sweep runner, judge panel, report, baseline recorder all exist and are substantive | ✓ VERIFIED | All 7 source modules exist; 48 unit tests pass without Bedrock |
| 9   | Fixture corpus covers 2–3 repo shapes (single-package, monorepo, edge-case) | ✗ FAILED | Only 1 vault (round-trip-vault, monorepo shape); ROADMAP SC1 requires 2–3 repos |
| 10  | Sweep produces observable cost-frontier table from real model runs | ✗ FAILED | eval/baselines/ does not exist; no sweep results committed; ROADMAP SC2 requires run evidence |

**Score:** 8/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `cores/eval-harness/pyproject.toml` | workspace member + deepeval/pytest-evals deps | ✓ VERIFIED | name="eval-harness", all deps declared |
| `cores/eval-harness/src/eval_harness/pricing.py` | PRICES dict + cost_for_usage | ✓ VERIFIED | 9 model entries (3 Claude + 5 Bedrock + nova-micro); exports PRICES, UnknownModelError, cost_for_usage |
| `cores/eval-harness/src/eval_harness/structural.py` | check_structural() with 7 EVAL-06 keys | ✓ VERIFIED | Returns dict with all 7 keys; T-4-01 isinstance guard present |
| `cores/eval-harness/src/eval_harness/isolation.py` | EvalWorktree async context manager | ✓ VERIFIED | shutil.copytree + tmpdir cleanup; no subprocess/oauth/git |
| `cores/eval-harness/src/eval_harness/sweep.py` | SweepResult + run_sweep() | ✓ VERIFIED | asyncio.gather(return_exceptions=True); model_id sanitization; seed=None; JSON schema validation |
| `cores/eval-harness/src/eval_harness/judge.py` | panel_score + make_judge + JUDGE_PANEL_CONFIG | ✓ VERIFIED | Heterogeneous panel (Sonnet + Nova Pro); explicit model= on every GEval; no OpenAI strings |
| `cores/eval-harness/src/eval_harness/report.py` | cost_frontier_table + regression_check + print_frontier | ✓ VERIFIED | Sorted descending; "below threshold" AssertionError confirmed |
| `cores/eval-harness/src/eval_harness/baseline.py` | RunResult + _build_cmd + run_headless + BaselineRecorder | ✓ VERIFIED | 8-field EVAL-08 schema; seed=None; no shell=True; prompt always last arg |
| `eval/cases/query_cases.json` | 3+ eval test cases | ✓ VERIFIED | 4 cases covering package-lookup, concept, cross-reference, format |
| `eval/README.md` | "Recording a Baseline" section | ✓ VERIFIED | Prerequisites, exact command, expected output structure, seed=null note |
| `cores/eval-harness/tests/eval/test_sweep_eval.py` | pytest-evals two-phase sweep integration | ✓ VERIFIED | pytestmark=[pytest.mark.eval]; analysis calls regression_check; 15 tests gated |
| `cores/vault-io/tests/fixtures/round-trip-vault` (2–3 shapes) | single-package + monorepo + edge-case vaults | ✗ MISSING | Only round-trip-vault (monorepo shape) committed; 2 additional fixture vaults required |
| `eval/baselines/` | baseline JSON files from actual recording | ✗ MISSING | Directory does not exist; ROADMAP SC1 requires evidence of actual baseline recording |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `pool.py _write_trace()` | `eval_harness.pricing.cost_for_usage` | lazy import in `_compute_cost_usd()` | ✓ WIRED | Pattern `from eval_harness.pricing import UnknownModelError, cost_for_usage` present inside try/except |
| `run_query()` | `librarian_model_override` param | ChatBedrockConverse direct construction | ✓ WIRED | 4 matches in query.py (signature + docstring + conditional + usage) |
| `sweep.py run_sweep()` | `run_query(librarian_model_override=model_id)` | EvalWorktree async context manager | ✓ WIRED | `librarian_model_override=model_id` at line 193 inside EvalWorktree |
| `sweep.py SweepResult` | `check_structural(result, vault_path)` | structural.check_structural() call | ✓ WIRED | `structural = check_structural(result, wt.path)` present |
| `judge.py panel_score()` | `GEval(model=AmazonBedrockModel(...))` | explicit model= arg | ✓ WIRED | `model=judge` on every GEval instantiation; no "gpt"/"openai" strings found |
| `report.py regression_check()` | `pytest.mark.eval_analysis` assertion | AssertionError with "below threshold" | ✓ WIRED | Message confirmed; test_sweep_eval.py calls `regression_check(mean_score, threshold=0.5)` |
| `BaselineRecorder.record()` | `eval/baselines/<case_id>.json` | json.dumps with 8-field schema | ✓ WIRED | Implementation complete; no actual baseline files committed (infrastructure gap only) |
| `_build_cmd()` | subprocess (never shell=True) | list form cmd with prompt as final arg | ✓ WIRED | `assert isinstance(cmd, list)` guard; shell=True appears only in docstring comment (negated) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `sweep.py run_sweep()` | `result` from `run_query()` | `ChatBedrockConverse` via `run_query(librarian_model_override=model_id)` | Yes — real Bedrock API calls when executed | ✓ FLOWING (gated by Bedrock credentials) |
| `sweep.py _extract_tokens_from_traces()` | `tokens_in`, `tokens_out` | trace JSONL written by `SubagentPool._write_trace()` | Yes — real trace JSONL with token fields | ✓ FLOWING |
| `report.cost_frontier_table()` | `quality_score` | `result.judge_scores["mean"]` or structural fallback | Yes — judge scores from panel_score() or structural | ✓ FLOWING |
| `baseline.py run_headless()` | `assistant_text` | `claude -p` subprocess stdout stream-json events | Yes — real subprocess output | ✓ FLOWING (gated by claude CLI) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| eval-harness importable | `uv run --package eval-harness python -c "import eval_harness"` | exits 0 | ✓ PASS |
| All 5 Bedrock model IDs in PRICES | python check via importlib | `5-model check: True` | ✓ PASS |
| librarian_model_override in run_query signature | python inspect check | `True` | ✓ PASS |
| regression_check raises "below threshold" | python -c call with score=0.3 | AssertionError: "Quality score 0.300 below threshold 0.500" | ✓ PASS |
| structural returns 7 keys | python check via importlib | `count: 7` | ✓ PASS |
| judge exports ok + panel config heterogeneous | python import check | `['us.anthropic.claude-sonnet-4-6', 'us.amazon.nova-pro-v1:0']` | ✓ PASS |
| 48 unit tests pass without Bedrock | `uv run --package eval-harness pytest -m "not eval and not integration" -q` | `48 passed, 16 deselected in 1.05s` | ✓ PASS |
| eval tests gated without --run-eval | `pytest tests/eval/ -m "not eval"` | `15 deselected in 0.01s` | ✓ PASS |
| no shell=True in baseline.py | grep check | Count 1 (in docstring comment only, negated) | ✓ PASS |
| no OpenAI model strings in judge.py | grep check | 0 matches | ✓ PASS |
| models.toml judge_b = nova-pro | grep check | `model_id = "us.amazon.nova-pro-v1:0"` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| EVAL-01 | 04-01 | eval-harness is a separate package usable by future agents | ✓ SATISFIED | Standalone cores/eval-harness workspace member; no in-tree coupling to code-wiki-agent except declared workspace dep |
| EVAL-02 | 04-01 | Fixture corpus: 2–3 small test repos covering different shapes | ✗ BLOCKED | Only 1 fixture vault (round-trip-vault); single-package and edge-case shapes absent |
| EVAL-03 | 04-04 | Baseline recorder: headless claude -p subprocess, instructions documented | ✓ SATISFIED | baseline.py with BaselineRecorder + run_headless; eval/README.md with exact command |
| EVAL-04 | 04-02 | Model sweep runner for N candidate Bedrock models | ✓ SATISFIED | run_sweep() with asyncio.gather; librarian_model_override; EvalWorktree isolation |
| EVAL-05 | 04-03 | deepeval AmazonBedrockModel; heterogeneous judge panel | ✓ SATISFIED | Two-judge panel (Claude Sonnet + Nova Pro); explicit model= on every GEval instance |
| EVAL-06 | 04-01/02 | Structural metrics: citations, wikilinks resolve, frontmatter, JSON schema | ✓ SATISFIED | check_structural() returns all 7 keys; deterministic, no LLM calls |
| EVAL-07 | 04-01/03 | Cost-frontier report with cost-optimal model highlighted | ✓ SATISFIED | cost_frontier_table() sorted by quality_score descending; print_frontier() formatter |
| EVAL-08 | 04-02/04 | Reproducibility: model ARN + prompt hash + timestamp + seed in each result | ✓ SATISFIED | SweepResult.seed=None documented; BaselineRecorder snapshot has 8 EVAL-08 fields |
| EVAL-09 | 04-03 | Regression check: CI-friendly failure if quality below threshold | ✓ SATISFIED | regression_check() raises AssertionError("...below threshold..."); called in test_query_sweep_analysis |
| EVAL-10 | 04-03 | pytest-evals integration: @pytest.mark.eval, opt-in, CI-skippable | ✓ SATISFIED | pytestmark=[pytest.mark.eval] gates entire file; 15 tests collected but deselected without --run-eval |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| No debt markers (TBD/FIXME/XXX) found in any phase 4 source file | — | — | — | Clean |

Scanned all 7 source modules and all test files. No unreferenced TODO/FIXME/XXX markers found. No empty return stubs. No hardcoded empty data passed to rendering. All `seed=None` values are intentional documented design choices, not stubs.

### Human Verification Required

#### 1. Position Bias Confirmation

**Test:** Set `CODE_WIKI_RUN_EVAL=1` and `CODE_WIKI_RUN_JUDGES=1`, then run: `uv run --package eval-harness pytest cores/eval-harness/tests/eval/test_sweep_eval.py::test_position_bias_check --run-eval -v`
**Expected:** Test PASSES; `position_bias_check()` returns delta < 0.05, confirming judge panel has low position sensitivity
**Why human:** Requires real Bedrock API calls to Claude Sonnet and Nova Pro; cannot be verified programmatically without credentials and network access

#### 2. Full Sweep Execution (ROADMAP SC2 + SC3)

**Test:** Run `CODE_WIKI_RUN_EVAL=1 CODE_WIKI_RUN_JUDGES=1 uv run --package eval-harness pytest cores/eval-harness/tests/ --run-eval --run-eval-analysis -v`
**Expected:** Test output includes a cost-frontier table with 3 rows (haiku, nova-lite, qwen3-32b); analysis passes regression_check at threshold 0.5; cheaper model is within measurable quality margin of more expensive one
**Why human:** Requires real Bedrock credentials and live model calls

---

## Gaps Summary

### Gap 1 (BLOCKER): Missing fixture corpus shapes — EVAL-02 partially unmet

ROADMAP SC1 and EVAL-02 require "2–3 small test repos with pre-built wikis committed to `tests/fixtures/` covering single-package, monorepo, and edge-case shapes." Only one vault exists: `cores/vault-io/tests/fixtures/round-trip-vault/` which is a monorepo shape.

The plan's `must_haves.truths` narrowed EVAL-02 to "eval/cases/query_cases.json contains 3+ test cases" — but per verification rules, PLAN frontmatter cannot reduce ROADMAP success criteria. The roadmap SC1 is the contract.

**Root cause:** Plan 01 mapped EVAL-02 to the eval cases JSON rather than creating additional fixture vaults. The round-trip-vault (from Phase 1/3 vault IO work) covers the monorepo shape. Two more fixture vaults need to be created and committed.

**To fix:**
1. Create a minimal single-package fixture vault (one package, flat wiki structure with a few pages)
2. Create an edge-case fixture vault (e.g., pages with truncated frontmatter, missing citation targets, empty packages list)
3. Commit both to `cores/vault-io/tests/fixtures/` (or `agents/code-wiki-agent/tests/fixtures/`)
4. Update `eval/cases/query_cases.json` with cases targeting each vault shape

### Gap 2 (BLOCKER): No baseline recordings committed — ROADMAP SC1 partially unmet

ROADMAP SC1 requires that "the baseline recorder produces a snapshot of the current lattice-wiki query output that is reproducible." No baselines are committed. The infrastructure (BaselineRecorder, eval/README.md) is correct and complete, but the one-time recording step has not been run.

**Note:** SC1 frames this as a "one-time manual step" — the baseline recorder was designed for this. The gap is that the step has not been performed and committed.

**To fix:**
1. Ensure `claude` CLI with lattice-wiki plugin is available
2. Run: `CODE_WIKI_RUN_EVAL=1 uv run --package eval-harness python -m eval_harness.baseline --cases eval/cases/query_cases.json --vault cores/vault-io/tests/fixtures/round-trip-vault --out eval/baselines/`
3. Commit the resulting `eval/baselines/*.json` files

These two gaps share a common root: the phase focused on infrastructure correctness (which is excellent) but stopped before completing the observable outputs that ROADMAP success criteria SC1 explicitly require.

---

_Verified: 2026-05-14T21:00:00Z_
_Verifier: Claude (gsd-verifier)_
