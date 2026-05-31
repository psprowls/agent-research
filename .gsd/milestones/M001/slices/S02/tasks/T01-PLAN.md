---
estimated_steps: 9
estimated_files: 1
skills_used: []
---

# T01: Added a selective preserved high-notes section to M001 context with source-path references for v1.1 through v1.11 legacy trajectory.

Why: R002 requires preserving useful legacy `.planning` signal without copying the archive wholesale. S03 also needs a compact, traceable high-note set before it can normalize requirements.

Expected executor skills: write-docs, verify-before-complete.

Do:
1. Treat S01's PROJECT content from the preloaded context as the current-truth frame; do not rework that artifact unless a direct contradiction is found.
2. Edit M001 context and add one dedicated section, preferably `## Preserved Legacy High Notes and Caveats`, near the existing prior-art/scope discussion.
3. Add a concise shipped-trajectory subsection with source-path references. Preserve representative high notes only: v1.1 cost-frontier/eval/observability, v1.2 workspace/plugin/rebrand, v1.5 `graph-io` plus `source-parser`, v1.6-v1.10 graph/wiki evolution, and v1.11 TypeScript `type` node handling.
4. Cite the evidence paths inline, especially `.planning/MILESTONES.md` and `.planning/milestones/v1.11-ROADMAP.md`.
5. Keep the language explicitly selective and non-exhaustive so the section cannot be mistaken for a wholesale `.planning` import.

Done when: M001 context has a readable high-notes subsection that a fresh S03 executor can use without opening the full archive, includes the key source paths, and does not promote any deferred work into active M001 scope.

## Inputs

- None specified.

## Expected Output

- Update the implementation and proof artifacts needed for this task.

## Verification

test -s .gsd/milestones/M001/M001-CONTEXT.md

## Observability Impact

No runtime observability impact. The context section itself is the inspection surface for future planning agents.
