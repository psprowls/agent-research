"""Cross-cutting validation: entity templates align with ADMITTED_KINDS (URI-03 / D-18 / Pitfall 5).

Closes the loop between Plan 01's `ADMITTED_KINDS` constant and Plan 02's
seven `entity-*.md` templates. Catches drift if a future change adds a
template without updating ADMITTED_KINDS, or vice versa.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
import pytest

from wiki_io.entity_writer import ADMITTED_KINDS

TEMPLATE_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "wiki_io" / "assets" / "page-templates"
)
ENTITY_TEMPLATES = sorted(TEMPLATE_DIR.glob("entity-*.md"))


def test_seven_entity_templates_exist() -> None:
    """Exactly 7 entity-*.md files exist (one per admitted kind)."""
    assert len(ENTITY_TEMPLATES) == 7, (
        f"expected 7 entity templates, got {len(ENTITY_TEMPLATES)}: "
        f"{[p.name for p in ENTITY_TEMPLATES]}"
    )


@pytest.mark.parametrize(
    "template_path",
    ENTITY_TEMPLATES,
    ids=[p.name for p in ENTITY_TEMPLATES],
)
def test_each_template_kind_in_admitted_kinds(template_path: Path) -> None:
    """Each template's frontmatter kind: value is in ADMITTED_KINDS (D-18)."""
    fm = frontmatter.load(template_path)
    kind = fm.get("kind")
    assert kind in ADMITTED_KINDS, (
        f"{template_path.name}: kind {kind!r} not in ADMITTED_KINDS "
        f"({sorted(ADMITTED_KINDS)})"
    )


@pytest.mark.parametrize(
    "template_path",
    ENTITY_TEMPLATES,
    ids=[p.name for p in ENTITY_TEMPLATES],
)
def test_each_template_has_narrative_h2(template_path: Path) -> None:
    """Each template body contains the literal `## Narrative` H2 section (D-16)."""
    fm = frontmatter.load(template_path)
    assert "\n## Narrative\n" in fm.content, (
        f"{template_path.name}: missing `## Narrative` H2 section"
    )


def test_templates_cover_all_admitted_kinds() -> None:
    """The 7 templates' kind values exactly equal ADMITTED_KINDS (bijection)."""
    kinds_in_templates: set[str] = set()
    for tpl in ENTITY_TEMPLATES:
        fm = frontmatter.load(tpl)
        kind = fm.get("kind")
        assert isinstance(kind, str), f"{tpl.name}: kind is not a string: {kind!r}"
        kinds_in_templates.add(kind)
    assert kinds_in_templates == ADMITTED_KINDS, (
        f"template kinds {sorted(kinds_in_templates)} != ADMITTED_KINDS "
        f"{sorted(ADMITTED_KINDS)}"
    )
