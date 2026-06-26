"""Guidance index generation (spec: <workspace>raw/specs/_archived/2026-06-09-guidance-index-pages-design.md)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from wiki_io.update_index import (
    GENERATED_FILES,
    render_guidance_root_index,
    render_guidance_topic_index,
    scan_guidance_topics,
    topic_label,
    update_guidance_indexes,
    update_index,
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


class TestRenderGuidanceTopicIndex:
    def _entry(self, **overrides):
        entry = {
            "path": "guidance/deep-agents/skill-md-requires-yaml-frontmatter.md",
            "title": "SKILL.md Requires YAML Frontmatter",
            "summary": "Every SKILL.md must open with a YAML frontmatter block.",
            "impact": "high",
        }
        entry.update(overrides)
        return entry

    def test_full_entry_with_summary_and_impact(self):
        text = render_guidance_topic_index("deep-agents", [self._entry()], "wiki")
        assert (
            "- [[guidance/deep-agents/skill-md-requires-yaml-frontmatter|SKILL.md Requires YAML Frontmatter]]"
            " — Every SKILL.md must open with a YAML frontmatter block. _(high)_" in text
        )

    def test_missing_summary_omits_dash_segment(self):
        text = render_guidance_topic_index("deep-agents", [self._entry(summary="")], "wiki")
        assert (
            "- [[guidance/deep-agents/skill-md-requires-yaml-frontmatter|SKILL.md Requires YAML Frontmatter]]"
            " _(high)_" in text
        )
        assert "]] —" not in text

    def test_missing_impact_omits_suffix(self):
        text = render_guidance_topic_index("deep-agents", [self._entry(impact="")], "wiki")
        assert "_(" not in text

    def test_frontmatter_and_banner(self):
        today = dt.date.today().isoformat()
        text = render_guidance_topic_index("deep-agents", [self._entry()], "wiki")
        lines = text.splitlines()
        assert lines[0] == "---"
        assert "title: Deep Agents Guidance Index" in lines
        assert "category: index" in lines
        assert f"updated: {today}" in lines
        assert "# Deep Agents Guidance Index" in lines
        assert f"_Auto-generated {today} • 1 pages_" in lines


class TestRenderGuidanceRootIndex:
    def test_topics_sorted_alphabetically_with_counts(self):
        topics = {
            "expo": [{"path": "guidance/expo/a.md", "title": "A", "summary": "", "impact": ""}],
            "deep-agents": [
                {"path": f"guidance/deep-agents/p{i}.md", "title": f"P{i}", "summary": "", "impact": ""}
                for i in range(9)
            ],
        }
        text = render_guidance_root_index(topics, "wiki")
        deep = text.index("- [[guidance/deep-agents/index|Deep Agents]] — 9 pages")
        expo = text.index("- [[guidance/expo/index|Expo]] — 1 page")
        assert deep < expo

    def test_singular_page_count(self):
        topics = {"expo": [{"path": "guidance/expo/a.md", "title": "A", "summary": "", "impact": ""}]}
        text = render_guidance_root_index(topics, "wiki")
        assert "— 1 page" in text
        assert "— 1 pages" not in text

    def test_frontmatter(self):
        today = dt.date.today().isoformat()
        topics = {"expo": [{"path": "guidance/expo/a.md", "title": "A", "summary": "", "impact": ""}]}
        text = render_guidance_root_index(topics, "wiki")
        lines = text.splitlines()
        assert lines[0] == "---"
        assert "title: Guidance Index" in lines
        assert "category: index" in lines
        assert f"updated: {today}" in lines
        assert "# Guidance Index" in lines


class TestUpdateGuidanceIndexes:
    def test_absent_guidance_writes_nothing(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        update_guidance_indexes(wiki)
        assert not (wiki / "guidance").exists()

    def test_empty_topic_dirs_write_nothing(self, tmp_path):
        wiki = tmp_path / "wiki"
        (wiki / "guidance" / "empty-topic").mkdir(parents=True)
        update_guidance_indexes(wiki)
        assert not (wiki / "guidance" / "index.md").exists()
        assert not (wiki / "guidance" / "empty-topic" / "index.md").exists()

    def test_single_topic_writes_root_and_topic_index(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(
            wiki / "guidance" / "expo" / "use-eas.md",
            title="Use EAS",
            summary="Build with EAS.",
            impact="high",
        )
        update_guidance_indexes(wiki)

        root = (wiki / "guidance" / "index.md").read_text(encoding="utf-8")
        assert "- [[guidance/expo/index|Expo]] — 1 page" in root

        topic = (wiki / "guidance" / "expo" / "index.md").read_text(encoding="utf-8")
        assert "- [[guidance/expo/use-eas|Use EAS]] — Build with EAS. _(high)_" in topic

    def test_multiple_topics_alphabetical_in_root(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "expo" / "a.md", title="A")
        _write_guidance_page(wiki / "guidance" / "deep-agents" / "b.md", title="B")
        update_guidance_indexes(wiki)
        root = (wiki / "guidance" / "index.md").read_text(encoding="utf-8")
        assert root.index("Deep Agents") < root.index("Expo")
        assert (wiki / "guidance" / "deep-agents" / "index.md").exists()
        assert (wiki / "guidance" / "expo" / "index.md").exists()

    def test_rerun_is_idempotent(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "expo" / "a.md", title="A", impact="low")
        update_guidance_indexes(wiki)
        first_root = (wiki / "guidance" / "index.md").read_bytes()
        first_topic = (wiki / "guidance" / "expo" / "index.md").read_bytes()
        update_guidance_indexes(wiki)
        assert (wiki / "guidance" / "index.md").read_bytes() == first_root
        assert (wiki / "guidance" / "expo" / "index.md").read_bytes() == first_topic

    def test_generated_index_not_listed_as_content_on_rerun(self, tmp_path):
        """The root index must not list itself or topic indexes after a re-run."""
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "expo" / "a.md", title="A")
        update_guidance_indexes(wiki)
        update_guidance_indexes(wiki)
        root = (wiki / "guidance" / "index.md").read_text(encoding="utf-8")
        assert "— 1 page" in root  # index.md not counted as a content page


class TestUpdateIndexIntegration:
    def test_update_index_regenerates_guidance_indexes(self, tmp_path):
        wiki = tmp_path / "wiki"
        _write_guidance_page(wiki / "guidance" / "expo" / "a.md", title="A")
        # update_index also needs the vault root to exist (it does) — no other seeding required.
        update_index(wiki)
        assert (wiki / "guidance" / "index.md").exists()
        assert (wiki / "guidance" / "expo" / "index.md").exists()

    def test_guidance_root_index_in_generated_files(self):
        assert "guidance/index.md" in GENERATED_FILES
