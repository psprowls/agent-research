from __future__ import annotations

import json
import os
import re
import subprocess

import pytest

# load-bearing: 260521-ans — strip ANSI so Typer --help output is parseable.
# Disable Rich's ANSI rendering so help output is plain text — otherwise
# `\x1b[1;36mbootstrap\x1b[0m` breaks both substring and `\b`-boundary checks
# (the trailing `m` in the SGR sequence is alphanumeric). This env injection
# is NOT cosmetic — removing NO_COLOR / TERM / COLUMNS will silently break
# test_cli_help_lists_bootstrap_subcommand and test_cli_help_init_subcommand_removed.
# Future maintainers refactoring this block: `grep -r 260521-ans .planning/` for
# the original incident context before changing anything.
_PLAIN_HELP_ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}


def _run_help() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--package", "graph-wiki-cli", "gw", "--help"],
        capture_output=True,
        text=True,
        env=_PLAIN_HELP_ENV,
    )


def test_cli_help_exits_zero() -> None:
    result = _run_help()
    assert result.returncode == 0, f"--help exited {result.returncode}\n{result.stderr}"
    assert "gw" in result.stdout.lower()


def test_cli_help_lists_bootstrap_subcommand() -> None:
    """`--help` lists `bootstrap` (Phase 18 / CMD-02 rename)."""
    result = _run_help()
    assert result.returncode == 0, f"--help exited {result.returncode}\n{result.stderr}"
    # Match `bootstrap` as a word-boundary subcommand entry (e.g. "  bootstrap   ...").
    assert re.search(r"\bbootstrap\b", result.stdout), (
        f"`bootstrap` must appear in --help output after Phase 18 rename.\nstdout:\n{result.stdout}"
    )


def test_cli_help_init_subcommand_removed() -> None:
    """`--help` does NOT list a standalone `init` subcommand (no backwards-compat alias).

    Distinguish from `ingest` (a sibling subcommand) by matching `init` as a whole word
    on its own line in the commands list — not a prefix of `ingest`.
    """
    result = _run_help()
    assert result.returncode == 0, f"--help exited {result.returncode}\n{result.stderr}"
    # `init` must not appear as a standalone token in the subcommand list.
    # `ingest` (an existing sibling) is allowed and is not matched by \binit\b.
    # We scope the negative assertion to the "Commands" section of the --help
    # output to avoid false positives from e.g. the path `--init-vault` or
    # other --help-time prose; Typer renders subcommands under a "Commands:" /
    # "Commands" header.
    stdout = result.stdout
    sections = re.split(r"(?im)^\s*[╭╰│]?\s*Commands\s*[╮╯│]?\s*$", stdout, maxsplit=1)
    commands_section = sections[1] if len(sections) > 1 else stdout
    # Literal-string assertion (matches the planner's grep:  init.*not in / not in.*init):
    assert " init " not in commands_section and "\ninit\n" not in commands_section, (
        f"`init` must NOT appear as a Typer subcommand after Phase 18 hard-cut rename.\n"
        f"Commands section:\n{commands_section}"
    )
    # Word-boundary regex backstop (catches table-rendered help output):
    assert not re.search(r"(?m)^\s*init\b", commands_section), (
        f"`init` must NOT appear as a Typer subcommand row after Phase 18 rename.\n"
        f"Commands section:\n{commands_section}"
    )


@pytest.mark.parametrize("namespace", ["graph", "wiki", "work"])
def test_help_json_serializes_every_namespace(namespace: str) -> None:
    """`gw help <namespace> --json` emits valid JSON for all subapps.

    Regression: `graph` carries an option with a `Path` default
    (`--repo`, defaulting to `Path.cwd()`), which crashed the help serializer
    with `TypeError: Object of type PosixPath is not JSON serializable` because
    `_command_to_help_entry` dumped `param.default` raw. The serializer must
    coerce non-JSON-native defaults so every command's help renders.
    """
    result = subprocess.run(
        ["uv", "run", "--package", "graph-wiki-cli", "gw", "help", namespace, "--json"],
        capture_output=True,
        text=True,
        env=_PLAIN_HELP_ENV,
    )
    assert result.returncode == 0, f"help {namespace} --json exited {result.returncode}\n{result.stderr}"
    payload = json.loads(result.stdout)
    assert payload["path"] == [namespace]
    assert isinstance(payload["commands"], list) and payload["commands"]
