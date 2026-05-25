---
phase: 21-rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r
plan: 03
subsystem: agents/graph-wiki-agent
tags: [rename, refactor, rebrand, imports, python-module-sweep, pytest-green]
requires:
  - 21-02 (pyproject + console scripts renamed; uv.lock regenerated)
provides:
  - graph-wiki-agent src/ + tests/ rebranded end-to-end (imports, identifiers, strings, trace-dir fragment)
  - pytest non-integration green from this layer forward (D-11 gate satisfied)
  - graph-wiki-agent CLI + graph-wiki-mcp module both importable + invocable under new names
affects:
  - agents/graph-wiki-agent/src/graph_wiki_agent/**/*.py
  - agents/graph-wiki-agent/src/graph_wiki_mcp/**/*.py
  - agents/graph-wiki-agent/tests/**/*.py
  - agents/graph-wiki-agent/tests/prompts/__snapshots__/*.ambr
tech-stack:
  added: []
  patterns:
    - "scripted-sed sweep via `grep -rEl | while read f; do sed -i ''`"
    - "two-commit revertable cadence (src first, tests + kebab strings second)"
key-files:
  created: []
  modified:
    - "11 files in agents/graph-wiki-agent/src/ (commit ab8f8a9)"
    - "43 files in agents/graph-wiki-agent/{src,tests}/ (commit 29eca18) — including 1 .ambr snapshot"
decisions:
  - "Extended `.code-wiki/` sed pattern to also cover bare `.code-wiki` (no trailing slash) because vault path constructions like `vault_path / \".code-wiki\"` would otherwise still resolve to the old directory at runtime — a Rule 1 bug the plan's pattern would have missed."
  - "Reverted exactly one `.code-wiki` reference inside tests/unit/test_trace_viewer.py (the `_REAL_V0_FIXTURE_DIR` constant) and annotated it with a NOTE(21-03) comment. The fixture itself lives in packages/wiki-io/tests/fixtures/round-trip-vault/.code-wiki/ — cross-package surface explicitly deferred to plan 21-04. Reverting the constant keeps the test pointing at the on-disk fixture; plan 21-04 will rename both together."
  - "Task 1 committed src/ on import smoke only (not pytest) because pytest cannot collect tests/ while test imports still reference code_wiki_agent. Per-task pytest gate as written in plan was unreachable; final pytest gate at end of Task 2 satisfies the D-11 acceptance."
metrics:
  duration_min: ~6
  completed: 2026-05-19
---

# Phase 21 Plan 03: rename-code-wiki-agent-to-graph-wiki-agent-update-all-code-r Summary

D-09 layer 3 — the main event. Swept imports + symbol renames + string literals + trace-dir path fragments inside `agents/graph-wiki-agent/` (src/ + tests/ + one .ambr snapshot). Two atomic commits in the planned revertable cadence; pytest non-integration green at 212 passed / 1 skipped / 5 deselected.

## Commits

| Hash | Subject | Files | Insertions/Deletions |
|------|---------|-------|----------------------|
| ab8f8a9 | refactor(21): rebrand imports + identifiers + trace-dir in graph-wiki-agent src/ | 11 | 65 / 65 |
| 29eca18 | refactor(21): rebrand kebab strings + tests in graph-wiki-agent | 43 | 581 / 581 |

Both commits land on branch `worktree-agent-a1ea85adb2b9031a5` (will be merged into `rename-21` / `main` by orchestrator).

## Surgical-Changes Verification

`git show --name-only HEAD~1 HEAD` shows ALL paths under `agents/graph-wiki-agent/`. No collateral edits to pyproject, planning, packages/, or other agents — Karpathy §3 (Surgical Changes) honored.

## Numstat (combined)

54 files changed across the two commits, 646 insertions / 646 deletions — symmetric counts confirm pure-rebrand semantics (every change is a token swap, no logic touched).

See `/tmp/21-03-summary-data.txt` for the full per-file numstat (preserved in scratch but not checked in).

## Post-sweep grep (zero residuals)

```
$ grep -rE 'code-wiki-agent|code-wiki-mcp|code_wiki_agent|code_wiki_mcp|CodeWiki[A-Z]|\.code-wiki/' agents/graph-wiki-agent/
(zero matches)
```

Note: one residual bare-form `.code-wiki` exists inside `tests/unit/test_trace_viewer.py:1085` — annotated with `NOTE(21-03): wiki-io fixture dir rename deferred to plan 21-04`. This is intentional (see Deviations §2) and does NOT match the must_have grep pattern (which requires the `/` suffix).

## D-11 Gate — pytest non-integration green

```
================ 212 passed, 1 skipped, 5 deselected in 18.63s =================
```

Exit code 0 (captured via `$?` after redirected pytest run, not pipe — PIPESTATUS-equivalent). The 1 skipped is the integration-tagged `test_all_six_tools_end_to_end` which requires `CODE_WIKI_RUN_INTEGRATION=1` (env var rename deferred to plan 21-04).

## Console-script smoke tests (proves layer-2 + layer-3 cohere)

```
$ uv run graph-wiki-agent --help
 Usage: graph-wiki-agent [OPTIONS] COMMAND [ARGS]...
 graph-wiki-agent: AWS Bedrock-powered wiki maintenance CLI.
 ...

$ uv run python -c "from graph_wiki_mcp import server"
(exit 0)
```

Both entry points (declared in pyproject by plan 21-02, made importable by plan 21-03) resolve end-to-end.

## D-02 filename spot-check

```
$ find agents/graph-wiki-agent/tests -name '*code_wiki*' -o -name '*code-wiki*'
(empty)
```

No test filenames embed the old slug — no renames needed (matches planning-time expectation).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended `.code-wiki/` sed pattern to cover bare-form `.code-wiki`**

- **Found during:** Task 1 pre-edit grep (Step 1)
- **Issue:** The plan's sed expression `s/\.code-wiki\//.graph-wiki\//g` only catches `.code-wiki/` (slash-suffixed). But many references in `commands/query.py`, `commands/scan.py`, `commands/lint.py`, `commands/ingest.py` use bare-string form: `vault_path / ".code-wiki" / "traces"`, `".code-wiki" in candidate.parts`. These paths would still resolve to the old (now-nonexistent post-21-04) directory at runtime — a guaranteed bug.
- **Fix:** Used `s/\.code-wiki/\.graph-wiki/g` (no trailing-slash constraint) in both Task 1 and Task 2 substitutions. Pre-checked with `grep -rEn 'code-wiki[^-/]|code-wiki$'` to confirm no collisions with `code-wiki-agent` kebab strings (the latter is followed by `-`, not by quote/space, so no overlap).
- **Files modified:** All sed-target files in both commits (the substitution is no-op where the slash form is present, so the broader pattern is safe).
- **Commits:** ab8f8a9, 29eca18

**2. [Rule 3 - Blocking] Reverted one `.code-wiki` in test_trace_viewer.py (cross-package fixture path)**

- **Found during:** Task 2 pytest gate (Step 5)
- **Issue:** Test `test_v0_real_fixture_renders_and_warns_once` uses `_REAL_V0_FIXTURE_DIR = Path(...) / "wiki-io" / ... / ".graph-wiki" / "traces"` after the sed sweep. But the actual fixture directory at `packages/wiki-io/tests/fixtures/round-trip-vault/.code-wiki/` is **cross-package surface** (outside `agents/graph-wiki-agent/`) — the Task 2 acceptance grep mandates HEAD touch only `agents/graph-wiki-agent/`, so we cannot rename the fixture dir from this plan. Result: 1 test failure (`No real v0 fixtures found at ... .graph-wiki/traces`).
- **Fix:** Reverted just the `.graph-wiki` path component in this single constant to `.code-wiki` and annotated with `# NOTE(21-03): wiki-io fixture dir rename deferred to plan 21-04 (cross-package sweep)`. Plan 21-04 will rename the fixture directory AND re-update the constant in the same commit.
- **Files modified:** agents/graph-wiki-agent/tests/unit/test_trace_viewer.py:1085
- **Commit:** 29eca18

**3. [Plan-mechanical] Task 1 gate ran on import smoke instead of pytest**

- **Found during:** Task 1 Step 5 (pytest gate)
- **Issue:** The plan's Task 1 Step 5 calls for `uv run pytest agents/graph-wiki-agent/tests/ -m "not integration"` after the src/-only commit. But pytest cannot collect tests/ while test imports still reference `code_wiki_agent.*` — test collection errors with `ModuleNotFoundError`. The src-only intermediate state is structurally untestable via pytest until Task 2 sweeps tests/.
- **Fix:** Gated Task 1 on (a) `uv sync` exit 0 and (b) `python -c "import graph_wiki_agent.cli; import graph_wiki_mcp.server"` exit 0 — proves the src/ rename is internally coherent. Final pytest gate satisfied at end of Task 2, where it's reachable.
- **Files modified:** None (this is a gate-procedure adjustment, not a code change).
- **Commit:** Reflected in 21-03-SUMMARY commit message rationale.

### Skipped/Deferred Items

The following remain `code-wiki` / `code_wiki` references inside `agents/graph-wiki-agent/`, deferred to plan 21-04:

- `CODE_WIKI_RUN_INTEGRATION` env-var name (in conftest.py + every integration test) — cross-consumer rename (env-var contract used by eval-harness, subagent-runtime, etc.)
- `CODE_WIKI_CONFIG` reference in src/graph_wiki_agent/config.py docstring line 12 (vestigial pathway comment — env-var rename surface)
- `.code-wiki` bare path in tests/unit/test_trace_viewer.py:1085 (wiki-io cross-package fixture, see Deviation §2)

## Auth Gates

None encountered. Pure local sed-style refactor.

## Known Stubs

None. Pure structural rename — no placeholder values introduced.

## Pointers Forward

Plan 21-04 closes out the rename:
- `CODE_WIKI_*` env-var rename (cross-consumer: eval-harness, subagent-runtime, tests/test_integration_gate.py, conftest.py, integration tests, docs)
- Vault-io fixture dir rename: `packages/wiki-io/tests/fixtures/round-trip-vault/.code-wiki/` → `.graph-wiki/` (re-aligns the test_trace_viewer constant simultaneously)
- Plugin shell-out scripts (referenced in 21-PATTERNS.md)
- Integration gate test
- Any remaining cross-package references outside `agents/graph-wiki-agent/`

## Self-Check: PASSED

- Commit ab8f8a9: FOUND in git log
- Commit 29eca18: FOUND in git log
- agents/graph-wiki-agent/src/graph_wiki_agent/cli.py: FOUND, references graph_wiki_agent (no code_wiki)
- agents/graph-wiki-agent/src/graph_wiki_mcp/server.py: FOUND, references graph_wiki_agent (no code_wiki)
- agents/graph-wiki-agent/tests/conftest.py: FOUND, references graph_wiki_agent
- pytest exit code: 0 (212 passed, 1 skipped, 5 deselected)
- `uv run graph-wiki-agent --help`: exit 0, renders Typer help
- `uv run python -c "from graph_wiki_mcp import server"`: exit 0
- Surgical-changes assertion: zero files outside `agents/graph-wiki-agent/` touched by either commit (verified via `git show --name-only HEAD~1 HEAD`)
