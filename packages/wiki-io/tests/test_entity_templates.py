"""Cross-cutting validation: entity templates align with ADMITTED_KINDS (URI-03 / D-18 / Pitfall 5).

Closes the loop between Plan 01's `ADMITTED_KINDS` constant and Plan 02's
`entity-*.md` templates. Catches drift if a future change adds a template
without updating ADMITTED_KINDS, or vice versa.

Phase 51 PKGFAM-03: count was 6 (`entity-package-family.md` retired).
Phase 52 D-06: count is now 7 (`entity-app.md` added).
"""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter
import pytest
from wiki_io.entity_writer import ADMITTED_KINDS

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "src" / "wiki_io" / "assets" / "page-templates"
ENTITY_TEMPLATES = sorted(TEMPLATE_DIR.glob("entity-*.md"))


def test_six_entity_templates_exist() -> None:
    """Exactly 7 entity-*.md files exist (one per admitted kind).

    Phase 51 PKGFAM-03: was 6 after `entity-package-family.md` was retired.
    Phase 52 D-06: now 7 with the addition of `entity-app.md`.
    """
    assert len(ENTITY_TEMPLATES) == 7, (
        f"expected 7 entity templates, got {len(ENTITY_TEMPLATES)}: {[p.name for p in ENTITY_TEMPLATES]}"
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
        f"{template_path.name}: kind {kind!r} not in ADMITTED_KINDS ({sorted(ADMITTED_KINDS)})"
    )


@pytest.mark.parametrize(
    "template_path",
    ENTITY_TEMPLATES,
    ids=[p.name for p in ENTITY_TEMPLATES],
)
def test_each_template_has_narrative_h2(template_path: Path) -> None:
    """Each template body contains the literal `## Narrative` H2 section (D-16)."""
    fm = frontmatter.load(template_path)
    assert "\n## Narrative\n" in fm.content, f"{template_path.name}: missing `## Narrative` H2 section"


def test_templates_cover_all_admitted_kinds() -> None:
    """The 6 templates' kind values exactly equal ADMITTED_KINDS (bijection)."""
    kinds_in_templates: set[str] = set()
    for tpl in ENTITY_TEMPLATES:
        fm = frontmatter.load(tpl)
        kind = fm.get("kind")
        assert isinstance(kind, str), f"{tpl.name}: kind is not a string: {kind!r}"
        kinds_in_templates.add(kind)
    assert kinds_in_templates == ADMITTED_KINDS, (
        f"template kinds {sorted(kinds_in_templates)} != ADMITTED_KINDS {sorted(ADMITTED_KINDS)}"
    )


# --- Phase 56 (ENTITY-01/02, D-01/D-08/D-09) -------------------------------
# D-01 two-token rule: a template's data-bearing body H1 is a {{...}} data
# token (scanner-substituted), NOT a `# <...>` angle placeholder. Instruction
# angles inside guidance are left as `<...>` and are out of scope here.

_BODY_H1_TOKEN_RE = re.compile(r"^# \{\{[a-z_]+\}\}$", re.MULTILINE)


@pytest.mark.parametrize(
    "template_path",
    ENTITY_TEMPLATES,
    ids=[p.name for p in ENTITY_TEMPLATES],
)
def test_each_template_body_h1_is_data_token(template_path: Path) -> None:
    """Each template body H1 is a `# {{..._name}}` data token (D-01, SCAN-01 anchor)."""
    body = frontmatter.load(template_path).content
    assert _BODY_H1_TOKEN_RE.search(body), f"{template_path.name}: body H1 is not a `# {{{{..._name}}}}` data token"
    # No data-bearing `# <...>` angle H1 may survive in the body.
    assert not re.search(r"^# <", body, re.MULTILINE), (
        f"{template_path.name}: a data-bearing `# <...>` angle H1 still survives"
    )


def _body(name: str) -> str:
    return frontmatter.load(TEMPLATE_DIR / name).content


def test_entity_package_migrated_sections() -> None:
    """entity-package.md carries the migrated Purpose section (D-08)."""
    body = _body("entity-package.md")
    assert "\n## Purpose\n" in body, "entity-package.md: missing migrated `## Purpose`"


def test_entity_app_migrated_sections() -> None:
    """entity-app.md carries the migrated Platform & runtime section (D-08)."""
    body = _body("entity-app.md")
    assert "## Platform & runtime" in body, "entity-app.md: missing migrated `## Platform & runtime`"


