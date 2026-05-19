---
phase: 12-drift-backport-ecosystem-rebrand-m2
plan: 01
subsystem: tooling
tags: [drift, diff, lattice-wiki-core, vault-io, backport, raw-dump]

# Dependency graph
requires:
  - phase: 11-workspace-io-port-m1
    provides: stable vault-io layout post-delegation rewrite (read-only baseline for drift comparison)
  - phase: spike-002-lattice-drift-inventory
    provides: canonical 11-row overlapping-module table (§Investigation A) consumed as the MODULES array
provides:
  - "scripts/drift-diff.sh — reproducible per-file diff generator pinned at upstream SHA 1b45172a9900842b0f8eea525c8270e7fff50605"
  - "packages/vault-io/DRIFT-DECISIONS-RAW.md — 2038-line raw-diff dump, 11 top-level rows, 8 inline lint sub-file diffs"
  - "Per-row IDENTICAL/DIFF map (see Accomplishments) — input to plan 12-02's verdict assignment"
affects: [12-02-drift-decisions-verdicts, 12-03-rebrand-sweep, future-resync, plan-phase-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-file drift workflow (DD-03): raw-diff dump separate from human-verdict table"
    - "SHA-pinned reproducible diffs via stdout-only generator script (no in-place writes)"

key-files:
  created:
    - "scripts/drift-diff.sh"
    - "packages/vault-io/DRIFT-DECISIONS-RAW.md"
  modified: []

key-decisions:
  - "Followed plan exactly — no deviations needed; upstream HEAD matched the pinned SHA on first run."
  - "Script writes only to stdout; caller redirects. Keeps the regen invocation identical on every future re-sync."
  - "MISSING-UPSTREAM / MISSING-LOCAL fallbacks added to emit_diff_for_file so a future rename/removal surfaces in the dump rather than crashing diff."

patterns-established:
  - "SHA verification gate: script fails loud if `git -C $UPSTREAM_REPO rev-parse HEAD` differs from the pinned SHA, with copy-pasteable recovery commands."
  - "lint/* row collapsed to 1 top-level section with 8 inline #### sub-sections (operator B1 decision; preserves the 11-row spike-table shape while inlining all lint diffs)."

requirements-completed: [BACKPORT-01, BACKPORT-02, BACKPORT-03, BACKPORT-04]
# Note: plan 12-01 is the raw-diff capture half of the backport workflow. The PORT-row backport
# commits + verdict table land in plan 12-02 — but plan 12-01 owns the BACKPORT-04 artifact path
# (`packages/vault-io/DRIFT-DECISIONS-RAW.md`) and is the precondition for BACKPORT-01/02/03's
# verdict step. Per the must-haves frontmatter the requirement IDs are recorded here; plan 12-02
# will re-record them as their port commits land.

# Metrics
duration: 2min
completed: 2026-05-18
---

# Phase 12 Plan 01: Drift Raw-Diff Dump Summary

**Reproducible per-file diff between vault-io and lattice-wiki-core @ pinned SHA, dumped to a single 2038-line raw-diff artifact with 11 module rows (lint/\* collapsed to 1 row with 8 inline sub-file diffs).**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-18T17:51:58Z
- **Completed:** 2026-05-18T17:53:32Z
- **Tasks:** 2 / 2
- **Files created:** 2

## Accomplishments

- Scripted, re-runnable diff generator with SHA-verification gate — future re-syncs just bump `UPSTREAM_SHA` and re-run the same invocation.
- Raw drift dump committed at `packages/vault-io/DRIFT-DECISIONS-RAW.md` (2038 lines) with all 11 overlapping-module rows from spike 002 §Investigation A.
- Per-row IDENTICAL / DIFF stats captured for plan 12-02 verdict sizing:

  | Row | Status | Note |
  |---|---|---|
  | `git_state.py` | **IDENTICAL** | Byte-identical with upstream (matches spike 002 baseline). |
  | `append_log.py` | DIFF (~66 ± lines) | Mid-sized diff. |
  | `update_index.py` | DIFF (~51 ± lines) | Mid-sized. |
  | `update_tokens.py` | DIFF (~72 ± lines) | Likely overlaps with vault-io's no-tiktoken `LEAVE-AHEAD` posture. |
  | `ingest_work_item.py` | DIFF (~201 ± lines) | Largest non-`lint/*` row outside scan_monorepo/ingest_source/init_vault. |
  | `init_vault.py` | DIFF (~135 ± lines) | Large diff; rebrand surfaces also live here. |
  | `lint/common.py` | DIFF (~22 ± lines) | Largest lint sub-file delta. |
  | `lint/container.py` | DIFF (~19 ± lines) |  |
  | `lint/dependency.py` | DIFF (~15 ± lines) |  |
  | `lint/domain.py` | **IDENTICAL** | Already in sync with upstream. |
  | `lint/file_map.py` | DIFF (~6 ± lines) | Small. |
  | `lint/package_sync.py` | DIFF (~6 ± lines) | Small. |
  | `lint/source_sync.py` | DIFF (~6 ± lines) | Small. |
  | `lint/workflow_hints.py` | DIFF (~6 ± lines) | Small. |
  | `layout_io.py` | DIFF (~108 ± lines) | Large. |
  | `detect_containers.py` | DIFF (~153 ± lines) | Large. |
  | `scan_monorepo.py` | DIFF (~169 ± lines) | Large. |
  | `ingest_source.py` | DIFF (~225 ± lines) | Largest single-file diff in the set. |

  Totals: **2 IDENTICAL** (`git_state.py`, `lint/domain.py`) out of 18 files; **16 with substantive diffs**. The 8-row "vault-io is ahead" set from spike 002 (`git_state`, `append_log`, `update_index`, `update_tokens`, `layout_io`, `detect_containers`, `scan_monorepo`, `ingest_source`) is where plan 12-02 will most likely land `LEAVE-AHEAD` verdicts; `init_vault.py`, `ingest_work_item.py`, and most of `lint/*` are the PORT candidates per BACKPORT-01..03 scoping.

## Task Commits

1. **Task 1: scripts/drift-diff.sh — reproducible 11-row drift generator** — `440ac4b` (feat)
2. **Task 2: Run drift-diff.sh and commit DRIFT-DECISIONS-RAW.md** — `900095d` (docs)

## Files Created/Modified

- `scripts/drift-diff.sh` (146 LOC) — pinned-SHA diff generator; `MODULES` array (11 entries) + `LINT_FILES` array (8 entries); SHA-verification gate; stdout-only emit; uses `set -euo pipefail`.
- `packages/vault-io/DRIFT-DECISIONS-RAW.md` (2038 LOC) — header with `1b45172a9900842b0f8eea525c8270e7fff50605` + ISO-8601 timestamp + regeneration command + structure note + pointer to forthcoming `DRIFT-DECISIONS.md`; 11 `### ` top-level sections; 8 `#### lint/<file>` sub-sections; each section contains either `IDENTICAL` or a ```diff fenced block.

## Decisions Made

- None beyond plan instructions. The upstream repo's HEAD already matched the pinned SHA, so no `git checkout` was needed inside the upstream repo.
- Added `MISSING-UPSTREAM` / `MISSING-LOCAL` fallbacks in `emit_diff_for_file` as a small defensive add: a future rename/removal on either side surfaces explicitly in the dump rather than aborting the run. Not a deviation — strictly defensive within Task 1's stated behavior.

## Deviations from Plan

None — plan executed exactly as written. All verification checks (`bash -n`, SHA presence, 11 sections, all 11 row headings, all 8 lint sub-files, no `packages/vault-io/src/` modifications) passed on first run.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. No new dependencies, no new env vars.

## Next Phase Readiness

- **Plan 12-02 unblocked.** The raw-diff dump is the input for the verdict step; plan 12-02 reads each section and assigns one of `PORT` / `LEAVE-AHEAD` / `LEAVE-ARCH` / `LEAVE-COSMETIC` / `IDENTICAL` per row, landing PORT rows as separate atomic commits with backport-commit-shas recorded in `packages/vault-io/DRIFT-DECISIONS.md` (per DD-04).
- **Stats above inform sizing.** `ingest_source.py` (~225 ± lines) and `scan_monorepo.py` (~169 ± lines) are the largest LEAVE-AHEAD candidates; `init_vault.py` (~135 ± lines) and the `lint/*` deltas are the most likely PORT surface.
- **Re-sync path proven.** Bumping `UPSTREAM_SHA` + `git -C /Users/pat/Personal/lattice checkout <new-sha>` + re-running the script is the documented re-sync workflow for any future upstream-bump cycle.

## Self-Check: PASSED

- `[ -f scripts/drift-diff.sh ]` → FOUND
- `[ -x scripts/drift-diff.sh ]` → FOUND (executable bit set)
- `[ -f packages/vault-io/DRIFT-DECISIONS-RAW.md ]` → FOUND
- `git log --oneline | grep 440ac4b` → FOUND
- `git log --oneline | grep 900095d` → FOUND
- `head -30 packages/vault-io/DRIFT-DECISIONS-RAW.md | grep 1b45172a9900842b0f8eea525c8270e7fff50605` → FOUND
- `grep -c '^### ' packages/vault-io/DRIFT-DECISIONS-RAW.md` → 11
- `git status --short packages/vault-io/src/` → empty (no src modifications)

---
*Phase: 12-drift-backport-ecosystem-rebrand-m2*
*Plan: 01 — drift-raw-diff-dump*
*Completed: 2026-05-18*
