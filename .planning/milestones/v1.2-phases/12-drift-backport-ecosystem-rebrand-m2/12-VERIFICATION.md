---
phase: 12-drift-backport-ecosystem-rebrand-m2
verified: 2026-05-18T19:06:18Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 12: Drift Backport + Ecosystem Rebrand (M2) Verification Report

**Phase Goal:** Substantive upstream improvements from `lattice-wiki-core` land in `wiki-io`, deliberate forks stay forked with written rationale, and no `lattice*` symbol survives in the in-scope code/planning surface.

**Verified:** 2026-05-18T19:06:18Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `packages/wiki-io/lint/` matches upstream behavior on substantive changes; `DRIFT-DECISIONS.md` records a per-file verdict (port vs. leave) with one-line rationale for each candidate module from spike 002. | VERIFIED | `packages/wiki-io/DRIFT-DECISIONS.md` exists; 11 verdict-table rows confirmed (`grep -cE '^\| `\`' = 11`); each row has SR-03 vocabulary verdict + one-line rationale; lint/* row = LEAVE-AHEAD (wiki-io is ahead: `_is_placeholder_target` relocation + `kind==package` guard); SHA pin `1b45172a9900842b0f8eea525c8270e7fff50605` in header. |
| 2 | `init_vault.py` and `ingest_work_item.py` divergence decisions are documented in `DRIFT-DECISIONS.md` with backport applied or explicit leave-alone justification. | VERIFIED | Row 6 (`init_vault.py`) = LEAVE-AHEAD with rationale "D-02 lib-ification + WR-01: wiki-io drops `lattice_workspace.init` dep, swaps `sys.exit` for `RuntimeError`..."; Row 5 (`ingest_work_item.py`) = LEAVE-AHEAD with rationale "D-02 lib-ification: wiki-io exposes `file_work_item(wiki, fm, body, ...)` library shape..." Both justifications present in the verdict table. |
| 3 | `grep -rE 'lattice\|LATTICE\|lattice_workspace\|lattice_wiki_core' packages/ agents/ .planning/ CLAUDE.md` returns zero hits (excluding commit-history refs and explicit allowlist entries). | VERIFIED | `bash scripts/check-brand.sh` exits 0 ("BRAND-04 OK: zero unallowlisted hits"). Empirically confirmed: 273 raw hits, 0 unallowlisted after `.brand-grep-allow` filtering. Adversarial test: injected `import lattice_workspace` regression into `packages/wiki-io/src/wiki_io/_test_regression.py` — gate correctly exited 1 with "BRAND-04 FAIL: 1 unallowlisted hits"; restored to green after removal. |
| 4 | `.planning/spikes/CONVENTIONS.md` correctly reflects `packages/` (not `cores/`). | VERIFIED | `grep -E 'cores/' .planning/spikes/CONVENTIONS.md` returns empty (exit 1); `grep 'packages/'` finds 2 references on lines 9 and 28. |
| 5 | Full test suite passes (`uv run pytest`) — no regressions from rename surgery. | VERIFIED | `uv run pytest` exits 0: **526 passed, 30 skipped, 19 snapshots passed** in 34.90s. Skips are integration tests gated on `GRAPH_WIKI_RUN_INTEGRATION=1` env var. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/wiki-io/DRIFT-DECISIONS-RAW.md` | Per-file unified diff dump of 11 overlapping spike-table module rows vs upstream @ pinned SHA; lint/* collapsed with 8 inline sub-file diffs | VERIFIED | File exists (78685 bytes); header pins SHA `1b45172a9900842b0f8eea525c8270e7fff50605`; `grep -c '^### '` = 11 top-level sections; `grep -c '^#### lint/'` = 8 inline sub-sections. |
| `scripts/drift-diff.sh` | Reproducible diff generator script | VERIFIED | Exists, executable (`-rwxr-xr-x`); passes `bash -n`; contains SHA pin; uses `set -euo pipefail`; honors `UPSTREAM_REPO` env override per WR-01 fix. |
| `packages/wiki-io/DRIFT-DECISIONS.md` | Human-verdict table for 11 overlapping module rows | VERIFIED | Exists (6216 bytes); SHA pin in header; 11 verdict rows; every row has SR-03 vocabulary token; rationale citations to D-02/WR-01/WR-02 and PROJECT.md stripped subsystems present. |
| `.planning/phases/12-.../12-02-scratch-verdicts.md` | Persisted verdict scratch ledger | VERIFIED | Exists; referenced by 12-02 SUMMARY as canonical pre-publication source. |
| `.planning/phases/12-.../12-03-carry-forward-refs.md` | Inventory of intentionally-preserved `lattice` references | VERIFIED | Exists; 52 entries across 10 classes per 12-03 SUMMARY; consumed by 12-04 allowlist authoring. |
| `plugins/` | Empty directory placeholder for Phase 14 | VERIFIED | Exists with `plugins/.gitkeep`. |
| `.planning/spikes/CONVENTIONS.md` | Reference corrected `cores/` → `packages/` | VERIFIED | `cores/` absent; `packages/` present on lines 9, 28 (BRAND-02). |
| `scripts/check-brand.sh` | Re-runnable BRAND-04 grep gate | VERIFIED | Exists, executable; passes `bash -n`; uses `set -euo pipefail`; grep pattern matches `lattice\|LATTICE\|lattice_workspace\|lattice_wiki_core`; grep target list includes `plugins/`; strips blank/comment lines from allowlist (CR-01 fix); excludes `__pycache__`/`*.pyc` (bb84a6d). |
| `.brand-grep-allow` | Versioned allowlist with per-entry rationale | VERIFIED | Exists (10486 bytes / 167 lines); R-01/R-02/R-03/R-04 section headers present; carry-forward section header references `12-03-carry-forward-refs.md`; per-entry `# rationale:` comments present. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `packages/wiki-io/DRIFT-DECISIONS-RAW.md` | upstream `lattice-wiki-core` source @ pinned SHA | `diff -u` (pinned SHA in header) | WIRED | Header contains pinned SHA `1b45172a9900842b0f8eea525c8270e7fff50605`; script `drift-diff.sh` verifies upstream HEAD == pinned SHA before emitting diffs. |
| `packages/wiki-io/DRIFT-DECISIONS.md` | `packages/wiki-io/DRIFT-DECISIONS-RAW.md` | table verdicts reference the raw diff dump | WIRED | DRIFT-DECISIONS.md line 4: "**Raw diff source-of-truth:** [`DRIFT-DECISIONS-RAW.md`](./DRIFT-DECISIONS-RAW.md)" — both files share the same pinned SHA. |
| PORT verdict rows | atomic backport commits | `backport-commit-sha` column | N/A | Zero PORT verdicts at this sync (all 11 rows = IDENTICAL/LEAVE-AHEAD/LEAVE-ARCH). All `backport-commit-sha` cells = `—` as required by plan 02 for non-PORT verdicts. |
| `scripts/check-brand.sh` | `.brand-grep-allow` | `grep -vF -f <(grep -vE '^[[:space:]]*(#\|$)' .brand-grep-allow)` | WIRED | Script line 40 wires allowlist as filter; CR-01 fix correctly strips blanks/comments to prevent BSD-grep empty-pattern footgun; verified empirically via injected regression. |
| `.brand-grep-allow` | `12-03-carry-forward-refs.md` | comment section header references file path | WIRED | Allowlist lines 90-95 contain "Phase 12 plan-03 carry-forward refs (from .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md)"; 22 per-file entries + 9 post-hoc additions follow. |

### Data-Flow Trace (Level 4)

Phase artifacts are documentation files + shell scripts + an allowlist — none render dynamic data through fetch/state paths. Behavior is verified via shell execution in Behavioral Spot-Checks and Probe Execution below.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Brand grep gate exits 0 on clean tree | `bash scripts/check-brand.sh; echo $?` | "BRAND-04 OK: zero unallowlisted hits" / exit 0 | PASS |
| Brand grep gate exits 1 on regression | `cp lattice_import_file packages/wiki-io/src/wiki_io/_test.py && bash scripts/check-brand.sh` | "BRAND-04 FAIL: 1 unallowlisted hits" / exit 1 | PASS |
| Raw diff dump has 11 top-level rows | `grep -c '^### ' packages/wiki-io/DRIFT-DECISIONS-RAW.md` | 11 | PASS |
| Raw diff dump has 8 lint sub-file diffs | `grep -c '^#### lint/' packages/wiki-io/DRIFT-DECISIONS-RAW.md` | 8 | PASS |
| Verdict table has 11 rows | `grep -cE '^\| \`' packages/wiki-io/DRIFT-DECISIONS.md` | 11 | PASS |
| SHA pin in DRIFT-DECISIONS.md header | `head -10 packages/wiki-io/DRIFT-DECISIONS.md \| grep -c 1b45172a9900842b0f8eea525c8270e7fff50605` | ≥1 | PASS |
| `cores/` absent from CONVENTIONS.md | `grep -E 'cores/' .planning/spikes/CONVENTIONS.md` | empty (rc=1) | PASS |
| layout_io.py accepts legacy + new sentinels (WR-02) | Read `packages/wiki-io/src/wiki_io/layout_io.py` lines 35-48 | Both `LAYOUT_START` and `_LEGACY_LAYOUT_START` defined; `_BLOCK_RE` uses alternation `(?:NEW\|LEGACY)` | PASS |
| `plugins/` placeholder exists | `ls -la plugins/` | Contains `.gitkeep` | PASS |
| pytest suite green | `uv run pytest` | 526 passed, 30 skipped, 19 snapshots passed | PASS |

### Probe Execution

Phase 12 is a documentation + rebrand phase. The single shell-level "probe" is the brand gate, captured under Behavioral Spot-Checks above. No `scripts/*/tests/probe-*.sh` files exist in this repo — convention not adopted.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| BACKPORT-01 | 12-01, 12-02 | Body-diff inventory of `lint/*` (8 files); substantive upstream changes backported, identical contracts left alone, decision logged per file. | SATISFIED | DRIFT-DECISIONS-RAW.md contains 8 inline `#### lint/` sub-section diffs; DRIFT-DECISIONS.md row 7 (`lint/*`) verdict = LEAVE-AHEAD with rationale documenting `_is_placeholder_target` relocation and `kind==package` guard. Per 12-02 SUMMARY: sub-file inspection found no per-file divergence requiring different verdict. |
| BACKPORT-02 | 12-01, 12-02 | Body-diff `init_vault.py` against upstream; substantive changes backported, otherwise documented as "leave-alone" with reason. | SATISFIED | DRIFT-DECISIONS.md row 6 verdict = LEAVE-AHEAD with rationale citing D-02 lib-ification + WR-01 (`lattice_workspace.init` dropped, `sys.exit`→`RuntimeError`, `print`→`logger`). |
| BACKPORT-03 | 12-01, 12-02 | `ingest_work_item.py` API divergence decision recorded — `file_work_item` lib shape retained unless backport rationale emerges. | SATISFIED | DRIFT-DECISIONS.md row 5 verdict = LEAVE-AHEAD with rationale "D-02 lib-ification: wiki-io exposes `file_work_item(wiki, fm, body, ...)` library shape... per PROJECT.md / BACKPORT-03". |
| BACKPORT-04 | 12-01, 12-02 | All "leave" decisions from spike 002 §Investigation A documented in `packages/wiki-io/DRIFT-DECISIONS.md`. | SATISFIED | File exists at canonical path; 11 rows cover full spike-table; all leave-decisions have rationale text citing Phase 11 D-IDs, WR-01/WR-02, or stripped subsystems. |
| BRAND-01 | 12-03 | All legacy upstream `lattice`/`LATTICE`/`lattice_workspace`/`lattice_wiki_core` references renamed to `graph-wiki` (kebab) or `graph_wiki` (snake). | SATISFIED | 5 atomic commits (`00d3e6f`, `4291c94`, `ccb5876`, `ed8229c`, `71c125f`) swept all in-scope surfaces; verified by `check-brand.sh` exit 0 + empirical 0 unallowlisted hits. |
| BRAND-02 | 12-03 | `.planning/spikes/CONVENTIONS.md` `cores/` → `packages/` reference corrected. | SATISFIED | `cores/` absent from file; `packages/` present on lines 9 and 28. |
| BRAND-04 | 12-04 | `scripts/check-brand.sh` reports zero unallowlisted hits across in-scope paths after rebrand. | SATISFIED | Script exists, executable, gates correctly green; empirical regression injection confirms gate is not silently passing (CR-01 fix verified). |

No ORPHANED requirements: REQUIREMENTS.md maps exactly 7 IDs to Phase 12 (BACKPORT-01..04, BRAND-01, BRAND-02, BRAND-04); all 7 are claimed by Phase 12 plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `packages/wiki-io/src/wiki_io/init_vault.py` | 154-158 | Stale docstring claim "Phase 5 will provide a workspace-bootstrap equivalent" | Info | Pre-existing, surfaced in IN-01 of REVIEW.md; not introduced by Phase 12. |
| `packages/wiki-io/src/wiki_io/lint/container.py` | 35 | User-facing message references non-existent `/graph-wiki:bootstrap` slash command | Info | Pre-existing forward-reference flagged in IN-02; slash command lands in Phase 14. |
| `packages/wiki-io/src/wiki_io/scan_monorepo.py` | 834 | `_dt.date.fromtimestamp` ignores timezone | Info | Pre-existing per IN-03; predates Phase 12. |

No BLOCKER or WARNING anti-patterns. No debt markers (`TBD`/`FIXME`/`XXX`) introduced by Phase 12 that lack issue references.

### Human Verification Required

None. All success criteria are programmatically verifiable: grep gate execution, file existence, header SHA pin, table row counts, pytest exit code. Visual / UX behavior is not in scope for this phase.

### Code Review Closure

A `12-REVIEW.md` finding 1 BLOCKER (CR-01: brand gate silently passing open on macOS BSD grep) and 5 WARNINGS was filed. All findings resolved in commits `c2f1692..bb84a6d`:

- **CR-01** (gate fail-open): Fixed in `c2f1692` — strip blank/comment lines via `<(grep -vE ...)`; verified empirically via regression injection. Hardened further in `bb84a6d` by excluding `__pycache__`/`*.pyc`.
- **WR-01** (`drift-diff.sh` hardcoded path): Fixed in `2d43c3e` — `UPSTREAM_REPO="${UPSTREAM_REPO:-/Users/pat/Personal/lattice}"`.
- **WR-02** (layout sentinel break): Fixed in `6f4199c` — `read_layout()` accepts both `<!-- lattice-wiki:layout:* -->` and `<!-- graph-wiki:layout:* -->`; `write_layout()` emits only new form. Allowlist entry added in `3b2db48`. Preserves CLAUDE.md §Constraints "must read existing upstream lattice-wiki vaults without modification".
- **WR-03** (comment-pattern fragility): Resolved by CR-01 fix (comments now stripped before being passed as patterns).
- **WR-04** (stale `LINTED_TOPS` comment): Fixed in `f3d6aed`.
- **WR-05** (`date -u` portability comment): Fixed in `639080b`.

### Gaps Summary

None. All 5 ROADMAP success criteria are met with codebase evidence. All 7 phase requirements are SATISFIED. The brand gate has been adversarially tested (regression injection confirms it fails on unallowlisted hits) — the gate is NOT silently passing. The format-compatibility constraint from project CLAUDE.md is preserved via the dual-sentinel `_BLOCK_RE`. The test suite passes (526 passed). All review findings closed.

---

_Verified: 2026-05-18T19:06:18Z_
_Verifier: Claude (gsd-verifier)_
