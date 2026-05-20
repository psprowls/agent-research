---
phase: 07-cost-frontier-sweep
plan: "02"
subsystem: agent-commands
tags: [model-override, single-role-swap, chatbedrockconverse, sweep-runner, tdd]

# Dependency graph
requires:
  - phase: 07-01
    provides: test scaffolds and models.toml sweep_candidates arrays that define the roles to sweep
provides:
  - role_model_overrides dict parameter on run_query (librarian, synthesizer, code_reader)
  - model_override: str | None parameter on run_scan, run_lint, run_ingest_source
  - backward-compatible librarian_model_override alias on run_query
  - unit test file agents/graph-wiki-agent/tests/test_command_overrides.py (7 tests)
affects: [07-05-sweep-runner, future-sweep-runner-plans]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Override resolution: (role_model_overrides or {}).get(role) for safe None-guard"
    - "load_role_config(role) for region and max_tokens when constructing ChatBedrockConverse from override"
    - "Closure model_override capture: pass model_override through _semantic_pass so run_linter_group closure can use it"
    - "TDD RED/GREEN: write all 7 tests first (fail), then implement (pass)"
    - "Pool task executor mock: make pool.run_all invoke the task function to test closures inside it"

key-files:
  created:
    - agents/graph-wiki-agent/tests/test_command_overrides.py
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py

key-decisions:
  - "Override resolution via (role_model_overrides or {}).get(role) guards against None without an explicit 'if role_model_overrides' branch, matching the PATTERNS.md shape"
  - "role_model_overrides['librarian'] takes precedence over deprecated librarian_model_override via 'or' chaining"
  - "_semantic_pass gains model_override: str | None = None parameter so the run_linter_group closure can capture it from the enclosing scope"
  - "Test for linter: pool.run_all mock must invoke the task function (run_linter_group) to exercise the closure — static FanOutResult mock would silently skip the override path"
  - "ChatBedrockConverse always uses region_name and max_tokens from load_role_config; caller cannot supply region (T-07-03 mitigated)"

patterns-established:
  - "single-role-swap: only the named role in role_model_overrides gets the candidate; all others fall through to make_llm"
  - "LLM construction gate: if model_override is not None: ChatBedrockConverse(model_id=override, region_name=cfg['region'], max_tokens=cfg['max_tokens']) else: make_llm('role')"
  - "Pool mock pattern for closure testing: async _mock_run_all(items, task, **kwargs) that calls await task(item) per item"

requirements-completed: [SWEEP-01]

# Metrics
duration: 9min
completed: 2026-05-17
---

# Phase 7 Plan 02: Command Override Surfaces Summary

**Per-role model_override surfaces added to all six agent command entry points, enabling D-06 single-role-swap sweep protocol with 7 unit tests asserting override threading and backward compatibility.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-17T03:53:06Z
- **Completed:** 2026-05-17T04:01:32Z
- **Tasks:** 3 (with TDD RED/GREEN cycle)
- **Files modified:** 5 (4 command files + 1 test file)

## Accomplishments

- Extended `run_query` with `role_model_overrides: dict[str, str] | None` supporting librarian, synthesizer, and code_reader roles; `_run_code_fallback` gains `code_reader_override: str | None = None`
- Added `model_override: str | None = None` to `run_scan`, `run_lint`, and `run_ingest_source`; each conditionally constructs `ChatBedrockConverse` with config from `load_role_config`
- Created `test_command_overrides.py` with 7 passing unit tests; `test_run_query_other_roles_unaffected` directly asserts D-06 single-role-swap protocol
- All 158 pre-existing tests remain green; no regressions

## Task Commits

Each task was committed atomically:

