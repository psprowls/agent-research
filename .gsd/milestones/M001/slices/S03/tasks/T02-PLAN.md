---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T02: Hardened deferred and out-of-scope requirement records, adding R011 to explicitly exclude M001 cost-frontier execution and winner selection.

Expected executor skills: write-docs, verify-before-complete.

Why: The normalized capability contract must separate active initialization work from future work and explicit non-goals. S02 preserved deferred sweep/caveat context, but S03 must make those boundaries visible in REQUIREMENTS so future `/gsd auto` work does not accidentally resume archived plans or treat deferred debug/eval work as completed.

Do: Using GSD requirement tools, add or update deferred future-work and out-of-scope/anti-feature records. Deferred records should include the cost-frontier sweep debug/rerun/winner-selection handoff sourced to `.planning/CONTINUE-sweep-harness-fixes-3.md` and the optional archive index/backlog idea sourced to M001 context; they must be labeled future/deferred and must not be owner-mapped as active M001 execution. Anti-feature records should explicitly prohibit: wholesale `.planning` conversion; reusable migration tooling or legacy backfill in M001; blind legacy plan resumption or exhaustive archive audit; and M001 cost-frontier execution or authoritative winner selection. If new records receive IDs different from R006-R010 references in `.gsd/milestones/M001/M001-CONTEXT.md`, update the context references in this task so cross-artifact traceability remains honest. Keep all descriptions capability/constraint-oriented rather than task checklists.

Failure Modes (Q5): If GSD auto-assigned IDs differ from the context, reconcile references rather than hardcoding IDs; if a deferred item lacks current-source support, mark it as reference-only future context; if an anti-feature is mentioned, phrase it as an explicit exclusion rather than an affirmative completed claim.

Negative Tests (Q7): Verify the requirements do not contain affirmative claims that M001 ran the sweep, selected authoritative cost-frontier winners, completed wholesale conversion, or backfilled legacy audits. Verify deferred records include source paths and future/deferred labels.

Done when: `.gsd/REQUIREMENTS.md` has separate deferred and anti-feature/out-of-scope buckets with source-path traceability, and any context requirement references match the IDs actually produced by the GSD DB.

## Inputs

- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-CONTEXT.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/CONTINUE-sweep-harness-fixes-3.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/deferred-items.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/PROJECT.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.planning/MILESTONES.md`

## Expected Output

- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-CONTEXT.md`

## Verification

test -s .gsd/REQUIREMENTS.md

## Observability Impact

Improves planning failure visibility by making deferred and excluded work inspectable in the rendered requirement contract instead of buried in legacy archive notes.
