from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import typer
from graph_wiki_cli.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_root_app_mounts_wiki_group_with_subcommands() -> None:
    """`gw wiki` is registered and still exposes the wiki-only `lint`.

    query/log/ingest were promoted to top-level `gw` commands and no longer
    live under the wiki group.
    """
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    assert "wiki" in root_command.commands

    wiki_group = root_command.commands["wiki"]
    assert "lint" in set(wiki_group.commands)
    assert {"query", "log", "ingest"}.isdisjoint(set(wiki_group.commands))


def test_query_log_ingest_are_top_level() -> None:
    """query/ingest are registered at the root (promoted out of `gw wiki`).

    `log` was subsequently relocated under `gw util`, so it is no longer a
    top-level command — its placement is covered by test_cli_boundary.py.
    """
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    for name in ("query", "ingest"):
        assert name in root_command.commands


def test_ingest_source_cli_warns_on_degraded_and_stripped(tmp_path):
    """Text-mode CLI prints loud warnings (stderr) when frontmatter didn't
    parse and when wikilinks were stripped. Click 8.3 captures stderr
    separately from stdout."""
    from unittest.mock import AsyncMock

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
        source_type="note",
        stripped_wikilinks=["Made Up Person", "fake/page"],
        frontmatter_parsed=False,
    )

    with patch(
        "graph_wiki_cli.cli.run_ingest_source",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = runner.invoke(app, ["ingest", str(src)])

    assert result.exit_code == 0
    # stdout carries the ok line + the source_type
    assert "source_type: note" in result.stdout
    # warnings go to stderr (err=True)
    assert "frontmatter did not parse" in result.stderr
    assert "stripped 2 unresolved wikilink(s)" in result.stderr
    assert "Made Up Person" in result.stderr


def test_ingest_source_cli_prints_suggestions_and_degraded(tmp_path):
    """Text-mode CLI lists suggestions and warns when the suggest pass degraded."""
    from unittest.mock import AsyncMock

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
        source_type="doc",
        stripped_wikilinks=[],
        frontmatter_parsed=True,
        suggested_pages=[
            {
                "kind": "concept",
                "title": "Idea",
                "slug": "idea",
                "mode": "create_new",
                "existing_slug": None,
                "rationale": "r",
                "status": "proposed",
            },
        ],
        suggestions_parsed=False,
    )

    with patch(
        "graph_wiki_cli.cli.run_ingest_source",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = runner.invoke(app, ["ingest", str(src)])

    assert result.exit_code == 0
    assert "suggested 1 page(s)" in result.stdout
    assert "concept" in result.stdout
    assert "idea" in result.stdout
    # degraded warning goes to stderr (err=True); Click 8.2+ keeps stderr separate
    assert "suggestion pass degraded" in result.stderr


def test_ingest_source_cli_prints_guidance_pages(tmp_path):
    """Text-mode CLI lists guidance pages when guidance_pages_written is non-empty."""
    from unittest.mock import AsyncMock

    from graph_wiki_core.commands.ingest import IngestResult

    src = tmp_path / "skill.md"
    src.write_text("# Skill\n\nBody.", encoding="utf-8")

    fake_result = IngestResult(
        status="ok",
        page_path="sources/react-native-skill.md",
        slug="react-native-skill",
        title="React Native Skill",
        page_type="source",
        source_path=str(src),
        cross_refs_updated=1,
        source_type="skill",
        guidance_pages_written=[
            "wiki/guidance/react-native/use-virtualizer.md",
            "wiki/guidance/react-native/avoid-inline-styles.md",
        ],
    )

    with patch(
        "graph_wiki_cli.cli.run_ingest_source",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = runner.invoke(app, ["ingest", str(src)])

    assert result.exit_code == 0
    assert "wrote 2 guidance page(s)" in result.stdout
    assert "wiki/guidance/react-native/use-virtualizer.md" in result.stdout


def test_ingest_source_cli_prints_archive_to(tmp_path):
    """Text-mode CLI reports the raw/_archive/ destination when set."""
    from unittest.mock import AsyncMock

    from graph_wiki_core.commands.ingest import IngestResult

    src = tmp_path / "auth.md"
    src.write_text("# Auth Spec\n\nBody.", encoding="utf-8")

    fake_result = IngestResult(
        status="ok",
        page_path="sources/auth-spec.md",
        slug="auth-spec",
        title="Auth Spec",
        page_type="source",
        source_path=str(src),
        cross_refs_updated=1,
        source_type="spec",
        archived_to="raw/_archive/specs/auth.md",
    )

    with patch(
        "graph_wiki_cli.cli.run_ingest_source",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        result = runner.invoke(app, ["ingest", str(src)])

    assert result.exit_code == 0
    assert "[ok] Archived source → raw/_archive/specs/auth.md" in result.stdout


def test_proposals_and_proposal_subcommands_registered() -> None:
    """`gw wiki proposals` (list) and `gw wiki proposal approve|reject` exist."""
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    wiki_group = root_command.commands["wiki"]
    assert "proposals" in wiki_group.commands
    proposal_group = wiki_group.commands["proposal"]
    assert set(proposal_group.commands) >= {"approve", "reject"}


def test_proposals_list_prints_open_records(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app

    records = [
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "a",
            "title": "A",
            "status": "proposed",
            "origins": [{"ref": "sources/s", "source": "ingest"}],
        },
    ]
    with patch("graph_wiki_cli.wiki_cli.main.run_list_proposals", return_value=records) as mock_fn:
        result = runner.invoke(app, ["wiki", "proposals", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "concept-a" in result.output
    assert "proposed" in result.output
    mock_fn.assert_called_once_with(workspace_path=tmp_path, status="proposed", kind=None)


def test_proposal_approve_flips_and_exits_zero(tmp_path: Path) -> None:
    from graph_wiki_cli.cli import app
    from graph_wiki_core.commands.proposals import ProposalDecision

    fake = ProposalDecision(proposal_id="adr-0007-md", status="approved")
    with patch("graph_wiki_cli.wiki_cli.main.run_set_proposal_status", return_value=fake) as mock_fn:
        result = runner.invoke(app, ["wiki", "proposal", "approve", "adr-0007-md", "--workspace", str(tmp_path)])

    assert result.exit_code == 0, result.output
    assert "approved" in result.output
    mock_fn.assert_called_once_with("adr-0007-md", "approved", workspace_path=tmp_path)


def test_proposal_reject_unknown_exits_nonzero() -> None:
    from graph_wiki_cli.cli import app

    with patch(
        "graph_wiki_cli.wiki_cli.main.run_set_proposal_status",
        side_effect=ValueError("no proposal note found for 'concept-nope'"),
    ):
        result = runner.invoke(app, ["wiki", "proposal", "reject", "concept-nope"])

    assert result.exit_code == 1
    assert "no proposal note found" in result.output


def test_wiki_archive_subcommand_registered() -> None:
    """`gw wiki archive` is registered under the wiki group."""
    import typer
    from graph_wiki_cli.cli import app

    root_command = typer.main.get_command(app)
    wiki_group = root_command.commands["wiki"]
    assert "archive" in wiki_group.commands


def test_wiki_archive_sweep_passes_none_slugs(tmp_path: Path) -> None:
    """Zero positional args → sweep mode (slugs=None)."""
    from unittest.mock import AsyncMock, patch

    from graph_wiki_core.commands.wiki_archive import WikiArchiveResult

    fake = WikiArchiveResult(dry_run=False, moved=[{"slug": "adrs/x", "src": "a", "dst": "b"}], skipped=[])
    with patch("graph_wiki_cli.wiki_cli.main.run_wiki_archive", new_callable=AsyncMock, return_value=fake) as mock_fn:
        result = runner.invoke(app, ["wiki", "archive", "--workspace", str(tmp_path)])

    assert result.exit_code == 0
    assert mock_fn.call_args.kwargs["slugs"] is None
    # Human output renders moved pages as "src -> dst" (mirrors `gw work archive`).
    assert "a -> b" in result.stdout


def test_wiki_archive_targeted_passes_slug_list(tmp_path: Path) -> None:
    """Positional args → targeted mode (slugs list)."""
    from unittest.mock import AsyncMock, patch

    from graph_wiki_core.commands.wiki_archive import WikiArchiveResult

    fake = WikiArchiveResult(
        dry_run=False, moved=[], skipped=[{"slug": "adrs/y", "reason": "status='accepted' is not terminal"}]
    )
    with patch("graph_wiki_cli.wiki_cli.main.run_wiki_archive", new_callable=AsyncMock, return_value=fake) as mock_fn:
        result = runner.invoke(app, ["wiki", "archive", "adrs/y", "--workspace", str(tmp_path)])

    assert result.exit_code == 0
    assert mock_fn.call_args.kwargs["slugs"] == ["adrs/y"]
    assert "not terminal" in result.stdout


def test_wiki_archive_dry_run_and_json(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock, patch

    from graph_wiki_core.commands.wiki_archive import WikiArchiveResult

    fake = WikiArchiveResult(dry_run=True, moved=[{"slug": "concepts/z", "src": "a", "dst": "b"}], skipped=[])
    with patch("graph_wiki_cli.wiki_cli.main.run_wiki_archive", new_callable=AsyncMock, return_value=fake) as mock_fn:
        result = runner.invoke(app, ["wiki", "archive", "--dry-run", "--json", "--workspace", str(tmp_path)])

    assert result.exit_code == 0
    assert mock_fn.call_args.kwargs["dry_run"] is True
    assert '"dry_run": true' in result.stdout
    assert "concepts/z" in result.stdout
