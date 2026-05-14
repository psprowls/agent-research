from __future__ import annotations

"""Stub tests for the CLI query subcommand (Plan 03 deliverable).

These stubs exist so the test runner discovers Phase 3 CLI tests from Wave 0
onwards. All tests are marked xfail until Plan 03 implements the `query`
subcommand in code_wiki_agent.cli and code_wiki_agent.commands.query.

Requirements covered: CLI-01, CLI-03, CLI-05, CLI-06, CLI-07, CMD-08.
"""

import pytest


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_query_help_exits_zero() -> None:
    """code-wiki-agent query --help exits with code 0 (CLI-01)."""
    assert False, "stub — Plan 03"


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_shared_impl_is_imported_from_commands() -> None:
    """CLI query subcommand delegates to commands.query.run_query, not inline logic (CLI-03)."""
    assert False, "stub — Plan 03"


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_state_gate_flag_present() -> None:
    """query subcommand checks the vault state gate before running (CMD-08)."""
    assert False, "stub — Plan 03"


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_vault_flag_passes_path() -> None:
    """--vault flag overrides default vault path and passes it to run_query (CLI-05)."""
    assert False, "stub — Plan 03"


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_exit_code_1_on_runtime_error() -> None:
    """query subcommand exits with code 1 and actionable stderr on runtime error (CLI-06)."""
    assert False, "stub — Plan 03"


@pytest.mark.xfail(reason="Implemented in Plan 03", strict=False)
def test_headless_mode_non_tty() -> None:
    """query subcommand works correctly in non-TTY (headless/CI) mode (CLI-07)."""
    assert False, "stub — Plan 03"
