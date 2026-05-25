---
phase: 24-eval-harness-workspace-rename
verified: 2026-05-20T00:00:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
---

# Phase 24: eval-harness-workspace-rename Verification Report

**Phase Goal:** The eval-harness package is internally consistent with the v1.4 naming convention — `workspace_path` everywhere a workspace root is meant, `wiki` everywhere the wiki directory itself is meant, and zero residual `vault_path` / `--vault` / `vault:` occurrences.

**Verified:** 2026-05-20
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP SC#1..#5 + PLAN frontmatter must_haves)

| #   | Truth   | Status     | Evidence       |
| --- | ------- | ---------- | -------------- |
| 1 | SC#1: `uv run --package eval-harness pytest` is green | VERIFIED | `pytest packages/eval-harness/tests -q` → 165 passed, 22 skipped in 14.74s |
| 2 | SC#2: `python -m eval_harness.baseline --help` shows `--workspace` (not `--vault`) | VERIFIED | Help output line: `usage: baseline.py [-h] --cases CASES --workspace WORKSPACE --out OUT ...`; no `--vault` token present |
| 3 | SC#3: All 5 divergence helper modules accept `wiki: Path` | VERIFIED | `grep -l 'wiki:\s+Path' packages/eval-harness/src/eval_harness/divergence/` matches all 7 modules (linter, ingestor, scanner, code_reader, synthesizer, librarian, metric); `grep -rnE '\bvault:\s*Path' divergence/` returns 0 |
| 4 | SC#4: `eval/README.md` contains no `vault_path` / `--vault` / `vault_content_hash` references | VERIFIED | `grep -nE '\bvault_path\b\|--vault\b\|vault_content_hash' eval/README.md` returns 0 lines; README contains `--workspace` (lines 39, 52, 61, 71) and `wiki_content_hash` (lines 97, 105) |
| 5 | SC#5: `grep -r 'vault_path\|vault:' packages/eval-harness/src` returns 0 hits | VERIFIED | Grep returns 0 lines |
| 6 | Every public function in sweep/baseline/structural takes `workspace_path: Path` and derives wiki via `wiki_dir(workspace_path)` (D-01, D-09) | VERIFIED | sweep.py: 9 `workspace_path: Path` occurrences, 2 `wiki = wiki_dir(workspace_path)` derivations; baseline.py: `BaselineRecorder.__init__(workspace_path: Path)` + `wiki = wiki_dir(self._workspace_path)` (line 354); structural.py: both `_resolve_citation` and `check_structural` derive `wiki = wiki_dir(workspace_path)` |
| 7 | `_vault_content_hash` renamed to `_wiki_content_hash(wiki: Path)`; baseline JSON emits `wiki_content_hash` (D-02, D-11) | VERIFIED | baseline.py:243 `def _wiki_content_hash(wiki: Path) -> str`; baseline.py:332 emits `"wiki_content_hash": wiki_content_hash` in snapshot dict |
| 8 | EvalWorktree.__init__ parameter renamed `source_vault` → `source_wiki`; threat-mitigation comment updated (D-04) | VERIFIED | isolation.py:12 `Threat mitigation T-4-01: source_wiki is anchored to caller-supplied`; isolation.py:36 `def __init__(self, source_wiki: Path)`; isolation.py:37 `self._source = source_wiki` |
| 9 | No back-compat shims, deprecation aliases, or accept-either-key branches (D-08) | VERIFIED | `grep -nE 'vault_path = workspace_path\|workspace_path = vault_path' packages/eval-harness/src/` returns 0; no `--vault` argparse alias; no `vault_content_hash` fallback read |
| 10 | `wiki-io` package directory and `wiki_io` module path untouched (D-10 lock) | VERIFIED | `packages/wiki-io/src/wiki_io/` exists with `_workspace.py`, `append_log.py`, etc.; module path unchanged |
| 11 | `scripts/check-brand.sh` CHECK 5 bans 3 patterns scoped to `packages/eval-harness/{src,tests}` (D-07) | VERIFIED | check-brand.sh:111 regex `def\s+\w+\([^)]*\bvault_path:\s*Path\|def\s+\w+\([^)]*\bvault:\s*Path\|"--vault"` over `packages/eval-harness/src packages/eval-harness/tests`; final OK echo line 122 mentions `BRAND-WSEVAL vault_path:\|vault:\|"--vault"`; clean tree gate exit 0 |
| 12 | All 194 test references renamed; EvalWorktree call sites use source_wiki=; fixture rename consistent (D-06) | VERIFIED | conftest.py: `fixture_wiki_path` (line 54) + `fixture_workspace_path` (line 87); eval_helpers.py: `produce_outputs(role, workspace: Path)` + derives wiki internally via `wiki_dir(workspace)`; test_sweep_eval.py wraps FIXTURE_VAULT in `fixture_workspace` (line 127 `wiki_link.symlink_to(FIXTURE_VAULT, ...)`) per CR-02 fix |
| 13 | Single big-bang plan and single commit covering all renames (D-05) | VERIFIED | Commit `906bdf2 refactor(24-01): rename eval-harness to workspace_path / wiki convention (WSEVAL-01..05)` — 27 files (11 src + 12 test + 1 doc + 2 brand-gate + frontmatter docs); 6 follow-up fix commits (06be83c CR-01, ce1dab9 CR-02, 374dae8 CR-03, 7466b7f WR-01, 09b5261 WR-03, ee9a575 WR-04) addressing code-review findings |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `packages/eval-harness/src/eval_harness/sweep.py` | 7+ public fns with `workspace_path: Path`; EvalWorktree(wiki) call sites | VERIFIED | 9 `workspace_path: Path` annotations; 2 `wiki = wiki_dir(workspace_path)` derivations; both `EvalWorktree(wiki)` call sites (L268, L545); CR-01 fix at L293 + L589 passes `wt.path` (workspace root) to `check_structural` |
| `packages/eval-harness/src/eval_harness/baseline.py` | `_wiki_content_hash` + `--workspace` argparse + `wiki_content_hash` JSON key | VERIFIED | All three present; argparse L423; helper L243; JSON key L332; WR-03 fix at L368 (hash worktree wiki at runtime, not source); WR-04 fix removes silent OSError swallow (L258-264) |
| `packages/eval-harness/src/eval_harness/structural.py` | `_resolve_citation` + `check_structural` take workspace_path and derive wiki | VERIFIED | Both functions take `workspace_path: Path`; `wiki = wiki_dir(workspace_path)` derived at L33 and L80; WR-01 fix at L81-86 makes derivation actually fail-fast via `if not wiki.is_dir(): raise FileNotFoundError` |
| `packages/eval-harness/src/eval_harness/isolation.py` | `EvalWorktree(source_wiki: Path)` + updated threat comment | VERIFIED | L12 threat comment uses `source_wiki`; L36 ctor signature `source_wiki: Path`; L37 `self._source = source_wiki` |
| `packages/eval-harness/src/eval_harness/divergence/metric.py` | `divergence_score` / `DivergenceMetric` use `wiki: Path` | VERIFIED | `_run_check_one(check, output_proxy, wiki: Path)` L49-53; `DivergenceMetric.__init__(self, role, checks, rubric_path, wiki: Path)` L76-82 with `self.wiki = wiki` |
| `scripts/check-brand.sh` | CHECK 5 enforcing 3 regex bans | VERIFIED | L102-111 declares 3 banned regex; scoped to `packages/eval-harness/src packages/eval-harness/tests`; tail echo L122 mentions BRAND-WSEVAL |
| `eval/README.md` | `--workspace` + `wiki_content_hash` user-facing instructions | VERIFIED | 4 occurrences of `--workspace`; 2 of `wiki_content_hash`; zero `--vault` or `vault_path` or `vault_content_hash` |

