---
phase: 12-drift-backport-ecosystem-rebrand-m2
plan: 02
subsystem: wiki-io
tags: [drift, backport, wiki-io, lattice-wiki-core, m2]
requires:
  - 12-01 (DRIFT-DECISIONS-RAW.md exists with 11 sections + raw diffs)
provides:
  - canonical-drift-decisions-artifact (packages/wiki-io/DRIFT-DECISIONS.md)
  - persisted-verdict-ledger (.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md)
affects:
  - packages/wiki-io/
tech-stack:
  added: []
  patterns:
    - "Two-file drift ledger pattern (RAW dump + verdict table referencing the dump)"
    - "Pinned upstream SHA in artifact header for auditable re-sync"
key-files:
  created:
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md
    - packages/wiki-io/DRIFT-DECISIONS.md
  modified: []
decisions:
  - "All 11 overlapping module rows resolve as non-PORT — no substantive upstream change warrants backport at this sync"
  - "lint/* row collapsed as a single LEAVE-AHEAD verdict; sub-file inspection found no per-file divergence requiring a footnote"
  - "init_vault.py classified LEAVE-AHEAD (dominant divergence is D-02 lib-ification + WR-01 MCP error handling) even though it also contains a LEAVE-ARCH-flavored package-family choice strip"
metrics:
  duration_minutes: ~15
  tasks_completed: 2
  completed: 2026-05-18
---

# Phase 12 Plan 02: Verdicts and Backports Summary

Assigned SR-03 verdicts to all 11 overlapping module rows from `DRIFT-DECISIONS-RAW.md` and published the canonical `packages/wiki-io/DRIFT-DECISIONS.md` table with the pinned upstream SHA. Zero PORT verdicts — every drift hunk is an intentional wiki-io divergence (lib-ification / MCP error handling / no-tiktoken) or an out-of-v1.2 subsystem strip (package-family / CLI `main()`).

## Verdict Tally

| Verdict | Count | Modules |
|---------|-------|---------|
| IDENTICAL | 1 | `git_state.py` |
| LEAVE-AHEAD | 6 | `append_log.py`, `update_index.py`, `update_tokens.py`, `ingest_work_item.py`, `init_vault.py`, `lint/*` |
| LEAVE-ARCH | 4 | `layout_io.py`, `detect_containers.py`, `scan_monorepo.py`, `ingest_source.py` |
| LEAVE-COSMETIC | 0 | — |
| PORT | 0 | — |

## Backport Commits

None — no PORT verdicts at this sync.

## Plan Commits

| Task | Description | Commit |
|------|-------------|--------|
| 1a | Scaffold drift-verdict scratch template (11 rows) | `64d5588` |
| 1b | Record drift verdicts in scratch (11 rows) | `f43120d` |
| 2 | Publish wiki-io DRIFT-DECISIONS.md (11 rows, 0 PORT) | `16fd3ff` |

## Acceptance Gates

- **SR-04 closure gate:** `uv run pytest` exits 0 (526 passed, 30 skipped) before and after the verdict-recording commits.
- **Task 1 verify:** 11 scratch rows present; every row has an SR-03-vocabulary verdict in column 7; every module spike-row name appears in the scratch file.
- **Task 2 verify:** SHA pin `1b45172a9900842b0f8eea525c8270e7fff50605` in header; all 11 expected module path-literals present in the verdict table; every data row has exactly one SR-03 vocabulary token.

## Modules Requiring Operator Input

None. The plan is marked `autonomous: false` to allow pauses on genuine ambiguity, but every row's verdict was unambiguous after reading the raw diff against the SR-01/SR-02/SR-03 priors. Specifically:
- The 4 LEAVE-ARCH rows all match the planner's operator-prior hints (package-family strip / CLI `main()` strip) verbatim.
- 5 of the 6 LEAVE-AHEAD rows match the planner's hints verbatim (WR-01/WR-02, lib-ification, no-tiktoken, file_work_item shape).
- `init_vault.py` was flagged TBD in the prior — body-diff confirmed all `-` lines are intentional wiki-io strips (lattice_workspace.init dep, sys.exit, package-family choice) and all `+` lines are intentional wiki-io additions (logger, RuntimeError, raw/work mkdir). Net: LEAVE-AHEAD (D-02 lib-ification + WR-01). No PORT-eligible upstream change found.
- `lint/*` was flagged TBD per-file — body-diff confirmed all 8 sub-files share LEAVE-AHEAD: substantive wiki-io divergences (placeholder predicate relocation, kind==package guard) and import-rename-only edits in the rest. No sub-file warrants a different verdict.

## Canonical Verdict Ledger

`.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md` — the populated scratch file is the persisted source-of-truth that the final `packages/wiki-io/DRIFT-DECISIONS.md` was rendered from. Both files cite the same pinned upstream SHA.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1–3 auto-fixes triggered; no Rule 4 architectural pauses.

## Closed Requirements

- BACKPORT-01 (lint/* body-diff inventory) — LEAVE-AHEAD documented
- BACKPORT-02 (init_vault.py body-diff) — LEAVE-AHEAD documented
- BACKPORT-03 (ingest_work_item.py API divergence) — LEAVE-AHEAD documented (`file_work_item` lib shape retained)
- BACKPORT-04 (DRIFT-DECISIONS.md location) — file published at `packages/wiki-io/DRIFT-DECISIONS.md`

## Self-Check: PASSED

- `.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-02-scratch-verdicts.md` — present
- `packages/wiki-io/DRIFT-DECISIONS.md` — present, SHA pin verified
- Commits `64d5588`, `f43120d`, `16fd3ff` — all present in `git log`
- `uv run pytest` — 526 passed, 30 skipped (skips are integration tests gated on env var)
