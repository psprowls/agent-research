"""Tests for path-qualified wikilinks in package and domain overview templates.

Bare `[[api]]`-style wikilinks in the Sub-pages block confuse lint_wiki because
the resolver only matches against on-disk paths. A page at
``packages/foo/foo.md`` with `[[api]]` would need a sibling named ``api.md`` —
which is correct on disk — but the orphan check then fails to recognize
``packages/foo/api`` as having an inbound link, since the parent overview
points to a stem that resolves only via the bare-filename shorthand and not
via the link_targets set.

Path-qualified form `[[packages/<slug>/api|api]]` resolves directly via
link_targets containment and renders the same in Obsidian.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path


ASSETS = Path(__file__).resolve().parents[1] / "src" / "vault_io" / "assets" / "page-templates"


def test_package_overview_renders_path_qualified_wikilinks(tmp_path: Path) -> None:
    """Rendering the package overview through init_vault.render_template with a
    PACKAGE_SLUG variable produces path-qualified [[packages/<slug>/<sub>|<sub>]]
    wikilinks in the Sub-pages section."""
    from vault_io.init_vault import render_template

    src = ASSETS / "package" / "overview.md"
    dest = tmp_path / "myslug.md"
    today = dt.date.today().isoformat()
    ok = render_template(
        src,
        dest,
        {"PACKAGE_TITLE": "myslug", "PACKAGE_SLUG": "myslug", "DATE": today},
    )
    assert ok is True
    rendered = dest.read_text(encoding="utf-8")

    # Path-qualified forms present.
    assert "[[packages/myslug/api|api]]" in rendered
    assert "[[packages/myslug/patterns|patterns]]" in rendered
    assert "[[packages/myslug/work|work]]" in rendered
    assert "[[packages/myslug/context|context]]" in rendered

    # Bare forms absent.
    assert "[[api]]" not in rendered
    assert "[[patterns]]" not in rendered
    assert "[[work]]" not in rendered
    assert "[[context]]" not in rendered

    # No leftover unsubstituted slug tokens.
    assert "{{PACKAGE_SLUG}}" not in rendered


def test_domain_overview_renders_path_qualified_wikilinks(tmp_path: Path) -> None:
    """Rendering the domain overview through ensure_domain_page (the production
    code path) produces a path-qualified [[domains/<slug>/details|details]]
    wikilink in the Sub-pages section."""
    from vault_io.layout_io import ensure_domain_page

    # ensure_domain_page needs a templates_dir that mirrors the assets layout
    # under the wiki's .templates/ directory.
    templates_dir = tmp_path / ".templates"
    (templates_dir / "domain").mkdir(parents=True)
    src = ASSETS / "domain" / "overview.md"
    (templates_dir / "domain" / "overview.md").write_text(
        src.read_text(encoding="utf-8"), encoding="utf-8"
    )

    domain_dir = tmp_path / "domains" / "myslug"
    domain_dir.mkdir(parents=True)
    today = dt.date.today().isoformat()
    dest, created = ensure_domain_page(
        domain_dir, domain_title="myslug", templates_dir=templates_dir, today=today
    )
    assert created is True
    rendered = dest.read_text(encoding="utf-8")

    # Path-qualified form present.
    assert "[[domains/myslug/details|details]]" in rendered

    # Bare form absent.
    assert "[[details]]" not in rendered

    # No leftover unsubstituted slug tokens.
    assert "{{DOMAIN_SLUG}}" not in rendered
