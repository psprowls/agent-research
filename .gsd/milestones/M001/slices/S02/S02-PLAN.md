# S02: Preserve legacy high notes and caveats

**Goal:** Curate high-value legacy `.planning` high notes and caveats into the active M001 context while preserving the archive/reference boundary and preventing deferred items from becoming active scope.
**Demo:** M001 context captures useful `.planning` high notes, deferred sweep work, stale snapshot caveat, and archive boundary without wholesale import.

## Must-Haves

- M001 context contains a dedicated preserved high-notes and caveats section with source-path references to the sampled legacy archive files.
- The section captures representative shipped trajectory high notes, the deferred cost-frontier sweep handoff, the stale `test_graph_query_output` snapshot caveat, historical process-debt caveats, and archive/reference rules.
- Verification proves required source references and deferred labels are present and prohibited overclaims are absent.
- R002 and R003 can be validated from the context artifact without wholesale archive conversion or runtime sweep execution.

## Proof Level

- This slice proves: Contract/document-artifact proof. Real product runtime is not required; human/UAT is not required. The proof is an executable assertion script over the curated context artifact plus DB-backed requirement validation after assertions pass.

## Integration Closure

Consumes S01's current-truth posture and archive-boundary framing. Produces the curated high-note/caveat set that S03 needs to normalize active, deferred, and out-of-scope requirements. No runtime wiring is introduced.

## Verification

- No runtime observability changes. Diagnostic surface is the persisted context artifact, the S02 verifier script/output, task summaries, and requirement validation notes.

## Tasks

- [x] **T01: Added a selective preserved high-notes section to M001 context with source-path references for v1.1 through v1.11 legacy trajectory.** `est:45m`
  Why: R002 requires preserving useful legacy `.planning` signal without copying the archive wholesale. S03 also needs a compact, traceable high-note set before it can normalize requirements.
  - Verify: test -s .gsd/milestones/M001/M001-CONTEXT.md

- [x] **T02: Labeled deferred sweep, stale snapshot, historical process-debt, and archive-boundary caveats in M001 context with an executable S02 verifier.** `est:45m`
  Why: R003 requires future agents to see which legacy items are deferred, stale, historical process debt, or archive/reference evidence rather than active M001 commitments. The slice should close with executable, negation-aware document assertions before requirements are validated.
  - Verify: python .gsd/milestones/M001/slices/S02/verify_s02_context.py
