from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from graph_wiki_cli.cli import app

runner = CliRunner()


def test_wiki_cli_module_exposes_wiki_app_and_main() -> None:
    """The relocated module exposes a `wiki` Typer app and a `main()` entry."""
    from graph_wiki_cli.wiki_cli import main as wiki_main

    assert isinstance(wiki_main.wiki_app, typer.Typer)
    assert wiki_main.wiki_app.info.name == "wiki"
    assert hasattr(wiki_main, "main")


def test_root_app_mounts_wiki_group_with_subcommands() -> None:
    """`gw wiki` is registered and exposes query/log/lint/ingest."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "wiki" in root_command.commands

    wiki_group = root_command.commands["wiki"]
    assert {"query", "log", "lint", "ingest"} <= set(wiki_group.commands)

    ingest_group = wiki_group.commands["ingest"]
    assert {"source", "work-item"} <= set(ingest_group.commands)


def test_moved_commands_no_longer_top_level() -> None:
    """query/log/lint/ingest are no longer registered at the root."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    for name in ("query", "log", "lint", "ingest"):
        assert name not in root_command.commands


def test_ack_drift_subcommand_registered() -> None:
    """`gw wiki ack-drift` is registered under the wiki group."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    wiki_group = root_command.commands["wiki"]
    assert "ack-drift" in wiki_group.commands


def test_ack_drift_cli_clears_and_exits_zero(tmp_path: Path) -> None:
    """`gw wiki ack-drift <uri> --workspace <ws>` exits 0 and prints cleared count."""
    from graph_wiki_core.commands.ack_drift import AckDriftResult

    fake_page = tmp_path / "pkg-a.md"
    fake_result = AckDriftResult(page_path=fake_page, cleared=2)

    with patch("graph_wiki_cli.wiki_cli.main.run_ack_drift", return_value=fake_result) as mock_fn:
        result = runner.invoke(app, ["wiki", "ack-drift", "pkg:org/repo/pkg-a", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "Cleared 2" in result.output
    mock_fn.assert_called_once_with("pkg:org/repo/pkg-a", workspace_path=tmp_path)


def test_ack_drift_cli_unknown_entity_exits_nonzero() -> None:
    """`gw wiki ack-drift` exits 1 when run_ack_drift raises ValueError."""
    with patch("graph_wiki_cli.wiki_cli.main.run_ack_drift", side_effect=ValueError("no entity page found")):
        result = runner.invoke(app, ["wiki", "ack-drift", "pkg:does/not/exist"])

    assert result.exit_code == 1
    assert "no entity page found" in result.output


def test_ingest_source_cli_warns_on_degraded_and_stripped(tmp_path):
    """Text-mode CLI prints loud warnings (stderr) when frontmatter didn't
    parse and when wikilinks were stripped. Click 8.3 captures stderr
    separately from stdout."""
    from unittest.mock import AsyncMock

    from graph_wiki_cli.wiki_cli.main import wiki_app
    from graph_wiki_core.commands.ingest import IngestResult

    src = tmp_path / "doc.md"
    src.write_text("# Doc\n\nBody.", encoding="utf-8")

    fake_result = IngestResult(
        status="ok",
        page_path="sources/doc.md",
        slug="doc",
        title="Doc",
        page_type="source",
        source_path=str(src),
        cross_refs_updated=1,
        source_kind="unknown",
        stripped_wikilinks=["Made Up Person", "fake/page"],
        frontmatter_parsed=False,
    )

    with patch(
        "graph_wiki_cli.wiki_cli.main.run_ingest_source",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = runner.invoke(wiki_app, ["ingest", "source", str(src)])

    assert result.exit_code == 0
    # stdout carries the ok line + the descriptive source_kind
    assert "source_kind: unknown" in result.stdout
    # warnings go to stderr (err=True)
    assert "frontmatter did not parse" in result.stderr
    assert "stripped 2 unresolved wikilink(s)" in result.stderr
    assert "Made Up Person" in result.stderr
