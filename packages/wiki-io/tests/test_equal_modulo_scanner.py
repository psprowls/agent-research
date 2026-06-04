"""Living Wiki M2c #3: body comparison that ignores scanner-owned section bodies."""

from __future__ import annotations

from wiki_io.entity_writer import _equal_modulo_scanner

# A page whose scanner sections are FILLED (as found on disk after a scan).
_FILLED = """---
uri: pkg:org/repo/pkg-a
kind: package
language: python
---
# pkg-a

## Narrative
Real narrative prose written by the narrator.

## Purpose
> A human wrote this.

## File map - pkg-a
### pkg-a/
| Path | Kind | Description |
|---|---|---|
| `mod.py` | file | does a thing |

## Referenced in wiki
- [[entities/other]]
"""

# The SAME page as write_entities re-renders it: scanner sections reset to
# placeholders AND the File-map heading uses the slug suffix (`pkg_pkg-a`),
# not the dir basename (`pkg-a`). Frontmatter + preamble + human section match.
_PLACEHOLDER = """---
uri: pkg:org/repo/pkg-a
kind: package
language: python
---
# pkg-a

## Narrative
_(scanner will populate on next scan)_

## Purpose
> A human wrote this.

## File map - pkg_pkg-a
> TODO: <Overview>

### pkg_pkg-a/
| Path | Kind | Description |
|---|---|---|
| `<file>` | file | — TODO |

## Referenced in wiki
_(scanner will populate on next scan)_
"""


def test_equal_when_only_scanner_bodies_and_filemap_heading_differ() -> None:
    # Despite different scanner bodies AND a different `## File map` heading
    # suffix, the two pages are equal modulo scanner sections.
    assert _equal_modulo_scanner(_FILLED, _PLACEHOLDER) is True


def test_not_equal_when_human_section_differs() -> None:
    edited = _FILLED.replace("> A human wrote this.", "> A human EDITED this.")
    assert _equal_modulo_scanner(edited, _PLACEHOLDER) is False


def test_not_equal_when_frontmatter_differs() -> None:
    edited = _FILLED.replace("language: python", "language: rust")
    assert _equal_modulo_scanner(edited, _PLACEHOLDER) is False


def test_not_equal_when_preamble_differs() -> None:
    edited = _FILLED.replace("# pkg-a", "# pkg-a-renamed")
    assert _equal_modulo_scanner(edited, _PLACEHOLDER) is False


def test_not_equal_when_human_section_added() -> None:
    added = _PLACEHOLDER.replace(
        "## Referenced in wiki",
        "## Extra Notes\n> new human section\n\n## Referenced in wiki",
    )
    assert _equal_modulo_scanner(_FILLED, added) is False


def test_identical_text_is_equal() -> None:
    assert _equal_modulo_scanner(_FILLED, _FILLED) is True


def test_malformed_text_is_not_equal() -> None:
    # A parse failure must be conservative — treated as "changed" (write).
    assert _equal_modulo_scanner("\x00not yaml frontmatter", _FILLED) is False


def test_unparseable_frontmatter_is_not_equal() -> None:
    # Genuinely broken YAML frontmatter raises in frontmatter.loads → the
    # conservative except branch returns False (caller writes the page).
    broken = "---\nkey: : broken: :\n---\nbody"
    assert _equal_modulo_scanner(broken, _FILLED) is False
