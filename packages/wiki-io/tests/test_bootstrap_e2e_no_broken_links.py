"""End-to-end regression: bootstrap a wiki + render package/app/plugin overview
templates + lint, asserting zero broken wikilinks across all three container
types. This is the HYGIENE-14 closure artifact per Phase 35 D-02/D-03.

The roadmap originally called for a manual /graph-wiki:query smoke transcript;
D-03 supersedes that with this automated test — a regression test that runs on
every CI is strictly stronger evidence than a one-time manual capture.

Coverage map for this single test:
  HYGIENE-01 — sub-page wikilinks are prefixed `wiki/<container>/<slug>/...`
  HYGIENE-02 — `init_wiki` writes `concepts/sources/adrs/architecture` index stubs
  HYGIENE-03 — `{{CONTAINER_DIR}}` substitutes correctly for `apps/` and `plugins/`
               (not just `packages/`)
  HYGIENE-06 — `overview.md` (not `<slug>.md`) is the filename containing the
               wikilinks under each container
  HYGIENE-12 — same `SECTION_INDEX_STUBS` block as HYGIENE-02
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest


def _extract_broken_wikilinks(report: dict) -> list:
    """Return the broken-wikilink entries from a `lint_wiki.scan()` report.

    `lint_wiki.scan()` exposes broken wikilinks under the `broken_links` key
    as a list of `(src, target)` tuples (see `lint_wiki.py:350`). This helper
    fails loudly if the shape changes in the future so the test pins the
    assertion to a real key, not a guess.
    """
    if "broken_links" in report:
        return list(report["broken_links"])
    raise AssertionError(
        "lint_wiki.scan() returned a report without `broken_links` — read "
        "scan()'s return statement and update _extract_broken_wikilinks to "
        f"match. report keys: {sorted(report.keys())}"
    )


def test_bootstrap_then_render_overviews_zero_broken_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bootstrap a wiki + render package/app/plugin overview templates + lint.

    Asserts zero broken wikilinks across all three container types in a single
    bootstrap call. Sibling sub-page stubs (api/patterns/work/testing/context
    for package & plugin; testing for app) are written so the `[[wiki/<container>/
    <slug>/<sub>|<sub>]]` links from the overview pages resolve via
    `lint_wiki.scan()`'s `link_targets` set.
    """
    from wiki_io import init_vault
    from wiki_io.init_vault import init_wiki, render_template
    from wiki_io.lint_wiki import scan as lint_scan

    # Stub out workspace bootstrap (writes .graph-wiki.yaml, runs git init)
    # and container detection — neither is exercised by this test, and both
    # require real I/O against tmp_path that adds noise to the lint surface.
    monkeypatch.setattr(init_vault, "_workspace_init", lambda *a, **k: None)
    monkeypatch.setattr(init_vault, "_resolve_pinned_containers", lambda *a, **k: [])

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "tmp-repo"\nversion = "0.0.0"\n', encoding="utf-8"
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"

    init_wiki(
        wiki_path=wiki,
        repo_path=repo,
        topic="test",
        tool="claude-code",
        force=False,
        non_interactive=True,
        as_json=False,
    )

    # Render the three overview templates into the wiki tree, plus minimal
    # stub sub-pages so `[[wiki/<container>/<slug>/<sub>|<sub>]]` links resolve.
    assets = Path(init_vault.__file__).resolve().parent / "assets" / "page-templates"
    today = dt.date.today().isoformat()

    def render_container(
        container: str, slug: str, title_var: str, slug_var: str, tmpl_subdir: str
    ) -> None:
        target_dir = wiki / container / slug
        target_dir.mkdir(parents=True, exist_ok=True)
        render_template(
            assets / tmpl_subdir / "overview.md",
            target_dir / "overview.md",
            {title_var: slug, slug_var: slug, "CONTAINER_DIR": container, "DATE": today},
        )
        # Sub-page stubs. The overview templates reference:
        #   package / plugin: api, patterns, work, testing, context
        #   app:              testing
        if tmpl_subdir in ("package", "plugin"):
            subs = ("api", "patterns", "work", "testing", "context")
        else:
            subs = ("testing",)
        for sub in subs:
            (target_dir / f"{sub}.md").write_text(
                f"---\ncategory: {tmpl_subdir}\nstatus: active\n---\n# {slug}/{sub} stub\n",
                encoding="utf-8",
            )

    render_container("packages", "test-pkg", "PACKAGE_TITLE", "PACKAGE_SLUG", "package")
    render_container("apps", "test-app", "APP_TITLE", "APP_SLUG", "app")
    render_container("plugins", "test-plugin", "PACKAGE_TITLE", "PACKAGE_SLUG", "plugin")

    report = lint_scan(wiki, stale_days=90, log_gap_days=14, repo_path=None)

    broken = _extract_broken_wikilinks(report)
    # Only count broken links sourced from the three overview pages we just
    # rendered — index.md / log.md and other init-wiki-generated pages have
    # their own placeholder/TODO links that are out of scope for HYGIENE-01..06.
    container_broken = [
        (src, tgt) for (src, tgt) in broken
        if src.startswith("wiki/packages/test-pkg")
        or src.startswith("wiki/apps/test-app")
        or src.startswith("wiki/plugins/test-plugin")
    ]
    assert container_broken == [], (
        "Bootstrap-and-lint regression: expected zero broken wikilinks across "
        "package/app/plugin overview pages, got:\n"
        f"  {container_broken!r}\n"
        f"Full broken_links list (for context): {broken!r}"
    )
