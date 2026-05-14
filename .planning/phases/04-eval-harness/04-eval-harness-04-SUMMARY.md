---
phase: 04-eval-harness
plan: "04"
subsystem: eval
tags:
  - baseline
  - subprocess
  - headless
  - tdd
  - security
dependency_graph:
  requires:
    - "04-01: eval-harness foundation (pricing, structural, conftest, query_cases.json)"
  provides:
    - eval_harness.isolation (EvalWorktree async context manager)
    - eval_harness.baseline (RunResult, _build_cmd, run_headless, BaselineRecorder, EVAL_SYSTEM_PROMPT_QA)
    - eval/README.md (baseline recording instructions)
  affects:
    - "04-02: sweep runner (uses run_headless, EvalWorktree, EVAL_SYSTEM_PROMPT_QA)"
    - "04-03: judge/report (uses baseline JSON as oracle for regression_check)"
tech_stack:
  added: []
  patterns:
    - "Port pattern: drop lattice-wiki OAuth/git/simulator sections, keep headless subprocess core"
    - "Security pattern T-4-03: subprocess command always a list; assert isinstance(cmd, list) guard"
    - "Security pattern T-4-05: case_id sanitized via re.sub before use as filename"
    - "Security pattern T-4-01: case dict validated (isinstance checks) before subprocess/file use"
    - "Baseline schema: 8 EVAL-08 fields including seed=None (claude CLI has no seed param)"
    - "Vault hash: sha256 over sorted md5s of all .md files — deterministic and stable"
key_files:
  created:
    - cores/eval-harness/src/eval_harness/isolation.py
    - cores/eval-harness/src/eval_harness/baseline.py
    - cores/eval-harness/tests/test_baseline.py
    - eval/README.md
  modified: []
key_decisions:
  - "EvalWorktree uses shutil.copytree into tempdir (not git worktree) — sufficient for read-heavy query eval"
  - "run_headless() returns (RunResult, str) tuple — answer text accumulated separately from result metadata"
  - "seed=None explicit in baseline schema for uniformity with future SweepResult snapshots"
  - "isolation.py created as prerequisite (not in plan 04 scope explicitly, but required by baseline.py import)"

patterns-established:
  - "Subprocess security: _build_cmd always returns list; shell=False implicit; prompt always final argv"
  - "_vault_content_hash: sha256 of sorted md5 digests — O(n files) but fully deterministic"

requirements-completed:
  - EVAL-03
  - EVAL-08

duration: 12min
completed: 2026-05-14
---

# Phase 04 Plan 04: Baseline Recorder Summary

**Headless `claude -p` baseline recorder with EVAL-08 reproducibility schema (8 fields incl. seed=None), T-4-03/T-4-05 security controls, and `eval/README.md` documenting how to record a baseline.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-14T~20:00Z
- **Completed:** 2026-05-14T~20:12Z
- **Tasks:** 1 (TDD: RED commit + GREEN commit)
- **Files modified:** 4 created

## Accomplishments

- `isolation.py`: EvalWorktree async context manager — `shutil.copytree` into tempdir, cleanup on `__aexit__`; simplified port from lattice-evals dropping all OAuth/git/CLAUDE_CONFIG_DIR sections
- `baseline.py`: Clean port of `runner_headless.py` with lattice-wiki-specific code dropped; one-shot `claude -p` subprocess runner with 300s timeout; `_build_cmd()` security-hardened (always list, never shell string, prompt always final argv, assert guard); `_vault_content_hash()` for EVAL-08 vault fingerprinting; `BaselineRecorder` with 8-field EVAL-08 snapshot schema; CLI entry point (`python -m eval_harness.baseline`)
- `eval/README.md`: "Recording a Baseline" section with prerequisites, exact command variants, expected output structure, and seed=null explanation

## Task Commits

TDD cycle:

1. **RED: test_baseline.py** - `9ea2f22` (test)
2. **GREEN: baseline.py + isolation.py + eval/README.md** - `a346bd4` (feat)

## Files Created/Modified