def test_entity_test_suite_owns_testing_prose() -> None:
    """entity-test-suite.md owns the testing-derived sections (D-09)."""
    body = _body("entity-test-suite.md")
    for heading in ("## How to run", "## Test conventions", "## Fixtures", "## Coverage"):
        assert heading in body, f"entity-test-suite.md: missing `{heading}`"


@pytest.mark.parametrize("name", ["entity-package.md", "entity-app.md"])
def test_no_testing_section_leaked_into_package_or_app(name: str) -> None:
    """Testing prose stays in entity-test-suite.md, not entity-package/app (D-09)."""
    body = _body(name).lower()
    assert "## how to run" not in body, f"{name}: testing `## How to run` leaked in"
    assert "## test conventions" not in body, f"{name}: testing `## Test conventions` leaked in"


# --- Phase 58 (SC#1, D-01/D-02/D-03) ----------------------------------------
# Regression guard: the ## Related block in entity templates must be
# Obsidian-safe — no `<...>` placeholder text, no leading `>` (blockquote),
# no `:` character on any body line.

_RELATED_BLOCK_RE = re.compile(r"^## Related\n(.*?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL)


def _related_block_body(template_name: str) -> str | None:
    """Return the body text after `## Related` up to the next H2 or EOF.

    Returns None if the template has no `## Related` section.
    """
    body = _body(template_name)
    m = _RELATED_BLOCK_RE.search(body)
    if m is None:
        return None
    return m.group(1)


def test_all_entity_templates_have_referenced_in_wiki_section() -> None:
    """Slice 4: every entity template carries the scanner-owned
    `## Referenced in wiki` section with a placeholder."""
    from importlib.resources import files

    tdir = files("wiki_io.assets.page-templates")
    kinds = [
        "package",
        "app",
        "domain",
        "repository",
        "dependency",
        "test-suite",
        "agent-plugin",
    ]
    for kind in kinds:
        body = (tdir / f"entity-{kind}.md").read_text(encoding="utf-8")
        assert "## Referenced in wiki" in body, f"missing in entity-{kind}.md"
        # Placeholder mirrors the ## Narrative convention.
        idx = body.index("## Referenced in wiki")
        after = body[idx:]
        assert (
            "_(scanner will populate on next scan)_" in after.split("\n\n", 1)[0]
            or "_(scanner will populate" in after[:120]
        ), f"no placeholder in entity-{kind}.md"


@pytest.mark.parametrize(
    "template_path",
    ENTITY_TEMPLATES,
    ids=[p.name for p in ENTITY_TEMPLATES],
)
def test_related_block_is_obsidian_safe(template_path: Path) -> None:
    """## Related block body has no `<` placeholder, no leading `>`, no `:` (SC#1 D-02).

    Templates with no ## Related section are skipped — they are not required
    to carry one (entity-test-suite.md, entity-dependency.md).
    """
    related_body = _related_block_body(template_path.name)
    if related_body is None:
        pytest.skip(f"{template_path.name}: no ## Related section — skip")

    for line in related_body.splitlines():
        assert "<" not in line, f"{template_path.name}: ## Related body contains `<` placeholder text: {line!r}"
        assert not line.startswith(">"), (
            f"{template_path.name}: ## Related body line starts with `>` (Obsidian blockquote): {line!r}"
        )
        assert ":" not in line, f"{template_path.name}: ## Related body line contains `:`: {line!r}"


# --- Task 8 (slice4-ingest-entities-parity) ----------------------------------


def test_source_template_uses_entities_and_has_entity_uri() -> None:
    from importlib.resources import files

    body = (files("wiki_io.assets.page-templates") / "source.md").read_text(encoding="utf-8")
    # Forward-link to entities, not legacy packages/domains.
    assert "[[entities/" in body
    assert "[[packages/" not in body
    assert "[[domains/" not in body
    # Singular canonical anchor present in frontmatter.
    assert "entity_uri:" in body


# --- Task 4 (Living Wiki M1 preservation) ------------------------------------

_FORWARD_LINK_HEADINGS = (
    "## Concepts",
    "## Dependencies",
    "## Decisions",
    "## Contrasts / alternatives",
)


@pytest.mark.parametrize(
    "template_path",
    ENTITY_TEMPLATES,
    ids=[p.name for p in ENTITY_TEMPLATES],
)
def test_no_forward_link_stub_sections(template_path: Path) -> None:
    """Entity templates must not carry the duplicative forward-link stubs;
    `## Referenced in wiki` (backlinks) supersedes them (Living Wiki M1)."""
    text = template_path.read_text(encoding="utf-8")
    for heading in _FORWARD_LINK_HEADINGS:
        assert not re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE), (
            f"{template_path.name} still carries `{heading}`"
        )
