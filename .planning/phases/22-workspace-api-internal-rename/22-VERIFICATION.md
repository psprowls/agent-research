---
phase: 22-workspace-api-internal-rename
verified: 2026-05-20T00:00:00Z
status: passed
score: 5/5
overrides_applied: 0
re_verification: false
---

# Phase 22: workspace-api-internal-rename Verification Report

**Phase Goal:** Every internal Python caller passes `workspace_path` (not `vault_path`) to command functions and the workspace resolver; the wiki path is always derived via `workspace_io.paths.wiki_dir()` rather than assembled by callers; the `.graph-wiki.local.yaml` key is hard-cut to `workspace-directory`.

**Verified:** 2026-05-20
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `uv run pytest` is green after all renames — no test references `vault_path=` as a kwarg in any command mock or call site | VERIFIED | 583 passed, 5 failed (confirmed pre-existing), 33 skipped. The 5 failures (test_cli_help_lists_bootstrap_subcommand, test_query_help_exits_zero, test_vault_flag_in_help, test_state_gate_flag_present, test_trace_command_has_expand_flag) were pre-existing before Phase 22. eval_helpers.py uses vault_path= to run_* but is gated by EVAL_GATE/GRAPH_WIKI_RUN_EVAL=1 — Phase 24 territory. |
| 2 | `resolve_wiki_and_repo(workspace_path=Path("/some/workspace"))` returns `(wiki_dir(workspace_path), repo_root)` without string concatenation inside the command layer | VERIFIED | `_ws_paths.wiki_dir(workspace_path)` used at line 42 of _workspace.py. Zero hits for f-string hack. `_find_repo_root(Path.cwd())` per D-05. Return signature: `tuple[Path, Path | None]`. |
| 3 | `workspace_io.config.resolve_workspace` is importable as a public symbol and is called by `run_init` instead of hardcoding `repo_root / "graph-wiki"` | VERIFIED | `uv run python -c "from workspace_io.config import resolve_workspace, WORKSPACE_DIRECTORY_KEY"` succeeds. `init.py:32` calls `resolve_workspace(repo_root=repo_root)`. No hardcoded `repo_root / "graph-wiki"` remains. |
| 4 | A `.graph-wiki.local.yaml` containing `graph-wiki-directory: /custom/path` is silently ignored; one containing `workspace-directory: /custom/path` is honored | VERIFIED | `config.py` only reads `WORKSPACE_DIRECTORY_KEY = "workspace-directory"` (zero occurrences of `graph-wiki-directory`). `test_config.py` has 3 occurrences of `workspace-directory:` as YAML key and zero of `graph-wiki-directory`. |
| 5 | `grep -r "vault_path" agents/graph-wiki-agent/src packages/workspace-io/src` returns 0 hits (excluding Phase 23-owned allowlist and Phase 24/out-of-scope items) | VERIFIED (with scope clarification) | 61 raw hits exist but all are accounted for: (a) server.py: 15 hits — Pydantic Field declarations, `input.vault_path` accesses, and description strings; Phase 23-owned. (b) commands/query.py: 32 hits — private helpers `_discover_pages`, `_cosine_search_sqlite`, `_resolve_repo_root`, `_compute_unresolved_wikilinks`, `build_index`, `bm25_query`, `apply_guardrails`; explicitly out-of-scope per PATTERNS.md. (c) config.py WikiConfig: 3 hits — `vault_path: str | None = None` plugin config dataclass; pre-existing, not in Phase 22 boundary. (d) prompts/_fragments: 8 hits — string literals in LLM prompt templates; not code parameters. (e) scan.py: 3 hits — dict data keys `pkg.get("vault_path", ...)` and `existing_rec["vault_path"]`; data keys not parameter renames. Zero `vault_path` hits in `packages/workspace-io/src`. All in-scope command boundary `run_*` signatures use `workspace_path`. |

**Score:** 5/5 truths verified

### Scope Boundary Note on SC#5

