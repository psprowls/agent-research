---
quick_id: 260521-ans
slug: typer-help-ansi-strip
status: complete
date: 2026-05-21
---

# Quick Task 260521-ans — Summary

## Outcome

Resolved 5 pre-existing unit-test failures caused by ANSI escape codes in Typer/Rich
`--help` output. Added `NO_COLOR=1`, `TERM=dumb`, `COLUMNS=200` to the subprocess
env in every `--help`-capturing test.

Before: `159 passed, 5 failed, 1 skipped`
After:  `165 passed, 0 failed, 0 skipped` (5 fixed + 1 unblocked snapshot)

## Failures resolved

1. `test_cli_help.py::test_cli_help_lists_bootstrap_subcommand`
2. `test_cli_query.py::test_query_help_exits_zero`
3. `test_cli_query.py::test_vault_flag_in_help`
4. `test_cli_query.py::test_state_gate_flag_present`
5. `test_trace_viewer.py::test_trace_command_has_expand_flag`

Bonus: `test_trace_viewer.py::test_cost_rollup_snapshot` was self-skipping
because `_trace_supports_expand_flag()` used the same broken `--help` capture.
Fixing that helper unblocks the snapshot test.

## Files changed

- `agents/graph-wiki-agent/tests/unit/test_cli_help.py` — `_run_help()` now passes `env=_PLAIN_HELP_ENV`
- `agents/graph-wiki-agent/tests/unit/test_cli_query.py` — 3 `subprocess.run` calls + module-level `_PLAIN_HELP_ENV`
- `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` — 2 `subprocess.run` calls (test + `_trace_supports_expand_flag` helper)

## Root cause

Typer renders `--help` via Rich, which emits ANSI SGR sequences
(`\x1b[1;36mbootstrap\x1b[0m`) even when stdout is a pipe. The trailing `m`
in the SGR escape is alphanumeric, so `re.search(r"\bbootstrap\b", stdout)`
finds no word boundary between `m` and `b`, and `"--top-k" in stdout` fails
because the flag is split across two SGR runs (`--top\x1b[0m\x1b[1;36m-k`).

Setting `NO_COLOR=1` disables Rich's color output entirely; `TERM=dumb` is a
belt-and-braces for Rich's terminal detection; `COLUMNS=200` prevents
table-wrap from splitting flag names across lines.
