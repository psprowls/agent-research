---
estimated_steps: 4
estimated_files: 1
skills_used: []
---

# T02: Verified the PROJECT artifact’s current-truth claims and archive-boundary exclusions without product runtime changes.

Expected executor skills: `verify-before-complete`.

Why: The highest S01 risk is over-importing `.planning` or turning deferred legacy work into active scope. This task closes the slice by checking that the PROJECT artifact contains required current-truth claims and omits prohibited overclaims.

Do: Run focused static checks against the rendered `.gsd/PROJECT.md`. Confirm positive claims for active source of truth, archive/reference boundary, v1.11 shipped state, and all live package names. Confirm the artifact does not say wholesale conversion is complete, does not introduce migration tooling as an M001 deliverable, does not describe Phase 60 as active/resumable, and does not make the cost-frontier sweep active M001 execution. If a check fails, update the PROJECT artifact through `gsd_summary_save` and rerun verification.

Done when: positive checks pass, negative checks find no prohibited overclaims, and no product runtime changes were made.

## Inputs

- None specified.

## Expected Output

- Update the implementation and proof artifacts needed for this task.

## Verification

test -s .gsd/PROJECT.md && rg "active source of truth" .gsd/PROJECT.md && rg "archive/reference" .gsd/PROJECT.md && rg "v1.11" .gsd/PROJECT.md && rg "graph-wiki-agent" .gsd/PROJECT.md && rg "subagent-runtime" .gsd/PROJECT.md && rg "model-adapter" .gsd/PROJECT.md && rg "source-parser" .gsd/PROJECT.md && rg "graph-io" .gsd/PROJECT.md

## Observability Impact

No runtime impact. Produces verification evidence in the task summary for future planning agents.