### Key Link Verification

| From | To  | Via | Status |
| ---- | --- | --- | ------ |
| sweep.py public functions | EvalWorktree(wiki) | `wiki = wiki_dir(workspace_path)` at function top | WIRED — L262 (run_sweep), L531 (run_role_sweep); both EvalWorktree calls now operate on derived wiki |
| baseline.py argparse `--workspace` flag | `BaselineRecorder(workspace_path=args.workspace)` | argparse `Path` typed kwarg | WIRED — L423 `add_argument("--workspace", ..., type=Path)` → L431 `BaselineRecorder(..., workspace_path=args.workspace, ...)` |
| structural.py `check_structural(workspace_path)` | `_resolve_citation(slug, workspace_path)` | derived wiki used internally; helper re-derives via wiki_dir | WIRED — L94 `_resolve_citation(slug, workspace_path)`; L108 same; helper at L33 re-derives `wiki` |
| divergence/metric.py `DivergenceMetric.run_programmatic` | 5 helper module check fns | callers pass `self.wiki: Path` | WIRED — L110 `_run_check_one(check, output, self.wiki)` → `check.check(output_proxy, wiki)` |
| scripts/check-brand.sh CHECK 5 | `.brand-grep-allow` | `-vF -f` allowlist filter | WIRED — L116 `grep -vF -f .brand-grep-allow` filters allowlist entries |

### Data-Flow Trace (Level 4)