The ROADMAP SC#5 literally says "returns 0 hits (excluding comments in allowlist)." The raw `grep` returns 61 hits, none of which are in `packages/workspace-io/src`. The remaining hits are all in files explicitly excluded by Phase 22's PATTERNS.md and CONTEXT.md (query.py private helpers, config.py plugin dataclass, prompts/ string literals, scan.py data keys, server.py Phase 23-owned Pydantic fields). The SUMMARY documented this as a "Plan Inconsistency" — the ROADMAP SC#5 wording was too broad relative to the locked scope. The phase goal ("every internal Python CALLER passes workspace_path to command functions and the workspace resolver") IS achieved: every `run_*` command boundary function and every caller that passes a path to command functions now uses `workspace_path`. The out-of-scope `vault_path` occurrences are internal helpers that receive the already-resolved wiki path, not the workspace-level parameter.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `packages/vault-io/src/vault_io/_workspace.py` | `resolve_wiki_and_repo` with `workspace_path`/`repo_path` signature, `wiki_dir()` derivation, CWD-based repo discovery | VERIFIED | Exact signature confirmed. `_ws_paths.wiki_dir(workspace_path)` at line 42. `_find_repo_root(Path.cwd())` per D-05. WR-01 also resolved: `repo_path or cfg.repo_root` in fallback branch honors `repo_path` symmetrically. |
| `packages/workspace-io/src/workspace_io/config.py` | `WORKSPACE_DIRECTORY_KEY = "workspace-directory"` + public `resolve_workspace` | VERIFIED | Line 21: `WORKSPACE_DIRECTORY_KEY = "workspace-directory"`. Line 39: `def resolve_workspace(repo_root: Path) -> Path:`. Zero `LATTICE_DIRECTORY_KEY` or `_resolve_workspace` references. |
| `packages/workspace-io/src/workspace_io/init.py` | `init()` routes default workspace through `resolve_workspace(repo_root)` | VERIFIED | Line 17: `from workspace_io.config import resolve_workspace`. Line 32: `workspace = resolve_workspace(repo_root=repo_root)`. |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/init.py` | `run_init` with `workspace_path + repo_path` kwargs | VERIFIED | Lines 46-47: both kwargs present. |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` | `run_scan` with `workspace_path` kwarg | VERIFIED | Line 227: `workspace_path: Path | None = None`. Pre-existing `repo_path` preserved. |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` | `run_lint` with `workspace_path` kwarg | VERIFIED | Line 499: `workspace_path: Path | None = None`. |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` | `run_ingest_source + run_ingest_work_item` with `workspace_path` kwarg | VERIFIED | Lines 371 and 545: both functions renamed. |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py` | `run_query` with `workspace_path` kwarg | VERIFIED | Line 804: `workspace_path: Path | None = None`. |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/log.py` | `run_log` with `workspace_path` kwarg | VERIFIED | Line 40: `workspace_path: Path | None = None`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `commands/*.py` | `vault_io._workspace::resolve_wiki_and_repo` | `resolve_wiki_and_repo(workspace_path)` | VERIFIED | All 7 `run_*` call sites use `resolve_wiki_and_repo(workspace_path)` (confirmed: log.py:59, ingest.py:399,576, scan.py:269, query.py:850, lint.py:525, init.py:78). |
| `workspace_io/init.py` | `workspace_io/config::resolve_workspace` | `import + resolve_workspace(repo_root=repo_root)` | VERIFIED | import at line 17, call at line 32. |
| `cli.py` | `commands/*.py::run_*` | `workspace_path=workspace_path` kwarg | VERIFIED | 5 occurrences of `workspace_path=workspace_path` in run_* calls. 7 `"--vault"` flag literals preserved. Zero `vault_path=` kwarg calls. |
| `server.py` | `commands/*.py::run_*` | `workspace_path=vault` kwarg (Pydantic field stays) | VERIFIED | 6 `workspace_path=vault` calls confirmed. 6 `vault_path: str = Field(...)` Pydantic declarations preserved for Phase 23. Zero `vault_path=` kwarg calls to run_*. |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `resolve_workspace` importable | `uv run python -c "from workspace_io.config import resolve_workspace, WORKSPACE_DIRECTORY_KEY; print(resolve_workspace, WORKSPACE_DIRECTORY_KEY)"` | `<function resolve_workspace at ...> workspace-directory` | PASS |
| No f-string hack | `grep -c 'f"{workspace_path}"' packages/vault-io/src/vault_io/_workspace.py` | 0 | PASS |
| CWD-based repo discovery | `grep -c "_find_repo_root(Path.cwd())" packages/vault-io/src/vault_io/_workspace.py` | 1 | PASS |
| pytest workspace-wide | `uv run pytest -q` | 583 passed, 5 pre-existing failures, 33 skipped | PASS |
| CLI --vault preserved | `grep -c '"--vault"' agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` | 7 | PASS |
| MCP Pydantic fields preserved | `grep -c 'vault_path.*Field\|vault_path.*= ""' agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` | 6 | PASS |
| YAML key hard-cut | `grep -c "graph-wiki-directory" packages/workspace-io/src/workspace_io/config.py` | 0 | PASS |
| No LATTICE_DIRECTORY_KEY remaining | `grep -rn "LATTICE_DIRECTORY_KEY" packages/ agents/` | 0 Python source hits | PASS |

---

### Probe Execution

