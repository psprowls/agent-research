# S03: Normalize capability contract — Research

**Date:** 2026-05-31

## Summary

S03 is a planning-artifact normalization slice, not a product-code slice. Its owned active requirement is R004: initialized GSD artifacts must be internally consistent, traceable to sampled legacy sources, and honest about omissions. It also directly supports S04/R005 by producing the normalized requirement contract that final readiness validation will consume.

The main finding is that the slice should start with the requirements projection itself. The preloaded compact requirements show only R001, R003, R004, and R005, while milestone context references R002 and R006-R010, and the worktree currently has no rendered `.gsd/REQUIREMENTS.md` file. Runtime metadata says R002/R003 were advanced and validated, so this may be a render/projection gap rather than missing DB state. The first executor task should therefore inventory/regenerate requirements through the GSD requirement tools before editing content assumptions.

The normalized contract should make three buckets explicit: active/validated initialization requirements (R001-R005, with owners S01-S04), deferred future work (at least cost-frontier sweep rerun and optional archive index), and explicit anti-features/out-of-scope boundaries (wholesale `.planning` conversion, reusable migration tooling/backfill, blind legacy plan resumption/exhaustive audit, and M001 cost-frontier execution). Use the same archive-boundary language established by S01/S02 and preserve source-path traceability to sampled legacy/current files.

## Recommendation

Use DB-backed GSD requirement operations to normalize and render `.gsd/REQUIREMENTS.md`; do not hand-edit the rendered file as the source of truth. Treat the current absent rendered file and R002/R006-R010 mismatch as the highest-risk seam: first prove what the DB/projector currently contains, then add/update requirement records only as needed.

Recommended implementation shape:

1. Regenerate or otherwise force-render `.gsd/REQUIREMENTS.md` via requirement update/save tooling. Confirm whether R002 already exists in DB despite being absent from the preloaded compact excerpt.
2. Update active requirements so they have clear owners and validation posture:
   - R001 validated owner `M001/S01` — active GSD source of truth.
   - R002 validated owner `M001/S02` — selective high-note preservation without wholesale conversion.
   - R003 validated owner `M001/S02` — deferred/caveat labeling.
   - R004 active owner `M001/S03` — requirement contract consistency/traceability/honesty.
   - R005 active owner `M001/S04` — final initialized readiness/execution readiness.
3. Add or normalize deferred/out-of-scope records (referenced by M001 context as R006-R010). If any IDs do not exist, create new records with capability/anti-feature descriptions rather than manually assigning IDs; then update context references only if the generated IDs differ.
4. Add an S03 verifier script that asserts rendered requirements contain the active/deferred/out-of-scope buckets, owner mapping, source references, and prohibited-overclaim protections.

This follows the installed `write-docs` skill's reader-test principle: the REQUIREMENTS artifact must be understandable to a fresh future agent without session context, with clear bucket labels and no ambiguous archive promotion.

## Implementation Landscape

### Key Files

- `.gsd/REQUIREMENTS.md` — Target rendered artifact. Currently absent in the worktree even though the preloaded GSD context contains a compact requirements excerpt. This is the primary artifact S03 must produce/normalize.
- `.gsd/milestones/M001/M001-CONTEXT.md` — Source of the expected contract. It references R001-R010 and names the required active, deferred, and out-of-scope boundaries. It also contains source-path references to preserve in requirements traceability.
- `.gsd/PROJECT.md` — Current-truth frame established by S01. Its “Active Source of Truth,” “Current Known Boundaries,” and “Inspection Surface” sections provide boundary wording that requirements should not contradict.
- `.gsd/milestones/M001/M001-ROADMAP.md` — Slice ownership map. S03 outcome is specifically “REQUIREMENTS separates active initialization requirements, deferred future work, and explicit out-of-scope archive conversion.”
- `.gsd/milestones/M001/slices/S02/verify_s02_context.py` — Pattern to follow for an artifact-contract verifier: required text/patterns plus prohibited affirmative overclaims. S03 should create an analogous verifier for requirements.
- `.planning/CONTINUE-sweep-harness-fixes-3.md` — Evidence source for deferred cost-frontier sweep debug/rerun/winner-selection work.
- `.planning/deferred-items.md` — Evidence source for stale snapshot caveat around `agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_output`.
- `.planning/PROJECT.md` and `.planning/MILESTONES.md` — Evidence sources for historical process-debt notes and shipped trajectory, but reference-only; do not promote to active requirements without current-source verification.
- `pyproject.toml` and `agents/graph-wiki-agent/pyproject.toml` — Current package evidence if requirements mention live project/package boundaries.

### Natural Seams

- **Requirement inventory/render seam:** Determine what the GSD DB/projector currently knows and make `.gsd/REQUIREMENTS.md` exist. This is independent of prose polishing and should happen first.
- **Active requirements seam:** Normalize R001-R005 owner/status/validation language against S01/S02 summaries and S03/S04 responsibilities.
- **Deferred/out-of-scope seam:** Add/update R006-R010-style records for future work and anti-features, ensuring they are not mapped as active M001 execution.
- **Verifier seam:** Add `verify_s03_requirements.py` after the intended requirements shape is known. This can be built mostly independently from final wording once required phrases/patterns are defined.

