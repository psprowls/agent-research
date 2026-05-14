---
phase: 04-eval-harness
plan: "01"
subsystem: eval-harness
tags:
  - eval
  - pricing
  - structural-checks
  - bedrock
  - tdd
dependency_graph:
  requires:
    - "03-query-vertical-slice"
  provides:
    - eval_harness.pricing (cost_for_usage, PRICES, UnknownModelError)
    - eval_harness.structural (check_structural, 7 EVAL-06 keys)
    - eval/cases/query_cases.json (4 fixture-based eval cases)
    - run_query() librarian_model_override parameter
    - pool.py _write_trace() real cost_usd accounting
  affects:
    - cores/subagent-runtime/src/subagent_runtime/pool.py
    - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
    - cores/model-adapter/src/model_adapter/models.toml
tech_stack:
  added:
    - "eval-harness workspace member (cores/eval-harness)"
    - "deepeval>=4.0.0"
    - "pytest-evals>=0.3.4"
    - "python-frontmatter>=1.1.0 (used in structural.py)"
  patterns:
    - "TDD RED/GREEN cycle for pricing and structural modules"
    - "Lazy import pattern for optional eval-harness dep in subagent-runtime pool.py"
    - "Citation resolution: exact match then glob fallback (base filename)"
key_files:
  created:
    - cores/eval-harness/pyproject.toml
    - cores/eval-harness/src/eval_harness/__init__.py
    - cores/eval-harness/src/eval_harness/pricing.py
    - cores/eval-harness/src/eval_harness/structural.py
    - cores/eval-harness/tests/conftest.py
    - cores/eval-harness/tests/test_pricing.py
    - cores/eval-harness/tests/test_structural.py
    - eval/cases/query_cases.json
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/commands/query.py
    - cores/subagent-runtime/src/subagent_runtime/pool.py
    - cores/model-adapter/src/model_adapter/models.toml
    - uv.lock
decisions:
  - "Lazy import in pool.py: eval_harness imported inside try/except inside _compute_cost_usd() so subagent-runtime has no hard dependency on eval-harness (per D-05)"
  - "Citation resolution uses exact match first, then glob on basename — handles packages stored as subdirectories (e.g. packages/lattice-wiki-core/ directory with lattice-wiki-core.md inside)"
  - "judge_b changed from claude-sonnet-4-6 to nova-pro-v1:0 per D-07 (cost-frontier evaluation)"
  - "UnknownModelError is a subclass of KeyError — caught explicitly alongside ImportError in pool.py fallback"
metrics:
  duration: "325s"
  completed: "2026-05-14"
  tasks_completed: 3
  files_changed: 12
---

# Phase 04 Plan 01: Eval Harness — Foundation and Infrastructure Summary

**One-liner:** `eval-harness` workspace package with Bedrock pricing table (9 models), EVAL-06 structural checker (7 keys), `run_query` model override hook, and real cost accounting in pool traces.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1a | Scaffold eval-harness package — pyproject, __init__, conftest, eval cases | 03421d2 | pyproject.toml, __init__.py, conftest.py, query_cases.json, uv.lock |
| 1b (RED) | Add failing tests for pricing and structural modules | 1a53aac | test_pricing.py, test_structural.py |
| 1b (GREEN) | Implement pricing and structural modules | 0f2dbe5 | pricing.py, structural.py |
| 2 | Modify query.py, pool.py, and models.toml | 79a24d0 | query.py, pool.py, models.toml, ruff-sorted test files |

## What Was Built

### eval-harness workspace package

New `cores/eval-harness/` package registered as a `uv` workspace member. Declares `deepeval>=4.0.0`, `pytest-evals>=0.3.4`, `python-frontmatter>=1.1.0`, and workspace deps on `code-wiki-agent`, `subagent-runtime`, `model-adapter`.

### eval_harness.pricing

Ported from `lattice-evals/pricing.py` with extensions:
- 3 original Claude model entries with cache keys (opus-4-7, sonnet-4-6, haiku-4-5)
- 6 new Bedrock entries (claude-haiku/sonnet via cross-region profiles, nova-pro, nova-lite, nova-micro, qwen3-32b)
- `cost_for_usage(model, usage)` sums only the keys present in the model's price dict — Bedrock non-Claude models have no `cache_read`/`cache_write` keys
- `UnknownModelError(KeyError)` for unknown model IDs

