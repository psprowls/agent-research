---
phase: 25-packages-dir-misclassification-fix
verified: 2026-05-21T00:00:00Z
status: passed
score: 5/5 must-haves verified (revised per D-12/D-13)
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
  gaps_closed: []
  gaps_remaining: []
  regressions: []
---

# Phase 25: packages-dir-misclassification-fix Verification Report

**Phase Goal (post D-12/D-13):** `graph-wiki-agent bootstrap` on this repo (non-interactive) classifies `packages/` as `package`, the plugin shim auto-inherits, unit tests pin the contract, and the pending bug-report todo is resolved.

**Verified:** 2026-05-21
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (revised criteria, EC#X)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| EC#1 | `python -m vault_io.detect_containers --json` on this repo classifies `packages` as `package`, `children_count=5`, with honest skipped reason | VERIFIED | Direct `detect()` call against repo root returned `{"source": "packages", "classification": "package", "children_count": 5, "reason": "5/6 children have manifests; 1 dir(s) and 0 loose .md skipped"}` |
| EC#2 | `_classify_dir` with fixture dir containing 5/6 manifested children returns `package` (unit test) | VERIFIED | `test_mixed_manifest_dirs_classify_as_package` present at `packages/vault-io/tests/test_detect_containers.py:115`, PASSES |
| EC#3 | `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` is unchanged and still `from vault_io.detect_containers import main` | VERIFIED | File is 9 lines, contains `from vault_io.detect_containers import main`; `git log 6b67ffd..HEAD -- <shim>` returns empty (no Phase 25 modification) |
| EC#5 | `.planning/todos/pending/2026-05-20-fix-packages-dir-misclassification.md` moved to `.planning/todos/resolved/` | VERIFIED | `test -f resolved/...` passes; `test -f pending/...` fails (file removed); commit `c961fc5` is the `git mv` (rename detected); footer `Resolved by Phase 25` present in the moved file |
| Roadmap | ROADMAP.md Phase 25 success criteria reflect D-12/D-13 (4 SCs, `--interactive` SC#4 deleted, SC#3 reworded to passthrough shim, SC#5 reduced to todo-move) | VERIFIED | Phase 25 block at `ROADMAP.md:126-134` has exactly 4 numbered SCs; SC#3 reads `imports main from the updated vault_io.detect_containers (passthrough shim — no separate port)`; line 81 one-liner says `permissive heuristic`; old `>=80% majority` and `--interactive flag is visible` clauses absent |

**Score:** 5/5 truths verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/vault-io/src/vault_io/detect_containers.py` | `_classify_dir` Rule 3 collapsed to permissive `≥1 manifest_kids → package`; fallback `ambiguous` retained | VERIFIED | Lines 112-135: single permissive branch with `manifest_kids = [c for c in children if _has_manifest(c)]`; `children_count = len(manifest_kids)` per D-02; reason string contains `len(manifest_kids)/len(children)` + `skipped` per D-02. Fallback branches at 137-151 retain exactly 2 `"classification": "ambiguous"` occurrences (D-04). Old all-or-nothing gate `len(manifest_kids) == len(children) and not md_files` is gone (grep returns 0). |
| `packages/vault-io/tests/test_detect_containers.py` | 3 mandatory + 2 recommended new tests appended | VERIFIED | All 5 new test function defs present (grep returns 5); original 4 tests retained verbatim (lines 28-105). |
| `plugins/graph-wiki/skills/graph-wiki/references/detection-workflow.md` | Rule 3 uses `≥1 manifested child`; ambiguous bullets pruned | VERIFIED | Line 14 contains `≥1 manifested child (an immediate subdirectory containing a package manifest...)`; "Ambiguous containers" subsection (line 31-33) lists ONLY the empty/unrecognized bullet; the two contradicting bullets are gone. |
| `.planning/ROADMAP.md` | Phase 25 block revised per D-12/D-13 | VERIFIED | See Roadmap truth row above. |
| `.planning/todos/resolved/2026-05-20-fix-packages-dir-misclassification.md` | Moved from pending/, frontmatter preserved, Resolution footer | VERIFIED | Frontmatter `resolves_phase: 25` preserved; `Resolved by Phase 25` footer present; git history shows rename (commit `c961fc5`). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `vault_io.detect_containers._classify_dir` | `vault_io.init_vault._resolve_pinned_containers` | JSON classification field | VERIFIED | `_classify_dir` continues to return a dict with `classification` field consumed downstream; existing `if cls == "ambiguous"` branch in `init_vault.py` is intentionally unchanged (D-05). |
| `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` | `vault_io.detect_containers.main` | `from vault_io.detect_containers import main` | VERIFIED | Shim imports `main` and invokes it under `__main__`. Pat's shim auto-inherits the new classifier behavior (D-06). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_classify_dir(Path)` return dict | `classification`, `children_count`, `reason` | Filesystem scan of `_immediate_subdirs(d)` + `_has_manifest(c)` checks against `MANIFEST_FILES` set | Yes — operational run on this repo's `packages/` yielded real data: classification=package, children_count=5, reason names skipped `prompt_sources/` dir | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 9 tests in test_detect_containers.py all pass | `uv run --package vault-io pytest packages/vault-io/tests/test_detect_containers.py -v` | `9 passed in 0.06s` | PASS |
| Operational repro on this repo's packages/ dir | `detect(Path("/Users/pat/Personal/agent-research/.claude/worktrees/phase-25-discuss"))` then filter source==packages | classification=package, children_count=5, reason="5/6 children have manifests; 1 dir(s) and 0 loose .md skipped" | PASS |
| Plugin shim imports cleanly | `uv run python -c "from vault_io.detect_containers import main"` | exit 0 | PASS |
| Pre-existing test failures truly pre-existing | Checked out detect_containers.py + test file from pre-Phase-25 commit (6b67ffd) and re-ran `test_cli_help.py` | `test_cli_help_lists_bootstrap_subcommand` FAILS identically — ANSI escape codes wrap the `bootstrap` literal in Typer/Rich help output. Predates Phase 25 (test file last touched 29eca18 in Phase 21). | PASS (pre-existing confirmed) |

### Probe Execution

No project probes (`scripts/*/tests/probe-*.sh`) declared for Phase 25. PLAN does not reference probe-based verification. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description (REQUIREMENTS.md text vs. revised scope) | Status | Evidence |
|-------------|-------------|-------------------------------------------------------|--------|----------|
| PKGCLS-01 | 25-01-PLAN | `_classify_dir` loosens to permissive heuristic — original REQUIREMENTS.md text says "≥80%", but D-01 narrowed to "≥1 manifested child" with full Pat ratification; spirit preserved | SATISFIED | Code change at `detect_containers.py:118-135`; unit tests `test_mixed_manifest_dirs_*` + `test_single_manifested_child_*` pin both 5/6 and 1/6 cases |
| PKGCLS-02 | 25-01-PLAN | Plugin-side classifier updated to match | SATISFIED (via D-06) | Plugin shim is a 9-line passthrough that auto-inherits via `from vault_io.detect_containers import main`. No plugin-side code change required. |
| PKGCLS-03 | 25-01-PLAN | `--interactive` flag on bootstrap + doc updates | PARTIALLY SATISFIED (doc-side only; flag deferred per D-12) | Doc-side: `detection-workflow.md` updated (Task 3). Flag-side: explicitly deferred to backlog. **Backlog item must be opened by Pat** per SUMMARY §"Next Phase Readiness". |
| PKGCLS-04 | 25-01-PLAN | Unit test asserts 5/6 → package + operational verification | SATISFIED | `test_mixed_manifest_dirs_classify_as_package` passes; operational `detect()` confirmed on this repo. |
| PKGCLS-05 | 25-01-PLAN | Pending todo moved to resolved/ | SATISFIED | Commit `c961fc5` performed `git mv`; resolution footer appended. |

No orphaned requirements detected — all PKGCLS-01..05 are claimed by 25-01-PLAN.

### Anti-Patterns Found

None blocking. No `TBD`/`FIXME`/`XXX` markers introduced in Phase 25 commits. No empty implementations, stubs, or hollow returns. `manifest_kids` flows from filesystem reads to the return dict — no static/empty data.

### Decision Compliance (D-01..D-13)

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01: Rule 3 permissive (`≥1 manifested child → package`) | HONORED | `detect_containers.py:118-120` — `if manifest_kids: ... classification: "package"` |
| D-02: `children_count = len(manifest_kids)`; honest reason | HONORED | `detect_containers.py:133` sets `children_count = len(manifest_kids)`; reason string at lines 124-129 contains `f"{len(manifest_kids)}/{len(children)}"` + `"skipped"` |
| D-03: Old all-or-nothing gate removed | HONORED | `grep -c "len(manifest_kids) == len(children) and not md_files"` returns 0 |
| D-04: `ambiguous` retained only for fallback | HONORED | Exactly 2 `"classification": "ambiguous"` strings remain (lines 137-151), both in genuine no-rule-matched fallback paths |
| D-05: `init_vault.py::_resolve_pinned_containers` NOT edited | HONORED | `git log 6b67ffd..HEAD -- packages/vault-io/src/vault_io/init_vault.py` returns empty |
| D-06: Plugin shim auto-inherits, NOT edited | HONORED | Shim is 9 lines, `from vault_io.detect_containers import main`; no Phase 25 commits touch it |
| D-07/D-08: `detection-workflow.md` updated in lockstep, no new heading | HONORED | Rule 3 line uses `≥1 manifested child`; existing numbered rule structure reused |
| D-09: 3 new mandatory unit tests | HONORED + 2 recommended also added | All 5 test functions present + passing |
| D-10: Existing 4 tests still pass | HONORED | All 9 tests pass (original 4 + new 5) |
| D-11: Pending todo moved via `git mv` with footer | HONORED | Rename commit `c961fc5`; resolution footer present |
| D-12: `--interactive` flag deferred; SC#4 removed; `init.py` NOT edited | HONORED | ROADMAP.md SC#4 absent; `git log 6b67ffd..HEAD -- agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` returns empty |
| D-13: ROADMAP SC#5 reworded to drop `--interactive` flag-visibility clause | HONORED | Current SC#4 (renumbered from SC#5) reads `.planning/todos/pending/... is moved to .planning/todos/resolved/` — no `--help` clause |

### Out-of-Scope Confirmations

| Item | Expected | Status |
|------|----------|--------|
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` modified by Phase 25 | NO (deferred per D-12) | CONFIRMED — no Phase 25 commits touch it |
| `plugins/graph-wiki/skills/graph-wiki/scripts/detect_containers.py` modified by Phase 25 | NO (auto-inherits per D-06) | CONFIRMED — no Phase 25 commits touch it |
| `packages/vault-io/tests/helpers.py` created by Phase 25 | NO (RESEARCH correction — file does not exist; tests use inline `tmp_path`) | CONFIRMED — `git log --diff-filter=A -- packages/vault-io/tests/helpers.py` returns empty (file never existed) |
| `plugins/graph-wiki/CLAUDE.md` modified by Phase 25 | NO (RESEARCH said interactive framing remains valid for fallback-ambiguous rows) | CONFIRMED — no Phase 25 commits touch it |

### Risks / Gaps / Notes

**No blocking gaps.** All revised acceptance criteria are met.

**Notes for human awareness (non-blocking):**

1. **Pre-existing CLI-help test failures (5 tests).** Confirmed pre-existing by reverting Phase 25 code/tests to pre-Phase-25 baseline (commit `6b67ffd`) and re-running `agents/graph-wiki-agent/tests/unit/test_cli_help.py::test_cli_help_lists_bootstrap_subcommand` — identical failure with same ANSI-escape root cause. These tests were created in commit `29eca18` (Phase 21) and break because Typer/Rich emits styled output that interleaves ANSI escapes with the literal `bootstrap` token. **Recommended:** file a separate quick-fix todo to either strip ANSI codes in the test helper or invoke Typer with `rich_markup_mode=None` in tests. **Not a Phase 25 regression.**

2. **`--interactive` flag backlog item must be opened by Pat** (deferred per D-12). The SUMMARY §"Next Phase Readiness" already drafts the verbatim wording; Phase 25 declared this a follow-up.

3. **ROADMAP.md still contains the literal substring `--interactive` twice** in the Phase 25 region (line 2 goal + SC#1), but only in the contextual "without `--interactive`" framing — i.e. specifying that bootstrap must work non-interactively on this repo. This is the original SC#1 text retained intentionally; D-12 only deleted the SC that required exposing the flag. Reads correctly.

4. **`graph-wiki/` directory contains untracked files** (`.graph-wiki.yaml`, `CLAUDE.md`) in the worktree at verification time, but these are unrelated artifacts from earlier sessions (visible in `git stash` history pre-Phase 25). Not produced by Phase 25 work.

### Human Verification Required

None. The phase goal is mechanically verifiable end-to-end:
- Unit tests cover the new contract.
- Operational `detect()` against this repo's `packages/` dir confirms PKGCLS-04 without needing a TTY.
- All file existence / non-existence / wiring checks are scripted.

The full `graph-wiki-agent bootstrap` end-to-end command path (CLI → run_init → init_wiki → _resolve_pinned_containers → detect_containers → _classify_dir) is not exercised in this verification because (a) it requires a live AWS Bedrock session and (b) the leaf function `_classify_dir` — the only Phase 25 code change — is verified directly. The bootstrap-level UAT is reserved for the deferred `--interactive` backlog phase.

### Gaps Summary

No gaps. All revised success criteria are met. The five pre-existing CLI-help test failures are documented as pre-existing (verified by checking out Phase 25 files to baseline and re-running the same tests with identical failure mode), not caused by Phase 25, and should be tracked as a separate quick-fix todo.

---

*Verified: 2026-05-21*
*Verifier: Claude (gsd-verifier, Opus 4.7)*