### Build Order

1. **First proof:** Render/inventory `.gsd/REQUIREMENTS.md`. The worktree lacks the file, and preloaded context has a possible mismatch around R002/R006-R010. Do not plan content edits until this is resolved.
2. Normalize active owner/status records and validations for R001-R005, using the S01/S02 closeout evidence and leaving R004 active for S03 until the verifier passes.
3. Add/update deferred and anti-feature requirement records. Keep descriptions capability-oriented and use classes such as `continuity`, `failure-visibility`, `constraint`, or `anti-feature` as appropriate; do not invent IDs manually if new records are needed.
4. Create and run `.gsd/milestones/M001/slices/S03/verify_s03_requirements.py`.
5. Update R004 validation with the fresh verifier evidence after the verifier passes.

### Verification Approach

Use a fresh, explicit `python3` command for closeout-safe verification; prior project memory notes a bare `python` shim can be unreliable in this worktree.

Recommended verifier command:

```bash
python3 .gsd/milestones/M001/slices/S03/verify_s03_requirements.py
```

Verifier assertions should include:

- `.gsd/REQUIREMENTS.md` exists and is non-empty.
- Active/validated initialization requirements are present and owner-mapped: R001→S01, R002→S02, R003→S02, R004→S03, R005→S04.
- Deferred future-work requirements are labeled deferred and include cost-frontier sweep rerun/winner-selection and optional archive index without active M001 ownership.
- Out-of-scope/anti-feature requirements explicitly prohibit wholesale `.planning` conversion, reusable migration tooling/backfill, blind legacy plan resumption/exhaustive audit, and M001 cost-frontier execution.
- Required source references appear: `.planning/CONTINUE-sweep-harness-fixes-3.md`, `.planning/deferred-items.md`, `.planning/PROJECT.md`, `.planning/MILESTONES.md`, `.gsd/PROJECT.md`, and `.gsd/milestones/M001/M001-CONTEXT.md`.
- Prohibited affirmative overclaims are absent, e.g. “M001 completed wholesale conversion,” “M001 ran the sweep,” “authoritative cost-frontier winners selected,” or “legacy audits backfilled.”

## Constraints

- Use GSD requirement tools as the source of truth for requirement records and rendered `.gsd/REQUIREMENTS.md`; do not manually edit generated requirement output unless the GSD tooling explicitly requires a root-level artifact rewrite.
- Do not `mkdir` S03 manually unless the executor discovers the GSD tool did not materialize it; the auto-mode notification says the slice directory is already allocated, but current filesystem inspection only shows S01/S02 directories.
- `.planning/` is evidence/reference only. Requirements may cite it, but must not treat old phases, deferred work, or process debt as active execution commitments.
- New requirements get auto-assigned IDs. If R006-R010 are absent in DB, create records and then adjust context references if their generated IDs differ rather than hardcoding IDs.

## Common Pitfalls

- **Assuming the compact preloaded REQUIREMENTS excerpt is complete** — It omits R002 and R006-R010 despite runtime/context references. Start from a fresh DB-backed render/inventory.
- **Promoting deferred sweep work into active scope** — The cost-frontier sweep requires debugging, Bedrock spend, reruns, and human winner selection; it is future work, not M001 execution.
- **Writing requirements as task lists** — The desired contract is capability/constraint/anti-feature requirements with owners/traceability, not a migration checklist.
- **Using brittle literal checks** — Follow S02’s verifier pattern: assert required concepts and prohibit specific affirmative overclaims while allowing honest negated boundary language.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| GSD/document authoring | `write-docs` | Installed; relevant for fresh-reader clarity and reader-test framing. |
| GSD slice decomposition | `decompose-into-slices` | Installed but not needed for this research slice because the roadmap already defines S03’s boundary. |

## Sources

- Artifact inventory found `.gsd/REQUIREMENTS.md` and `.gsd/DECISIONS.md` absent in the worktree, while context/roadmap files exist (source: `gsd_exec` run `841b85c3-0b9c-44db-b029-1965b1503383`).
- Legacy/current reference check confirmed cited source files exist: `.planning/PROJECT.md`, `.planning/MILESTONES.md`, `.planning/ROADMAP.md`, `.planning/CONTINUE-sweep-harness-fixes-3.md`, `.planning/deferred-items.md`, root `pyproject.toml`, and `agents/graph-wiki-agent/pyproject.toml` (source: `gsd_exec` run `b4ac094e-8b25-42f1-b089-7eca219ebbff`).
- Prior project memory confirms M001’s governing decisions: curate current truth/high-value notes, no migration automation, and preserve deferred/caveat items as labeled future context rather than active scope (source: `memory_query` results MEM001, MEM002, MEM006).