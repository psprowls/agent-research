---
estimated_steps: 3
estimated_files: 2
skills_used: []
---

# T01: Restored the M001 decisions projection and added the composed S04 readiness verifier.

Why: S04 acceptance requires PROJECT, REQUIREMENTS, CONTEXT, DECISIONS, and ROADMAP artifacts, but the worktree currently lacks `.gsd/DECISIONS.md`. A final verifier is also needed so readiness is executable rather than prose-only. Expected executor skills: `verify-before-complete`, `python-testing-patterns`, `write-docs`.

Do: First restore the compact `.gsd/DECISIONS.md` projection for D001-D003 from the inlined decision context without creating duplicate DB decisions. Then create `.gsd/milestones/M001/slices/S04/verify_s04_readiness.py`. The verifier must use `python3`-safe standard-library code, run the S02 and S03 verifier scripts as subprocesses, and perform S04-specific checks only: required artifacts exist and are non-empty; S01-S03 summaries exist; roadmap lists S01-S04 with dependency order and the `S04 → Future milestones` boundary; requirements show R001-R004 validated, R005 active or validated and owned by M001/S04, R006-R007 deferred, and R008-R011 out-of-scope without active M001 owners; decisions include the three required concepts; sampled `.planning` and package manifest source paths exist; and prohibited affirmative overclaims are absent. Keep negative checks negation-aware so exclusions such as `not wholesale conversion` remain allowed.

Done when: the decisions projection exists, the S04 verifier exists, and `python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py` exits 0 before R005 validation.

## Inputs

- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/PROJECT.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-CONTEXT.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-ROADMAP.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S01/S01-SUMMARY.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S02/S02-SUMMARY.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S03/S03-SUMMARY.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S02/verify_s02_context.py`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S03/verify_s03_requirements.py`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/PROJECT.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/ROADMAP.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/MILESTONES.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/milestones/v1.11-ROADMAP.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/CONTINUE-sweep-harness-fixes-3.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/deferred-items.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/pyproject.toml`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/agents/graph-wiki-agent/pyproject.toml`

## Expected Output

- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/DECISIONS.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S04/verify_s04_readiness.py`

## Verification

python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py

## Observability Impact

Creates the final readiness diagnostic. Negative tests should include missing-artifact detection, dependency-verifier failure propagation, missing decision concepts, missing roadmap dependency mapping, and affirmative-overclaim rejection.
