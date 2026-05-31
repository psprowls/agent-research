# S04 — Research

**Date:** 2026-05-31

## Summary

S04 owns active requirement R005: M001 must prove the roadmap and initialized artifacts are execution-ready for future GSD work. The dependent slices have already produced the core inputs: `.gsd/PROJECT.md` from S01, curated M001 context plus `.gsd/milestones/M001/slices/S02/verify_s02_context.py` from S02, and the normalized requirements contract plus `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py` from S03. A fresh baseline run of the S02 and S03 verifiers passed with `python3`, so S04 should compose those diagnostics rather than reimplement their detailed checks.

The main readiness gap found during research is that the worktree currently has no `.gsd/DECISIONS.md` file, even though the preloaded milestone context includes three decisions (D001-D003) and final integrated acceptance says PROJECT, REQUIREMENTS, CONTEXT, DECISIONS, and ROADMAP artifacts must exist. S04 planning should explicitly handle this projection/rendering gap before final verification. A second gotcha from memory is that GSD closeout readiness is not only DB status: the slice summary file, slice UAT file, and roadmap checkbox must all render correctly after completion.

## Recommendation

Plan S04 as a short verification-and-closeout slice with two natural units. First, restore/ensure the decision artifact exists in the worktree and add an executable S04 readiness verifier that composes S02/S03 checks and validates only S04-specific integration claims. Second, run the final readiness verifier, update/validate R005 through the GSD requirement path, complete S04, and perform a post-closeout render check for the slice summary, UAT file, and roadmap checkbox.

Use `python3` for all verifier commands; project memory notes that bare `python` can be unreliable in this worktree. Keep verifier checks concept-level and negation-aware, following the S02/S03 pattern: assert required positive claims and explicitly forbid only affirmative overclaims, so boundary language such as “not wholesale conversion” remains allowed.

## Implementation Landscape

### Key Files

- `.gsd/PROJECT.md` — Current project truth from S01. Exists and names `.gsd/` as active source of truth, `.planning/` as archive/reference, the v1.11 shipped trajectory, and all live packages: `graph-wiki-agent`, `eval-harness`, `graph-io`, `model-adapter`, `source-parser`, `subagent-runtime`, `wiki-io`, and `workspace-io`.
- `.gsd/REQUIREMENTS.md` — Normalized requirements contract from S03. R005 is currently active and owned by `M001/S04`, with S01-S03 as support; R001-R004 are validated; R006-R007 are deferred; R008-R011 are out of scope.
- `.gsd/milestones/M001/M001-CONTEXT.md` — Curated milestone context. Already contains the selective high-note/caveat framing, source references, deferred cost-frontier handoff, stale snapshot caveat, process-debt notes, and archive/reference boundary language.
- `.gsd/milestones/M001/M001-ROADMAP.md` — Slice roadmap. S01-S03 are checked complete; S04 is currently unchecked. It includes dependency and boundary map sections that S04 should verify for execution readiness.
- `.gsd/DECISIONS.md` — **Missing in the worktree** during research. Preloaded context contains D001-D003, so S04 should either regenerate/render this via the appropriate GSD path or restore the compact projection before final readiness verification.
- `.gsd/milestones/M001/slices/S02/verify_s02_context.py` — Existing verifier for curated context/high-note/caveat boundary. Fresh run passed.
- `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py` — Existing verifier for requirements buckets, ownership, source coverage, and prohibited overclaims. Fresh run passed.
- `.gsd/milestones/M001/slices/S04/` — Empty at research time. This is the target for a new S04 verifier and later S04 summary/UAT outputs.
- Sampled source paths cited by M001 artifacts — `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/MILESTONES.md`, `.planning/milestones/v1.11-ROADMAP.md`, `.planning/CONTINUE-sweep-harness-fixes-3.md`, `.planning/deferred-items.md`, root `pyproject.toml`, `agents/graph-wiki-agent/pyproject.toml`, and all package `pyproject.toml` files exist in the worktree.

### Build Order

1. **First proof: decision artifact/render gap.** Before writing the final verifier, resolve the missing `.gsd/DECISIONS.md` artifact. The verifier should fail if it is absent, because the milestone acceptance criteria require DECISIONS to render. Avoid creating duplicate decisions in the DB just to regenerate the file; if no render-only tool is available, restore the preloaded compact D001-D003 projection exactly and note why.
2. **Add S04 readiness verifier.** Create `.gsd/milestones/M001/slices/S04/verify_s04_readiness.py`. It should call or import subprocess runs for the S02 and S03 verifiers, then perform S04-specific cross-artifact checks.
3. **Run final readiness checks and validate R005.** Use the verifier evidence to update R005 from active to validated. Then complete S04 through the GSD closeout path.
4. **Post-closeout render check.** After slice completion, verify `.gsd/milestones/M001/slices/S04/S04-SUMMARY.md`, the S04 UAT artifact, and the roadmap checkbox for S04 are present/rendered; memory says DB status alone is not enough.

### Verification Approach

Recommended primary command after the S04 verifier exists:

