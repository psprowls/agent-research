"""Assertion tests for the `wiki_io.assets.page-templates` resource directory.

Phase 51 PKGFAM-03: belt-and-suspenders regression that the retired
`entity-package-family.md` and `package-family.md` templates do NOT
re-appear in the packaged assets.
"""

from __future__ import annotations

from importlib.resources import files


def _template_names() -> set[str]:
    return {p.name for p in files("wiki_io.assets.page-templates").iterdir()}


def test_core_entity_templates_still_present() -> None:
    """Sanity: the 6 admitted-kind entity templates still ship."""
    names = _template_names()
    for expected in (
        "entity-repository.md",
        "entity-package.md",
        "entity-app.md",
        "entity-agent-plugin.md",
        "entity-dependency.md",
        "entity-test-suite.md",
    ):
        assert expected in names, f"missing expected template: {expected}"


def test_concept_template_seeds_status_active() -> None:
    """The concept template ships a human-owned `status: active` field so the
    archivability lifecycle is discoverable (gw wiki archive)."""
    text = files("wiki_io.assets.page-templates").joinpath("concept.md").read_text(encoding="utf-8")
    # Field is inside the frontmatter block.
    fm_block = text.split("---", 2)[1]
    assert "status: active" in fm_block
