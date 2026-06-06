from __future__ import annotations

from pathlib import Path

import pytest


def _seed(wiki: Path):
    from wiki_io.proposals import upsert_proposal

    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "a",
            "title": "A",
            "origin": {"ref": "sources/spec", "source": "ingest", "rationale": "r"},
        },
    )
    upsert_proposal(
        wiki,
        {
            "kind": "adr",
            "mode": "update_existing",
            "target_slug": "0007-md",
            "title": "MD",
            "origin": {"ref": "sources/spec", "source": "ingest", "rationale": "r2"},
        },
    )


def test_run_list_proposals_defaults_to_proposed(tmp_path: Path) -> None:
    from unittest.mock import patch

    from graph_wiki_core.commands.proposals import run_list_proposals

    wiki = tmp_path / "wiki"
    _seed(wiki)
    with patch("graph_wiki_core.commands.proposals.resolve_wiki_and_repo", return_value=(wiki, None)):
        records = run_list_proposals(workspace_path=tmp_path)
    assert {r["target_slug"] for r in records} == {"a", "0007-md"}
    # kind filter narrows.
    with patch("graph_wiki_core.commands.proposals.resolve_wiki_and_repo", return_value=(wiki, None)):
        adrs = run_list_proposals(workspace_path=tmp_path, kind="adr")
    assert [r["target_slug"] for r in adrs] == ["0007-md"]


def test_run_set_proposal_status_flips_and_reports(tmp_path: Path) -> None:
    from unittest.mock import patch

    from graph_wiki_core.commands.proposals import run_set_proposal_status
    from wiki_io.proposals import proposal_path, read_proposal

    wiki = tmp_path / "wiki"
    _seed(wiki)
    with patch("graph_wiki_core.commands.proposals.resolve_wiki_and_repo", return_value=(wiki, None)):
        decision = run_set_proposal_status("adr-0007-md", "approved", workspace_path=tmp_path)
    assert decision.proposal_id == "adr-0007-md"
    assert decision.status == "approved"
    assert read_proposal(proposal_path(wiki, "adr", "0007-md"))["status"] == "approved"


def test_run_set_proposal_status_unknown_raises(tmp_path: Path) -> None:
    from unittest.mock import patch

    from graph_wiki_core.commands.proposals import run_set_proposal_status

    wiki = tmp_path / "wiki"
    _seed(wiki)
    with patch("graph_wiki_core.commands.proposals.resolve_wiki_and_repo", return_value=(wiki, None)):
        with pytest.raises(ValueError):
            run_set_proposal_status("concept-nope", "approved", workspace_path=tmp_path)
