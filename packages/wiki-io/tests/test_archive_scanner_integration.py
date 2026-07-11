# packages/wiki-io/tests/test_archive_scanner_integration.py
from __future__ import annotations

from pathlib import Path

from wiki_io.backlink_index import build_entity_backlink_map
from wiki_io.lint_wiki import mechanical_scan as scan


def _page(wiki: Path, rel: str, body: str = "") -> Path:
    p = wiki / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {Path(rel).stem}\n---\n\n{body}\n", encoding="utf-8")
    return p


def test_archived_adr_is_valid_target_not_orphan(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    # An active ADR links to the archived one by its archived path.
    _page(wiki, "adrs/0009-live.md", body="See [[adrs/_archive/0003-old]].")
    _page(wiki, "adrs/_archive/0003-old.md")

    # mechanical_scan() returns a dict with orphans / broken_links / stale keys.
    report = scan(wiki, stale_days=90, log_gap_days=14)

    # Archived page is a valid target → the link is not broken.
    assert not any("0003-old" in str(tgt) for _src, tgt in report["broken_links"])
    # Archived page is excluded from orphan/stale enumeration.
    assert "adrs/_archive/0003-old" not in report["orphans"]
    assert all("_archive" not in str(p) for p, _ in report["stale"])


def test_backlink_from_archived_page_excluded(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _page(wiki, "concepts/active.md", body="Uses [[entities/pkg_foo]].")
    _page(wiki, "concepts/_archive/retired.md", body="Used [[entities/pkg_foo]].")

    backmap = build_entity_backlink_map(wiki)

    # Compare wiki-relative paths: pytest's tmp_path dir name ("..._from_archived_...")
    # contains the substring "_archive", so matching against absolute paths is unsound.
    sources = {pp.relative_to(wiki).as_posix() for (_cat, _slug, pp) in backmap.get("pkg_foo", [])}
    assert any("concepts/active.md" in s for s in sources)
    assert not any("_archive" in s for s in sources)
