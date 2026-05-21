---
quick_id: 260521-ans
slug: typer-help-ansi-strip
date: 2026-05-21
---

# Quick Task 260521-ans — Strip ANSI from Typer `--help` capture in unit tests

## Problem

5 unit tests in `agents/graph-wiki-agent/tests/unit/` capture `--help` output via
`subprocess.run` and assert on substrings / word-boundary regexes against
`result.stdout`. Typer renders help through Rich, which emits ANSI escape codes
(e.g. `\x1b[1;36mbootstrap\x1b[0m`) even when stdout is a pipe. The trailing `m`
in `\x1b[1;36m` is alphanumeric, so:

- `re.search(r"\bbootstrap\b", stdout)` → no match (no word boundary between `m` and `b`)
- `"--top-k" in stdout` → false (text appears as `--top\x1b[0m\x1b[1;36m-k`)

Failures introduced in Phase 21 commit `29eca18b` (rebrand sweep updated string
literals but did not touch the help-capture mechanism). Verifier confirmed they
predate Phase 25 and are not regressions from that work.

## Failing tests

1. `tests/unit/test_cli_help.py::test_cli_help_lists_bootstrap_subcommand`
2. `tests/unit/test_cli_query.py::test_query_help_exits_zero`
3. `tests/unit/test_cli_query.py::test_vault_flag_in_help`
4. `tests/unit/test_cli_query.py::test_state_gate_flag_present`
5. `tests/unit/test_trace_viewer.py::test_trace_command_has_expand_flag`

## Fix

Pass `env={**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}` to
every `subprocess.run([..., "--help"])` call in the three affected test files.

- `NO_COLOR=1` — disables Rich color output (respects the [no-color.org] convention)
- `TERM=dumb` — additional belt-and-braces for Rich's terminal detection
- `COLUMNS=200` — keeps Rich from wrapping table rows in a way that could
  re-split flag names across line breaks

Verified manually: with these env vars, `bootstrap`, `--top-k`, `--workspace`,
`--no-state-gate`, and `--expand` all appear as contiguous, ANSI-free strings.

## Files to edit

- `agents/graph-wiki-agent/tests/unit/test_cli_help.py` — `_run_help()` helper
- `agents/graph-wiki-agent/tests/unit/test_cli_query.py` — 3 inline `subprocess.run` calls
- `agents/graph-wiki-agent/tests/unit/test_trace_viewer.py` — `test_trace_command_has_expand_flag` (+ the `_trace_supports_expand_flag` helper that gates a snapshot test on the same `--help` output)

## Verification

`uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/unit/ -q`
must show: 5 fewer failures, 0 new failures, snapshot count unchanged.

## Why not a different fix?

- **Strip ANSI in tests with regex** (`re.sub(r"\x1b\[[0-9;]*m", "", stdout)`):
  works, but duplicates the strip helper across 3 files. Env-var approach is one
  line per `subprocess.run` and addresses the root cause (the help renderer
  emitting ANSI) rather than papering over it in assertions.
- **Disable Rich in `cli.py`** (`Typer(rich_markup_mode=None)`): changes behavior
  for end users, not just tests. Out of scope.
- **Snapshot the help output**: brittle to flag additions; substring asserts are
  intentionally lax.
