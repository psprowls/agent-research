---
phase: 25-packages-dir-misclassification-fix
plan: 01
subsystem: graph-wiki
tags: [vault-io, detect_containers, classifier, _classify_dir, bootstrap, monorepo, packages]

# Dependency graph
requires:
  - phase: 24-eval-harness-workspace-rename
    provides: stable v1.4 workspace-rename baseline (no overlapping concerns; Phase 25 is independent per ROADMAP)
provides:
  - "_classify_dir Rule 3 is now a single permissive >=1-manifested-child branch"
  - "graph-wiki-agent bootstrap on this repo correctly classifies packages/ as `package` with children_count=5"
  - "Honest `reason` strings on permissive package classifications name what was skipped"
  - "Plugin reference doc detection-workflow.md kept in lockstep with the classifier change"
  - "Phase 25 ROADMAP success criteria reflect the D-12/D-13 revisions (4 SCs, --interactive deferred)"
  - "Bug-report todo 2026-05-20-fix-packages-dir-misclassification moved to resolved/ with Phase 25 footer"
affects: [graph-wiki bootstrap, vault-io detect, init_vault interactive prompt path (future --interactive backlog), eval-harness fixture detection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Permissive >=1-manifested-child heuristic for monorepo `packages/` containers (replaces old all-or-nothing gate)"
    - "Honest reason strings naming silently-skipped sibling dirs and loose .md files"

key-files:
  created: []
  modified:
    - packages/vault-io/src/vault_io/detect_containers.py
    - packages/vault-io/tests/test_detect_containers.py
    - plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md
    - .planning/ROADMAP.md
    - .planning/todos/resolved/2026-05-20-fix-packages-dir-misclassification.md  # moved from pending/

key-decisions:
  - "D-01: Rule 3 is permissive — >=1 manifested child wins; non-manifested siblings and loose .md at the container root are silently excluded from the wiki layout"
  - "D-02: children_count for `package` classifications reports manifested-child count (the count that actually gets wiki pages), not raw subdir count; reason string is honest about what was skipped"
  - "D-03: the old all-or-nothing gate (len(manifest_kids) == len(children) and not md_files) is removed; the mixed->ambiguous branch no longer exists"
  - "D-04: `ambiguous` retained only for the fallback branches (empty/unrecognized dirs)"
  - "D-06: plugin shim plugins/graph-wiki/.../scripts/detect_containers.py auto-inherits the change via `from vault_io.detect_containers import main` — no plugin-side port needed"
  - "D-12: --interactive flag on graph-wiki-agent bootstrap is deferred OUT of Phase 25; ROADMAP SC#4 removed"
  - "D-13: ROADMAP SC#5 reworded to drop --interactive visibility clause"

patterns-established:
  - "Permissive classifier rule: when a heuristic has a mixed signal, prefer the productive outcome (package classification) and silently exclude the non-conforming children rather than flagging the whole container ambiguous"
  - "Honest classifier `reason` strings: surface skipped children explicitly (e.g. `5/6 children have manifests; 1 dir(s) and 0 loose .md skipped`) instead of opaque counts"

requirements-completed: [PKGCLS-01, PKGCLS-02, PKGCLS-03, PKGCLS-04, PKGCLS-05]

# Metrics
duration: 6min
completed: 2026-05-21
---

# Phase 25 Plan 01: packages-dir-misclassification-fix Summary

**`_classify_dir` Rule 3 collapsed to a single permissive >=1-manifested-child branch, with honest reason strings and full plugin-reference-doc lockstep; `graph-wiki-agent bootstrap` on this repo now classifies `packages/` (5/6 manifested) as `package` instead of silently skipping it.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-21T15:30:58Z
- **Completed:** 2026-05-21T15:36:57Z
- **Tasks:** 6 (5 with edits, 1 verification gate)
- **Files modified:** 5 (1 rename)

## Accomplishments

- Rewrote `_classify_dir` Rule 3 in `packages/vault-io/src/vault_io/detect_containers.py` per locked decisions D-01..D-03: replaced two-branch logic (all-or-nothing `package` + mixed `ambiguous`) with a single permissive branch (>=1 manifested child → `package`, `children_count = len(manifest_kids)`, honest skipped-summary reason).
- Added 5 new unit tests pinning the new contract: 3 mandatory per D-09 (mixed-manifest, loose-md, empty-fallback) plus 2 recommended (single-manifested D-01 explicit, docs Rule 1 regression-guard).
- Verified operationally on this very repo: with a synthetic `.graph-wiki.yaml`, `uv run python -m vault_io.detect_containers --json` emits `{"source": "packages", "classification": "package", "children_count": 5, "reason": "5/6 children have manifests; 1 dir(s) and 0 loose .md skipped"}` — the bug-repro shape now resolves correctly.
- Updated plugin reference doc `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` per D-07/D-08: rule 3 wording now uses the literal `≥1 manifested child` token; the two contradicting bullets in "Ambiguous containers" subsection deleted.
- Revised `.planning/ROADMAP.md` Phase 25 block per D-12/D-13: one-liner reframed (`majority-manifest` → `permissive`, `--interactive` clause dropped); SCs collapsed from 5 to 4 (SC#4 deleted, SC#5 reworded + renumbered, SC#3 rewritten to describe the passthrough-shim D-06 guarantee).
- Resolved the pending bug-report todo via `git mv` (94% rename detected), with a "Resolved by Phase 25" footer appended; YAML frontmatter and original body preserved untouched.

## Task Commits

Each task was committed atomically on `worktree-phase-25-discuss`:

1. **Task 1 (RED): Add 5 unit tests pinning permissive Rule 3 contract** — `bbdeaa9` (test)
2. **Task 2 (GREEN): Rewrite `_classify_dir` Rule 3 to permissive >=1-manifest heuristic** — `9681394` (fix)
3. **Task 3: Update detection-workflow.md per D-07/D-08** — `1db8b6d` (docs)
4. **Task 4: Revise ROADMAP Phase 25 success criteria per D-12/D-13** — `adb19fb` (docs)
5. **Task 5: `git mv` pending todo to resolved/ with Phase 25 footer** — `c961fc5` (chore)
6. **Task 6: Full-workspace verification gate** — no commit (verification-only; results in this summary)

_TDD gate compliance: RED (`bbdeaa9` test commit, 3 failing) → GREEN (`9681394` fix commit, all 9 passing). No refactor commit needed — diff stayed surgical at 17/-11._

## Files Created/Modified

- `packages/vault-io/src/vault_io/detect_containers.py` — `_classify_dir` Rule 3 collapsed to a single permissive branch (lines 112-134 in current file); old all-or-nothing gate and mixed→ambiguous branch removed; fallback branches at 131-145 (now 142-156) preserved unchanged per D-04.
- `packages/vault-io/tests/test_detect_containers.py` — 5 new test functions appended; original 4 tests untouched.
- `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` — rule 3 (line 14) reworded to use `≥1 manifested child` language; "Ambiguous containers" subsection (lines 32-33) loses two contradicting bullets, retains only the empty/unrecognized bullet.
- `.planning/ROADMAP.md` — Phase 25 one-liner (line 81) and detail block (success criteria at lines 130-133) updated per D-12/D-13.
- `.planning/todos/resolved/2026-05-20-fix-packages-dir-misclassification.md` — moved from `pending/` via `git mv` (94% rename); 5-line Resolution footer appended.

## Decisions Made

All implementation decisions followed the locked Phase 25 CONTEXT decisions D-01..D-13. No new decisions surfaced during execution.

Two minor implementation-author choices within the latitude the plan explicitly granted:
- Reason-string wording for the permissive case: `"{N}/{M} children have manifests; {X} dir(s) and {Y} loose .md skipped"` (plan §Task 2 step 3 made wording author's discretion as long as invariants `f"{N}/{M}"` and `"skipped"` were present — both held).
- Recommended Tests 4 and 5 (single-manifested + docs-Rule-1 regression-guard) were added rather than skipped, because the ~25 LOC cost was small and locks D-01's "≥1 wins" semantics + Rule 1 rules-order survival explicitly.

## Deviations from Plan

**None — plan executed exactly as written.**

No deviation rules (1-4) fired during execution. The plan's locked decisions D-01..D-13 were sufficiently detailed that no auto-fixes, missing-functionality additions, or architectural questions surfaced. Out-of-scope guards (D-06 plugin shim, D-12 init.py / `--interactive`, no `helpers.py`) held cleanly.

## Issues Encountered

### Pre-existing test failures in `agents/graph-wiki-agent/` (out of scope, not caused by Phase 25)

The Task 6 full-workspace `uv run pytest` surfaced 5 pre-existing failures, all in `agents/graph-wiki-agent/tests/unit/`:

- `test_cli_help.py::test_cli_help_lists_bootstrap_subcommand`
- `test_cli_query.py::test_query_help_exits_zero`
- `test_cli_query.py::test_vault_flag_in_help`
- `test_cli_query.py::test_state_gate_flag_present`
- `test_trace_viewer.py::test_trace_command_has_expand_flag`

Root cause (pattern): all five assert that a literal token (e.g. `--workspace`, `--top-k`, `bootstrap`) appears in Typer `--help` output, but Typer in this repo's environment now emits ANSI-styled output (`\x1b[1m...`) that interleaves escapes with the literal — the substring assertion fails on the bracketed/wrapped form.

**Verified pre-existing**: ran `git stash -u` to remove all Phase 25 work, then re-ran the failing tests on HEAD~5 — same failures. None of these tests touch vault-io or detect_containers code; they are unrelated to the Phase 25 change and out of scope per execute-plan's SCOPE BOUNDARY rule. Recommend a separate quick-fix phase to strip ANSI codes in the help-text assertion helpers (or pass `rich_markup_mode=None` to Typer in tests).

The 585 other tests pass, including all 9 in `packages/vault-io/tests/test_detect_containers.py`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Bootstrap behavior fix complete. Pat can now run `graph-wiki-agent bootstrap` on this repo and `wiki/packages/` will be created automatically (PKGCLS-01 satisfied).
- **Follow-up backlog item to open** (Pat's action, deferred per D-12 — NOT part of Phase 25):
  > **`graph-wiki-agent bootstrap --interactive`: prompt user on fallback-ambiguous rows; thread non_interactive parameter through run_init.**
  Currently `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py:run_init` hardcodes `non_interactive=True`, so any genuinely ambiguous (empty/unrecognized) container row is silently skipped. Permissive Rule 3 narrows the surface where this matters but does not eliminate it. Add a `--interactive` Typer flag and thread it through `run_init` so users on a TTY can confirm classifications.
- Pre-existing CLI-help test failures (see Issues Encountered) are out of scope but should be tracked — recommend filing a quick-fix todo in `.planning/todos/pending/`.

## Self-Check: PASSED

Verified post-write:

- All 5 modified files exist on disk and contain the expected edits.
- All 5 task commits exist on `worktree-phase-25-discuss`:
  - `bbdeaa9` test(25-01) — Task 1 RED tests
  - `9681394` fix(25-01) — Task 2 GREEN classifier rewrite
  - `1db8b6d` docs(25-01) — Task 3 detection-workflow.md
  - `adb19fb` docs(25-01) — Task 4 ROADMAP revision
  - `c961fc5` chore(25-01) — Task 5 todo move
- Operational repro on this repo emits `{"source": "packages", "classification": "package", "children_count": 5, "reason": "5/6 children have manifests; 1 dir(s) and 0 loose .md skipped"}`.
- Plugin shim import `from vault_io.detect_containers import main` succeeds.
- Brand-gate `scripts/check-brand.sh` exits clean.
- `git diff --name-only` from this plan's commit range matches the plan's `files_modified` frontmatter exactly (one rename: pending/ → resolved/).

---
*Phase: 25-packages-dir-misclassification-fix*
*Completed: 2026-05-21*