### eval_harness.structural

`check_structural(result: QueryResult, vault_path: Path) -> dict` returning all 7 EVAL-06 keys:

| Key | Description |
|-----|-------------|
| `has_citation` | citations list is non-empty |
| `citations_resolve` | all citation slugs resolve to an .md file (vacuously True if empty) |
| `unresolved_citations` | list of slugs that did not resolve |
| `pages_drilled_positive` | pages_drilled > 0 |
| `has_code_path` | answer contains a path-like string |
| `frontmatter_valid` | all citation pages have a non-empty `title` in frontmatter |
| `json_schema_valid` | result fields are correct types |

T-4-01 security: `isinstance(result, QueryResult)` check raises `TypeError` before any field access.

### run_query() model override

`librarian_model_override: str | None = None` added to `run_query()`. When set, constructs `ChatBedrockConverse(model_id=override, region_name=..., max_tokens=...)` directly instead of calling `make_llm("librarian")`. This is the hook the eval sweep runner (Plan 02) uses to test model alternatives holding prompts fixed.

### pool.py cost accounting

Replaced `"cost_usd": None` with `"cost_usd": _compute_cost_usd(model_id, tokens_in, tokens_out)`. The helper uses a lazy import of `eval_harness.pricing` inside a try/except — subagent-runtime has no hard dependency on eval-harness; if eval-harness is not installed, cost_usd gracefully returns None.

### models.toml

`[roles.judge_b]` `model_id` changed from `"us.anthropic.claude-sonnet-4-6"` to `"us.amazon.nova-pro-v1:0"` per D-07 — the eval sweep will compare Sonnet vs Nova Pro as judge candidates.

### eval/cases/query_cases.json

4 eval cases based on the round-trip-vault fixture:
- Package lookup: "What does lattice-wiki-core do?"
- Concept: "How does the wiki index work?"
- Cross-reference: "Which packages use lattice-source-parser?"
- Format: "What is the log.md format?"

## Test Coverage

17 unit tests added across test_pricing.py and test_structural.py. All deterministic, no Bedrock calls required.

- TDD RED phase committed (1a53aac) with import failures confirming tests ran before modules existed
- TDD GREEN phase committed (0f2dbe5) with all 17 tests passing
- Full regression: 12 subagent-runtime tests + 55 code-wiki-agent tests still green

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Functionality] Added UnknownModelError to except clause in pool.py**
- **Found during:** Task 2
- **Issue:** `UnknownModelError` was imported but not caught — ruff F401 flagged it as unused
- **Fix:** Added `UnknownModelError` to the except tuple `(ImportError, KeyError, UnknownModelError)` — this is the correct behavior since `cost_for_usage` raises it, and `KeyError` alone would not catch the subclass consistently across Python versions
- **Files modified:** `cores/subagent-runtime/src/subagent_runtime/pool.py`
- **Commit:** 79a24d0

**2. [Rule 2 - Code Quality] Ruff import sort fixes**
- **Found during:** Task 2 verification
- **Issue:** `ruff check --fix` corrected I001 import ordering in structural.py, test_pricing.py, test_structural.py (formatting pass only, no logic change)
- **Files modified:** 3 eval-harness files
- **Commit:** 79a24d0

## Known Stubs

None. All modules implement their full contracts. The `eval/cases/query_cases.json` `expected_answer` values are short plausible phrases (not verbatim vault content) — this is intentional per the plan spec and appropriate for structural scoring in Plan 02's sweep runner.

## Self-Check: PASSED

Files verified to exist:
- `cores/eval-harness/pyproject.toml` — FOUND
- `cores/eval-harness/src/eval_harness/pricing.py` — FOUND
- `cores/eval-harness/src/eval_harness/structural.py` — FOUND
- `cores/eval-harness/tests/conftest.py` — FOUND
- `cores/eval-harness/tests/test_pricing.py` — FOUND
- `cores/eval-harness/tests/test_structural.py` — FOUND
- `eval/cases/query_cases.json` — FOUND

Commits verified: 03421d2, 1a53aac, 0f2dbe5, 79a24d0 — all present in git log.

TDD Gate Compliance:
- RED commit: 1a53aac (`test(04-01): add failing tests...`) — PASSED
- GREEN commit: 0f2dbe5 (`feat(04-01): implement pricing and structural...`) — PASSED
