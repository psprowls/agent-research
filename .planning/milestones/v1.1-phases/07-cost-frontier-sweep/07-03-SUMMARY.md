---
phase: 07-cost-frontier-sweep
plan: "03"
subsystem: config+fixtures
tags: [config, fixtures, models-toml, vault-thin, sweep-candidates]
requirements: [SWEEP-01]

dependency_graph:
  requires: ["07-01"]
  provides: ["sweep_candidates config for 07-05", "vault-thin fixtures for code_reader sweep"]
  affects: ["cores/model-adapter/src/model_adapter/models.toml", "eval/cases/code_reader_cases.json"]

tech_stack:
  added: []
  patterns: ["TOML sibling-key extension", "dedicated fixture file per role"]

key_files:
  created:
    - eval/cases/code_reader_cases.json
    - cores/eval-harness/tests/test_models_toml_sweep_candidates.py
  modified:
    - cores/model-adapter/src/model_adapter/models.toml
    - cores/model-adapter/models.toml

decisions:
  - "D-05: sweep_candidates as sibling of model_id in each [roles.{name}] block — loader-transparent (Tension 8 verified)"
  - "D-09: vault-thin cases in dedicated code_reader_cases.json (not appended to query_cases.json) — keeps non-code_reader sweep loops simple"
  - "D-01: judges (judge_a, judge_b) and aliases (haiku, sonnet) excluded from sweep_candidates"

metrics:
  duration: "3 minutes"
  completed: "2026-05-17"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 2
---

# Phase 7 Plan 03: sweep_candidates Config + Vault-Thin Fixtures Summary

**One-liner:** Added tier-to-role sweep_candidates arrays to six models.toml role blocks (D-03/D-05) and three vault-thin code_reader fixture cases (D-09), with loader-tolerance unit tests pinning the spec.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add sweep_candidates to six role blocks | 069a4a7 | cores/model-adapter/src/model_adapter/models.toml |
| 2 | Label stale stub TOML; create vault-thin fixtures | ad84a63 | cores/model-adapter/models.toml, eval/cases/code_reader_cases.json |
| 3 | Unit tests: loader tolerance + tier-to-role spec | ed910c8 | cores/eval-harness/tests/test_models_toml_sweep_candidates.py |

## Per-Role Candidate Map (D-03)

| Role | Tier | Candidates |
|------|------|-----------|
| librarian | quality | us.anthropic.claude-sonnet-4-6, us.anthropic.claude-haiku-4-5-20251001-v1:0, us.amazon.nova-pro-v1:0, qwen.qwen3-32b-v1:0 |
| synthesizer | quality | us.anthropic.claude-sonnet-4-6, us.anthropic.claude-haiku-4-5-20251001-v1:0, us.amazon.nova-pro-v1:0, qwen.qwen3-32b-v1:0 |
| linter | mid | us.anthropic.claude-haiku-4-5-20251001-v1:0, us.amazon.nova-pro-v1:0, us.amazon.nova-lite-v1:0, qwen.qwen3-32b-v1:0 |
| ingestor | mid | us.anthropic.claude-haiku-4-5-20251001-v1:0, us.amazon.nova-pro-v1:0, us.amazon.nova-lite-v1:0, qwen.qwen3-32b-v1:0 |
| scanner | cheap-fast | us.anthropic.claude-haiku-4-5-20251001-v1:0, us.amazon.nova-micro-v1:0, us.amazon.nova-lite-v1:0, qwen.qwen3-32b-v1:0 |
| code_reader | cheap-fast | us.anthropic.claude-haiku-4-5-20251001-v1:0, us.amazon.nova-micro-v1:0, us.amazon.nova-lite-v1:0, qwen.qwen3-32b-v1:0 |

## Vault-Thin Fixture Queries (D-09)

| case_id | query | tags |
|---------|-------|------|
| code-reader-01 | How is _StdoutGuard implemented in the MCP server? | code-reader, vault-thin |
| code-reader-02 | What does SubagentPool._write_trace write to the trace JSONL file? | code-reader, vault-thin |
| code-reader-03 | What are the exact parameters to _read_file_bounded? | code-reader, vault-thin |

These queries cannot be answered from the round-trip-vault fixture pages. They force the librarian fan-out to return empty useful_excerpts, causing _run_code_fallback to fire during code_reader sweep cells.

## Loader Tolerance Test Outcome

6 tests written and passing:
- `test_sweep_candidates_present_for_all_six_roles` — all six roles, 4 candidates each
- `test_tier_to_role_candidate_map` — D-03 quality/mid/cheap-fast tier assignments
- `test_no_sweep_candidates_for_judges` — judge_a/judge_b excluded per D-01
- `test_all_candidates_have_pricing` — every candidate model_id is in eval_harness.pricing.PRICES
- `test_make_llm_still_works_for_all_roles` — make_llm() unaffected by new key (Tension 8)
- `test_code_reader_cases_json_loads` — 3 cases, all tagged vault-thin

Full suite: 113 tests pass, 20 skipped (pending Plans 07-05+), no regressions.

## Decisions Made

- **D-05 placement:** `sweep_candidates` added as a sibling of `model_id` (not a nested `[roles.{name}.sweep]` subtable). Python's `tomllib` includes unknown keys in the returned dict transparently; `load_role_config()` returns the full dict. `make_llm()` reads only `model_id`, `region`, `max_tokens` — ignores new key. Zero loader changes required.
- **D-09 file separation:** Vault-thin cases live in `eval/cases/code_reader_cases.json` (not appended to `query_cases.json`). This keeps non-code_reader sweep loops simple — no per-case role filtering needed.
- **Pitfall 5 mitigation:** Added `# STUB:` notice to top-level `cores/model-adapter/models.toml` identifying it as inert and pointing to `src/model_adapter/models.toml` as the source of truth.

## Deviations from Plan

None — plan executed exactly as written.

- Task 3's test scaffold from Plan 07-01 did not exist; tests authored from scratch under the same conventions as existing test files. This is the documented fallback in the plan's action block ("if not part of 07-01 — author it now").
- Path resolution in `test_code_reader_cases_json_loads` required one correction (4 parents, not 5) to match the workspace layout; caught and fixed before commit.

## Known Stubs

None. All sweep_candidates arrays contain real, priced model IDs. The vault-thin fixture expected_answer strings describe the source-only nature of answers but are not misleading stubs — they are intentionally minimal since the sweep quality signal comes from the judge panel, not expected_answer comparison.

## Self-Check: PASSED

Files confirmed present:
- cores/model-adapter/src/model_adapter/models.toml — FOUND
- eval/cases/code_reader_cases.json — FOUND
- cores/eval-harness/tests/test_models_toml_sweep_candidates.py — FOUND

Commits confirmed:
- 069a4a7 — feat(07-03): add sweep_candidates arrays
- ad84a63 — chore(07-03): label stale stub TOML; add vault-thin fixtures
- ed910c8 — test(07-03): add loader tolerance + tier-to-role spec tests
