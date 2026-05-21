"""Unit tests for companion-fold filter in scan_monorepo._load_existing_pages.

Covers SCAN-01 and SCAN-02:
- Companion stems declared in workflow_hints frontmatter are NOT reported as
  separate pages (folded into their parent overview).
- Layout-pinned 'package' containers receive the same fold.
- wiki/apps/ pages are NOT folded (apps are single-file by convention).
- compute_diff reports 0 'deleted' entries for companion stems on the
  round-trip-vault fixture (where companion files exist on disk but their
  parent is still a current workspace).

Requirements: SCAN-01, SCAN-02
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ROUND_TRIP_VAULT = FIXTURES / "round-trip-vault"

# Minimal CLAUDE.md with graph-wiki layout block declaring a 'package' container.
# The sentinel comments are required by layout_io.read_layout() (see layout_io.py:32-48).
_LAYOUT_CLAUDE_MD = """\
# wiki — Code Wiki

Some description.

<!-- graph-wiki:layout:start -->
```yaml
version: 1
detected_at: 2026-01-01
repo_root: ..
containers:
  - source: custom-pkgs
    vault_dir: custom-pkgs
    classification: package
    children_count: 1
```
<!-- graph-wiki:layout:end -->
"""

_OVERVIEW_FRONTMATTER = """\
---
title: pkg-x
category: package
summary: A synthetic package for testing.
tags: []
updated: 2026-01-01
workflow_hints:
  planning: [api.md, patterns.md]
  brainstorming: [context.md]
  debugging: [work.md]
---

# pkg-x

Content here.
"""

_APP_OVERVIEW_FRONTMATTER = """\
---
title: foo
category: app
summary: A synthetic app.
tags: []
updated: 2026-01-01
workflow_hints:
  planning: [api.md]
  brainstorming: [context.md]
---

# foo

Content here.
"""


def _companion_vault_paths(pages: dict) -> set[str]:
    """Return the vault_path values whose file stem is a companion stem."""
    companion_stems = {"api", "context", "patterns", "work"}
    result = set()
    for _name, meta in pages.items():
        vp = meta.get("wiki_relative_path", "")
        stem = Path(vp).stem if vp else ""
        if stem in companion_stems:
            result.add(vp)
    return result


def test_load_existing_skips_companions() -> None:
    """Companion files (by file stem) in packages/ should not appear as page entries."""
    from vault_io.scan_monorepo import _load_existing_pages

    pages = _load_existing_pages(ROUND_TRIP_VAULT)

    # Companion files have stems like 'api', 'context', 'patterns', 'work'.
    # After the fix, no entry in pages should correspond to one of these files
    # when they live under packages/<pkg>/.
    leaked = _companion_vault_paths(pages)
    assert not leaked, (
        f"Companion files leaked into pages dict as separate entries: {leaked}. "
        f"Companion folding is broken."
    )

    # Parent overviews should still be present
    assert "lattice-curator-core" in pages, (
        f"Parent overview 'lattice-curator-core' is missing from pages. "
        f"Keys: {sorted(pages)}"
    )


def test_layout_pinned_package_skips_companions(tmp_path: Path) -> None:
    """layout-pinned 'package' containers receive the companion fold too."""
    from vault_io.scan_monorepo import _load_existing_pages

    # Build a synthetic vault with a layout-pinned container
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    # Write CLAUDE.md with layout block declaring custom-pkgs as 'package'
    (wiki / "CLAUDE.md").write_text(_LAYOUT_CLAUDE_MD, encoding="utf-8")

    # Create the layout-pinned container directory
    pkg_dir = wiki / "custom-pkgs" / "pkg-x"
    pkg_dir.mkdir(parents=True)

    # Parent overview with workflow_hints
    (pkg_dir / "pkg-x.md").write_text(_OVERVIEW_FRONTMATTER, encoding="utf-8")

    # Companion files — titles match what the real vault uses, stems are the key
    for companion in ("api", "context", "patterns", "work"):
        (pkg_dir / f"{companion}.md").write_text(
            f"---\ntitle: pkg-x — {companion.title()}\ncategory: package\n"
            f"summary: companion\ntags: []\nupdated: 2026-01-01\n---\n",
            encoding="utf-8",
        )

    pages = _load_existing_pages(wiki)

    leaked = _companion_vault_paths(pages)
    assert not leaked, (
        f"Companion files leaked into pages for layout-pinned package container: {leaked}. "
        f"Keys: {sorted(pages)}"
    )
    assert "pkg-x" in pages, f"Parent 'pkg-x' missing from pages. Keys: {sorted(pages)}"


def test_apps_not_filtered(tmp_path: Path) -> None:
    """wiki/apps/ pages are NOT folded — apps are single-file by convention (D-04)."""
    from vault_io.scan_monorepo import _load_existing_pages

    wiki = tmp_path / "wiki"
    wiki.mkdir()

    # App directory with a parent overview declaring workflow_hints
    app_dir = wiki / "apps" / "foo"
    app_dir.mkdir(parents=True)

    (app_dir / "foo.md").write_text(_APP_OVERVIEW_FRONTMATTER, encoding="utf-8")
    (app_dir / "api.md").write_text(
        "---\ntitle: api\ncategory: app\nsummary: app api companion\ntags: []\nupdated: 2026-01-01\n---\n",
        encoding="utf-8",
    )
    (app_dir / "context.md").write_text(
        "---\ntitle: context\ncategory: app\nsummary: app context companion\ntags: []\nupdated: 2026-01-01\n---\n",
        encoding="utf-8",
    )

    pages = _load_existing_pages(wiki)

    # Apps should NOT be folded — api and context should appear in pages
    # (they have category 'app' which scan will pick up)
    app_companion_vault_paths = {
        meta.get("wiki_relative_path", "")
        for _name, meta in pages.items()
        if Path(meta.get("wiki_relative_path", "")).stem in {"api", "context"}
    }
    assert app_companion_vault_paths, (
        f"App companion files (api, context) were incorrectly folded or not found. "
        f"pages keys: {sorted(pages)}"
    )


def test_compute_diff_no_phantom_deletes() -> None:
    """compute_diff reports 0 deleted entries for companion stems on the fixture vault."""
    from vault_io.scan_monorepo import _load_existing_pages, compute_diff

    existing = _load_existing_pages(ROUND_TRIP_VAULT)

    # Build a workspaces list matching the 7 fixture packages.
    # Companion pages (api/context/patterns/work stems) must NOT appear in deleted.
    package_names = [
        "lattice-curator-core",
        "lattice-evals",
        "lattice-graph-core",
        "lattice-source-parser",
        "lattice-wiki-agent",
        "lattice-wiki-core",
        "lattice-workspace",
    ]
    workspaces = [
        {"name": name, "path": f"packages/{name}", "type": "library", "language": "python"}
        for name in package_names
    ]

    diff = compute_diff(workspaces, existing)

    companion_stems = {"api", "context", "patterns", "work"}
    phantom_deletes = [
        d for d in diff["deleted"]
        if d in companion_stems or any(d.endswith(f"— {s.title()}") for s in companion_stems)
    ]
    assert not phantom_deletes, (
        f"Phantom companion deletes found in diff: {phantom_deletes}. "
        f"Full deleted list: {diff['deleted']}"
    )
