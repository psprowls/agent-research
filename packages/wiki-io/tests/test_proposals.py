"""Unit tests for wiki_io.proposals — the curated-page proposal ledger.
Pure Python, no Bedrock, no graph."""

from __future__ import annotations

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


def test_rich_proposal_body_renders_review_sections() -> None:
    from wiki_io.proposals import render_proposal_body

    record = {
        "kind": "concept",
        "mode": "create_new",
        "target_slug": "section-ownership",
        "title": "Section ownership",
        "status": "proposed",
        "rank": 1,
        "confidence": "high",
        "origins": [
            {
                "ref": "sources/spec",
                "source": "ingest",
                "rationale": "The source defines ownership boundaries.",
                "evidence": ["Scanner owns narrative sections.", "Humans own notes."],
                "existing_pages_considered": ["concepts/human-owned-sections"],
                "reasoning_summary": "This is reusable across scanner and ingest pages.",
                "potential_conflicts": ["May overlap with existing page ownership docs."],
                "implementation_notes": ["Create a concept page and link scanner docs."],
            }
        ],
    }

    body = render_proposal_body(record)

    assert "## Suggested Action" in body
    assert "Create new concept page `concepts/section-ownership.md`." in body
    assert "## Evidence From Source" in body
    assert "- Scanner owns narrative sections." in body
    assert "## Existing Pages Considered" in body
    assert "- [[concepts/human-owned-sections]]" in body
    assert "## Reasoning Summary" in body
    assert "This is reusable across scanner and ingest pages." in body
    assert "## Potential Conflicts" in body
    assert "## Implementation Notes" in body
    assert "## Origins" in body


def test_proposal_body_origins_wikilinks_only_page_refs() -> None:
    from wiki_io.proposals import render_proposal_body

    record = {
        "kind": "concept",
        "mode": "create_new",
        "target_slug": "section-ownership",
        "title": "Section ownership",
        "status": "proposed",
        "origins": [
            {"ref": "sources/spec", "source": "ingest", "rationale": "Page ref."},
            {"ref": "external-ticket", "source": "ingest", "rationale": "Plain ref."},
        ],
    }

    body = render_proposal_body(record)

    assert "**ingest · [[sources/spec]]**" in body
    assert "**ingest · external-ticket**" in body
    assert "[[external-ticket]]" not in body


def test_proposal_body_origins_has_fallback_when_empty() -> None:
    from wiki_io.proposals import render_proposal_body

    record = {
        "kind": "concept",
        "mode": "create_new",
        "target_slug": "section-ownership",
        "title": "Section ownership",
        "status": "proposed",
        "origins": [],
    }

    body = render_proposal_body(record)

    assert "## Origins" in body
    assert "No origins were captured." in body


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
    assert rec["origins"] == [{"ref": "sources/spec", "source": "ingest", "rationale": "A reusable split."}]


def test_split_proposal_id_parses_kind_prefix() -> None:
    import pytest
    from wiki_io.proposals import split_proposal_id

    assert split_proposal_id("adr-0007-markdown-canonical") == ("adr", "0007-markdown-canonical")
    assert split_proposal_id("concept-section-ownership") == ("concept", "section-ownership")
    with pytest.raises(ValueError):
        split_proposal_id("architecture-layers")


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


def test_upsert_persists_rank_confidence_and_rich_origin(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "concept_kind": "architecture",
            "mode": "update_existing",
            "target_slug": "runtime-flow",
            "title": "Runtime flow",
            "rank": 2,
            "confidence": "medium",
            "origin": {
                "ref": "sources/runtime",
                "source": "ingest",
                "rationale": "The source changes the runtime-flow thesis.",
                "evidence": ["Pipeline adds a reasoner stage."],
                "existing_pages_considered": ["concepts/runtime-flow"],
                "reasoning_summary": "Update the existing concept page.",
                "potential_conflicts": [],
                "implementation_notes": ["Append to How this synthesis has changed."],
            },
        },
    )

    rec = read_proposal(proposal_path(wiki, "concept", "runtime-flow"))
    assert rec["rank"] == 2
    assert rec["confidence"] == "medium"
    assert rec["origins"][0]["evidence"] == ["Pipeline adds a reasoner stage."]
    assert rec["concept_kind"] == "architecture"


def test_upsert_leaves_human_decided_untouched(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(wiki, _proposal(target_slug="a", title="Orig"))
    path = proposal_path(wiki, "concept", "a")
    # Human approves by editing status on disk.
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("status: proposed", "status: approved"), encoding="utf-8")
    before = path.read_text(encoding="utf-8")

    rec = upsert_proposal(wiki, _proposal(target_slug="a", title="NEW", origin=_origin(rationale="new evidence")))

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
    upsert_proposal(wiki, _proposal(target_slug="a", origin=_origin(ref="sources/two", rationale="changed")))
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


# ---------------------------------------------------------------------------
# D8 — non-change guard tests (index + backlink exclusion)
# ---------------------------------------------------------------------------


