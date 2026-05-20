---
phase: 18-plugin-command-rename
plan: 03
subsystem: cli
tags: [typer, cli, code-wiki-agent, rename, bootstrap, cmd-02]

# Dependency graph
requires:
  - phase: 18-plugin-command-rename
    provides: D-01 verb decision (bootstrap), D-02 surface scope (all three user-facing surfaces), D-04 hard cut (no compat alias), D-06 staged-commit cutover
provides:
  - Typer subcommand `code-wiki-agent bootstrap` (replaces `code-wiki-agent init`)
  - Test file rename `test_commands_init.py → test_commands_bootstrap.py` (git mv, history preserved)
  - Help-text assertions covering both positive (`bootstrap` present) and negative (`init` absent) cases
  - CLI portion of CMD-02 (the MCP portion was closed by parallel plan 18-02)
affects: [18-04 (consumer reference sweep), 18-06 (brand-gate enforcement)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "User-facing Typer subcommand renamed; internal Python module path (`code_wiki_agent.commands.init`) intentionally NOT renamed (D-02 — machine-facing, not user-typed)"
    - "Test surface follows production surface — when a CLI subcommand renames, its dedicated test file is renamed via `git mv` for grep parity"

key-files:
  created: []
  modified:
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py
    - agents/code-wiki-agent/tests/unit/test_cli_help.py
    - agents/code-wiki-agent/tests/unit/test_commands_bootstrap.py (renamed from test_commands_init.py)

key-decisions:
  - "Followed plan exactly — no deviations"
  - "Q1 resolution honored: test file renamed via `git mv` (preserves history; matches grep parity)"
  - "D-02 honored: import `from code_wiki_agent.commands.init import run_init` unchanged; helper `_make_init_result` retained"
  - "D-04 honored: no Typer alias for `init`; old slug exits with Typer's `code=2` no-such-command error"
  - "Two obsolete MCP-surface tests deleted from the renamed file per plan instruction (they live in renamed form in `test_mcp_new_tools.py`, added by parallel plan 18-02)"

patterns-established:
  - "User-vs-machine surface boundary: rename what users type (Typer `def init` → `def bootstrap`); leave what code imports (`from .commands.init import run_init`) untouched"
  - "Hard-cut renames over compat aliases: rely on Typer's native `no such command` error rather than maintaining a deprecation shim"
  - "Test-file rename via `git mv` for surface parity, even when the file's content edits are minimal"

requirements-completed: [CMD-02]

# Metrics
duration: ~10 min
completed: 2026-05-20
---

# Phase 18 Plan 03: Rename Typer CLI subcommand `init` → `bootstrap` Summary

**Bedrock Typer subcommand renamed `init` → `bootstrap` so Claude Code's native `/init` no longer collides; hard cut with no compat alias.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-20T02:00:00Z (approx)
- **Completed:** 2026-05-20T02:07:22Z
- **Tasks:** 2
- **Files modified:** 3 (1 source, 2 tests; 1 of those tests is a git-mv rename)

## Accomplishments

- `@app.command()` Typer function `def init(...)` renamed to `def bootstrap(...)` in `agents/code-wiki-agent/src/code_wiki_agent/cli.py:438`
- `agents/code-wiki-agent/tests/unit/test_commands_init.py` renamed via `git mv` to `test_commands_bootstrap.py` (R068 in git log — git tracked rename with 68% similarity)
- Two obsolete MCP-surface tests deleted from the renamed file (their renamed form lives in `test_mcp_new_tools.py` added by plan 18-02)
- `test_cli_help.py` augmented with positive (`bootstrap` appears) and negative (`init` not a standalone subcommand, disambiguated from `ingest`) assertions
- Per-commit pytest gate green: 209 passed, 1 skipped, 5 deselected (unchanged from pre-commit baseline)

## Task Commits

Both tasks landed in a single commit per the plan's Step 5 instruction:

1. **Task 1 + Task 2 (combined):** `5074d62` — `refactor(18): rename CLI subcommand init → bootstrap`

No separate plan-metadata commit yet — this SUMMARY.md is being committed next; STATE.md / ROADMAP.md updates are out of scope for this parallel-worktree executor (the parent orchestrator owns those merges).

## Files Created/Modified

- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — `def init(...)` → `def bootstrap(...)` (line 438; one-token change; decorator unchanged, body unchanged, docstring already aligned)
- `agents/code-wiki-agent/tests/unit/test_commands_bootstrap.py` — renamed from `test_commands_init.py` via `git mv`; CLI-surface test names renamed (`test_bootstrap_command`, `test_bootstrap_calls`); CliRunner subcommand argument changed from `"init"` to `"bootstrap"`; obsolete MCP-surface tests deleted; module-docstring updated; unused imports (`dataclasses`, `MagicMock`) pruned by the rewrite
- `agents/code-wiki-agent/tests/unit/test_cli_help.py` — added `test_cli_help_lists_bootstrap_subcommand` (positive) and `test_cli_help_init_subcommand_removed` (negative) assertions; refactored to share a `_run_help()` helper

## Decisions Made

None beyond honoring planner-resolved decisions:

- D-02 (user-facing surface only): preserved `from code_wiki_agent.commands.init import run_init` import and the `_make_init_result` helper that uses `code_wiki_agent.commands.init.InitResult`
- D-04 (hard cut): no Typer alias added; `code-wiki-agent init --help` exits with Typer's `code=2` "No such command"
- Q1 (test file rename): renamed via `git mv` (R068 entry in git log)
- Step 5 (single commit): both tasks landed together in `5074d62`
- The success-print line `[ok] Initialized wiki at: ...` was left as-is per "Claude's discretion" in the plan — it's descriptive prose, not a slug, and changing it would be churn without acceptance value

## Deviations from Plan

None — plan executed exactly as written.

Minor naming-pattern adjustments to satisfy the planner's literal `grep -cE '\btest_bootstrap_command\b|\btest_bootstrap_calls\b|...'` acceptance regex (which requires word-boundary endings, i.e. exact-identifier matches): the renamed tests are `def test_bootstrap_command(...)` and `def test_bootstrap_calls(...)` rather than `test_bootstrap_command_json_output` / `test_bootstrap_command_rejects_init`. Semantic intent unchanged; docstrings carry the descriptive detail.

## Issues Encountered

None. Pytest gate ran clean on first attempt. `--help` output rendered as expected with `bootstrap` in the Commands list and no `init` row.

## Verification Evidence

### Source-tree assertions (Task 1 automated gate)

```text
$ grep -cE '^\s*def init\b' agents/code-wiki-agent/src/code_wiki_agent/cli.py
0
$ grep -cE '^\s*def bootstrap\(' agents/code-wiki-agent/src/code_wiki_agent/cli.py
1
$ grep -nE 'from code_wiki_agent.commands.init import run_init' agents/code-wiki-agent/src/code_wiki_agent/cli.py
14:from code_wiki_agent.commands.init import run_init    # ← import unchanged per D-02
```

### Typer `--help` snippet (`code-wiki-agent --help`)

```text
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ version    Print version and exit.                                           │
│ trace      Render a JSONL trace file as a human-readable timeline.           │
│ query      Query the wiki using hybrid BM25+embedding search with librarian  │
│            fan-out.                                                          │
│ log        Append a timestamped event to the wiki log.md.                    │
│ bootstrap  Bootstrap a wiki vault structure (creates raw/ and work/          │
│            siblings).                                                        │
│ scan       Walk repo, diff packages vs vault, create/update stubs via        │
│            scanner fan-out.                                                  │
│ lint       Run mechanical + semantic lint pass over the wiki and report      │
│            findings.                                                         │
│ ingest     Ingest a source file or work item into the wiki.                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

`bootstrap` row present. No `init` row (the `ingest` row is the only one starting with `in`).

### Old subcommand rejected (`code-wiki-agent init --help`)

```text
Usage: code-wiki-agent [OPTIONS] COMMAND [ARGS]...
Try 'code-wiki-agent --help' for help.
╭─ Error ──────────────────────────────────────────────────────────────────────╮
│ No such command 'init'. Did you mean 'lint', 'ingest'?                       │
╰──────────────────────────────────────────────────────────────────────────────╯
$ echo "exit: $?"
exit: 2
```

### Git rename entry

```text
$ git log -1 --name-status
commit 5074d6208fc4661cc762992a399c1005237ff3b0
...
M	agents/code-wiki-agent/src/code_wiki_agent/cli.py
M	agents/code-wiki-agent/tests/unit/test_cli_help.py
R068	agents/code-wiki-agent/tests/unit/test_commands_init.py	agents/code-wiki-agent/tests/unit/test_commands_bootstrap.py
```

`R068` confirms git recorded the move as a rename (68% similarity — content edits kept under one-third of the file).

### Per-commit pytest gate

```text
$ uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/ -m "not integration" -q
.........s..............................................................  [ 34%]
........................................................................  [ 68%]
..................................................................        [100%]
--------------------------- snapshot report summary ----------------------------
19 snapshots passed.
209 passed, 1 skipped, 5 deselected in 21.82s
```

Exit code 0. The single skip is pre-existing (unrelated to this plan).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CLI portion of CMD-02 closed. Parallel plan 18-02 closes the MCP portion (also CMD-02). Plan 18-04 (consumer reference sweep) and plan 18-06 (brand-gate enforcement, including the `def init(` regex in `cli.py`) can proceed.
- The orchestrator merging this worktree into main alongside 18-02's worktree will resolve cleanly: 18-02 owns `server.py` + `test_mcp_new_tools.py`; 18-03 owns `cli.py` + `test_commands_bootstrap.py` + `test_cli_help.py`. No file overlap.
- After both merge, the two MCP tests that this plan deleted from `test_commands_bootstrap.py` will exist in their renamed form in `test_mcp_new_tools.py` (added by 18-02), preventing test-surface duplication.

## Self-Check: PASSED

- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — FOUND, contains `def bootstrap(`, zero `def init` lines
- `agents/code-wiki-agent/tests/unit/test_commands_bootstrap.py` — FOUND (R068 from test_commands_init.py)
- `agents/code-wiki-agent/tests/unit/test_commands_init.py` — MISSING (expected — renamed)
- `agents/code-wiki-agent/tests/unit/test_cli_help.py` — FOUND, contains positive + negative assertions
- Commit `5074d62` — FOUND in `git log`
- `code-wiki-agent --help` lists `bootstrap`, not `init` — VERIFIED via live CLI run
- `code-wiki-agent init --help` exits with code 2 — VERIFIED via live CLI run
- `uv run --package code-wiki-agent pytest ... -m "not integration"` → 209 passed — VERIFIED

---
*Phase: 18-plugin-command-rename*
*Completed: 2026-05-20*