- `cores/eval-harness/src/eval_harness/isolation.py` - EvalWorktree async context manager (shutil.copytree into tempdir)
- `cores/eval-harness/src/eval_harness/baseline.py` - RunResult, _build_cmd, _spawn, run_headless, _prompt_hash, _vault_content_hash, BaselineRecorder
- `cores/eval-harness/tests/test_baseline.py` - 11 unit tests (all pass; no subprocess spawned, no Bedrock calls)
- `eval/README.md` - Baseline recording guide with prerequisites, commands, output structure

## Decisions Made

- **EvalWorktree uses copytree (not git worktree):** Read-heavy eval runs don't need git history; shutil.copytree is simpler and avoids the git auth complexity that was dropped from the lattice-evals port.
- **run_headless returns (RunResult, str) tuple:** The answer text (concatenated assistant content blocks) is needed separately from the run metadata for snapshot construction. Cleaner than embedding in RunResult.
- **isolation.py created implicitly:** The plan imports `EvalWorktree` from `eval_harness.isolation` but isolation.py wasn't in the plan's `files_modified` list. It is a structural prerequisite for baseline.py to function — created per deviation Rule 3 (blocking dependency).
- **11 tests instead of 9:** Added `test_prompt_hash_differs_on_input` and split vault content hash into two separate tests for clearer coverage of determinism vs. non-empty output.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created isolation.py (missing prerequisite)**
- **Found during:** Task 1 implementation
- **Issue:** `baseline.py` imports `from eval_harness.isolation import EvalWorktree` but `isolation.py` was not listed in `files_modified` in the plan. Without it, `baseline.py` cannot be imported.
- **Fix:** Created `cores/eval-harness/src/eval_harness/isolation.py` as a simplified port from `lattice-evals/isolation.py` (dropping OAuth, git-worktree, and CLAUDE_CONFIG_DIR sections per the PATTERNS.md guidance already written for this file).
- **Files modified:** `cores/eval-harness/src/eval_harness/isolation.py`
- **Verification:** All 11 unit tests pass; `from eval_harness.baseline import BaselineRecorder` succeeds
- **Committed in:** a346bd4 (GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking prerequisite)
**Impact on plan:** Necessary prerequisite; no scope creep. isolation.py was already designed and documented in PATTERNS.md for this phase.

## Issues Encountered

None — the port was clean and the security controls (T-4-03, T-4-01, T-4-05) were straightforward to implement.

## Known Stubs

None. All modules implement their full contracts. `run_headless()` is a real subprocess runner (not mocked); unit tests use `_build_cmd()` and `_make_snapshot()` directly to avoid subprocess spawning in the test suite.

## Threat Flags

No new security surface beyond what the plan's threat model documents:

| Threat ID | File | Mitigation Applied |
|-----------|------|--------------------|
| T-4-03 | baseline.py `_build_cmd()` | `assert isinstance(cmd, list)`; shell=False implicit; prompt as final `cmd.append()` |
| T-4-01 | baseline.py `BaselineRecorder.record()` | `isinstance(case.get("case_id"), str)` and `isinstance(case.get("query"), str)` validated before use |
| T-4-05 | baseline.py `BaselineRecorder.record()` | `re.sub(r"[^a-zA-Z0-9._-]", "_", case_id)` before filename construction |

## Self-Check

Files verified to exist:
- `cores/eval-harness/src/eval_harness/isolation.py` — FOUND
- `cores/eval-harness/src/eval_harness/baseline.py` — FOUND
- `cores/eval-harness/tests/test_baseline.py` — FOUND
- `eval/README.md` — FOUND

Commits verified: 9ea2f22 (RED), a346bd4 (GREEN) — both present in git log.

TDD Gate Compliance:
- RED commit: 9ea2f22 (`test(04-04): add failing tests for baseline recorder (RED)`) — PASSED
- GREEN commit: a346bd4 (`feat(04-04): implement baseline recorder — isolation, baseline, eval README`) — PASSED

## Self-Check: PASSED

## Next Phase Readiness

- `EvalWorktree` and `run_headless()` are ready for the sweep runner (Plan 02) to use
- `BaselineRecorder.record_all()` is ready for `make record-baseline` integration
- `eval/README.md` documents the exact command sequence for operators recording a new oracle

---
*Phase: 04-eval-harness*
*Completed: 2026-05-14*
