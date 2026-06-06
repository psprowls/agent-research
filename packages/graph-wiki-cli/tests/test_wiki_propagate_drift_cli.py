"""gw wiki propagate-drift surface (M4 §3.7)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from graph_wiki_cli.wiki_cli.main import wiki_app
from graph_wiki_core.commands.propagate_drift import PropagateDriftResult
from typer.testing import CliRunner

runner = CliRunner()

_ConnStub = type("ConnStub", (), {"close": lambda self: None})


def _fake_result(**over):
    base = dict(
        pages_judged=2,
        entities_considered=3,
        notes_written=1,
        pages_stale=1,
        pages_skipped_settled=1,
        dry_run=False,
        proposals=[
            {"kind": "concept", "target_slug": "fanout", "origins": [{"ref": "entities/pkg_a", "source": "drift"}]}
        ],
    )
    base.update(over)
    return PropagateDriftResult(**base)


def test_propagate_drift_json_output():
    fake = AsyncMock(return_value=_fake_result())
    with (
        patch("graph_wiki_cli.wiki_cli.main.run_propagate_drift", new=fake),
        patch("graph_wiki_cli.wiki_cli.main.resolve_wiki_and_repo", return_value=(Path("/w/wiki"), Path("/w/repo"))),
        patch("graph_wiki_cli.wiki_cli.main.read_only_connect", return_value=_ConnStub()),
    ):
        result = runner.invoke(wiki_app, ["propagate-drift", "--json"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["pages_judged"] == 2
    assert payload["notes_written"] == 1
    assert payload["pages_skipped_settled"] == 1
    assert fake.await_count == 1


def test_propagate_drift_dry_run_flag_threads_through():
    fake = AsyncMock(return_value=_fake_result(dry_run=True, notes_written=0))
    with (
        patch("graph_wiki_cli.wiki_cli.main.run_propagate_drift", new=fake),
        patch("graph_wiki_cli.wiki_cli.main.resolve_wiki_and_repo", return_value=(Path("/w/wiki"), Path("/w/repo"))),
        patch("graph_wiki_cli.wiki_cli.main.read_only_connect", return_value=_ConnStub()),
    ):
        result = runner.invoke(wiki_app, ["propagate-drift", "--dry-run", "--only", "pkg_a"])
    assert result.exit_code == 0, result.stdout
    assert fake.await_args.kwargs["dry_run"] is True
    assert fake.await_args.kwargs["only"] == "pkg_a"
