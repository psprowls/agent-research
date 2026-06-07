from __future__ import annotations

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


def test_build_sidecar_excludes_archived(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    archived = work_dir / "archived"
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


def test_is_stale_false_when_all_items_older(tmp_path: Path) -> None:
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    _make_work_item(work_dir, "old", opened="2026-01-01", updated="2026-01-01")
    sidecar = {"generated_at": "2026-06-01T00:00:00+00:00", "items": []}

    assert is_stale(sidecar, work_dir) is False
