# S03: Normalize capability contract — UAT

**Milestone:** M001
**Written:** 2026-05-31T04:32:59.516Z

# S03: Normalize capability contract — UAT

**Milestone:** M001
**Written:** 2026-05-31

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S03 only changes planning and requirements artifacts; the acceptance signal is the rendered requirements contract plus its executable verifier, not a live runtime behavior.

## Preconditions

- Work from the M001 worktree root.
- `.gsd/REQUIREMENTS.md` exists and is the worktree-local rendered requirements projection.
- `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py` exists and is executable or runnable with `python3`.
- S01 and S02 are complete so their current-truth and legacy-high-note context is available.

## Smoke Test

Run:

```bash
python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py
```

Expected: the command exits 0 and prints that the S03 requirements verifier passed for the worktree-local `.gsd/REQUIREMENTS.md`.

## Test Cases

### 1. Active M001 ownership is normalized

1. Open `.gsd/REQUIREMENTS.md`.
2. Inspect R001 through R005.
3. **Expected:** R001 is validated and owned by M001/S01; R002 and R003 are validated and owned by M001/S02; R004 is validated and owned by M001/S03; R005 remains active and owned by M001/S04.

### 2. Deferred future work is clearly separated

1. In `.gsd/REQUIREMENTS.md`, inspect the Deferred section.
2. Review R006 and R007.
3. **Expected:** R006 and R007 are explicitly deferred/future-only, have no active M001 execution owner, and reference the relevant legacy/context sources rather than implying current completion.

### 3. Out-of-scope archive and eval exclusions are explicit

1. In `.gsd/REQUIREMENTS.md`, inspect the Out of Scope section.
2. Review R008 through R011.
3. **Expected:** The requirements explicitly exclude wholesale `.planning` conversion, backfilled audits, archive archaeology, and M001 cost-frontier execution/winner selection from this initialization milestone.

### 4. Traceability and omission honesty are mechanically checked

1. Run the S03 verifier.
2. Optionally inspect the verifier source for required source-path and negative-overclaim checks.
3. **Expected:** The verifier checks bucket membership, owner mappings, deferred/out-of-scope labels, required sampled source references, and negative cases for missing mappings/labels/sources or prohibited overclaims.

## Edge Cases

### Stale or mirrored requirements projection

1. If `.gsd/REQUIREMENTS.md` appears inconsistent with the DB-backed projection, rerun the S03 verifier against the worktree root.
2. **Expected:** The verifier fails if the worktree-local requirements contract drifts from the expected S03 shape; do not rely on a project-cache projection alone.

### Accidental activation of deferred work

1. Change R006 or R007 to look active or assign them an M001 execution owner.
2. Run the S03 verifier.
3. **Expected:** The verifier fails because deferred future work must not be treated as active M001 scope.

## Failure Signals

- The S03 verifier exits non-zero.
- R004 is not validated or is not owned by M001/S03.
- R005 is marked validated before S04 readiness verification.
- Deferred records have active M001 owners.
- Out-of-scope anti-features are missing or phrased as completed work.
- The requirements or context artifacts claim wholesale archive conversion, completed cost-frontier sweep execution, selected authoritative winners, or backfilled legacy audits.

## Not Proven By This UAT

- It does not prove S04 final readiness or whole-milestone consistency.
- It does not run product code, Bedrock calls, eval sweeps, or MCP/CLI workflows.
- It does not choose cost-frontier winners or validate future deferred requirements.

## Notes for Tester

This is a planning-contract slice. Treat `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py` as the authoritative diagnostic for S03 drift, and remember that `.planning/` remains archive/reference evidence rather than an active source of truth.
