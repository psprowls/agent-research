---
estimated_steps: 6
estimated_files: 1
skills_used: []
---

# T01: Rendered the DB-backed requirements contract and normalized active M001 requirement ownership for R001 through R005.

Expected executor skills: write-docs, verify-before-complete.

Why: S03's highest-risk seam is that the preloaded compact requirements and current worktree projection disagree: `.gsd/REQUIREMENTS.md` is absent in this worktree, while runtime context says R002/R003 were advanced and validated. Before adding new records, the executor must make the DB-backed requirements projection real and normalize the active initialization contract without hand-editing generated output.

Do: Use GSD requirement update/save tools as the source of truth, not a manual rewrite of `.gsd/REQUIREMENTS.md`. First inventory which requirement IDs are present after a render/update attempt. Normalize active records so future readers can see: R001 validated owner `M001/S01` for active GSD source of truth; R002 validated owner `M001/S02` for selective high-note preservation without wholesale conversion; R003 validated owner `M001/S02` for deferred/caveat labeling; R004 active owner `M001/S03` for internal consistency, traceability, and honesty about omissions; and R005 active owner `M001/S04` for final initialized readiness. If R002 is genuinely missing from the DB, create the selective high-note preservation requirement through the requirement-save tool, accept its auto-assigned ID, and note that downstream context references may need adjustment in T02 if the ID differs. Preserve the archive/reference boundary language from `.gsd/PROJECT.md` and `.gsd/milestones/M001/M001-CONTEXT.md`.

Failure Modes (Q5): If requirement tools fail to render, stop with the tool error rather than hand-editing the rendered file; if IDs differ from the context, record the observed IDs for T02 reconciliation; if current evidence is ambiguous, keep wording honest and do not mark unverified records validated.

Negative Tests (Q7): Check that active requirement wording does not promote `.planning/` to active truth, does not say M001 completed wholesale conversion, and does not say M001 ran the cost-frontier sweep.

Done when: `.gsd/REQUIREMENTS.md` exists, active initialization records are present with owner/status/validation posture, and deferred/out-of-scope additions remain for T02 rather than being mixed into active M001 execution.

## Inputs

- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/PROJECT.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-CONTEXT.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/M001-ROADMAP.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S01/S01-SUMMARY.md`
- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/milestones/M001/slices/S02/S02-SUMMARY.md`

## Expected Output

- `/Users/pat/.gsd/projects/a9290fa6210b/worktrees/M001/.gsd/REQUIREMENTS.md`

## Verification

test -s .gsd/REQUIREMENTS.md

## Observability Impact

Creates the primary inspection surface for S03: the rendered requirements artifact. Tool failures should be preserved in task evidence instead of masked by manual edits.
