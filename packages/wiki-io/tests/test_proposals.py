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


def _proposal(kind="concept", mode="create_new", target_slug="a", title="T", origin=None):
    return {
        "kind": kind,
        "mode": mode,
        "target_slug": target_slug,
        "title": title,
        "origin": origin or _origin(),
    }


def test_upsert_creates_note_on_empty_dir(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, upsert_proposal

    wiki = tmp_path / "wiki"  # NOTE: proposals/ does not exist yet
    rec = upsert_proposal(wiki, _proposal(kind="adr", target_slug="0007-md", title="MD"))

    path = proposal_path(wiki, "adr", "0007-md")
    assert path.exists()
    assert rec["status"] == "proposed"
    assert len(rec["origins"]) == 1
    on_disk = read_proposal(path)
    assert on_disk["status"] == "proposed"
    assert on_disk["origins"][0]["ref"] == "sources/spec"
    # Body renders the origin.
    assert "**ingest · [[sources/spec]]**" in path.read_text(encoding="utf-8")


def test_upsert_leaves_human_decided_untouched(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", title="Orig"))
    path = proposal_path(wiki, "concept", "a")
    # Human approves by editing status on disk.
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("status: proposed", "status: approved"), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    rec = upsert_proposal(
        wiki, _proposal(target_slug="a", title="NEW", origin=_origin(rationale="new evidence"))
    )

    assert rec["status"] == "approved"
    assert rec["title"] == "Orig"  # not overwritten
    assert path.read_text(encoding="utf-8") == before  # byte-identical: decision never stomped


def test_upsert_rejected_is_preserved_not_reproposed(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a"))
    path = proposal_path(wiki, "concept", "a")
    path.write_text(
        path.read_text(encoding="utf-8").replace("status: proposed", "status: rejected"),
        encoding="utf-8",
    )
    before = path.read_text(encoding="utf-8")

    rec = upsert_proposal(wiki, _proposal(target_slug="a"))
    assert rec["status"] == "rejected"
    assert path.read_text(encoding="utf-8") == before


def test_upsert_refresh_accumulates_origins_by_ref(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(ref="sources/one")))
    # A NEW ref appends a second origin.
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(ref="sources/two")))
    rec = read_proposal(proposal_path(wiki, "concept", "a"))
    assert [o["ref"] for o in rec["origins"]] == ["sources/one", "sources/two"]

    # The SAME ref re-firing updates in place (no duplicate); status stays proposed.
    upsert_proposal(
        wiki, _proposal(target_slug="a", origin=_origin(ref="sources/two", rationale="changed"))
    )
    rec = read_proposal(proposal_path(wiki, "concept", "a"))
    assert [o["ref"] for o in rec["origins"]] == ["sources/one", "sources/two"]
    assert rec["origins"][1]["rationale"] == "changed"
    assert rec["status"] == "proposed"


def test_upsert_identity_collapse_two_origins_one_note(tmp_path: Path) -> None:
    from wiki_io.proposals import list_proposals, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(ref="sources/one")))
    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "a",
            "title": "T",
            "origin": {"ref": "entities/pkg_x", "source": "drift", "rationale": "r"},
        },
    )
    records = list_proposals(wiki)
    assert len(records) == 1
    assert len(records[0]["origins"]) == 2


def test_upsert_byte_stable_no_op(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a"))
    path = proposal_path(wiki, "concept", "a")
    first = path.read_bytes()
    upsert_proposal(wiki, _proposal(target_slug="a"))  # identical evidence
    assert path.read_bytes() == first


def test_set_proposal_status_flips_and_preserves_body(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, set_proposal_status, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(rationale="keep me")))
    path = proposal_path(wiki, "concept", "a")

    ok = set_proposal_status(wiki, "concept", "a", "approved")
    assert ok is True
    rec = read_proposal(path)
    assert rec["status"] == "approved"
    # The rendered evidence body survives the status flip.
    assert "keep me" in path.read_text(encoding="utf-8")
    # A subsequent upsert (re-ingest) does not revert the decision.
    upsert_proposal(wiki, _proposal(target_slug="a", title="NEW"))
    assert read_proposal(path)["status"] == "approved"


def test_set_proposal_status_returns_false_when_missing(tmp_path: Path) -> None:
    from wiki_io.proposals import set_proposal_status

    assert set_proposal_status(tmp_path / "wiki", "concept", "nope", "approved") is False


def test_set_proposal_status_is_byte_stable(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, set_proposal_status, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a"))
    path = proposal_path(wiki, "concept", "a")
    set_proposal_status(wiki, "concept", "a", "approved")
    first = path.read_bytes()
    set_proposal_status(wiki, "concept", "a", "approved")
    assert path.read_bytes() == first
