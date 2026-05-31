# S03: Normalize capability contract

**Goal:** Normalize the DB-backed requirements contract so future agents can distinguish active M001 initialization requirements, deferred future work, and explicit out-of-scope archive-conversion anti-features with source-path traceability.
**Demo:** REQUIREMENTS separates active initialization requirements, deferred future work, and explicit out-of-scope archive conversion.

## Must-Haves

- `.gsd/REQUIREMENTS.md` is rendered from GSD requirement records and is non-empty.
- Active/validated initialization requirements are owner-mapped to slices: R001 to S01, R002 and R003 to S02, R004 to S03, and R005 to S04.
- Deferred future-work records are clearly labeled deferred and include the cost-frontier sweep rerun/winner-selection handoff and optional archive index without active M001 execution ownership.
- Out-of-scope/anti-feature records explicitly reject wholesale `.planning` conversion, reusable migration/backfill tooling, blind legacy plan resumption or exhaustive archive audit, and M001 cost-frontier execution.
- Requirements cite the relevant current and sampled legacy sources: `.gsd/PROJECT.md`, `.gsd/milestones/M001/M001-CONTEXT.md`, `.planning/CONTINUE-sweep-harness-fixes-3.md`, `.planning/deferred-items.md`, `.planning/PROJECT.md`, and `.planning/MILESTONES.md`.
- A slice verifier passes with `python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py` and protects against affirmative overclaims such as completed wholesale conversion, completed sweep execution, selected authoritative cost-frontier winners, or backfilled legacy audits.

## Proof Level

- This slice proves: Contract-level planning proof. This slice exercises rendered GSD artifacts and an executable verifier; no product runtime or human UAT is required. Requirement impact: R004 is owned directly, R005 is supported, and R001-R003 must remain consistent with their validated S01/S02 posture. Threat surface is limited to planning artifacts; no auth, network, user-input runtime, secrets, or data-exposure surface is introduced.

## Integration Closure

Consumes S01 current-truth framing and S02 curated high-note/caveat context, then produces the normalized requirement contract that S04 will validate during final initialized-readiness checks. No runtime wiring is introduced; the integration boundary is cross-artifact consistency among PROJECT, M001-CONTEXT, ROADMAP, and REQUIREMENTS.

## Verification

- Adds/updates artifact-level diagnostics only. The future inspection surface is `.gsd/REQUIREMENTS.md` plus `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py`; failures should identify missing buckets, owner mappings, source references, or prohibited overclaims.

## Tasks

- [x] **T01: Rendered the DB-backed requirements contract and normalized active M001 requirement ownership for R001 through R005.** `est:45m`
  Expected executor skills: write-docs, verify-before-complete.
  - Files: `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`
  - Verify: test -s .gsd/REQUIREMENTS.md

- [x] **T02: Hardened deferred and out-of-scope requirement records, adding R011 to explicitly exclude M001 cost-frontier execution and winner selection.** `est:1h`
  Expected executor skills: write-docs, verify-before-complete.
  - Files: `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`, `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-CONTEXT.md`
  - Verify: test -s .gsd/REQUIREMENTS.md

- [x] **T03: Added an executable S03 requirements verifier and validated R004 with passing verifier evidence.** `est:1h`
  Expected executor skills: verify-before-complete, write-docs.
  - Files: `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S03/verify_s03_requirements.py`, `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`
  - Verify: python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py

## Files Likely Touched

- /Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md
- /Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-CONTEXT.md
- /Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S03/verify_s03_requirements.py