def test_proposals_is_not_a_curated_index_lane() -> None:
    """spec §3.8: proposals/ is a transient queue, not an index lane."""
    from wiki_io.index_generator import CURATED_LANES
    from wiki_io.init_vault import SECTION_INDEX_STUBS
    from wiki_io.update_index import CATEGORY_INDEX_FILES

    assert "proposals" not in {lane[0] for lane in CURATED_LANES}
    assert "proposals" not in {lane[1] for lane in CURATED_LANES}
    assert "proposals" not in SECTION_INDEX_STUBS
    assert "proposals" not in {Path(v).parts[0] for v in CATEGORY_INDEX_FILES.values()}


def test_proposals_is_not_a_backlink_source() -> None:
    """spec §3.8: proposals/ is NOT in _PRESERVED_WIKI_DIRS (no backlinks)."""
    from wiki_io.backlink_index import _PRESERVED_WIKI_DIRS

    assert "proposals" not in _PRESERVED_WIKI_DIRS


def test_proposal_note_generates_no_entity_backlink(tmp_path: Path) -> None:
    """A proposals/ note linking [[entities/...]] must NOT backlink the entity."""
    from wiki_io.backlink_index import regenerate_referenced_in_wiki
    from wiki_io.proposals import upsert_proposal

    wiki = tmp_path / "wiki"
    entities = wiki / "entities"
    entities.mkdir(parents=True)
    (entities / "pkg_x.md").write_text(
        "---\nuri: pkg:o/r/pkg_x\nkind: package\n---\n\n# pkg_x\n\n"
        "## Narrative\nProse.\n\n## Referenced in wiki\n_(scanner will populate)_\n",
        encoding="utf-8",
    )
    # The proposal body carries an entities/ ref (M4-shaped origin).
    upsert_proposal(
        wiki,
        {
            "kind": "adr",
            "mode": "update_existing",
            "target_slug": "0007-md",
            "title": "MD",
            "origin": {"ref": "entities/pkg_x", "source": "drift", "rationale": "r"},
        },
    )
    regenerate_referenced_in_wiki(wiki)
    text = (entities / "pkg_x.md").read_text(encoding="utf-8")
    assert "_No wiki pages reference this entity yet._" in text
    assert "[[adr-0007-md]]" not in text


def test_update_index_ignores_proposals(tmp_path: Path) -> None:
    """update_index writes no proposals sub-index and omits proposal slugs."""
    from wiki_io.proposals import upsert_proposal
    from wiki_io.update_index import update_index

    wiki = tmp_path / "wiki"
    (wiki / "sources").mkdir(parents=True)
    upsert_proposal(
        tmp_path / "wiki",
        {  # writes wiki/proposals/concept-xyz.md
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "xyz",
            "title": "XYZ",
            "origin": _origin(),
        },
    )
    update_index(wiki)
    assert not (wiki / "proposals" / "index.md").exists()
    # No category sub-index mentions the proposal slug.
    for sub in wiki.rglob("index.md"):
        assert "concept-xyz" not in sub.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Task 8 — concept_kind plumbing
# ---------------------------------------------------------------------------


def test_concept_kind_roundtrips_and_survives_merge(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, upsert_proposal

    wiki = tmp_path / "wiki"
    proposal = {
        "kind": "concept",
        "concept_kind": "architecture",
        "target_slug": "runtime-flow",
        "title": "Runtime Flow",
        "origin": {"ref": "sources/spec-a", "source": "ingest", "rationale": "r"},
    }
    upsert_proposal(wiki, proposal)
    rec = read_proposal(proposal_path(wiki, "concept", "runtime-flow"))
    assert rec["concept_kind"] == "architecture"
    # merge: same note, second origin — concept_kind survives
    proposal2 = dict(proposal, origin={"ref": "sources/spec-b", "source": "ingest", "rationale": "r2"})
    upsert_proposal(wiki, proposal2)
    rec = read_proposal(proposal_path(wiki, "concept", "runtime-flow"))
    assert rec["concept_kind"] == "architecture"
    assert len(rec["origins"]) == 2


def test_suggested_action_names_kind_template(tmp_path: Path) -> None:
    from wiki_io.proposals import _suggested_action

    rec = {"kind": "concept", "target_slug": "runtime-flow", "mode": "create_new", "concept_kind": "architecture"}
    action = _suggested_action(rec)
    assert "concepts/runtime-flow.md" in action
    assert "kind: architecture" in action
    assert "concept-architecture.md" in action


def test_plain_concept_action_has_no_kind_suffix() -> None:
    from wiki_io.proposals import _suggested_action

    rec = {"kind": "concept", "target_slug": "auth", "mode": "create_new"}
    assert "kind:" not in _suggested_action(rec)


def test_adr_record_never_carries_concept_kind(tmp_path: Path) -> None:
    from wiki_io.proposals import proposal_path, read_proposal, upsert_proposal

    wiki = tmp_path / "wiki"
    upsert_proposal(
        wiki,
        {
            "kind": "adr",
            "target_slug": "0009-foo",
            "title": "Foo",
            "origin": {"ref": "sources/spec", "source": "ingest", "rationale": "r"},
        },
    )
    rec = read_proposal(proposal_path(wiki, "adr", "0009-foo"))
    assert "concept_kind" not in rec