```bash
python3 .gsd/milestones/M001/slices/S02/verify_s02_context.py
python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py
python3 .gsd/milestones/M001/slices/S04/verify_s04_readiness.py
```

Recommended contents for `verify_s04_readiness.py`:

- Assert these artifacts exist and are non-empty: `.gsd/PROJECT.md`, `.gsd/REQUIREMENTS.md`, `.gsd/DECISIONS.md`, `.gsd/milestones/M001/M001-CONTEXT.md`, `.gsd/milestones/M001/M001-ROADMAP.md`, and S01-S03 slice summaries.
- Run or replicate the S02 and S03 verifiers so their existing contracts remain the detailed authority for context and requirements.
- Assert roadmap contains all four artifact-focused slices with dependencies: S01 no deps, S02 depends S01, S03 depends S01/S02, S04 depends S01/S02/S03.
- Assert roadmap boundary map contains `S04 → Future milestones` and says it produces a verified initialized GSD state for future `/gsd auto` or focused milestone discussion.
- Assert requirements coverage: R001-R004 validated, R005 active or validated and owned by `M001/S04`, R006-R007 deferred, R008-R011 out-of-scope with no active M001 owner.
- Assert decisions include D001-D003 concepts: lean current-truth curation, manual curation/no migration automation, and deferred/caveat items captured as labeled future context.
- Assert source-reference existence for the sampled `.planning` files and package manifests listed above.
- Forbid affirmative overclaims: completed wholesale `.planning` conversion, exhaustive archive audit, active cost-frontier sweep/rerun, authoritative cost-frontier winners selected, historical audit/security-review backfill, Phase 60 reactivation, or product snapshot update in M001.

After S04 closeout, run a small final check (tool or script) that confirms `gsd_milestone_status` reports S04 complete and the rendered roadmap has S04 checked. If milestone completion is in scope after S04, validate the milestone with the same evidence before completing it.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|-------------------|------------|
| Detailed S02 context boundary checks | `.gsd/milestones/M001/slices/S02/verify_s02_context.py` | Already encodes high-note, caveat, source-reference, and prohibited-overclaim checks; avoids duplicated brittle regex work. |
| Detailed S03 requirements-contract checks | `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py` | Already verifies requirements buckets, ownership, deferred/out-of-scope labels, source references, and negative self-checks. |
| GSD status/closeout state | `gsd_milestone_status`, GSD completion/update tools | DB-backed state and rendered roadmap can diverge; use GSD tools plus filesystem render checks instead of ad hoc DB inspection. |

## Constraints

- Work must stay inside `/Users/pat/Personal/agent-research/.gsd/worktrees/M001`; do not `cd` outside the worktree.
- Use `python3`, not bare `python`, for verifier scripts.
- `.planning/` is read-only archive/reference evidence. S04 must not convert it, audit it exhaustively, or promote deferred items into active scope.
- GSD-rendered artifacts are preferred over manual edits. The missing decisions projection is the one known exception/gap to resolve carefully.
- S04 should not require the roadmap S04 checkbox to be checked before slice completion; check that only in the post-closeout verification.

## Common Pitfalls

- **Missing `.gsd/DECISIONS.md`** — final acceptance requires DECISIONS, but the file is absent in this worktree. Resolve this before declaring readiness.
- **Brittle prohibited-phrase checks** — PROJECT/CONTEXT/REQUIREMENTS intentionally mention prohibited work as exclusions. Forbid only affirmative completion/execution claims.
- **Premature S04 roadmap checkbox assertion** — the verifier run before `gsd_slice_complete` should expect S04 to exist and be planned/pending, not already checked complete.
- **DB-only closeout confidence** — memory says closeout should verify summary file, UAT file, and roadmap checkbox in addition to DB status.

## Open Risks

- There may be no render-only tool available for regenerating `.gsd/DECISIONS.md` from existing D001-D003 DB records. If so, execution needs a deliberate projection-restoration step without duplicating decisions.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Python verifier scripts | `python-testing-patterns` | Installed; useful if tasks expand the verifier with test-like helper structure. |
| Completion evidence | `verify-before-complete` | Installed; relevant rule is evidence before completion claims, especially for S04/R005 validation. |
| Planning/artifact prose | `write-docs` | Installed; useful if the DECISIONS projection or UAT/summary prose needs reader-facing clarity. |

## Sources

- Memory query found S04-relevant gotchas: use current-truth curation rather than wholesale import; capture deferred/caveats as future context; closeout requires summary/UAT/roadmap checkbox signals; prefer `python3` over bare `python`.
- `gsd_milestone_status(M001)` showed S01-S03 complete and S04 pending with no planned tasks yet.
- `gsd_exec` baseline `32340a70-a86b-4800-b149-e7429c803288` ran S02 and S03 verifiers successfully.
- `gsd_exec` scan `6830b439-b3a3-4969-aee8-d2befd3ab52e` found PROJECT/REQUIREMENTS/CONTEXT/ROADMAP present, S04 unchecked, and `.gsd/DECISIONS.md` missing.
- `gsd_exec` scan `f79ade42-8f35-4a40-ae48-07ac6172415b` confirmed cited legacy and package source paths are present.
