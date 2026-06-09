"""Guidance index generation (spec: docs/superpowers/specs/2026-06-09-guidance-index-pages-design.md)."""

from __future__ import annotations

from pathlib import Path

from wiki_io.update_index import (
    scan_guidance_topics,
    topic_label,
)


def _write_guidance_page(path: Path, *, title: str, summary: str = "", impact: str = "") -> None:
    """Write a guidance page with the flat frontmatter keys the index reads."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"title: {title}", "category: guidance"]
    if summary:
        lines.append(f"summary: {summary}")
    if impact:
        lines.append(f"impact: {impact}")
    lines += ["---", "", "Body.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


class TestTopicLabel:
    def test_hyphens_to_title_case(self):
        assert topic_label("deep-agents") == "Deep Agents"

    def test_underscores_to_title_case(self):
        assert topic_label("react_native") == "React Native"


class TestScanGuidanceTopics:
    def test_absent_guidance_dir_returns_empty(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        assert scan_guidance_topics(wiki) == {}

    def test_empty_guidance_dir_returns_empty(self, tmp_path):
        wiki = tmp_path / "wiki"
        (wiki / "guidance").mkdir(parents=True)
        assert scan_guidance_topics(wiki) == {}

    def test_single_topic_collects_pages(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(
            wiki / "guidance" / "expo" / "use-eas.md",
            title="Use EAS",
            summary="Build with EAS.",
            impact="high",
        )
        topics = scan_guidance_topics(wiki)
        assert list(topics) == ["expo"]
        entry = topics["expo"][0]
        assert entry["path"] == "guidance/expo/use-eas.md"
        assert entry["title"] == "Use EAS"
        assert entry["summary"] == "Build with EAS."
        assert entry["impact"] == "high"

    def test_topic_with_only_index_md_is_skipped(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "empty-topic" / "index.md", title="Idx")
        _write_guidance_page(wiki / "guidance" / "expo" / "page.md", title="Page")
        assert list(scan_guidance_topics(wiki)) == ["expo"]

    def test_loose_md_under_guidance_is_ignored(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "loose.md", title="Loose")
        assert scan_guidance_topics(wiki) == {}

    def test_dot_dirs_are_skipped(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / ".hidden" / "page.md", title="Hidden")
        assert scan_guidance_topics(wiki) == {}

    def test_entries_sorted_by_title_case_insensitive(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "t" / "z.md", title="Zeta")
        _write_guidance_page(wiki / "guidance" / "t" / "a.md", title="alpha")
        _write_guidance_page(wiki / "guidance" / "t" / "m.md", title="Mu")
        topics = scan_guidance_topics(wiki)
        assert [e["title"] for e in topics["t"]] == ["alpha", "Mu", "Zeta"]
