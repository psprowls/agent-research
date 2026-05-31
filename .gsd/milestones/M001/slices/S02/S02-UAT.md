# S02: Preserve legacy high notes and caveats — UAT

**Milestone:** M001
**Written:** 2026-05-31T04:09:22.222Z

# S02: Preserve legacy high notes and caveats — UAT

**Milestone:** M001
**Written:** 2026-05-31

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice only changes planning/context artifacts and adds an executable verifier; there is no runtime service or UI to exercise.

## Preconditions

- Worktree is `/Users/pat/Personal/agent-research/.gsd/worktrees/M001`.
- S01 is complete and `.gsd/milestones/M001/M001-CONTEXT.md` exists.
- The legacy `.planning` archive remains present as reference material.

## Smoke Test

Run:

```bash
python .gsd/milestones/M001/slices/S02/verify_s02_context.py
```

Expected: exit code 0 and output beginning with `S02 context verifier passed:`.

## Test Cases

### 1. Selective high notes are preserved

1. Open `.gsd/milestones/M001/M001-CONTEXT.md`.
2. Find the preserved legacy high-notes section.
3. Confirm it references legacy source paths and summarizes the v1.1-v1.11 shipped trajectory.
4. **Expected:** The context gives future agents the important legacy trajectory without copying the archive wholesale or claiming exhaustive migration.

### 2. Caveats and deferred work are clearly labeled

1. In `.gsd/milestones/M001/M001-CONTEXT.md`, review the deferred/caveat notes.
2. Confirm the deferred sweep handoff points to `.planning/CONTINUE-sweep-harness-fixes-3.md` and related deferred archive material.
3. Confirm stale `.planning/sweep/*.md` / `.planning/sweep/INDEX.md` snapshot language includes the `$7.02` caveat.
4. Confirm process-debt notes are framed as historical caveats rather than active commitments.
5. **Expected:** A future agent can distinguish current truth from deferred or stale legacy state.

### 3. Archive boundary is enforced by a diagnostic

1. Run `python .gsd/milestones/M001/slices/S02/verify_s02_context.py`.
2. **Expected:** The verifier passes and reports the verified M001 context path.

## Edge Cases

### Avoid wholesale-conversion overclaim

1. Search `.gsd/milestones/M001/M001-CONTEXT.md` for language implying the entire `.planning` archive was converted or exhaustively audited.
2. **Expected:** No such overclaim appears; the artifact presents the archive as reference material with selected high notes preserved.

### Stale archive snapshots remain caveated

1. Review references to `.planning/sweep/*.md` and `.planning/sweep/INDEX.md`.
2. **Expected:** They are labeled as stale/historical snapshots, not current execution state.

## Failure Signals

- `verify_s02_context.py` exits non-zero.
- The M001 context omits legacy source-path references for preserved high notes.
- Deferred sweep, stale snapshot, or process-debt notes are missing or unlabeled.
- The context claims wholesale `.planning` conversion or exhaustive archive import.

## Not Proven By This UAT

- It does not prove every file in `.planning` was reviewed or migrated; that is intentionally out of scope.
- It does not prove S03 requirements normalization is complete.
- It does not exercise runtime agent behavior or Bedrock integrations.

## Notes for Tester

Treat `.planning` as an archived reference set. The active acceptance signal for this slice is the curated M001 context plus the passing S02 verifier, not a one-to-one migration of legacy planning files.