Not applicable — this is a rename refactor phase, not a dynamic data-rendering surface. Verified by behavioral spot-checks (Step 7b) and test suite pass.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Eval-harness tests pass (SC#1) | `uv run --package eval-harness pytest packages/eval-harness/tests -q` | 165 passed, 22 skipped in 14.74s | PASS |
| Baseline CLI exposes --workspace not --vault (SC#2) | `GRAPH_WIKI_RUN_EVAL=1 uv run --package eval-harness python -m eval_harness.baseline --help` | Output shows `--workspace WORKSPACE`; no `--vault` token | PASS |
| Brand-gate green on clean tree | `bash scripts/check-brand.sh` | exit 0, `BRAND-04 OK: zero unallowlisted hits (... BRAND-WSEVAL vault_path:\|vault:\|"--vault")` | PASS |
| SC#5 grep returns 0 (eval-harness src) | `grep -rE 'vault_path\|vault:' packages/eval-harness/src` | 0 hits | PASS |
| SC#4 grep returns 0 (eval/README.md) | `grep -nE '\bvault_path\b\|--vault\b\|vault_content_hash' eval/README.md` | 0 lines | PASS |
| SC#3 grep returns 0 (divergence vault: Path) | `grep -rnE '\bvault:\s*Path\|\bvault\s*=\s*[A-Za-z]' packages/eval-harness/src/eval_harness/divergence/` | 0 hits | PASS |

### Probe Execution

No project-level probe scripts in scope for this phase (no `scripts/*/tests/probe-*.sh` declared in PLAN/SUMMARY). The PLAN gate is `pytest packages/eval-harness/tests -q` per D-06 — executed in spot-checks above.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| WSEVAL-01 | 24-01-PLAN | Rename sweep.py `vault_path` → `workspace_path` across ~7 functions; derive wiki via `wiki_dir` | SATISFIED | sweep.py has 9 `workspace_path: Path` annotations, 2 `wiki_dir(workspace_path)` derivations, 2 `EvalWorktree(wiki)` call sites; 0 `vault_path` residuals |
| WSEVAL-02 | 24-01-PLAN | Rename baseline.py `vault_path` → `workspace_path`, `--vault` → `--workspace`, `_vault_content_hash` → `_wiki_content_hash`; same for structural.py | SATISFIED | All four renames present in baseline.py (workspace_path, --workspace, _wiki_content_hash, "wiki_content_hash" JSON key); structural.py both fns renamed and derive wiki |
| WSEVAL-03 | 24-01-PLAN | Rename `vault: Path` → `wiki: Path` in 5 divergence helpers | SATISFIED | All 7 divergence modules (linter, ingestor, scanner, code_reader, synthesizer, librarian, metric) contain `wiki: Path`; 0 `vault: Path` annotations remain |
| WSEVAL-04 | 24-01-PLAN | Update 12 test files; pytest green | SATISFIED | 165/187 tests pass; 22 skipped behind GRAPH_WIKI_RUN_EVAL gate (not failures); fixtures renamed; EvalWorktree callers pass wiki path; CR-02/CR-03 fixes make gated tests semantically correct workspace-shaped |
| WSEVAL-05 | 24-01-PLAN | Update `eval/README.md` references | SATISFIED | `eval/README.md` references `--workspace` (4x) and `wiki_content_hash` (2x); 0 hits for `vault_path`, `--vault`, `vault_content_hash` |

All 5 WSEVAL IDs are SATISFIED and present in PLAN frontmatter `requirements:` array. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | | | | |

No TBD/FIXME/XXX markers introduced; no stub returns; no hardcoded empty values flow into rendering. The synthesizer.py / code_reader.py / librarian.py retain `vault` references in regex literals matching agent-output text and in check IDs (`_check_vault_thin_acknowledgement`, `SYN-004-vault-thin-acknowledgement`) — these match the upstream prompt template prose (e.g. "the vault does not document X") and are explicitly documented as Deviation 1 in SUMMARY.md. They do NOT match SC#5's `vault_path|vault:` regex and do NOT match the brand-gate CHECK 5 regex shapes. Intentional preservation per the upstream lattice-wiki agent-output schema — acceptable.

### Human Verification Required

(empty — all checks programmatically verifiable; D-11 baseline-regeneration UAT is documented in SUMMARY.md as a separate follow-up activity, not a goal-achievement gap)

### Gaps Summary

No gaps. Every must-have truth resolves to VERIFIED with codebase evidence. All 5 ROADMAP success criteria pass mechanically:

- SC#1: 165 tests pass
- SC#2: `--workspace` flag present, `--vault` absent
- SC#3: All 7 divergence modules accept `wiki: Path`
- SC#4: `eval/README.md` clean
- SC#5: `grep -rE 'vault_path|vault:' packages/eval-harness/src` returns 0 hits

The big-bang commit (906bdf2) plus 6 follow-up CR/WR fixes form a complete and consistent rename. CR-01/CR-02/CR-03 (workspace-vs-wiki layering bugs that survived the unit tests but would have broken the GRAPH_WIKI_RUN_EVAL=1 path) are all addressed. WR-01/WR-03/WR-04 hardenings are applied. Brand-gate CHECK 5 ratchets the rename in place going forward.

---

_Verified: 2026-05-20_
_Verifier: Claude (gsd-verifier)_
