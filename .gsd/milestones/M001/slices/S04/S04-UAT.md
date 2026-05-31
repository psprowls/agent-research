# S04: Verify initialized GSD readiness — UAT

**Milestone:** M001
**Written:** 2026-05-31T04:48:09.927Z

# S04: Verify initialized GSD readiness — UAT

**Milestone:** M001
**Written:** 2026-05-31

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S04 ships planning artifacts and executable diagnostics, not a live runtime. The acceptance signal is that the active `.gsd` projections are coherent, traceable, and verifiable by the composed readiness script.

## Preconditions

- Work from the M001 worktree root.
- S01, S02, and S03 are complete.
- `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, `.gsd/milestones/M001/M001-ROADMAP.md`, and `.gsd/milestones/M001/M001-CONTEXT.md` exist.
- The S02, S03, and S04 verifier scripts are present under `.gsd/milestones/M001/slices/`.

## Smoke Test

Run `python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py`. The command should exit 0 and print `S04 readiness verifier passed: initialized GSD artifacts are coherent and traceable`.

## Test Cases

### 1. Readiness verifier proves the initialized artifact set

1. From the M001 worktree root, run `python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py`.
2. Confirm the command exits 0.
3. **Expected:** The verifier reports that initialized GSD artifacts are coherent and traceable.

### 2. Dependency verifiers remain composed into final readiness

1. Inspect or run the S04 verifier.
2. Confirm it executes the S02 context verifier and S03 requirements verifier as part of the readiness check.
3. **Expected:** S04 readiness fails if the curated context or normalized requirements contract regresses.

### 3. R005 is validated by final readiness evidence

1. Open `.gsd/REQUIREMENTS.md`.
2. Locate R005.
3. **Expected:** R005 is marked `validated`, owned by `M001/S04`, and its validation text references the S04 readiness verifier and execution-ready roadmap evidence.

### 4. Roadmap is demoable and dependency-ordered

1. Open `.gsd/milestones/M001/M001-ROADMAP.md`.
2. Review slices S01 through S04 and their dependency metadata.
3. **Expected:** The roadmap presents demoable initialization slices in dependency order and S04 is the final readiness slice consuming S01-S03 outputs.

## Edge Cases

### Legacy archive overclaim regression

1. Introduce or imagine language that treats `.planning` as wholesale imported or active source of truth.
2. Run the S04 verifier.
3. **Expected:** The verifier should fail because M001 must preserve selected high notes without converting the legacy archive wholesale.

### Missing traceability regression

1. Remove or imagine removing required source-path references from the context or requirements projections.
2. Run the S04 verifier.
3. **Expected:** The verifier should fail because final readiness depends on sampled legacy source traceability.

## Failure Signals

- S04 verifier exits non-zero.
- `.gsd/REQUIREMENTS.md` leaves R005 active or lacks S04 validation evidence.
- `.gsd/DECISIONS.md` omits the restored M001 decisions projection.
- Roadmap slices lose dependency ordering, active/deferred boundaries, or demoable planning structure.
- Context or requirements artifacts imply wholesale `.planning` conversion or active use of stale archive state.

## Not Proven By This UAT

- It does not prove future feature milestones are correctly scoped.
- It does not run live AWS Bedrock, MCP, or CLI workflows.
- It does not validate the legacy `.planning` archive exhaustively; M001 intentionally sampled and preserved high notes only.

## Notes for Tester

This is an artifact-readiness slice. Treat the S04 verifier as the authoritative smoke test, and use manual artifact review only to understand failures or confirm human-readable coherence.
