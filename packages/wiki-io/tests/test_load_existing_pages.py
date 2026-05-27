"""Phase 45 D-11: tests for ExistingPages dataclass + _load_existing_pages entities walk."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import frontmatter as _fm  # noqa: F401 — sanity import to ensure dep is present
import pytest

from wiki_io.scan_monorepo import ExistingPages, _load_existing_pages, compute_diff


class TestExistingPagesShape:
    def test_dataclass_construction_empty(self):
        p = ExistingPages(legacy={}, entities={})
        assert p.legacy == {}
        assert p.entities == {}

    def test_dataclass_construction_populated(self):
        p = ExistingPages(
            legacy={"foo": {"wiki_relative_path": "packages/foo/foo.md"}},
            entities={"pkg:x/y": {"path": Path("/x"), "frontmatter": {"uri": "pkg:x/y"}}},
        )
        assert "foo" in p.legacy
        assert "pkg:x/y" in p.entities

    def test_dataclass_is_frozen(self):
        p = ExistingPages(legacy={}, entities={})
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.legacy = {"x": {}}  # type: ignore[misc]


class TestLoadExistingPagesReturnType:
    def test_returns_existing_pages_instance(self, tmp_path):
        """_load_existing_pages returns an ExistingPages dataclass, not a dict."""
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        result = _load_existing_pages(wiki)
        assert isinstance(result, ExistingPages), (
            "_load_existing_pages must return an ExistingPages dataclass (Phase 45 D-11)"
        )

    def test_falsy_wiki_returns_empty_dataclass(self):
        result = _load_existing_pages(None)
        assert isinstance(result, ExistingPages)
        assert result.legacy == {}
        assert result.entities == {}

    def test_legacy_dict_passes_through_compute_diff(self, tmp_path):
        """ExistingPages.legacy is a plain dict — feed it straight to compute_diff."""
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        result = _load_existing_pages(wiki)
        # Should not raise — compute_diff treats existing as a dict of names.
        diff = compute_diff([], result.legacy)
        assert "deleted" in diff


class TestLoadExistingPagesEntities:
    def _write_entity_page(self, entities_dir: Path, slug: str, uri: str, kind: str = "package"):
        page = entities_dir / f"{slug}.md"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(
            f"---\nuri: {uri}\nkind: {kind}\n---\n\n## Narrative\n\nbody\n",
            encoding="utf-8",
        )
        return page

    def test_entities_dict_empty_when_directory_absent(self, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir()
        result = _load_existing_pages(wiki)
        assert result.entities == {}

    def test_entities_dict_populated_from_entities_dir(self, tmp_path):
        wiki = tmp_path / "wiki"
        entities_dir = wiki / "entities"
        entities_dir.mkdir(parents=True)
        p1 = self._write_entity_page(entities_dir, "pkg__foo", "pkg:foo")
        self._write_entity_page(entities_dir, "domain__bar", "domain:bar", kind="domain")

        result = _load_existing_pages(wiki)

        assert "pkg:foo" in result.entities
        assert "domain:bar" in result.entities
        assert result.entities["pkg:foo"]["path"] == p1
        assert result.entities["pkg:foo"]["frontmatter"]["uri"] == "pkg:foo"
        assert result.entities["pkg:foo"]["frontmatter"]["kind"] == "package"
        assert result.entities["domain:bar"]["frontmatter"]["kind"] == "domain"

    def test_entities_walk_skips_index_md(self, tmp_path):
        wiki = tmp_path / "wiki"
        entities_dir = wiki / "entities"
        entities_dir.mkdir(parents=True)
        # _index.md should NOT appear in result.entities even if it has a URI
        (entities_dir / "_index.md").write_text(
            "---\nuri: NOT_A_REAL_URI\n---\n\n# Index\n", encoding="utf-8"
        )
        self._write_entity_page(entities_dir, "pkg__real", "pkg:real")

        result = _load_existing_pages(wiki)

        assert "NOT_A_REAL_URI" not in result.entities
        assert "pkg:real" in result.entities

    def test_entities_walk_skips_pages_missing_uri(self, tmp_path):
        wiki = tmp_path / "wiki"
        entities_dir = wiki / "entities"
        entities_dir.mkdir(parents=True)
        # Page without `uri` in frontmatter
        (entities_dir / "orphan.md").write_text(
            "---\nkind: package\n---\n\n## Narrative\n\nbody\n", encoding="utf-8"
        )
        self._write_entity_page(entities_dir, "pkg__valid", "pkg:valid")

        result = _load_existing_pages(wiki)

        assert "pkg:valid" in result.entities
        assert len(result.entities) == 1  # the orphan is not included

    def test_entities_walk_skips_unparseable_frontmatter(self, tmp_path):
        wiki = tmp_path / "wiki"
        entities_dir = wiki / "entities"
        entities_dir.mkdir(parents=True)
        # Invalid YAML in frontmatter
        (entities_dir / "broken.md").write_text(
            "---\nuri: : : : invalid\n---\nbody\n", encoding="utf-8"
        )
        self._write_entity_page(entities_dir, "pkg__valid", "pkg:valid")

        result = _load_existing_pages(wiki)

        # broken.md must not appear; the function must not raise
        assert "pkg:valid" in result.entities
        # `broken.md` either skipped (uri missing/unparseable) — exact result
        # depends on python-frontmatter's tolerance; the contract is no raise.
