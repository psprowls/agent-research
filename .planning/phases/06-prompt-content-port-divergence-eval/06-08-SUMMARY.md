---
phase: 06-prompt-content-port-divergence-eval
plan: 08
subsystem: testing
tags: [divergence-eval, programmatic-checks, rubrics, pytest, eval-harness]

requires:
  - phase: 06-02
    provides: test scaffold (test_divergence_checks.py skip-stubs)
  - phase: 06-04
    provides: vault-io round-trip-vault fixture used by fixture_vault_path
  - phase: 06-05
    provides: ingestor prompt content driving ING-001..006 check semantics
  - phase: 06-06
    provides: linter prompt content driving LNT-001..005 check semantics
  - phase: 06-07
    provides: scanner prompt content driving SCN-001..005 check semantics

provides:
  - DivergenceCheck dataclass, Verdict NamedTuple, AgentOutputProxy dataclass (check.py)
  - 15 programmatic divergence rules across 4 role modules (librarian, ingestor, linter, scanner)
  - 4 LLM-judge rubric files with provenance headers (rubrics/*.md)
  - ROLE_CHECKS and ROLE_RUBRICS re-exported from divergence/__init__.py
  - 37 unit tests covering all 15 rules (passing + failing cases per rule)

affects:
  - 06-09 (DivergenceMetric wraps ROLE_CHECKS and ROLE_RUBRICS)
  - 06-10 (baseline gate reads accepted_failures from check callables)
  - 06-11 (integration tests seed the vault and run the full metric)

tech-stack:
  added: []
  patterns:
    - "_get_check(checks, rule_id) helper isolates test code from list ordering"
    - "AgentOutputProxy as thin wrapper to decouple check interface from agent command types"
    - "Verdict(passed, excerpt) carries both gate result and evidence string for accepted_failures"
    - "Per-role *_CHECKS list constant pattern — one list per role, imported by ROLE_CHECKS dict"

key-files:
  created:
    - cores/eval-harness/src/eval_harness/divergence/__init__.py
    - cores/eval-harness/src/eval_harness/divergence/check.py
    - cores/eval-harness/src/eval_harness/divergence/librarian.py
    - cores/eval-harness/src/eval_harness/divergence/ingestor.py
    - cores/eval-harness/src/eval_harness/divergence/linter.py
    - cores/eval-harness/src/eval_harness/divergence/scanner.py
    - cores/eval-harness/src/eval_harness/divergence/rubrics/librarian.md
    - cores/eval-harness/src/eval_harness/divergence/rubrics/ingestor.md
    - cores/eval-harness/src/eval_harness/divergence/rubrics/linter.md
    - cores/eval-harness/src/eval_harness/divergence/rubrics/scanner.md
  modified:
    - cores/eval-harness/tests/test_divergence_checks.py

key-decisions:
  - "Verdict is a NamedTuple (not dataclass) because verdicts are immutable result objects"
  - "AgentOutputProxy.page_type defaults to empty string so non-ingestor callers omit it"
  - "ING-003/ING-004 return Verdict(passed=True) on missing page_type to avoid double-reporting (ING-002 owns missing-field detection)"
  - "LIB-001 passes vacuously when answer has no wikilinks (citation presence is LIB-002's job)"
  - "Rubric files use HTML-comment provenance headers (markdown has no native comment syntax)"
  - "_resolve_citation reused from eval_harness.structural — no re-implementation"

patterns-established:
  - "Programmatic check pattern: pure function (AgentOutputProxy, Path) -> Verdict with no side effects"
  - "Fail-safe defaults: checks that depend on earlier checks pass vacuously when the prereq would have caught the issue"
  - "Test naming: test_{rule_id_lowered}_passes_on_{valid_case} / test_{rule_id_lowered}_fails_on_{violating_case}"

requirements-completed: [EVAL-11]

duration: 45min
completed: 2026-05-15
---

# Phase 06 Plan 08: Divergence Rule Infrastructure Summary

**15 programmatic divergence check rules (LIB/ING/LNT/SCN), 4 LLM-judge rubrics, and 37 unit tests delivering EVAL-11 — all pure-Python, no Bedrock dependency**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-15T00:00:00Z
- **Completed:** 2026-05-15T00:45:00Z
- **Tasks:** 4 (Tasks 1-3 landed on main before this executor; Task 4 executed here)
- **Files modified:** 11

## Accomplishments

- Created DivergenceCheck / Verdict / AgentOutputProxy dataclass schema locked per D-08
- Implemented 15 programmatic check rules across 4 per-role modules: LIB-001..004, ING-001..004, LNT-001..003, SCN-001..004
- Created 4 LLM-judge rubric files (LIB-005/006, ING-005/006, LNT-004/005, SCN-005) with HTML-comment provenance headers
- Exposed ROLE_CHECKS and ROLE_RUBRICS dicts from divergence/__init__.py for 06-09 and 06-10 consumption
- Replaced all skip-stubs in test_divergence_checks.py with 37 assertion-based tests; all green

## Task Commits

Each task was committed atomically:

1. **Task 1: Create divergence/check.py + divergence/__init__.py** - `9d952eb` (feat)
2. **Task 2: Create per-role programmatic check modules** - `521b0f7` (feat)
3. **Task 3: Create LLM-judge rubric .md files + populate __init__.py re-export** - `a1c1eb9` (feat)
4. **Task 4: Expand test_divergence_checks.py with 37 unit tests** - `72cc605` (test)

## Files Created/Modified

- `cores/eval-harness/src/eval_harness/divergence/__init__.py` - Re-exports ROLE_CHECKS, ROLE_RUBRICS, DivergenceCheck, Verdict, AgentOutputProxy
- `cores/eval-harness/src/eval_harness/divergence/check.py` - DivergenceCheck dataclass, Verdict NamedTuple, AgentOutputProxy dataclass
- `cores/eval-harness/src/eval_harness/divergence/librarian.py` - LIB-001..004 check callables + LIBRARIAN_CHECKS list
- `cores/eval-harness/src/eval_harness/divergence/ingestor.py` - ING-001..004 check callables + INGESTOR_CHECKS list
- `cores/eval-harness/src/eval_harness/divergence/linter.py` - LNT-001..003 check callables + LINTER_CHECKS list
- `cores/eval-harness/src/eval_harness/divergence/scanner.py` - SCN-001..004 check callables + SCANNER_CHECKS list
- `cores/eval-harness/src/eval_harness/divergence/rubrics/librarian.md` - LIB-005/006 judge rubric
- `cores/eval-harness/src/eval_harness/divergence/rubrics/ingestor.md` - ING-005/006 judge rubric
- `cores/eval-harness/src/eval_harness/divergence/rubrics/linter.md` - LNT-004/005 judge rubric
- `cores/eval-harness/src/eval_harness/divergence/rubrics/scanner.md` - SCN-005 judge rubric
- `cores/eval-harness/tests/test_divergence_checks.py` - 37 unit tests covering all 15 programmatic rules

## Decisions Made

- Verdict is a NamedTuple rather than dataclass — immutable result objects, matching PATTERNS spec
- ING-003/ING-004 return pass vacuously when page_type is absent — avoids double-reporting with ING-002
- LIB-001 passes vacuously on answer with no wikilinks — citation presence is LIB-002's domain
- Reused `_resolve_citation` from `eval_harness.structural` for wikilink resolution in LIB-001 — no duplication

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None. All 15 checks are fully implemented and exercised by tests.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. Check callables are pure string/regex operations, consistent with threat model T-06-15 (no eval/exec of LLM output).

## Next Phase Readiness

- ROLE_CHECKS and ROLE_RUBRICS are ready for 06-09 (DivergenceMetric class)
- Verdict.excerpt strings carry evidence suitable for the accepted_failures array in 06-10 baseline gate
- All 37 unit tests green under `uv run pytest cores/eval-harness/tests/test_divergence_checks.py -x` without Bedrock

---
*Phase: 06-prompt-content-port-divergence-eval*
*Completed: 2026-05-15*
