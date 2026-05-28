"""Assertion tests for the `wiki_io.assets.page-templates` resource directory.

Phase 51 PKGFAM-03: belt-and-suspenders regression that the retired
`entity-package-family.md` and `package-family.md` templates do NOT
re-appear in the packaged assets.
"""
from __future__ import annotations

from importlib.resources import files


def _template_names() -> set[str]:
    return {p.name for p in files("wiki_io.assets.page-templates").iterdir()}


def test_no_package_family_template() -> None:
    """Phase 51 PKGFAM-03: the two package-family templates are deleted."""
    names = _template_names()
    assert "entity-package-family.md" not in names, (
        "entity-package-family.md must stay deleted (Phase 51 PKGFAM-03)"
    )
    assert "package-family.md" not in names, (
        "package-family.md must stay deleted (Phase 51 PKGFAM-03)"
    )


def test_core_entity_templates_still_present() -> None:
    """Sanity: the 6 admitted-kind entity templates still ship."""
    names = _template_names()
    for expected in (
        "entity-repository.md",
        "entity-domain.md",
        "entity-package.md",
        "entity-plugin.md",
        "entity-dependency.md",
        "entity-test-suite.md",
    ):
        assert expected in names, f"missing expected template: {expected}"
