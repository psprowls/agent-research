---
phase: 06-prompt-content-port-divergence-eval
plan: 15
subsystem: eval-harness / scanner divergence
tags: [gap-closure, scanner, eval-fixture, baseline, UAT-G5, BLOCKING-LIVE]
requires: [06-11]
provides:
  - run_scan(..., repo_path=...) override (regression-safe extension)
  - cores/eval-harness scanner divergence baseline (live-Bedrock recorded)
affects:
  - agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
  - cores/eval-harness/tests/eval_helpers.py
  - cores/eval-harness/baselines/divergence-scanner.json
tech-stack:
  added: []
  patterns: [pytest, deepeval/Bedrock judge panel, divergence regression]
key-files:
  created: []
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py
    - agents/code-wiki-agent/tests/unit/test_commands_scan.py
    - cores/eval-harness/tests/eval_helpers.py
    - cores/eval-harness/baselines/divergence-scanner.json
    - .gitignore
decisions:
  - "When repo_path is supplied as an override, also bypass the vault's pinned_containers layout block — the vault layout describes the original monorepo, not the override repo, and almost certainly will not match its structure"
  - "SCN-003-no-file-map-section failure for run_scan stubs is accepted into the baseline: the pipeline deterministically appends a '## File map' suffix after the LLM body (RESEARCH Risk 5), so the rule will always trip for production scanner output by construction"
metrics:
  duration_sec: 479
  completed_date: 2026-05-16
  tasks_completed: 3
  files_modified: 5
  commits: 5
requirements: [EVAL-12, EVAL-13]
---

# Phase 06 Plan 15: Close UAT G5 — Scanner Divergence Fixture Summary

Threaded an optional `repo_path` override through `run_scan` so the scanner divergence test can point at `cores/eval-harness` as a known-good corpus regardless of pytest cwd; live-Bedrock re-recorded the baseline so `runs` is now non-zero across all five scanner rules.

## What was built

### `run_scan` signature extension

```diff
 async def run_scan(
     vault_path: Path | None = None,
     no_file_map: bool = False,
     max_depth: int = 3,
+    repo_path: Path | None = None,
 ) -> ScanResult:
```

Behavior when `repo_path` is supplied:
1. `repo = repo_path.resolve()` — overrides both `resolve_wiki_and_repo`'s repo slot and the `Path.cwd()` fallback.
2. Vault layout block (CLAUDE.md / AGENTS.md) is **not** read — `pinned_containers=None` is passed to `discover_workspaces`. This was the auto-discovered fix during Task 3 (see Deviations).
3. All downstream `repo` consumers (`discover_workspaces`, `attach_changed_files`, `compute_state_gate`, `pkg_dir`, `build_stub_prompt(repo_root=)`) receive the overridden repo uniformly.

### Eval helper wiring

`cores/eval-harness/tests/eval_helpers.py::_produce_scanner_outputs`:
```diff
- result = asyncio.run(run_scan(vault_path=vault))
+ result = asyncio.run(run_scan(vault_path=vault, repo_path=eval_harness_dir))
```
Skip guard message tightened to name the post-fix expectation; helper docstring updated to call out the explicit `repo_path` pass-through.

### Unit test

`agents/code-wiki-agent/tests/unit/test_commands_scan.py::test_run_scan_repo_path_overrides_cwd` (mock-based, no Bedrock) asserts:
- `discover_workspaces` receives `fake_repo.resolve()` (not cwd, not the value from `resolve_wiki_and_repo`)
- `compute_state_gate` and `attach_changed_files` receive the same overridden repo
- `discover_workspaces` receives `pinned_containers=None` when override is supplied

## Live Bedrock baseline re-record (Task 3)

Command (run autonomously per orchestrator approval):
```
CODE_WIKI_RUN_EVAL=1 uv run --package eval-harness pytest \
  cores/eval-harness/tests/test_divergence.py -s \
  --accept-divergence-baseline -k scanner -x
```

**Model used:** `us.anthropic.claude-haiku-4-5-20251001-v1:0` (bundled `cores/model-adapter/src/model_adapter/models.toml` default for the `scanner` role — `set_models_path` was not called by the test, so models-qwen.toml at the project root was not in effect).

