"""Tests for wiki_io.lint_wiki.mechanical_scan — the canonical mechanical scanner."""

from __future__ import annotations


def test_mechanical_scan_returns_pages_and_inline_fields(tmp_path):
    from wiki_io.lint_wiki import mechanical_scan

    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "proposals").mkdir(parents=True)
    (wiki / "concepts" / "a.md").write_text(
        "---\ntitle: A\ncategory: concept\nsummary: s\ntokens: 1\n---\n\nbody\n", encoding="utf-8"
    )
    # Proposal with no inbound links must NOT be flagged as an orphan.
    (wiki / "proposals" / "p.md").write_text(
        "---\nkind: adr\nmode: create_new\ntarget_slug: t\nstatus: proposed\ntokens: 1\n---\nbody\n",
        encoding="utf-8",
    )
    # Schema file must be ignored entirely.
    (wiki / "CLAUDE.md").write_text("schema\n", encoding="utf-8")

    r = mechanical_scan(wiki, stale_days=90, log_gap_days=14)

    assert set(r) >= {
        "pages",
        "orphans",
        "broken_links",
        "stale",
        "missing_frontmatter",
        "missing_tokens",
        "source_path_drift",
        "duplicate_titles",
        "log_gap",
        "total_pages",
    }
    assert "proposals/p" not in r["orphans"]
    assert "CLAUDE" not in {k.split("/")[-1] for k in r["pages"]}


def test_mechanical_scan_resolves_overview_shorthand(tmp_path):
    from wiki_io.lint_wiki import mechanical_scan

    wiki = tmp_path / "wiki"
    (wiki / "entities" / "alpha").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "entities" / "alpha" / "overview.md").write_text(
        "---\nuri: pkg:o/r/alpha\nkind: package\ntokens: 1\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "concepts" / "ref.md").write_text(
        "---\ntitle: Ref\ncategory: concept\nsummary: s\ntokens: 1\n---\n\nSee [[entities/alpha]].\n",
        encoding="utf-8",
    )
    r = mechanical_scan(wiki, stale_days=90, log_gap_days=14)
    # [[entities/alpha]] resolves to entities/alpha/overview — NOT a broken link.
    assert all("entities/alpha" != t for _s, t in r["broken_links"])


def test_mechanical_scan_returns_index_pages(tmp_path):
    """mechanical_scan gains an index_pages dict keyed like pages, holding every
    index.md's text/fm — but index.md entries stay absent from pages itself
    (unchanged orphan/stale/frontmatter behavior)."""
    from wiki_io.lint_wiki import mechanical_scan

    wiki = tmp_path / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "index.md").write_text(
        "---\ntitle: Index\ncategory: meta\nsummary: root index\n---\n\nWelcome.\n",
        encoding="utf-8",
    )

    r = mechanical_scan(wiki, stale_days=90, log_gap_days=14)

    assert "index_pages" in r
    assert "index" in r["index_pages"]
    assert r["index_pages"]["index"]["path"] == "index.md"
    assert r["index_pages"]["index"]["text"].startswith("---\ntitle: Index")
    assert r["index_pages"]["index"]["fm"]["title"] == "Index"
    # index.md must still be absent from pages (orphan/stale/frontmatter checks unchanged).
    assert "index" not in r["pages"]


def test_stale_check_accepts_date_typed_updated(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    # Unquoted date -> python-frontmatter yields datetime.date
    (wiki / "concepts" / "old-page.md").write_text(
        "---\ntitle: Old Page\ncategory: concept\nsummary: s\nupdated: 2020-01-01\ntokens: 1\n---\n\nbody\n",
        encoding="utf-8",
    )
    from wiki_io.lint_wiki import mechanical_scan

    result = mechanical_scan(wiki, stale_days=45, log_gap_days=7)
    assert ("concepts/old-page", "2020-01-01") in result["stale"]


def test_unparseable_frontmatter_is_reported_not_fatal(tmp_path):
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "broken.md").write_text("---\ntitle: [unclosed\n---\n\nbody\n", encoding="utf-8")
    from wiki_io.lint_wiki import mechanical_scan

    result = mechanical_scan(wiki, stale_days=45, log_gap_days=7)
    keys = [k for k, _err in result["unparseable_frontmatter"]]
    assert "concepts/broken" in keys
