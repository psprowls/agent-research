"""Per-kind concept templates carry `kind:` frontmatter (assets/page-templates/)."""

from __future__ import annotations

from wiki_io.concept_kinds import KIND_TEMPLATES
from wiki_io.init_vault import ASSETS_DIR

TEMPLATES = ASSETS_DIR / "page-templates"


def test_all_kind_templates_exist():
    for fname in KIND_TEMPLATES.values():
        assert (TEMPLATES / fname).is_file(), fname


def test_kind_frontmatter_lines():
    assert "kind: concept\n" in (TEMPLATES / "concept.md").read_text(encoding="utf-8")
    assert "kind: pattern\n" in (TEMPLATES / "concept-pattern.md").read_text(encoding="utf-8")
    text = (TEMPLATES / "concept-architecture.md").read_text(encoding="utf-8")
    assert "category: concept\n" in text
    assert "kind: architecture\n" in text
    assert "packages: []\n" in text  # template-specific frontmatter survives
    assert "## Thesis" in text  # body unchanged
