from __future__ import annotations

from pathlib import Path

from wiki_io.archive import TERMINAL_STATUSES_BY_DIR, plan_wiki_archive


def _write(wiki: Path, d: str, stem: str, status: str | None) -> Path:
    dir_path = wiki / d
    dir_path.mkdir(parents=True, exist_ok=True)
    fm = f"---\ntitle: {stem}\n"
    if status is not None:
        fm += f"status: {status}\n"
    fm += "---\n\nbody\n"
    p = dir_path / f"{stem}.md"
    p.write_text(fm, encoding="utf-8")
    return p


def test_sweep_picks_only_terminal_pages(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki, "adrs", "0001-keep", status="accepted")
    _write(wiki, "adrs", "0002-gone", status="superseded")

    plan = plan_wiki_archive(wiki)

    actioned = {a.slug for a in plan.actions}
    assert "adrs/0002-gone" in actioned
    assert "adrs/0001-keep" not in actioned
    assert any(s["slug"] == "adrs/0001-keep" and "not terminal" in s["reason"] for s in plan.skipped)


def test_sweep_can_scope_to_one_dir(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki, "adrs", "0002-gone", status="deprecated")
    _write(wiki, "concepts", "old-thing", status="superseded")

    plan = plan_wiki_archive(wiki, dirs=["adrs"])

    assert {a.slug for a in plan.actions} == {"adrs/0002-gone"}


def test_proposals_terminal_set(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki, "proposals", "approved-one", status="approved")
    _write(wiki, "proposals", "rejected-one", status="rejected")
    _write(wiki, "proposals", "created-one", status="created")
    _write(wiki, "proposals", "open-one", status="proposed")

    plan = plan_wiki_archive(wiki, dirs=["proposals"])

    assert {a.slug for a in plan.actions} == {
        "proposals/approved-one",
        "proposals/rejected-one",
        "proposals/created-one",
    }
    assert any(s["slug"] == "proposals/open-one" for s in plan.skipped)


def test_concept_without_status_is_skipped_in_sweep(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki, "concepts", "active-no-status", status=None)

    plan = plan_wiki_archive(wiki, dirs=["concepts"])

    assert plan.actions == []
    assert any(s["slug"] == "concepts/active-no-status" for s in plan.skipped)


def test_targeted_resolves_path_qualified_slug(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki, "adrs", "0002-gone", status="superseded")

    plan = plan_wiki_archive(wiki, slugs=["adrs/0002-gone"])

    assert {a.slug for a in plan.actions} == {"adrs/0002-gone"}


def test_targeted_unknown_dir_missing_and_nonterminal_skipped(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki, "adrs", "0001-keep", status="accepted")

    plan = plan_wiki_archive(
        wiki,
        slugs=["bogus/x", "adrs/does-not-exist", "adrs/0001-keep"],
    )

    assert plan.actions == []
    reasons = {s["slug"]: s["reason"] for s in plan.skipped}
    assert "expected <dir>/<slug>" in reasons["bogus/x"]
    assert "not found in adrs/" in reasons["adrs/does-not-exist"]
    assert "not terminal" in reasons["adrs/0001-keep"]


def test_dst_preserves_filename_under_archive(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki, "adrs", "0002-gone", status="superseded")

    plan = plan_wiki_archive(wiki, dirs=["adrs"])

    action = plan.actions[0]
    assert action.dst.parent == wiki / "adrs" / "_archive"
    assert action.dst.name == action.src.name


def test_parse_error_page_is_skipped_not_fatal(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    dir_path = wiki / "adrs"
    dir_path.mkdir(parents=True)
    # `@handle` is an invalid YAML indicator char → frontmatter parse raises.
    (dir_path / "broken.md").write_text("---\nauthors: [@psprowls]\n---\nbody\n", encoding="utf-8")

    plan = plan_wiki_archive(wiki, dirs=["adrs"])

    assert plan.actions == []
    assert any(s["slug"] == "adrs/broken" and "parse error" in s["reason"] for s in plan.skipped)


def test_index_md_is_never_actioned(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki, "concepts", "index", status="superseded")  # filename "index.md"

    plan = plan_wiki_archive(wiki, dirs=["concepts"])

    assert plan.actions == []


def test_terminal_status_map_shape() -> None:
    assert TERMINAL_STATUSES_BY_DIR["adrs"] == frozenset({"superseded", "deprecated"})
    assert TERMINAL_STATUSES_BY_DIR["concepts"] == frozenset({"superseded", "deprecated"})
    assert TERMINAL_STATUSES_BY_DIR["proposals"] == frozenset({"approved", "rejected", "created"})
