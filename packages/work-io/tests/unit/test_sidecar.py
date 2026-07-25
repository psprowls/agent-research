from __future__ import annotations

from datetime import datetime
from pathlib import Path

from work_io.sidecar import SCHEMA_VERSION, build_sidecar, is_stale, load_sidecar, write_sidecar


def _make_work_item(
    work_dir: Path,
    stem: str,
    status: str = "open",
    kind: str = "bug",
    severity: str | None = None,
    blast_radius: str | None = None,
    opened: str = "2026-01-01",
    updated: str = "2026-01-01",
) -> None:
    lines = [
        "---",
        f"title: {stem}",
        f"status: {status}",
        f"kind: {kind}",
        f"opened: {opened}",
        f"updated: {updated}",
    ]
    if severity:
        lines.append(f"severity: {severity}")
    if blast_radius:
        lines.append(f"blast_radius: {blast_radius}")
    lines += ["---", "", "## Body", ""]
    (work_dir / f"{opened}-{stem}.md").write_text("\n".join(lines))


def test_build_sidecar_basic(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "fix-bug", status="open", kind="bug", opened="2026-06-01", updated="2026-06-01")  # noqa: E501
    _make_work_item(
        work_dir, "add-feature", status="in-progress", kind="feature", opened="2026-05-01", updated="2026-05-15"
    )

    sidecar = build_sidecar(work_dir, vault_commit="abc123")

    assert sidecar["schema_version"] == SCHEMA_VERSION
    assert sidecar["vault_commit"] == "abc123"
    assert "generated_at" in sidecar
    assert len(sidecar["items"]) == 2
    assert sidecar["counts"]["by_status"]["open"] == 1
    assert sidecar["counts"]["by_status"]["in-progress"] == 1
    assert sidecar["counts"]["by_kind"]["bug"] == 1


def test_build_sidecar_excludes_index_md(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "index.md").write_text(
        "---\ntitle: Work Index\ncategory: index\nupdated: 2026-06-01\n---\n# Work Index\n"
    )
    _make_work_item(work_dir, "real-item", opened="2026-06-01", updated="2026-06-01")

    sidecar = build_sidecar(work_dir, vault_commit=None)
    slugs = [i["slug"] for i in sidecar["items"]]
    assert "index" not in slugs
    assert len(sidecar["items"]) == 1


def test_is_stale_ignores_index_md(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "index.md").write_text(
        "---\ntitle: Work Index\ncategory: index\nupdated: 2026-12-31\n---\n# Work Index\n"
    )
    sidecar = {"generated_at": "2026-06-01T00:00:00+00:00", "items": []}

    assert is_stale(sidecar, work_dir) is False


