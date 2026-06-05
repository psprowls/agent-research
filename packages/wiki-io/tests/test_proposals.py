from __future__ import annotations

"""Unit tests for wiki_io.proposals — the curated-page proposal ledger.
Pure Python, no Bedrock, no graph."""

from pathlib import Path


def _origin(ref="sources/spec", source="ingest", rationale="because.") -> dict:
    return {"ref": ref, "source": source, "rationale": rationale}


def test_proposal_path_is_kind_dash_slug(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path

    p = proposal_path(tmp_path / "wiki", "adr", "0007-markdown-canonical")
    assert p == tmp_path / "wiki" / "proposals" / "adr-0007-markdown-canonical.md"


def test_render_body_lists_one_block_per_origin() -> None:
    from wiki_io.proposals import render_proposal_body

    record = {
        "kind": "adr",
        "mode": "update_existing",
        "target_slug": "0007-md",
        "title": "Markdown stays canonical",
        "status": "proposed",
        "origins": [
            _origin(ref="sources/roadmap", rationale="Revisits the decision."),
            {"ref": "entities/pkg_wiki_io", "source": "drift", "rationale": "Async fan-out now."},
        ],
    }
    body = render_proposal_body(record)
    # Comment header references the approve command id.
    assert "approve via `gw wiki proposal approve adr-0007-md`" in body
    # One block per origin: "**<source> · [[<ref>]]**" then the rationale line.
    assert "**ingest · [[sources/roadmap]]**" in body
    assert "Revisits the decision." in body
    assert "**drift · [[entities/pkg_wiki_io]]**" in body
    assert "Async fan-out now." in body


def test_read_proposal_round_trips_a_written_note(tmp_path: Path) -> None:
    from wiki_io.proposals import read_proposal

    note = tmp_path / "concept-section-ownership.md"
    note.write_text(
        "---\n"
        "kind: concept\n"
        "mode: create_new\n"
        "target_slug: section-ownership\n"
        "title: Section Ownership\n"
        "status: proposed\n"
        "origins:\n"
        "- ref: sources/spec\n"
        "  source: ingest\n"
        "  rationale: A reusable split.\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )
    rec = read_proposal(note)
    assert rec["kind"] == "concept"
    assert rec["mode"] == "create_new"
    assert rec["target_slug"] == "section-ownership"
    assert rec["title"] == "Section Ownership"
    assert rec["status"] == "proposed"
    assert rec["origins"] == [
        {"ref": "sources/spec", "source": "ingest", "rationale": "A reusable split."}
    ]


def test_split_proposal_id_parses_kind_prefix() -> None:
    from wiki_io.proposals import split_proposal_id

    assert split_proposal_id("adr-0007-markdown-canonical") == ("adr", "0007-markdown-canonical")
    assert split_proposal_id("concept-section-ownership") == ("concept", "section-ownership")
    assert split_proposal_id("architecture-layers") == ("architecture", "layers")


def test_split_proposal_id_rejects_unknown_kind() -> None:
    import pytest

    from wiki_io.proposals import split_proposal_id

    with pytest.raises(ValueError):
        split_proposal_id("package-foo")
