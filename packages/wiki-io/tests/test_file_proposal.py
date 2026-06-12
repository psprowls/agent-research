"""file_proposal: args -> upsert_proposal, origin merge, CLI behavior."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from wiki_io.file_proposal import file_proposal, main
from wiki_io.proposals import proposal_path, read_proposal, set_proposal_status


def _mk_workspace(tmp_path: Path) -> tuple[Path, Path]:
    ws = tmp_path
    wiki = ws / "wiki"
    wiki.mkdir()
    return ws, wiki


def test_file_proposal_creates_proposed_note_with_ingest_origin(tmp_path: Path) -> None:
    _, wiki = _mk_workspace(tmp_path)
    record = file_proposal(
        wiki,
        kind="concept",
        target_slug="retry-budget",
        title="Retry Budget",
        ref="sources/2026-06-foo",
        rationale="Spec defines a cross-cutting retry budget.",
        evidence=["claim one", "claim two"],
    )
    path = proposal_path(wiki, "concept", "retry-budget")
    assert path.exists()
    assert record["status"] == "proposed"
    assert record["mode"] == "create_new"
    assert len(record["origins"]) == 1
    origin = record["origins"][0]
    assert origin["ref"] == "sources/2026-06-foo"
    assert origin["source"] == "ingest"
    assert origin["evidence"] == ["claim one", "claim two"]


def test_file_proposal_normalizes_target_slug(tmp_path: Path) -> None:
    _, wiki = _mk_workspace(tmp_path)
    record = file_proposal(
        wiki,
        kind="concept",
        target_slug="Retry Budget!",
        title="Retry Budget",
        ref="sources/2026-06-foo",
        rationale="r",
    )
    assert record["target_slug"] == "retry-budget"
    assert proposal_path(wiki, "concept", "retry-budget").exists()


def test_refiling_different_ref_merges_origins(tmp_path: Path) -> None:
    _, wiki = _mk_workspace(tmp_path)
    common = dict(kind="adr", target_slug="use-x", title="Use X", rationale="r")
    file_proposal(wiki, ref="sources/2026-06-a", **common)
    record = file_proposal(wiki, ref="sources/2026-06-b", **common)
    assert len(record["origins"]) == 2
    assert {o["ref"] for o in record["origins"]} == {"sources/2026-06-a", "sources/2026-06-b"}


def test_refiling_same_ref_updates_in_place(tmp_path: Path) -> None:
    _, wiki = _mk_workspace(tmp_path)
    common = dict(kind="concept", target_slug="t", title="T", ref="sources/2026-06-a")
    file_proposal(wiki, rationale="old", **common)
    record = file_proposal(wiki, rationale="new", **common)
    assert len(record["origins"]) == 1
    assert record["origins"][0]["rationale"] == "new"


def test_human_decided_note_is_never_stomped(tmp_path: Path) -> None:
    _, wiki = _mk_workspace(tmp_path)
    common = dict(kind="concept", target_slug="t", title="T", rationale="r")
    file_proposal(wiki, ref="sources/2026-06-a", **common)
    assert set_proposal_status(wiki, "concept", "t", "rejected")
    before = proposal_path(wiki, "concept", "t").read_text(encoding="utf-8")
    record = file_proposal(wiki, ref="sources/2026-06-b", **common)
    assert record["status"] == "rejected"
    assert len(record["origins"]) == 1
    assert proposal_path(wiki, "concept", "t").read_text(encoding="utf-8") == before


def test_invalid_kind_raises(tmp_path: Path) -> None:
    _, wiki = _mk_workspace(tmp_path)
    with pytest.raises(ValueError, match="invalid kind"):
        file_proposal(wiki, kind="entity", target_slug="t", title="T", ref="r", rationale="x")


def test_main_writes_note_and_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ws, wiki = _mk_workspace(tmp_path)
    main(
        [
            "--kind",
            "concept",
            "--target-slug",
            "retry-budget",
            "--title",
            "Retry Budget",
            "--ref",
            "sources/2026-06-foo",
            "--rationale",
            "Spec defines it.",
            "--evidence",
            "claim one",
            "--evidence",
            "claim two",
            "--workspace",
            str(ws),
            "--json",
        ]
    )
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "proposed"
    assert out["origins"] == 1
    assert Path(out["path"]).exists()
    rec = read_proposal(Path(out["path"]))
    assert rec["origins"][0]["evidence"] == ["claim one", "claim two"]


def test_main_rejects_nonexistent_workspace_with_exit_2(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--kind",
                "concept",
                "--target-slug",
                "t",
                "--title",
                "T",
                "--ref",
                "r",
                "--rationale",
                "x",
                "--workspace",
                str(missing),
            ]
        )
    assert excinfo.value.code == 2
    assert not missing.exists()


def test_main_rejects_unknown_kind_with_exit_2(tmp_path: Path) -> None:
    ws, _ = _mk_workspace(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        main(
            [
                "--kind",
                "entity",
                "--target-slug",
                "t",
                "--title",
                "T",
                "--ref",
                "r",
                "--rationale",
                "x",
                "--workspace",
                str(ws),
            ]
        )
    assert excinfo.value.code == 2