def test_build_sidecar_excludes_archive(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    archived = work_dir / "_archive"
    archived.mkdir()
    _make_work_item(work_dir, "active", opened="2026-06-01", updated="2026-06-01")
    _make_work_item(archived, "old", opened="2026-01-01", updated="2026-01-01")

    sidecar = build_sidecar(work_dir, vault_commit=None)
    assert len(sidecar["items"]) == 1
    assert sidecar["items"][0]["slug"] == "2026-06-01-active"


def test_build_sidecar_items_sorted_by_opened_desc(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "older", opened="2026-01-01", updated="2026-01-01")
    _make_work_item(work_dir, "newer", opened="2026-06-01", updated="2026-06-01")

    sidecar = build_sidecar(work_dir, vault_commit=None)
    assert sidecar["items"][0]["slug"] == "2026-06-01-newer"
    assert sidecar["items"][1]["slug"] == "2026-01-01-older"


def test_write_and_load_sidecar(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    sidecar = {
        "schema_version": 1,
        "generated_at": "2026-06-01T00:00:00+00:00",
        "vault_commit": None,
        "counts": {},
        "items": [],
    }

    write_sidecar(wiki, sidecar)

    assert (wiki / "work-index.json").exists()
    loaded = load_sidecar(wiki)
    assert loaded == sidecar


def test_load_sidecar_returns_none_when_absent(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    assert load_sidecar(wiki) is None


def test_is_stale_true_when_item_updated_after_generated(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "fresh", opened="2026-06-01", updated="2026-06-05")
    sidecar = {"generated_at": "2026-06-03T00:00:00+00:00", "items": []}

    assert is_stale(sidecar, work_dir) is True


def test_build_sidecar_stamps_updated_at(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "fix-bug", opened="2026-06-01", updated="2026-06-01")

    sidecar = build_sidecar(work_dir, vault_commit=None)

    assert sidecar["schema_version"] == SCHEMA_VERSION  # additive, no bump
    item = sidecar["items"][0]
    assert "updated_at" in item
    # parseable as an ISO-8601 datetime (raises if malformed)
    datetime.fromisoformat(item["updated_at"])
    # date-only `updated` is left untouched
    assert item["updated"] == "2026-06-01"


def test_is_stale_false_when_all_items_older(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "old", opened="2026-01-01", updated="2026-01-01")
    sidecar = {"generated_at": "2026-06-01T00:00:00+00:00", "items": []}

    assert is_stale(sidecar, work_dir) is False


def test_sidecar_epic_children_rollup(tmp_path) -> None:
    from work_io.sidecar import SCHEMA_VERSION, build_sidecar

    work = tmp_path / "work"
    work.mkdir()
    (work / "2026-01-01-epic.md").write_text(
        "---\ntitle: E\nkind: epic\nstatus: accepted\nopened: 2026-01-01\nupdated: 2026-01-01\n---\nbody\n",
        encoding="utf-8",
    )
    (work / "2026-01-02-child-a.md").write_text(
        "---\ntitle: A\nkind: feature\nstatus: resolved\nparent: 2026-01-01-epic\n"
        "opened: 2026-01-02\nupdated: 2026-01-02\n---\nbody\n",
        encoding="utf-8",
    )
    (work / "2026-01-03-child-b.md").write_text(
        "---\ntitle: B\nkind: feature\nstatus: open\nparent: 2026-01-01-epic\n"
        "opened: 2026-01-03\nupdated: 2026-01-03\n---\nbody\n",
        encoding="utf-8",
    )

    sc = build_sidecar(work, vault_commit=None)
    assert sc["schema_version"] == SCHEMA_VERSION == 3

    by_slug = {it["slug"]: it for it in sc["items"]}
    epic = by_slug["2026-01-01-epic"]
    assert epic["children"]["total"] == 2
    assert epic["children"]["terminal"] == 1
    assert epic["children"]["blocking"] == 1
    assert epic["children"]["by_status"] == {"resolved": 1, "open": 1}

    child = by_slug["2026-01-02-child-a"]
    assert child["parent"] == "2026-01-01-epic"
    assert "children" not in child


def test_sidecar_schema_version_3(tmp_path) -> None:
    from work_io.sidecar import SCHEMA_VERSION, build_sidecar

    assert SCHEMA_VERSION == 3
    (tmp_path / "work").mkdir()
    assert build_sidecar(tmp_path / "work", None)["schema_version"] == 3


def test_sidecar_feature_with_children_gets_rollup(tmp_path) -> None:
    from work_io.sidecar import build_sidecar

    work = tmp_path / "work"
    work.mkdir()
    (work / "2026-01-01-feature.md").write_text(
        "---\ntitle: F\nkind: feature\nstatus: accepted\nopened: 2026-01-01\nupdated: 2026-01-01\n---\nbody\n",
        encoding="utf-8",
    )
    (work / "2026-01-02-child.md").write_text(
        "---\ntitle: C\nkind: bug\nstatus: open\nparent: 2026-01-01-feature\n"
        "opened: 2026-01-02\nupdated: 2026-01-02\n---\nbody\n",
        encoding="utf-8",
    )

    sc = build_sidecar(work, vault_commit=None)
    feature = next(i for i in sc["items"] if i["kind"] == "feature")
    assert feature["children"] == {"total": 1, "by_status": {"open": 1}, "terminal": 0, "blocking": 1}


def test_sidecar_childless_feature_has_no_children_key(tmp_path) -> None:
    from work_io.sidecar import build_sidecar

    work = tmp_path / "work"
    work.mkdir()
    (work / "2026-01-01-feature.md").write_text(
        "---\ntitle: F\nkind: feature\nstatus: open\nopened: 2026-01-01\nupdated: 2026-01-01\n---\nbody\n",
        encoding="utf-8",
    )

    sc = build_sidecar(work, vault_commit=None)
    feature = next(i for i in sc["items"] if i["kind"] == "feature")
    assert "children" not in feature


def test_sidecar_childless_epic_keeps_zero_rollup(tmp_path) -> None:
    from work_io.sidecar import build_sidecar

    work = tmp_path / "work"
    work.mkdir()
    (work / "2026-01-01-epic.md").write_text(
        "---\ntitle: E\nkind: epic\nstatus: accepted\nopened: 2026-01-01\nupdated: 2026-01-01\n---\nbody\n",
        encoding="utf-8",
    )

    sc = build_sidecar(work, vault_commit=None)
    epic = next(i for i in sc["items"] if i["kind"] == "epic")
    assert epic["children"]["total"] == 0
