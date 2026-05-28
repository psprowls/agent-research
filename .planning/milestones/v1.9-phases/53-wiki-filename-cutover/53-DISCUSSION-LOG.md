# Phase 53 Discussion Log

**Phase:** 53 — Wiki Filename Cutover
**Discussed:** 2026-05-28
**Mode:** default (single-pass)

---

## Gray Areas Presented

1. **CLI shape** — extend `cg migrate-vault` vs. new sibling command.
2. **Atomic commit composition** — single commit vs. split by repo.
3. **File rename strategy** — `git mv` vs. re-emit via `write_entities`.
4. **Mapping derivation source** — walk entity files vs. query graph.

User selected: ALL FOUR for discussion.

---

## Discussion

### Areas 1-4 (initial recommendations)

**Claude recommended:** Extend `cg migrate-vault` into a migration-runner with dispatch + multi-migration manifest tracking; two-commit boundary by repo (vault atomic + per-plan code commits); `git mv` per entity file; walk entity files for frontmatter-uri-based mapping.

**User decision:** REJECTED ALL FOUR. Reason: "We do not need any sort of migration. There are no production wiki's in existance. I am the only developer and person using graph-wiki at this point."

### Phase reshape question

**Claude follow-up:** Proposed collapsing Phase 53 to cleanup + verification only — delete `encode_slug` / `decode_slug` (Phase 52 D-09 deferral), close fixture gaps, manual UAT via vault regen, ROADMAP §53 success-criteria edit. Three options offered (collapse-to-cleanup, merge-into-Phase-52, or skip-UAT).

**User decision:** Accepted "Phase 53 is now cleanup + verification only."

**Captured as:** D-01..D-10. CONTEXT.md describes the dramatically slimmer scope: no migration command, no rewriter, no atomic cutover commit. Pure source cleanup + fixture closure + ROADMAP/REQUIREMENTS reshape + manual UAT.

---

## Scope Creep Redirected

None — the user's direction REMOVED scope from Phase 53; no creep to redirect.

## Deferred Ideas

- Building a real migration system later (if graph-wiki ever has external users) — Phase 46 + originally-planned-Phase-53 architecture is the revival blueprint.
- Automated `cg migrate-vault` version detection — not needed for single-user.
- `cg verify-vault` automated UAT command — cheap to add but not required.

## Claude's Discretion (left to planner)

- Whether to mark WIKI-FN-05/06 as "Withdrawn" or rewrite to verification-language. Default: rewrite.
- Whether ROADMAP/REQUIREMENTS edits are a dedicated plan or folded. Default: dedicated (53-01).
- Whether to annotate `cg migrate-vault` docstring as v1.8-only. Default: leave intact.
- Timing of manual vault regen relative to PR merge. Default: after merge.

---

## Significance

This was the largest scope-shrinking decision in v1.9. Phase 53 went from "build a v1.9 cutover migration with rewriter + dispatch + manifest tracking + atomic vault commit" (multi-day phase) to "delete two functions + edit two markdown files + manually regen vault" (likely sub-day phase). The reshape is recorded explicitly in CONTEXT.md D-01..D-03 because downstream agents need to know that the original roadmap success criteria SC#1 and SC#2 are no longer applicable.

---

*See `53-CONTEXT.md` for the canonical decision record consumed by downstream agents.*
