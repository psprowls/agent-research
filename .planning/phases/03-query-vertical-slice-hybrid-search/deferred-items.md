# Deferred Items — Phase 03

Out-of-scope discoveries from 03-08 execution. Do NOT fix as part of this plan.

## Pre-existing CLI help test failures (unrelated to 03-08)

`agents/code-wiki-agent/tests/unit/test_cli_query.py` contains three tests that
assert plain-text substrings in `--help` output:

- `test_query_help_exits_zero` — asserts `"--top-k" in result.stdout`
- `test_vault_flag_in_help` — asserts `"--vault" in result.stdout`
- `test_state_gate_flag_present` — asserts `"--no-state-gate" in result.stdout`

These fail because Typer's `--help` output is wrapped with ANSI escape
sequences and flag names render across multi-line table cells, so the bare
substrings never appear.

Confirmed pre-existing on the `worktree-agent-a1ca122d8cb4cf147` branch
before any 03-08 changes were applied — `git stash` + run shows the same
failure. Out of scope for the 03-08 prompt + retry work.

Suggested fix (future plan): strip ANSI codes in the assertion or pass
`env={"NO_COLOR": "1"}` to the subprocess.
