---
phase: 53-wiki-filename-cutover
plan: 01
subsystem: planning-docs
tags: [requirements, roadmap, wiki-fn-05, wiki-fn-06, scope-reshape]

requires:
  - phase: 52
    provides: short_filename implementation + write_entities correctness (referenced by reshaped WIKI-FN-06)
provides:
  - REQUIREMENTS.md WIKI-FN-05 rewritten to verification-language (encode_slug/decode_slug removal + grep-zero gate)
  - REQUIREMENTS.md WIKI-FN-06 rewritten to verification-language (manual vault regen + UAT)
  - ROADMAP.md §Phase 53 reshaped (goal loosened; SC #1/#2 struck; SC #3/#4 reframed; Scope reshape note added)
affects: [53-02, 53-verification]

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "Followed canonical text from 53-CONTEXT.md D-10 and 53-RESEARCH.md verbatim — no improvisation on requirement wording (planning artifact is the contract for verify-phase)."
  - "Traceability table left untouched per acceptance criterion — Phase 53 → Pending stays until phase verification flips it."
  - "ROADMAP Progress table row unchanged — GSD state machine updates plans-complete column."

patterns-established: []

requirements-completed: []  # WIKI-FN-05/06 remain Pending — verification language only; codework lives in 53-02.

duration: ~6min
completed: 2026-05-28
---

# Phase 53, Plan 01: Reshape WIKI-FN-05/06 + ROADMAP §Phase 53 Summary

**REQUIREMENTS.md WIKI-FN-05/06 and ROADMAP.md §Phase 53 now describe the slimmed Phase 53 scope (D-10) — the migrate-vault / atomic-commit / idempotency criteria are gone; what replaces them is the encode_slug removal grep gate, the call-site rewrite pytest gate, and the manual vault regen UAT.**

## Performance

- **Duration:** ~6 min
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- WIKI-FN-05 rewritten to mention `encode_slug` / `decode_slug` removal, the `grep -rn 'encode_slug\|decode_slug' packages/ agents/` zero-hit gate, and the workspace pytest gate.
- WIKI-FN-06 rewritten to describe the manual vault regen procedure (delete entity dirs → `cg update --full` → `graph-wiki-agent scan`) and the UAT recording in `53-UAT.md`.
- ROADMAP.md §Phase 53 goal loosened; "Scope reshape" sentence added linking back to 53-CONTEXT.md D-01..D-10; all four SC items rewritten to match the new scope.

## Task Commits

1. **Task 53-01-01: Rewrite WIKI-FN-05/06 to verification-language** — `d04cc9a` (docs)
2. **Task 53-01-02: Reshape ROADMAP §Phase 53** — `d918873` (docs)

## Files Created/Modified
- `.planning/REQUIREMENTS.md` — WIKI-FN-05 and WIKI-FN-06 bullets rewritten. Traceability table unchanged.
- `.planning/ROADMAP.md` — §Phase 53 goal + SC block + Scope reshape line. Progress table row at line 294 unchanged; v1.9 summary block at line 157 unchanged.

## Decisions Made
None — plan executed exactly as written, using the canonical text from `53-RESEARCH.md`.

## Deviations from Plan
None.

## Verification

All plan-level `<verification>` checks pass:

1. `grep -F "encode_slug" .planning/REQUIREMENTS.md` → match (new WIKI-FN-05 text).
2. `grep -F "regenerated from scratch" .planning/REQUIREMENTS.md` → match (new WIKI-FN-06 text).
3. `grep -F "single atomic commit" .planning/REQUIREMENTS.md` → 0 matches (old wording gone).
4. §Phase 53 block contains `encode_slug`, `regenerated`, `Scope reshape`, `frontmatter.uri`; does NOT contain `single atomic commit` or `idempotent via manifest marker`.
5. `migrate-vault` does not appear anywhere in REQUIREMENTS.md (cleaner than the plan required — the only remaining mention is the `(Phase 53 reshape — superseded the original migrate-vault wording …)` parenthetical in the new WIKI-FN-05 text).
6. The REQUIREMENTS.md traceability table for WIKI-FN-05/06 is byte-identical to the prior state.
7. The ROADMAP.md Progress table row for Phase 53 (`| 53. Wiki Filename Cutover | v1.9 | 0/TBD | Not started | - |`) is unchanged.
8. No code paths changed — workspace pytest is unaffected (not run; markdown-only plan).

## Issues Encountered
None.

## Next Phase Readiness

Plan 53-02 can proceed. The verification language in WIKI-FN-05/06 and the new SC #1/#2 in ROADMAP.md §Phase 53 match exactly the grep / pytest / fixture / import-error gates that 53-02's task acceptance criteria will satisfy. No drift between planning docs and code-cleanup plan.

## Self-Check: PASSED