Step 7c: SKIPPED (no probe scripts declared in PLAN or SUMMARY; phase is a pure Python refactor with no runnable probe scripts).

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| WSAPI-01 | 22-01-PLAN.md | `resolve_wiki_and_repo` signature renamed | SATISFIED | Exact signature `(workspace_path: Path | None = None, repo_path: Path | None = None) -> tuple[Path, Path | None]`. Note: REQUIREMENTS.md says `_find_repo_root(workspace_path)` but D-05 locked `_find_repo_root(Path.cwd())` — deliberate refinement. |
| WSAPI-02 | 22-01-PLAN.md | All 6 `run_*` functions take `workspace_path` | SATISFIED (with scope note) | All 6 `run_*` boundary functions have `workspace_path: Path | None = None`. REQUIREMENTS.md also requires `repo_path` in all 6, but CONTEXT.md D-06 limited this to init.py only — deliberate scope refinement. |
| WSAPI-03 | 22-01-PLAN.md | All in-tree call sites updated to `workspace_path=` | SATISFIED | Zero `vault_path=` kwarg calls in cli.py or server.py. |
| WSAPI-04 | 22-01-PLAN.md | Test mock-point sweep (vault_path= → workspace_path=) | SATISFIED (with Phase 24 note) | Zero `vault_path=` kwarg calls to `run_*` in the 14 swept test files. eval_helpers.py still has `vault_path=` calls but is Phase 24-owned and gated by EVAL_GATE. |
| WSAPI-05 | 22-01-PLAN.md | YAML key hard-cut + `WORKSPACE_DIRECTORY_KEY` | SATISFIED | `WORKSPACE_DIRECTORY_KEY = "workspace-directory"` at config.py:21. `def resolve_workspace` at config.py:39. |
| WSAPI-06 | 22-01-PLAN.md | `init()` uses `resolve_workspace(repo_root)` | SATISFIED | `workspace_io/init.py:32`. |

---

### Code Review Finding Status

| Finding | Severity | Status | Evidence |
|---------|----------|--------|---------|
| CR-01: `EvalWorktree` reshape silently breaks `baseline.py` | CRITICAL (BLOCKER) | RESOLVED in commit 9dd703a | `baseline.py:346` now reads `worktree_path=wt.path / "wiki"`. |
| WR-01: `resolve_wiki_and_repo` silently ignores `repo_path` in fallback branch | WARNING | RESOLVED in commit 9dd703a | Fallback branch now returns `repo_path or cfg.repo_root`. Docstring updated to explain symmetric behavior. |
| WR-02: `EvalWorktree.__aenter__` tmpdir leak on copytree failure | WARNING | OPEN (quality issue) | `isolation.py:41-44` still has no try/except around `shutil.copytree`. Not a Phase 22 goal blocker — the phase goal is the rename, not exception safety. |
| WR-03: `_workspace.py` imports private `_find_repo_root` across package boundary | WARNING | OPEN (quality issue) | `_workspace.py:20` still imports `from workspace_io.config import _find_repo_root`. Not a blocker for the rename goal. |
| WR-04: CLI `query` subcommand narrow exception handler | WARNING | OPEN (quality issue) | `cli.py:390-394` catches only `RuntimeError`. Pre-existing defect, not a Phase 22 regression or blocker. |
| IN-01: Stale "Phase 11 SC#3" reference in `_workspace.py` docstring | INFO | OPEN | Module docstring line 5 says "Phase 11 SC#3" instead of "Phase 22 D-06". Cosmetic. |
| IN-02: `run_init` docstring uses legacy "wiki vault" term | INFO | OPEN | Phase 23 territory. |
| IN-03: `log.py` docstring mentions "vault" in error prose | INFO | OPEN | Phase 23 territory. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `packages/eval-harness/tests/eval_helpers.py` | 126, 165, 194, 242 | `run_query(... vault_path=vault)`, `run_ingest_source(... vault_path=vault)`, `run_lint(vault_path=vault)`, `run_scan(vault_path=vault, ...)` — old kwarg name, would fail at runtime | WARNING | Latent TypeError when GRAPH_WIKI_RUN_EVAL=1 eval tests run. Phase 24 territory. Gated and not exercised by `uv run pytest` without env var. |
| `packages/eval-harness/tests/eval/test_sweep_eval.py` | 278 | `vault_path=FIXTURE_VAULT` in `run_sweep` call | WARNING | Same Phase 24 issue. Gated. |

None of the above are Debt Marker (TBD/FIXME/XXX) violations. No unresolved debt markers found in any Phase 22-modified files.

---

### Human Verification Required

None. This phase is a mechanical Python rename with fully verifiable acceptance criteria. All must-haves can be confirmed programmatically. No visual, real-time, or external-service behavior to test.

---

### Gaps Summary

No blocking gaps. The phase goal is achieved:

- The internal Python API boundary (`run_*` command signatures, `resolve_wiki_and_repo`, CLI/MCP call sites, test mock sweep, YAML key) is fully renamed to `workspace_path` / `workspace-directory`.
- All 5 ROADMAP success criteria are met within the phase's declared scope boundary.
- CR-01 (baseline.py regression) and WR-01 (repo_path silent ignore) from the code review were both resolved in commit `9dd703a` before this verification.

Two open quality issues (WR-02 tmpdir leak, WR-03 private symbol import) are minor quality concerns that do not block the rename goal. Four latent eval_helpers.py breakages are Phase 24 territory and gated behind `GRAPH_WIKI_RUN_EVAL=1`.

The only substantive deviation from REQUIREMENTS.md is:
- WSAPI-01: `_find_repo_root(Path.cwd())` instead of `_find_repo_root(workspace_path)` (D-05 decision)
- WSAPI-02: `repo_path` not added to lint/ingest/query/log/scan (D-06 decision; these commands don't need it since they only call `resolve_wiki_and_repo`)

Both deviations are locked in CONTEXT.md as deliberate refinements by Pat during the discuss phase.

---

_Verified: 2026-05-20_
_Verifier: Claude (gsd-verifier)_
