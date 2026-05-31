# M001: Initialize GSD From Legacy Planning Archive

**Vision:** Initialize the new GSD project from the old pre-fork `.planning` archive by preserving current truth and high notes, while keeping `.planning` as backed-up archive/reference rather than converting it wholesale.

## Success Criteria

- `.gsd` becomes the active project planning source of truth for future work.
- Legacy `.planning` high notes are preserved without wholesale archive conversion.
- Deferred and caveat items are clearly separated from active M001 work.
- Active requirements are mapped to demoable slices and no active requirement is orphaned.
- Final artifacts are traceable to sampled legacy sources and current package evidence.

## Slices

- [x] **S01: Establish current project truth** `risk:medium` `depends:[]`
  > After this: PROJECT artifact accurately describes the current repo, shipped trajectory, package layout, and active GSD posture.

- [x] **S02: Preserve legacy high notes and caveats** `risk:high` `depends:[S01]`
  > After this: M001 context captures useful `.planning` high notes, deferred sweep work, stale snapshot caveat, and archive boundary without wholesale import.

- [x] **S03: Normalize capability contract** `risk:medium` `depends:[S01,S02]`
  > After this: REQUIREMENTS separates active initialization requirements, deferred future work, and explicit out-of-scope archive conversion.

- [x] **S04: Verify initialized GSD readiness** `risk:high` `depends:[S01,S02,S03]`
  > After this: A final consistency pass proves initialized GSD artifacts are coherent, traceable to sampled sources, and ready for future `/gsd auto` work.

## Boundary Map

### S01 → S02

Produces:
- Current project summary, shipped trajectory, package layout, and archive-boundary language stable enough for later context curation.

Consumes:
- `.planning/PROJECT.md`, `.planning/ROADMAP.md`, root/package `pyproject.toml` files.

### S02 → S03

Produces:
- Curated high-note and caveat set: shipped v1.0-v1.11 trajectory, deferred sweep handoff, stale snapshot caveat, process-debt notes, and explicit archive/reference boundary.

Consumes:
- S01 current-truth framing.

### S03 → S04

Produces:
- Normalized active/deferred/out-of-scope requirement contract with slice ownership and traceability.

Consumes:
- S01 current-truth framing and S02 caveat/high-note set.

### S04 → Future milestones

Produces:
- Verified initialized GSD state ready for future `/gsd auto` or focused milestone discussion.

Consumes:
- PROJECT, REQUIREMENTS, M001-CONTEXT, ROADMAP, and DECISIONS artifacts.
