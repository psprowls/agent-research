---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: Added an executable S03 requirements verifier and validated R004 with passing verifier evidence.

Expected executor skills: verify-before-complete, write-docs.

Why: S03 needs closeout-safe proof that the normalized contract remains internally consistent and honest after DB-backed rendering. A verifier gives S04 and future agents one authoritative diagnostic for missing buckets, broken owner mapping, missing source references, or prohibited affirmative overclaims.

Do: Create `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py`, following the pattern of `.gsd/milestones/M001/slices/S02/verify_s02_context.py` but targeting requirements. The script should assert that `.gsd/REQUIREMENTS.md` exists and is non-empty; active/validated requirements are present and owner-mapped to S01-S04; deferred future-work requirements mention cost-frontier sweep rerun/winner-selection and optional archive index as deferred/future, not active M001 work; anti-feature/out-of-scope requirements prohibit wholesale `.planning` conversion, reusable migration/backfill tooling, blind legacy plan resumption or exhaustive audit, and M001 sweep execution; required source references appear; and prohibited affirmative overclaims are absent. Use negation-aware checks so honest exclusions are allowed. Run the verifier with `python3`. After it passes, update R004 validation/status through the GSD requirement update tool with the fresh verifier evidence, then rerun the verifier so the final rendered requirements still pass.

Failure Modes (Q5): If the verifier fails because requirements are missing generated IDs or labels, fix the DB-backed requirement records rather than weakening the verifier; if phrase checks are brittle, adjust toward concept-level/negation-aware assertions; if `python` is unreliable, use `python3` explicitly.

Negative Tests (Q7): The verifier must fail on missing owner mapping, missing deferred labels, missing source references, and affirmative overclaims such as `M001 completed wholesale conversion`, `M001 ran the sweep`, `authoritative cost-frontier winners selected`, or `legacy audits backfilled`.

Done when: `python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py` exits 0 after R004 validation has been recorded, and the task evidence names the passing command.

## Inputs

- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-CONTEXT.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S02/verify_s02_context.py`

## Expected Output

- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S03/verify_s03_requirements.py`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`

## Verification

python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py

## Observability Impact

Adds the durable S03 diagnostic script that future agents and S04 can run to localize requirements-contract drift.