**Result:** 1 passed in 14.51s. `+1 ~0 -60` written to vault (1 added — the `eval-harness` workspace; 60 deleted — the round-trip-vault's lattice-* pages that have no analogue in `cores/eval-harness`).

**Baseline file:** `cores/eval-harness/baselines/divergence-scanner.json`
- `agent_commit`: `13da865` (the Rule 1 fix commit — see Deviations)
- `recorded_at`: `2026-05-16T23:13:05.607607+00:00`

**Per-rule SCN counts (from the baseline):**

| Rule                            | Runs | Failures | Notes |
|---------------------------------|------|----------|-------|
| SCN-001-frontmatter-present     | 1    | 0        |       |
| SCN-002-required-fields         | 1    | 0        |       |
| SCN-003-no-file-map-section     | 1    | 1        | Accepted — pipeline deterministically appends `## File map` after LLM body (RESEARCH Risk 5); rule will always trip by construction for `run_scan` stubs |
| SCN-004-overview-present        | 1    | 0        |       |
| SCN-JUDGE                       | 1    | 0        | Bedrock judge panel ran and unanimously approved the eval-harness stub |

**Sanity follow-up** (without `--accept-divergence-baseline`): 1 passed in 14.90s — the regression gate matches the just-written baseline.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `repo_path` override also needs to bypass vault `pinned_containers`**
- **Found during:** Task 3 first live-Bedrock run
- **Symptom:** First run completed in 0.45s with `scan complete: +0 ~0 -60` and `result.added=[], result.updated=[], result.errors=[]`. The SubagentPool was called with `items=0` — no Bedrock call happened despite the test sequence succeeding.
- **Root cause:** The round-trip-vault's `CLAUDE.md` carries a `lattice-wiki:layout` block declaring `containers: [{source: packages, vault_dir: packages, classification: package}, {source: plugins, ..., classification: package}, ...]`. When `run_scan` read this layout and passed it as `pinned_containers` to `discover_workspaces(cores/eval-harness, pinned_containers=[...])`, the discovery looked for `cores/eval-harness/packages/` and `cores/eval-harness/plugins/` — neither exists — and returned zero workspaces. So `diff["new"]` was empty, `fan_items` was empty, and the pool ran 0 items with no Bedrock call.
- **Fix:** In Step 2 of `run_scan`, only read the layout block when `repo_path is None`. When the caller is explicitly overriding the repo, they are saying "treat this as a known-good monorepo regardless of vault layout assumptions" — fall back to unpinned discovery (pyproject.toml-driven).
- **Files modified:** `agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py`, `agents/code-wiki-agent/tests/unit/test_commands_scan.py` (added a `pinned_containers is None` assertion to the new test)
- **Commit:** `13da865`

### Test side-effects reverted

The scanner divergence test mutates the real `round-trip-vault` fixture in two ways: (a) stale-tags 60 packages and appends 60 log entries, (b) writes a new `packages/eval-harness/eval-harness.md` stub plus a trace JSONL. Both were reverted before each commit using `git checkout -- cores/vault-io/tests/fixtures/round-trip-vault/` (scoped path, allowed by destructive-git prohibition) and `rm -rf` for the untracked outputs. Pre-existing fixture trace JSONL files (from earlier eval runs) were left alone.

This vault-mutation behavior is a real concern but is out of scope for plan 06-15 — a future plan should either (a) have the divergence helper copy the vault to a tmp_path before invoking the scanner, or (b) record stale-tag behavior in the baseline so it's regression-checked rather than fixture-mutating. Logged via deferred-items below.

### Deferred Items

- **Scanner divergence test mutates the round-trip-vault fixture on every run.** Out of scope here (the plan was scoped to fix the skip). Suggested follow-on: in `_produce_scanner_outputs`, `shutil.copytree` the vault to a `tmp_path` before passing to `run_scan`, then read stubs back from the tmp copy. This would also eliminate the need to manually revert the fixture before each commit.

## Verification results

| Check | Command | Result |
|-------|---------|--------|
| Unit test for `repo_path` override | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/test_commands_scan.py -k repo_path_overrides_cwd -x -q` | PASS |
| Full scan test suite | `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/test_commands_scan.py -x -q` | 7/7 PASS |
| Helper kwarg present | `grep -c 'repo_path=eval_harness_dir' cores/eval-harness/tests/eval_helpers.py` | 1 |
| Live Bedrock baseline write | `CODE_WIKI_RUN_EVAL=1 ... -k scanner --accept-divergence-baseline` | 1 passed in 14.51s — baseline written with runs=1 across all 5 rules |
| Live Bedrock regression sanity | `CODE_WIKI_RUN_EVAL=1 ... -k scanner` (no accept flag) | 1 passed in 14.90s — gate matches new baseline |

## Self-Check

- agents/code-wiki-agent/src/code_wiki_agent/commands/scan.py: FOUND (modified — repo_path param added at line 224, override logic at lines 260-266, pinned bypass at lines 268-278)
- agents/code-wiki-agent/tests/unit/test_commands_scan.py: FOUND (modified — new test_run_scan_repo_path_overrides_cwd appended)
- cores/eval-harness/tests/eval_helpers.py: FOUND (modified — repo_path=eval_harness_dir at line 242)
- cores/eval-harness/baselines/divergence-scanner.json: FOUND (modified — runs=1, agent_commit=13da865)
- Commit 5eef098 (RED test): FOUND
- Commit cd2f248 (GREEN implementation): FOUND
- Commit a4ea344 (helper wiring): FOUND
- Commit 13da865 (Rule 1 fix): FOUND
- Commit 1de34bb (baseline + gitignore): FOUND

## Self-Check: PASSED
