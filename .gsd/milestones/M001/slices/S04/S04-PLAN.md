# S04: Verify initialized GSD readiness

**Goal:** Prove the initialized GSD state is coherent, traceable, and ready for future /gsd auto or focused milestone work by restoring the missing decisions projection, composing dependency verifiers, and validating R005 readiness evidence.
**Demo:** A final consistency pass proves initialized GSD artifacts are coherent, traceable to sampled sources, and ready for future `/gsd auto` work.

## Must-Haves

- S04 is successful when `.gsd/DECISIONS.md` exists with D001-D003 concepts, `.gsd/milestones/M001/slices/S04/verify_s04_readiness.py` passes with `python3`, S02 and S03 verifiers still pass, R005 is validated or ready to validate from the S04 evidence, and closeout verifies the S04 summary file, S04 UAT artifact, and the S04 roadmap checkbox after slice completion.

## Proof Level

- This slice proves: final-assembly. Real runtime required: no product runtime, but executable artifact verification is required. Human/UAT required: no; UAT is rendered planning closeout evidence.

## Integration Closure

Consumes S01 PROJECT truth, S02 curated context verifier, S03 requirements-contract verifier, M001 roadmap, requirements projection, and decisions projection. Introduces one S04 readiness verifier as the final diagnostic surface. After closeout, nothing remains for M001 initialization except optional milestone-level validation/completion using the same evidence.

## Verification

- Adds `.gsd/milestones/M001/slices/S04/verify_s04_readiness.py` as the inspection surface for future agents to diagnose initialization drift. Failure visibility is explicit assertion output naming missing artifacts, broken dependency verifier commands, missing source references, missing roadmap dependency mapping, missing decisions concepts, or prohibited overclaims.

## Tasks

- [x] **T01: Restored the M001 decisions projection and added the composed S04 readiness verifier.** `est:45m`
  Why: S04 acceptance requires PROJECT, REQUIREMENTS, CONTEXT, DECISIONS, and ROADMAP artifacts, but the worktree currently lacks `.gsd/DECISIONS.md`. A final verifier is also needed so readiness is executable rather than prose-only. Expected executor skills: `verify-before-complete`, `python-testing-patterns`, `write-docs`.
  - Files: `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/DECISIONS.md`, `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S04/verify_s04_readiness.py`
  - Verify: python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py

- [x] **T02: Validated R005 in the requirements projection after fresh S02, S03, and S04 readiness checks.** `est:30m`
  Why: R005 remains the only active M001 initialization requirement and is owned by S04. It should be validated only after the composed readiness verifier passes with fresh evidence. Expected executor skills: `verify-before-complete`, `python-testing-patterns`.
  - Files: `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`
  - Verify: python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py

## Files Likely Touched

- /Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/DECISIONS.md
- /Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S04/verify_s04_readiness.py
- /Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md
