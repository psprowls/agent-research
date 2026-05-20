from __future__ import annotations

import re
import subprocess


def _run_help() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-agent", "--help"],
        capture_output=True,
        text=True,
    )


def test_cli_help_exits_zero() -> None:
    result = _run_help()
    assert result.returncode == 0, f"--help exited {result.returncode}\n{result.stderr}"
    assert "code-wiki-agent" in result.stdout.lower()


def test_cli_help_lists_bootstrap_subcommand() -> None:
    """`--help` lists `bootstrap` (Phase 18 / CMD-02 rename)."""
    result = _run_help()
    assert result.returncode == 0, f"--help exited {result.returncode}\n{result.stderr}"
    # Match `bootstrap` as a word-boundary subcommand entry (e.g. "  bootstrap   ...").
    assert re.search(r"\bbootstrap\b", result.stdout), (
        f"`bootstrap` must appear in --help output after Phase 18 rename.\n"
        f"stdout:\n{result.stdout}"
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
