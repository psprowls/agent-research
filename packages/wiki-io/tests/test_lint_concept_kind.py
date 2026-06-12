"""concept_kind lint checks: invalid kind on concepts/ pages; legacy architecture/ dir."""

from __future__ import annotations

from wiki_io.lint.concept_kind import check


def _pages(**kind_by_slug):
    return {
        f"concepts/{slug}": {"fm": ({"kind": k} if k else {}), "path": f"concepts/{slug}.md"}
        for slug, k in kind_by_slug.items()
    }


def test_invalid_kind_warns(tmp_path):
    issues = check(_pages(weird="bogus"), tmp_path / "wiki")
    assert len(issues) == 1
    assert "concepts/weird" in issues[0] and "bogus" in issues[0]


def test_valid_and_missing_kinds_silent(tmp_path):
    pages = _pages(a="concept", b="pattern", c="architecture", d=None)
    assert check(pages, tmp_path / "wiki") == []


def test_non_concepts_pages_ignored(tmp_path):
    pages = {
        "entities/pkg_x": {"fm": {"kind": "package"}, "path": "entities/pkg_x.md"},
        "work/2026-06-11-foo": {"fm": {"kind": "feature"}, "path": "work/2026-06-11-foo.md"},
    }
    assert check(pages, tmp_path / "wiki") == []


def test_legacy_architecture_dir_with_content_warns(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "architecture").mkdir(parents=True)
    (wiki / "architecture" / "index.md").write_text("# stub\n", encoding="utf-8")
    (wiki / "architecture" / "overview.md").write_text("# page\n", encoding="utf-8")
    issues = check({}, wiki)
    assert len(issues) == 1
    assert "kind: architecture" in issues[0] and "overview" in issues[0]


def test_index_only_or_absent_architecture_dir_silent(tmp_path):
    wiki = tmp_path / "wiki"
    assert check({}, wiki) == []
    (wiki / "architecture").mkdir(parents=True)
    (wiki / "architecture" / "index.md").write_text("# stub\n", encoding="utf-8")
    assert check({}, wiki) == []
