---
phase: 26-plugin-prompt-source-mirror-sync
plan: 04
subsystem: build-hygiene
tags: [deletion, brand-gate, hard-cut, mirror-invariant-end, D-01, D-02, D-10, D-11, D-13]
dependency_graph:
  requires:
    - 26-03-SUMMARY.md (D-08 three-check provenance gate green)
    - 26-02-SUMMARY.md (all 56 AUDIT rows applied; tree fully un-referenced in scope)
    - 26-AUDIT.md (anchor decisions consumed by Plan 02)
    - 26-CONTEXT.md (D-01/D-02/D-10/D-11/D-13 directives)
  provides:
    - "packages/prompt-sources/ tree deleted (19 files removed)"
    - "pyproject.toml [tool.uv.workspace] exclude entry removed"
    - "scripts/check-brand.sh CHECK 6 block (BRAND-PROMPT-SOURCES) — bans reintroduction of the literal `packages/prompt-sources` under agents/, packages/, plugins/, scripts/, tests/"
    - ".planning/todos/resolved/2026-05-21-phase-26-prompt-sources-deletion.md — audit-trail per Phase 25 PKGCLS pattern"
  affects:
    - "v1.4 milestone close — Phase 26 retires the Phase 23 mirror invariant"
    - "future phases — canonical surfaces (plugins/graph-wiki/, CLAUDE.md.template, prompts/sources/) are single-source-of-truth for prompt anchors"
tech_stack:
  added: []
  patterns:
    - "Brand-gate CHECK block (sequential numbering): CHECK 6 mirrors CHECK 5 structural template (Phase 18/22/23/24 prior art)"
    - "Fixed-string grep (-F) for non-regex path literals — faster + safer than -E"
    - "Allowlist rationale block convention — per-entry comments name R-decision / carry-forward class"
    - "PKGCLS resolved-todo audit trail (Phase 25 pattern) — `.planning/todos/resolved/YYYY-MM-DD-phase-N-<slug>.md`"
key_files:
  created:
    - .planning/todos/resolved/2026-05-21-phase-26-prompt-sources-deletion.md
    - .planning/phases/26-plugin-prompt-source-mirror-sync/26-04-SUMMARY.md
  modified:
    - scripts/check-brand.sh
    - .brand-grep-allow
    - pyproject.toml
  deleted:
    - packages/prompt-sources/ (entire tree, 19 files)
decisions:
  - "D-01/D-02 satisfied in a single commit: `git rm -r packages/prompt-sources/` (19 files) + 1-line `pyproject.toml` exclude removal staged together; uv sync stays coherent (verified post-commit)."
  - "D-10/D-11 CHECK 6 implemented exactly as the plan's <interfaces> spec: -F fixed-string grep against the literal `packages/prompt-sources` under agents/ packages/ plugins/ scripts/ tests/ (.planning/ excluded as historical record), BRAND-PROMPT-SOURCES error tag, summary echo extended."
  - "Allowlist seeding: test_provenance.py is already allowlisted on line 251 (Phase 21 Provenance carry-forward). Per acceptance criterion (`grep -E '^agents/.../test_provenance\\.py$' .brand-grep-allow | wc -l` must return 1), DID NOT duplicate the path entry — added only the Phase 26 §D-11 rationale block referencing the existing line."
  - "Extra allowlist entry (Rule 2/3 deviation, see below): packages/eval-harness/tests/fixtures/post-rebrand-vault/ is a recorded Phase-16 baseline fixture vault that names `packages/prompt-sources` as Test-data (R-02 class). Rewriting would invalidate the seeded baseline. Allowlisted with rationale."
  - "Pre-existing v1.4 audit lattice references (Rule 3 deviation, see below): .planning/v1.4-MILESTONE-INTEGRATION.md, .planning/milestones/v1.4-MILESTONE-AUDIT.md, and .planning/phases/26-... were unallowlisted before Plan 04 (predated this plan's start). Added narrow allowlist entries in the same Plan-meta + Upstream-reference class as Phase 22/23/24 archive exemptions."
metrics:
  duration_minutes: ~25
  tasks_completed: 2
  files_touched: 22
  files_deleted: 19
  files_created: 2
  commits: 2
  test_files_passing: 599
  test_files_skipped: 32
completed: 2026-05-21
---

# Phase 26 Plan 04: packages/prompt-sources/ deletion + brand-gate Summary

**Hard-cut deletion of the 19-file upstream-snapshot tree, single-line `pyproject.toml` exclude removal, new BRAND-PROMPT-SOURCES CHECK 6 in `check-brand.sh`, and full verification (uv sync + 599-test graph-wiki-agent + 599-test eval-harness + brand-gate) green against the resulting tree.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files touched:** 22 (19 deleted + 3 modified + 2 created)

