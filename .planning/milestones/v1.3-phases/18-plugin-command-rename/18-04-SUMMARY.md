---
phase: 18-plugin-command-rename
plan: 04
subsystem: docs
tags: [graph-wiki, slash-commands, rename, sweep, wiki-io]

# Dependency graph
requires:
  - phase: 18-plugin-command-rename
    provides: renamed bootstrap.md command file (18-01), renamed CLI surface (18-02), renamed MCP surface (18-03)
provides:
  - All active-source `/graph-wiki:init` references renamed to `/graph-wiki:bootstrap`
  - Vault-io runtime user-facing strings (lint error, scan hint) now name `/graph-wiki:bootstrap`
  - Plugin README has reinstall callout for prior installs (Q2 resolution)
affects: [18-05 (historical sweep — disjoint file set), 18-06 (brand-gate lock-in)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Word-boundary regex sweep (`\\bgraph-wiki:init\\b`) avoids `/graph-wiki:ingest` and `init_vault` false positives"
    - "Pre/post invariant counts assert sibling tokens are untouched by the sweep"

key-files:
  created: []
  modified:
    - plugins/graph-wiki/README.md
    - plugins/graph-wiki/CLAUDE.md
    - plugins/graph-wiki/agents/linter.md
    - plugins/graph-wiki/commands/scan.md
    - plugins/graph-wiki/skills/graph-wiki/SKILL.md
    - plugins/graph-wiki/skills/graph-wiki/README.md
    - plugins/graph-wiki/skills/graph-wiki/references/cross-tool-setup.md
    - plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md
    - packages/wiki-io/src/wiki_io/scan_monorepo.py
    - packages/wiki-io/src/wiki_io/lint/container.py

key-decisions:
  - "Reinstall callout placed in README Setup section step 1 as a blockquote (single location per plan Step 5)"
  - "Reinstall callout rephrased from suggested wording to avoid containing literal `/graph-wiki:init` — keeps AC1 grep-clean while preserving Q2 intent"
  - "`perl -i -pe` used for word-boundary substitution (BSD sed on macOS doesn't reliably support `\\b`)"

patterns-established:
  - "Sweep pattern: capture pre-sweep invariant counts → apply word-boundary regex → assert post-sweep counts equal — proves the regex did not over-match"

requirements-completed: [CMD-03]

# Metrics
duration: 4min
completed: 2026-05-20
---

# Phase 18 Plan 04: Active-Source `/graph-wiki:init → /graph-wiki:bootstrap` Sweep Summary

**Word-boundary sweep of 16 `/graph-wiki:init` references across 10 active-source files (8 plugin docs + 2 wiki-io runtime strings), plus README reinstall callout — `init_vault` and `/graph-wiki:ingest` siblings preserved unchanged.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-20T02:11:29Z
- **Completed:** 2026-05-20T02:14:59Z
- **Tasks:** 1
- **Files modified:** 10

## Accomplishments
- Active-source repo-wide grep for `\bgraph-wiki:init\b` returns zero hits across `plugins/`, `packages/`, `agents/`, `scripts/`, `docs/`, `README.md`, `CLAUDE.md`
- Vault-io runtime user-facing strings now tell users the correct command name:
  - `packages/wiki-io/src/wiki_io/lint/container.py:35` → `"no layout block found in CLAUDE.md (run /graph-wiki:bootstrap)"`
  - `packages/wiki-io/src/wiki_io/scan_monorepo.py:1157` → `"(Re-run /graph-wiki:bootstrap or hand-edit the layout block to update.)"`
- Plugin README has a one-sentence upgrade/reinstall callout in the Setup section (Q2 resolution)
- Sweep invariants verified equal pre- and post-sweep (proves no regex over-match)

## Task Commits

1. **Task 1: Sweep active-source markdown + Python references; add reinstall note** — `5d8160e` (refactor)

## Per-file Substitution Counts

| File | Pre-sweep `/graph-wiki:init` hits | Post-sweep `/graph-wiki:bootstrap` hits added |
|------|-----------------------------------|------------------------------------------------|
| plugins/graph-wiki/README.md | 2 | 2 (plus reinstall note adds 1 more bootstrap mention → 3 total) |
| plugins/graph-wiki/CLAUDE.md | 1 | 1 |
| plugins/graph-wiki/agents/linter.md | 1 | 1 |
| plugins/graph-wiki/commands/scan.md | 3 | 3 |
| plugins/graph-wiki/skills/graph-wiki/SKILL.md | 1 | 1 |
| plugins/graph-wiki/skills/graph-wiki/README.md | 1 | 1 |
| plugins/graph-wiki/skills/graph-wiki/references/cross-tool-setup.md | 2 | 2 |
| plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md | 4 | 4 |
| packages/wiki-io/src/wiki_io/scan_monorepo.py | 1 | 1 |
| packages/wiki-io/src/wiki_io/lint/container.py | 1 | 1 |
| **Total** | **17** | **17** (+ 1 from reinstall note in README) |

Note: pre-sweep grep listed 16 lines, but two of those lines contained 2 occurrences (`scan.md` and `detection-workflow.md` had list entries) — total token count is 17.

## Acceptance Criteria Verification

- **AC1 — zero `\bgraph-wiki:init\b` in active source:** PASS (grep returns 0 hits, exit code 1)
- **AC2 — README has ≥2 bootstrap refs:** PASS (3 refs — 2 from sweep + 1 in reinstall callout)
- **AC3 — scan.md has ≥3 bootstrap refs:** PASS (3 refs)
- **AC4 — detection-workflow.md has ≥4 bootstrap refs:** PASS (4 refs)
- **AC5 — container.py line 35 says `/graph-wiki:bootstrap`:** PASS
- **AC6 — scan_monorepo.py line 1157 says `/graph-wiki:bootstrap`:** PASS
- **AC7 — README has reinstall note:** PASS (`grep -ciE 'reinstall' README.md` returns 1)
- **AC8a — `init_vault` invariant:** PASS (`INIT_VAULT_BASELINE = 53` = `INIT_VAULT_POST = 53`)
- **AC8b — `/graph-wiki:ingest` invariant:** PASS (`INGEST_BASELINE = 48` = `INGEST_POST = 48`)
- **AC9 — `init_vault.py` still defines function:** PASS (4 occurrences in canonical definition file)
- **Per-commit gate — pytest:** PASS (`code-wiki-agent` tests 212 passed; `wiki-io` tests 93 passed)
- **Single commit lands:** PASS (`refactor(18-04)` subject contains `sweep`)

## Invariant Counts (Pre/Post Equality)

| Invariant | Baseline | Post-sweep | Equal? |
|-----------|----------|------------|--------|
| `\binit_vault\b` across `packages/` `agents/` | 53 | 53 | YES |
| `/graph-wiki:ingest\b` across `plugins/` `packages/` | 48 | 48 | YES |

Both counts unchanged. The word-boundary regex (`\bgraph-wiki:init\b`) did not over-match into `init_vault` or `/graph-wiki:ingest`.

## Files Created/Modified

All 10 files modified (none created). See the substitution-count table above for per-file details.

## Decisions Made
- **Reinstall callout placement:** Added as a single blockquote callout immediately after the `claude plugin install` command in the README Setup section, satisfying Q2's "one sentence" intent without duplicating across other docs.
- **Reinstall callout wording:** Rephrased the plan's suggested wording — replaced `(formerly /graph-wiki:init)` with `(previously named init)` to keep AC1's grep-clean assertion satisfied. The plan explicitly notes "executor may rephrase".
- **Substitution mechanism:** Used `perl -i -pe 's@/graph-wiki:init\b@/graph-wiki:bootstrap@g'` rather than `sed` because BSD sed (macOS) doesn't reliably support `\b` word-boundary anchors. Perl's word-boundary semantics are POSIX-portable.

## Deviations from Plan

**Minor: AC1 reconciliation with Step 5 suggested wording**

- **Found during:** Step 5 (add reinstall note) acceptance check
- **Issue:** The plan's suggested wording for the reinstall note included the literal `/graph-wiki:init` (as `(formerly /graph-wiki:init)`), which would violate AC1's zero-hit invariant.
- **Fix:** The plan explicitly allows rephrasing ("executor may rephrase"). Rephrased to `(previously named init)` — preserves intent (signals the old name to upgrading users) while keeping AC1 grep-clean.
- **Files modified:** `plugins/graph-wiki/README.md` (line 27 only)
- **Verification:** `grep -rEn '\bgraph-wiki:init\b' plugins/ packages/ agents/ scripts/ docs/ README.md CLAUDE.md` returns 0 hits.
- **Committed in:** `5d8160e`

This is not a true "deviation" — the plan explicitly permitted rephrasing. Documenting for transparency.

---

**Total deviations:** 0 auto-fix deviations (1 documented executor wording choice within plan-permitted bounds)
**Impact on plan:** None — all acceptance criteria pass exactly as specified.

## Issues Encountered

None — the sweep executed cleanly. BSD sed's lack of `\b` support was anticipated and handled with `perl -i -pe`.

## User Setup Required

None.

## Commit SHA

- `5d8160e` — `refactor(18-04): sweep active-source /graph-wiki:init → /graph-wiki:bootstrap references`

## Next Phase Readiness

- Active-source portion of CMD-03 is closed.
- Plan 18-05 (historical `.planning/` sweep) runs in parallel — disjoint file set.
- Plan 18-06 (brand-gate lock-in) can now establish a CI gate asserting zero `\bgraph-wiki:init\b` going forward.

## Self-Check: PASSED

- File `plugins/graph-wiki/README.md` — FOUND, contains 3 `/graph-wiki:bootstrap` refs and 1 `reinstall` mention
- File `packages/wiki-io/src/wiki_io/lint/container.py` — FOUND, line 35 contains `/graph-wiki:bootstrap`
- File `packages/wiki-io/src/wiki_io/scan_monorepo.py` — FOUND, line 1157 contains `/graph-wiki:bootstrap`
- Commit `5d8160e` — FOUND in `git log --oneline`
- Active-source grep `\bgraph-wiki:init\b` — returns 0 hits across `plugins/`, `packages/`, `agents/`, `scripts/`, `docs/`, `README.md`, `CLAUDE.md`
- Invariants `init_vault` (53) and `/graph-wiki:ingest` (48) — both unchanged pre→post

---
*Phase: 18-plugin-command-rename*
*Plan: 04*
*Completed: 2026-05-20*
