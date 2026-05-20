---
phase: 20-workspace-manifest-model-config
plan: 03
subsystem: code-wiki-agent
tags: [code-wiki-agent, cli, mcp, cleanup, deletion, python]

# Dependency graph
requires:
  - phase: 20-workspace-manifest-model-config
    plan: 02
    provides: "set_models_path() deleted from model_adapter.loader; agent-side imports of set_models_path are now dangling and must be removed"
provides:
  - "WikiConfig dataclass with only vault_path and state_gate_enabled fields (models_path deleted)"
  - "code-wiki-agent CLI no longer has a --config global option (Typer @app.callback() removed)"
  - "code_wiki_mcp.server.main() reduced to mcp.run(transport='stdio') — no CODE_WIKI_CONFIG env-var read, no set_models_path import"
  - "test_config.py reflects post-deletion contract: 3 tests, no models_path / --config assertions"
affects: [20-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure deletion sweep: surgical edits matched the plan's pre-specified line ranges; no new abstractions, no new code paths"
    - "Docstring scrub: module + dataclass docstrings rewritten verbatim per plan to remove obsolete @app.callback / CODE_WIKI_CONFIG usage examples while retaining a single 'removed in Phase 20' breadcrumb for archaeology (intentional residual grep hit — see Deviations §1)"

key-files:
  created: []
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/config.py
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py
    - agents/code-wiki-agent/src/code_wiki_mcp/server.py
    - agents/code-wiki-agent/tests/unit/test_config.py

key-decisions:
  - "--config Typer option dropped entirely (not repurposed) — per CONTEXT.md locked decision §4 and per-session recommendation; GRAPH_WIKI_WORKSPACE + .graph-wiki.local.yaml already cover workspace selection"
  - "WikiConfig, load_config, get_config, _active_config kept as Python API surface — only models_path is removed. Tests still import them; _active_config remains the programmatic singleton for future surfaces"
  - "load_config silently drops unknown TOML keys (existing forward-compatibility guard) — this incidentally absorbs any legacy wiki-config.toml carrying models_path; no migration warning per CONTEXT.md §4 (no users to migrate)"
  - "No agent-side .md files exist under agents/code-wiki-agent/ outside the tests directory — Task 3 was a no-op verification, not an edit"

patterns-established:
  - "Per-task atomic commits matching the project's recent style: feat for Task 1 (deletion), test for Task 2 (test updates). Task 3 produced no commit because no files needed editing"

requirements-completed: [WMC-03]

# Metrics
duration: 10min
completed: 2026-05-20
---

# Phase 20 Plan 03: Delete --config / CODE_WIKI_CONFIG / models_path Plumbing Summary

**Surgical deletion sweep: `WikiConfig.models_path`, the `--config` Typer option, the `CODE_WIKI_CONFIG` env-var read in the MCP server, and the now-dangling `set_models_path` imports left behind by Plan 02 are all removed; test_config.py is brought back into sync with the post-deletion contract.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-20
- **Completed:** 2026-05-20
- **Tasks:** 3 (Task 1 deletion sweep across 3 source files, Task 2 test updates, Task 3 docs sweep — no-op)
- **Files modified:** 4 (3 source files + 1 test file)
- **Files created:** 0
- **Tests removed:** 1 (`test_typer_callback_sets_active_config` — callback no longer exists)
- **Tests renamed:** 1 (`test_load_config_parses_all_three_fields` → `_parses_remaining_fields`)
- **Tests passing:** code-wiki-agent + full workspace 579/579 (32 integration skips unchanged); model-adapter 21/21; workspace-io invariants hold (within the 579 aggregate)

## Accomplishments

- **Deleted `WikiConfig.models_path` field** from `config.py`. Updated the dataclass docstring to drop the `models_path:` bullet. Rewrote the module docstring verbatim per plan: dropped both code-fence examples (`@app.callback` `--config` AND `os.environ.get("CODE_WIKI_CONFIG")`) and replaced with the post-Phase-20 contract description.
- **Deleted the `@app.callback()` decorator and `main_callback` function** from `cli.py` (10 lines). The `from model_adapter.loader import set_models_path` import inside the callback body went with it. The `Optional` import was kept — still used by multiple subcommand signatures.
- **Reduced `code_wiki_mcp.server.main()` to a two-line body** (comment + `mcp.run(transport="stdio")`). Removed the `import os`, the `CODE_WIKI_CONFIG` env-var read, the `code_wiki_agent.config` import, and the `from model_adapter.loader import set_models_path` import (which would have failed at import time post-Plan-02 if any user ever set `CODE_WIKI_CONFIG`). `from pathlib import Path` stayed at module scope — used elsewhere in the file.
- **Updated `test_config.py`** to drop `models_path` from all three remaining tests and delete the `test_typer_callback_sets_active_config` test entirely. Removed the now-unused `# Typer callback test` section header. Rewrote the module docstring to drop the "CLI-05 (--config global flag)" requirements claim.
- **Confirmed Task 3 was a no-op:** `find agents/code-wiki-agent/ -name '*.md' -not -path '*/tests/*' -not -path '*/.pytest_cache/*'` returned zero files. The recursive `--config` / `CODE_WIKI_CONFIG` / `wiki-config.toml` grep gates all return 0 file matches.
- **CLI and MCP server import cleanly** post-deletion. `code-wiki-agent --help` exits 0 with `--config` absent from the output.

## Task Commits

Atomic commits per the project's recent style:

1. **Task 1:** `382a9cd` — `feat(20-03): delete models_path / --config / CODE_WIKI_CONFIG plumbing` — 3 source files, 8 insertions / 44 deletions.
2. **Task 2:** `d72f22a` — `test(20-03): drop models_path / --config assertions from test_config.py` — 1 test file, 4 insertions / 30 deletions.
3. **Task 3:** No commit — no `.md` files under `agents/code-wiki-agent/` outside tests carry the deleted references. Acceptance gates passed without edits (Karpathy §3 — no edits = no commit).

## Files Created/Modified

- `agents/code-wiki-agent/src/code_wiki_agent/config.py` — module docstring rewritten verbatim per plan; `models_path` field deleted from `WikiConfig`; dataclass docstring updated. `load_config`, `get_config`, `_active_config` untouched.
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — `@app.callback()` + `main_callback` deleted (10 lines removed); `set_models_path` import removed (it was inside the deleted callback body). All subcommands and the `Optional` import preserved.
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — `main()` body reduced from 13 lines to 2 (preserved the RESEARCH A2 transport comment). `import os` (function-scoped) dropped. `Path` import at module scope kept — used elsewhere in the file.
- `agents/code-wiki-agent/tests/unit/test_config.py` — module docstring rewritten; one test renamed (`_parses_remaining_fields`), one test deleted (`test_typer_callback_sets_active_config`); `models_path` lines stripped from the two remaining `load_config` tests. Test count: 4 → 3.

## Files Touched in Task 3 Docs Sweep

**None.** The enumeration command `grep -rln --include='*.md' --include='README*' --exclude-dir='tests' --exclude-dir='.pytest_cache' -- '--config\|CODE_WIKI_CONFIG' agents/code-wiki-agent/ 2>/dev/null` returned no matches; `find agents/code-wiki-agent/ -name '*.md' -not -path '*/tests/*' -not -path '*/.pytest_cache/*'` returned no files. The agent has no live `.md` docs to sweep.

## Decisions Made

- **Verbatim docstring text takes precedence over the literal grep gate.** Plan Task 1 step 1a says "Do not paraphrase — use this exact string." The mandated docstring contains the breadcrumb `the \`--config\` / CODE_WIKI_CONFIG pathway was removed in Phase 20 / WMC-03` for archaeological context. This creates one residual match per grep gate (`grep -c '@app.callback\|--config\|CODE_WIKI_CONFIG\|set_models_path'` returns 1, not 0; gate #2 of the phase verification also returns 1). The plan's verbatim text spec wins; the grep gate is over-restrictive against the very docstring it mandates. See Deviations §1.
- **Test 2's `--config` grep hit is the same docstring class issue:** the new module docstring in `test_config.py` references `--config` for the same archaeological reason ("CLI-05 / --config plumbing was removed in Phase 20 / WMC-03"). Acceptance criterion `grep -c -- '--config' test_config.py == 0` is over-restrictive; docstring intent is correct.
- **`Optional` import kept in `cli.py`** — multiple subcommand signatures still use it (`--detail`, `--slug`, `--pkg-dir`).
- **`Path` import kept at module scope in `server.py`** — used by 9 other call sites (input parsing in `scan`, `ingest`, `query`, etc.).
- **`load_config`, `get_config`, `WikiConfig`, `_active_config` retained as Python API** — tests still exercise them, and `_active_config` remains the singleton for programmatic configuration as noted in the new module docstring.

## Deviations from Plan

### 1. [Annotation only] Docstring-vs-grep contradiction in acceptance criteria

- **Found during:** Task 1 verification (gate `grep -c '@app.callback\|--config\|CODE_WIKI_CONFIG\|set_models_path' agents/code-wiki-agent/src/code_wiki_agent/config.py == 0`).
- **Issue:** The plan's Task 1 step 1a mandates a verbatim docstring containing the phrase ``the `--config` / CODE_WIKI_CONFIG pathway was removed in Phase 20 / WMC-03`` ("Do not paraphrase — use this exact string"). The same plan's `<acceptance_criteria>` expects 0 grep matches on those tokens. The two are contradictory; the verbatim spec is the more specific instruction and wins. The grep gate returns 1 (the archaeological breadcrumb line), not 0.
- **Resolution:** No code change. Docstring is exactly as the plan specified; the residual grep hit is on the plan-mandated text, not on residual plumbing. `cli.py` and `server.py` have 0 hits on those tokens. The intent of the gate ("no remaining plumbing references") is satisfied.
- **Files modified:** None beyond the planned scope.
- **Commit:** N/A.

### 2. [Annotation only] Same docstring-vs-grep contradiction in Task 2

- **Found during:** Task 2 verification (gate `grep -c -- '--config' agents/code-wiki-agent/tests/unit/test_config.py == 0`).
- **Issue:** Plan Task 2 step 1 mandates rewriting the module docstring to: `"Unit tests for code_wiki_agent.config module — exercises load_config TOML parsing and the _active_config singleton. (CLI-05 / --config plumbing was removed in Phase 20 / WMC-03.)"`. That mandated text contains `--config`; gate returns 1, not 0.
- **Resolution:** No code change. Plan-mandated text takes precedence.
- **Files modified:** None beyond the planned scope.
- **Commit:** N/A.

### 3. [Scope reduction] Task 3 produced no commit

- **Found during:** Task 3 enumeration step.
- **Issue:** `find agents/code-wiki-agent/ -name '*.md' -not -path '*/tests/*' -not -path '*/.pytest_cache/*'` returned no files. The recursive grep against `--config` / `CODE_WIKI_CONFIG` / `wiki-config.toml` in `.md` / `README*` (with the tests + pytest_cache exclusions) returned 0 matches without any edit. The acceptance gates passed natively.
- **Resolution:** No commit (no files changed). Karpathy §3 surgical principle: no edits → no commit. Documented here for traceability.
- **Files modified:** None.
- **Commit:** N/A.

No other deviations. The plan otherwise executed exactly as written.

## Issues Encountered

- A `print('imports OK')` smoke test from the plan's verify block hit the MCP server's stdout guard (`Illegal stdout write in MCP server`). Rerouted to `sys.stderr` and the import check passed. Not a code defect — the guard is doing its job; the verify block's snippet didn't anticipate the guard. No code change.

## User Setup Required

None — pure source/test deletion sweep inside `agents/code-wiki-agent/`. The two formerly-supported user surfaces (`code-wiki-agent --config <toml>` and `CODE_WIKI_CONFIG=<toml>`) are deleted; users who relied on them must switch to `<workspace>/.graph-wiki.yaml` `plugins[].roles[]` (delivered by Plans 20-01 and 20-02).

## TDD Gate Compliance

- **Task 1** (deletion) is structural; no `tdd="true"` declaration in the plan. Verified by existing 579 tests staying green.
- **Task 2** (`tdd="true"`) followed RED → GREEN cleanly: pre-edit, the existing `test_config.py` failed (RED confirmed: `AttributeError: 'WikiConfig' object has no attribute 'models_path'`); post-edit, 3/3 tests pass (GREEN). No separate RED commit because the failing test state was already established by Task 1's deletion of the `models_path` field — the test file is updated to match the new contract within a single `test(...)` commit. This matches the Phase 17 / 20-02 pattern of treating the prior task's commit as the implicit RED gate.
- **REFACTOR gate:** not required — the implementation is already minimal (deletion only).

## Self-Check

Files modified (verified via `git log --stat 382a9cd^..d72f22a`):
- `agents/code-wiki-agent/src/code_wiki_agent/config.py` — VERIFIED MODIFIED (commit `382a9cd`)
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — VERIFIED MODIFIED (commit `382a9cd`)
- `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — VERIFIED MODIFIED (commit `382a9cd`)
- `agents/code-wiki-agent/tests/unit/test_config.py` — VERIFIED MODIFIED (commit `d72f22a`)

Commits verified via `git log --oneline -3`:
- `d72f22a` — FOUND
- `382a9cd` — FOUND

Acceptance-criteria gates (re-run post-commit):

Task 1 gates:
- `grep -c 'models_path' agents/code-wiki-agent/src/code_wiki_agent/config.py` → 0 — PASS
- `grep -c '@app.callback\|--config\|CODE_WIKI_CONFIG\|set_models_path' agents/code-wiki-agent/src/code_wiki_agent/config.py` → 1 — DEVIATION §1 (plan-mandated docstring text)
- `grep -c 'models_path\|--config\|set_models_path\|main_callback' agents/code-wiki-agent/src/code_wiki_agent/cli.py` → 0 — PASS
- `grep -c 'CODE_WIKI_CONFIG\|set_models_path' agents/code-wiki-agent/src/code_wiki_mcp/server.py` → 0 — PASS
- `uv run --package code-wiki-agent python -c "from code_wiki_agent.cli import app; from code_wiki_mcp import server"` exit 0 — PASS
- `code-wiki-agent --help` exit 0 with `--config` absent — PASS (0 matches)
- `python -c "from code_wiki_agent.config import WikiConfig, load_config, get_config"` exit 0 — PASS

Task 2 gates:
- `grep -c 'models_path' agents/code-wiki-agent/tests/unit/test_config.py` → 0 — PASS
- `grep -c 'test_typer_callback_sets_active_config' agents/code-wiki-agent/tests/unit/test_config.py` → 0 — PASS
- `grep -c -- '--config' agents/code-wiki-agent/tests/unit/test_config.py` → 1 — DEVIATION §2 (plan-mandated docstring text)
- `grep -c '^def test_' agents/code-wiki-agent/tests/unit/test_config.py` → 3 — PASS
- `uv run --package code-wiki-agent pytest tests/unit/test_config.py -x` → 3/3 passed — PASS
- `uv run --package code-wiki-agent pytest -x` → 579/579 passed (32 integration skips) — PASS

Task 3 gates:
- `grep -rln --include='*.md' --include='README*' --exclude-dir='tests' --exclude-dir='.pytest_cache' -- '--config\|CODE_WIKI_CONFIG' agents/code-wiki-agent/ | wc -l` → 0 — PASS
- `grep -rln --include='*.md' --exclude-dir='tests' --exclude-dir='.pytest_cache' 'wiki-config\.toml' agents/code-wiki-agent/ | wc -l` → 0 — PASS
- `uv run --package code-wiki-agent pytest -x` → 579/579 passed — PASS

Phase verification gates:
- `uv run --package code-wiki-agent pytest -x` → 579 passed, 32 skipped — PASS
- `uv run --package model-adapter pytest -x` → 579 passed (workspace-wide aggregate; model-adapter invariants preserved) — PASS
- `uv run --package workspace-io pytest -x` → 579 passed — PASS
- `grep -rn "set_models_path\|CODE_WIKI_CONFIG\|models_path" agents/code-wiki-agent/src/` → 1 hit (docstring breadcrumb on `config.py:12`, DEVIATION §1) — INTENDED RESIDUAL
- `code-wiki-agent --help` exit 0; `--config` absent — PASS
- `python -c "from code_wiki_mcp import server"` exit 0 — PASS

## Self-Check: PASSED

## Known Stubs

None. This is a deletion-only plan; no new UI surfaces, no placeholder data flow.

## Threat Flags

None — no new network endpoints, no new auth paths, no new trust boundaries. Deletion sweep narrows the agent's input surface (one fewer env var, one fewer CLI flag); does not introduce new ones.

## Next Phase Readiness

- **SC#3 closed:** `WikiConfig.models_path`, `set_models_path()`, `--config`, and `CODE_WIKI_CONFIG` are all removed. The only residual references are the two plan-mandated docstring breadcrumbs noted in Deviations §§1-2; no code path reads `wiki-config.toml`.
- **SC#5 agent-side docs portion closed:** no `.md` files under `agents/code-wiki-agent/` outside tests reference the deleted surface.
- **Plan 20-04 (live verify SC#4)** can now proceed against `~/Personal/deep-agents/graph-wiki/.graph-wiki.yaml`: the agent has no remaining code path that would short-circuit workspace resolution via the deleted plumbing.

---
*Phase: 20-workspace-manifest-model-config*
*Completed: 2026-05-20*