## Accomplishments

- `packages/prompt-sources/` tree removed via `git rm -r` (19 files: SKILL.md, SOURCE-COMMIT, wiki-claude-md-template.md, 6 agents/*, 10 references/*). The Phase 23 D-08 mirror invariant ("whenever `plugins/graph-wiki/.../<X>.md` changes, the `packages/prompt-sources/...` mirror must change in the same commit") becomes moot — the duplicate tree is gone.
- `pyproject.toml`: `exclude = ["packages/prompt-sources"]` line removed from `[tool.uv.workspace]` table; uv workspace resolves cleanly without remnant exclusion state.
- `scripts/check-brand.sh`: CHECK 6 block added (mirrors CHECK 5 structural template), with `-F` fixed-string grep against the literal `packages/prompt-sources` under `agents/ packages/ plugins/ scripts/ tests/`. Path scope EXCLUDES `.planning/` per D-11 (archived milestones, retrospectives, phase histories legitimately reference the deleted tree as historical record). Summary echo extended with `BRAND-PROMPT-SOURCES packages/prompt-sources` tag.
- `.brand-grep-allow`: Phase 26 §D-11 rationale block added; one fixture-vault allowlist entry (recorded test data, R-02 class); two narrow Rule-3 entries for pre-existing v1.4 audit lattice references.
- `.planning/todos/resolved/2026-05-21-phase-26-prompt-sources-deletion.md`: audit-trail file mirroring the Phase 25 PKGCLS pattern, documenting the deletion + canonical-surface re-pointer summary.

## Task Commits

1. **Task 1: Add CHECK 6 to check-brand.sh; seed .brand-grep-allow** — `0e43202` (feat)
2. **Task 2: Delete packages/prompt-sources/, remove pyproject.toml exclude, verify the full gate** — `2523dac` (feat)

## Verification (all four required checks)

```text
1. uv sync                                  → green (workspace resolves, no exclude remnant)
2. uv run --package graph-wiki-agent pytest → 599 passed, 32 skipped (85.22s)
3. uv run --package eval-harness pytest     → 599 passed, 32 skipped (80.16s)
4. bash scripts/check-brand.sh              → exit 0 (BRAND-04 OK ... + BRAND-PROMPT-SOURCES)
```

Final brand-gate summary line emitted on success:

```
BRAND-04 OK: zero unallowlisted hits (BRAND-04 lattice + BRAND-CMD graph-wiki:init|wiki_init + BRAND-CMD-CLI def init( all clean + BRAND-WSAPI vault_path|--vault|"vault_path" + BRAND-WSEVAL vault_path:|vault:|"--vault" + BRAND-PROMPT-SOURCES packages/prompt-sources)
```

## Files Created/Modified

- `scripts/check-brand.sh` — CHECK 6 block (~16 lines) appended after CHECK 5, before the final summary echo. Summary echo extended.
- `.brand-grep-allow` — 4 new rationale blocks: v1.4 milestone audit docs, Phase 26 phase dir, Phase 26 §D-11 (test_provenance.py acknowledgement, no duplicate path), eval-harness post-rebrand-vault fixture.
- `pyproject.toml` — single-line removal: `exclude = ["packages/prompt-sources"]`. `[tool.uv.workspace]` table retained (now `members = [...]` only).
- `.planning/todos/resolved/2026-05-21-phase-26-prompt-sources-deletion.md` — new file, audit-trail.
- `packages/prompt-sources/` — entire tree deleted (19 files via `git rm -r`).

## Brand-gate triage (post-deletion hits)

After Task 2's deletion + pyproject edit, `bash scripts/check-brand.sh` reported 11 unallowlisted CHECK 1 (lattice) hits in `.planning/` paths — verified pre-existing (re-tested via `git stash` against pre-Task-1 tree, also failed with the same 11 hits). All hits classified as Plan-meta + Upstream-reference (same R-class as Phase 22/23/24 archive exemptions already in the allowlist):

| File | Class | Rationale |
|------|-------|-----------|
| `.planning/v1.4-MILESTONE-INTEGRATION.md` | Plan-meta + Upstream-reference | Names the upstream lattice-wiki → graph-wiki rebrand direction throughout |
| `.planning/milestones/v1.4-MILESTONE-AUDIT.md` | Plan-meta + Upstream-reference | Narrates the cores → packages + lattice-wiki → graph-wiki rebrand history |
| `.planning/phases/26-plugin-prompt-source-mirror-sync/` (8 files) | Phase-archive | CONTEXT / AUDIT / PATTERNS / PLAN / DISCUSSION-LOG / SUMMARY narrate the upstream-lattice provenance of the deleted tree |

Resolution: allowlist (per the plan's Task 2 fall-back: "rewrite at source if it's a stray reference, allowlist with `.brand-grep-allow` rationale block only if genuinely load-bearing"). These docs ARE load-bearing — they document why the deletion happened and what was removed. Same allowlist class precedent: `.planning/milestones/v1.3-MILESTONE-AUDIT.md` (line 308), `.planning/phases/22-...` (line 327), `.planning/phases/23-...` (line 329), `.planning/phases/24-...` (line 331).

The expected CHECK 6 hit on `test_provenance.py` did NOT surface — its literal `packages/prompt-sources/foo.md` is already swept by line 251's Phase 21 Provenance carry-forward entry. The newly-discovered CHECK 6 hits on `packages/eval-harness/tests/fixtures/post-rebrand-vault/` (3 files) are recorded fixture-vault Test-data (R-02 class) and allowlisted with rationale.

## Decisions Made

- **Allowlist semantics:** test_provenance.py is already covered by the Phase 21 line 251 entry — adding a duplicate path would either be a no-op or trip the acceptance grep that expects exactly one `^agents/.../test_provenance\\.py$` line. Resolved by adding ONLY the Phase 26 §D-11 rationale comment block (no duplicate path entry).
- **Fixture vault treatment:** `packages/eval-harness/tests/fixtures/post-rebrand-vault/` is recorded baseline data from Phase 16; the fixture intentionally documents the package layout when `packages/prompt-sources/` existed. Rewriting would invalidate the seeded baseline (Test-data R-02). Allowlisted instead of edited.
- **pyproject cleanup choice (per plan's Task 2 reader's-discretion):** kept the `[tool.uv.workspace]` table header even though only `members` remains. The plan's verification (`uv sync`) succeeded either way; left the table for clarity (members declaration is what tells uv this is a workspace root).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pre-existing v1.4 audit lattice references blocked brand-gate**
- **Found during:** Task 2 verification (final `bash scripts/check-brand.sh`)
- **Issue:** CHECK 1 (BRAND-04 lattice) was failing with 11 unallowlisted hits across `.planning/v1.4-MILESTONE-INTEGRATION.md`, `.planning/milestones/v1.4-MILESTONE-AUDIT.md`, and the Phase 26 phase dir. Verified pre-existing (also failed against pre-Task-1 tree via `git stash`). The brand-gate is a required success criterion for Plan 04, so these hits blocked plan completion.
- **Fix:** Added narrow allowlist entries in the same Plan-meta + Upstream-reference class as the existing Phase 22/23/24 archive exemptions. Each entry carries a one-line rationale comment naming its R-class.
- **Files modified:** `.brand-grep-allow`
- **Verification:** `bash scripts/check-brand.sh` → exit 0 with `BRAND-04 OK` summary
- **Committed in:** `2523dac` (Task 2 commit)

**2. [Rule 2 - Missing Critical] CHECK 6 surfaced unanticipated fixture-vault hits not enumerated in plan**
- **Found during:** Task 2 verification (the first `bash scripts/check-brand.sh` run after deletion)
- **Issue:** CHECK 6's `-F packages/prompt-sources` grep hit 3 files under `packages/eval-harness/tests/fixtures/post-rebrand-vault/` (recorded Phase-16 baseline fixture vault). The plan anticipated only `test_provenance.py` as the in-scope hit; the fixture vault was not enumerated.
- **Fix:** Allowlisted the fixture vault dir with a Test-data R-02 rationale. The fixture is recorded measurement data — rewriting would invalidate the seeded Phase-16 baseline used by `packages/eval-harness/tests/test_scanner_regression.py:27` (`FIXTURE_VAULT = ... "post-rebrand-vault"`). The pinned `_EXPECTED_PACKAGE_FILES` list (L31-38) still includes `"prompt-sources"` as part of the recorded fixture-vault schema. Per the plan's Task 2 triage rule: "rewrite at source if it's a stray reference, allowlist with `.brand-grep-allow` rationale block only if genuinely load-bearing" — this is load-bearing as recorded baseline.
- **Files modified:** `.brand-grep-allow`
- **Verification:** brand-gate green; scanner-regression test green (part of 599 passing eval-harness tests).
- **Committed in:** `2523dac` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking from pre-existing state, 1 missing-critical-coverage discovered during gate verification)
**Impact on plan:** Both auto-fixes preserve the plan's success criteria without semantic scope creep. The v1.4 audit allowlist entries follow the established Phase 22/23/24 archive-exemption precedent; the fixture-vault entry follows the Phase 12 round-trip-vault precedent (line 21). No production code rewritten; no rubric / prompt content touched.

## Issues Encountered

- Initial `git stash` / `git stash pop` cycle (used to confirm the v1.4 lattice hits were pre-existing) unstaged the deletion + pyproject edit. Re-staged via `git add` before commit. No data loss; staging state recovered cleanly.

## Phase 26 D-01..D-13 Coverage Cross-Reference

| Decision | Surface | Plan(s) | Status after Plan 04 |
|----------|---------|---------|---------------------|
| D-01 — Delete `packages/prompt-sources/` | tree deletion via `git rm -r` | **04** | **DONE** — 19 files removed in commit `2523dac` |
| D-02 — Remove `exclude` line from pyproject | 1-line edit, same commit as deletion | **04** | **DONE** — line removed in commit `2523dac`; uv sync green |
| D-03 — GitHub-slug rule for anchors | mechanical slug translation | 02 (apply), 03 (verify) | DONE (Plan 02 applied, Plan 03 `slugify` helper verifies) |
| D-04 — Per-anchor audit table | unresolvable-anchor decisions | 01 (audit), 02 (apply) | DONE (`26-AUDIT.md` produced and consumed) |
| D-05 — Drop line-range pins from `# Source:` | Option A 1-line shape | 02 | DONE (all 8 fragments + 4 builders + 6 rubrics use 1-line shape) |
| D-06 — Agent-local sources tree for Bedrock-only roles | new dir + 2 .md files | 02 | DONE (`prompts/sources/{code_reader,synthesizer}.md` created with rebrand) |
| D-07 — Re-anchor LOG_FORMAT/STYLE_RULES to CLAUDE.md.template | RESTORE-CONTENT for 2 headings | 02 | DONE (`## Log format`, `## Style` headings + bodies inserted into template) |
| D-08 — `test_provenance.py` three-check gate | whitelist + resolution + semantic-drift ≥70% | 03 | DONE (all 3 checks live; KNOWN_D09_FINDINGS registry seeded) |
| D-09 — No silent threshold downgrades | KNOWN_D09_FINDINGS registry | 03 | DONE (6 narrow-port findings registered with rationale) |
| D-10 — New CHECK block in `check-brand.sh` numbered after current ceiling | CHECK 6 (sequential after CHECK 5) | **04** | **DONE** — CHECK 6 inserted in commit `0e43202` |
| D-11 — Path-scope ban for `packages/prompt-sources` literal under `agents/ packages/ plugins/ scripts/ tests/` (.planning/ excluded) | -F fixed-string grep | **04** | **DONE** — CHECK 6 uses `-F` against the correct scope; .planning/ exempted |
| D-12 — No coverage for `prompt_sources` Python module name | path-level block in D-11 catches future reintroduction | **04** | **DONE** — path-level CHECK 6 is the only enforcement layer; no separate Python-module check (intentional, per D-12) |
| D-13 — Ordered milestones (audit → re-anchor → test upgrade → delete + gate) | 4 plans, 1 per milestone | 01, 02, 03, **04** | **DONE** — Plan 04 is the final ordered milestone (delete + gate) |

All 13 v1.4 decisions are covered with at least one explicit citation in `must_haves.truths` across Plans 01-04.

## User Setup Required

None — no external service configuration required. All work is local to the repo tree, the brand-gate, and the test suite.

## Next Phase Readiness

- **Phase 26 fully closed.** The mirror invariant from Phase 23 D-08 is retired; every prompt-anchor in the repo points at exactly one canonical surface.
- **Brand-gate hardened.** CHECK 6 prevents reintroduction of the deleted-tree path literal under all source paths; future PRs that re-create the tree (intentionally or accidentally) will fail CI.
- **No outstanding deferred items from Plan 04.** Plan 03's `deferred-items.md` (6 D-09 narrow-port findings) remains as documented v1.5+ candidates, but is unrelated to Plan 04's surface.

## Self-Check: PASSED

Verified via direct file/commit inspection:

- `[ -f scripts/check-brand.sh ]` → FOUND (CHECK 6 present, lines after CHECK 5)
- `[ ! -d packages/prompt-sources ]` → CONFIRMED DELETED
- `[ -f .planning/todos/resolved/2026-05-21-phase-26-prompt-sources-deletion.md ]` → FOUND (contains `Resolved by Phase 26`)
- `[ -f .planning/phases/26-plugin-prompt-source-mirror-sync/26-04-SUMMARY.md ]` → THIS FILE
- `git log --oneline --all | grep -q 0e43202` → FOUND (Task 1)
- `git log --oneline --all | grep -q 2523dac` → FOUND (Task 2)
- `grep -c 'packages/prompt-sources' pyproject.toml` → 0 (line removed)
- `bash scripts/check-brand.sh; echo $?` → 0 (gate green)

---
*Phase: 26-plugin-prompt-source-mirror-sync*
*Plan: 04*
*Completed: 2026-05-21*