1. **RED phase: failing tests** — `d9f68ff` (test: add failing tests for per-role model_override surfaces)
2. **Task 1 GREEN: run_query** — `2745a82` (feat: extend run_query with role_model_overrides)
3. **Task 2 GREEN: scan/lint/ingest** — `75406f1` (feat: add model_override to run_scan, run_lint, run_ingest_source)
4. **Task 3 fix: lint mock** — `b69751d` (test: fix lint test mock to execute run_linter_group closure)

## Override Resolution Table

| Role | Parameter | Command Function | Override Path |
|------|-----------|-----------------|---------------|
| librarian | `role_model_overrides["librarian"]` or `librarian_model_override` | `run_query` | Step 6 LLM construction |
| synthesizer | `role_model_overrides["synthesizer"]` | `run_query` | Step 7 synth_llm construction |
| code_reader | `role_model_overrides["code_reader"]` | `run_query` -> `_run_code_fallback` | code_reader_override parameter |
| scanner | `model_override` | `run_scan` | before SubagentPool fan-out |
| linter | `model_override` | `run_lint` -> `_semantic_pass` -> `run_linter_group` | closure capture |
| ingestor | `model_override` | `run_ingest_source` | Step 5 LLM construction |

## Files Created/Modified

- `agents/graph-wiki-agent/tests/test_command_overrides.py` — 7 unit tests proving each override surface routes to ChatBedrockConverse with the candidate model_id; includes D-06 single-role-swap assertion and librarian backward-compat test
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` — role_model_overrides parameter, synthesizer override, _run_code_fallback code_reader_override parameter, updated librarian resolution
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — ChatBedrockConverse import, model_override parameter and conditional LLM construction
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` — ChatBedrockConverse import, model_override threaded through _semantic_pass into run_linter_group closure
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` — ChatBedrockConverse import, load_role_config import, model_override parameter and conditional LLM construction

## Decisions Made

- `(role_model_overrides or {}).get(role)` pattern used throughout (not `role_model_overrides.get(role) if role_model_overrides else None`) to match PATTERNS.md idiom
- `_semantic_pass` signature extended with `model_override: str | None = None` rather than reading from closure — makes the parameter explicit and avoids relying on Python's closure capture of a variable that could be rebound
- Lint test uses a real task-executor mock (`async _mock_run_all`) rather than a static `FanOutResult` to verify the closure path; static mock would silently pass without exercising the override

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lint test mock did not invoke the task closure**
- **Found during:** Task 3 GREEN verification (test_run_lint_model_override)
- **Issue:** Static `FanOutResult` mock caused `run_linter_group` to never execute, so `ChatBedrockConverse` was never called inside the closure, making the assertion vacuously fail
- **Fix:** Replaced with `_mock_run_all` that calls `await task(item)` per item; also added `domain_placement` and `dependency_layer` keys to `_module_pass` mock to match `LintResult` field set; added non-empty pages fixture so `page_quality` group fires
- **Files modified:** `agents/graph-wiki-agent/tests/test_command_overrides.py`
- **Verification:** `test_run_lint_model_override` passes; ChatBedrockConverse called once with candidate model_id
- **Committed in:** `b69751d`

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test mock)
**Impact on plan:** Necessary to correctly prove the linter override path. No scope creep.

## Threat Surface Scan

T-07-03 mitigated: `region_name` and `max_tokens` in every ChatBedrockConverse construction come from `load_role_config(role)`, not from the caller. No new cross-region routing surface introduced.

## Issues Encountered

None beyond the lint test mock issue (documented as deviation above).

## Known Stubs

None — all override surfaces wire to real ChatBedrockConverse construction. No placeholder values.

## Next Phase Readiness

- Plan 07-05 (sweep runner) can now call `run_query(role_model_overrides={"librarian": candidate})` to swap one role at a time
- `run_scan(model_override=candidate)`, `run_lint(model_override=candidate)`, `run_ingest_source(source_path, model_override=candidate)` ready for sweep driver
- All command defaults unchanged when model_override is None

---
*Phase: 07-cost-frontier-sweep*
*Completed: 2026-05-17*
