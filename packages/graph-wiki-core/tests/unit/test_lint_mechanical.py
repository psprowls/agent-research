"""Tests for graph_wiki_core.commands.lint_mechanical — the single lint
aggregator (moved from wiki-io with scan/print_report)."""

from __future__ import annotations

from pathlib import Path


def test_lint_mechanical_importable() -> None:
    """lint_mechanical exports library callables only."""
    from graph_wiki_core.commands import lint_mechanical

    assert callable(lint_mechanical.scan)
    assert callable(lint_mechanical.print_report)
    assert not hasattr(lint_mechanical, "main")


def test_lint_wiki_scan_runs_on_fixture_vault(tmp_path: Path) -> None:
    """scan(wiki, stale_days, log_gap_days) returns a structurally well-formed dict.

    A minimal wiki directory is constructed under tmp_path so that scan() has
    a valid wiki.exists() and a clean workspace to walk. The test asserts the
    top-level keys expected on the return value — no finding-count assertions.
    """
    from graph_wiki_core.commands.lint_mechanical import scan

    # Create a minimal workspace/wiki layout.
    # scan() treats wiki.parent as the workspace and rglobs *.md under it.
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()

    # Seed one page with full frontmatter so scan() has something to process.
    (wiki / "index.md").write_text(
        "---\ntitle: Index\ncategory: meta\nsummary: root index\n---\n\nWelcome.\n",
        encoding="utf-8",
    )
    page = wiki / "concepts"
    page.mkdir()
    (page / "example.md").write_text(
        "---\ntitle: Example\ncategory: concept\nsummary: an example page\ntokens: 100\n---\n\nBody.\n",
        encoding="utf-8",
    )

    result = scan(wiki, stale_days=90, log_gap_days=14)

    # Structural assertions — top-level keys must be present.
    expected_keys = {
        "wiki",
        "total_pages",
        "orphans",
        "broken_links",
        "stale",
        "missing_frontmatter",
        "missing_tokens",
        "duplicate_titles",
        "log_gap",
        "code_drift",
        "file_map_drift",
        "package_sync_drift",
        "domain_placement",
        "dependency_layer",
        "workflow_hints",
        "concept_kind",
    }
    assert expected_keys.issubset(result.keys()), f"scan() result missing keys: {expected_keys - result.keys()}"

    # Basic type assertions.
    assert isinstance(result["wiki"], str)
    assert isinstance(result["total_pages"], int)
    assert isinstance(result["orphans"], list)
    assert isinstance(result["broken_links"], list)
    assert isinstance(result["stale"], list)
    assert isinstance(result["missing_frontmatter"], list)
    assert isinstance(result["missing_tokens"], list)
    assert isinstance(result["duplicate_titles"], dict)


def _legit_page() -> str:
    """Frontmatter for a fully valid wiki page (no lint findings)."""
    return "---\ntitle: Foo\ncategory: concept\nsummary: a legit page\ntokens: 100\nupdated: 2099-01-01\n---\n\nBody.\n"


def test_schema_files_excluded_from_page_enumeration(tmp_path: Path) -> None:
    """CLAUDE.md and AGENTS.md at the wiki root are schema files, not pages —
    lint must not flag them for missing_frontmatter or missing_tokens, and they
    must not contribute to total_pages."""
    from graph_wiki_core.commands.lint_mechanical import scan

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()

    # Schema files (no frontmatter, plain content).
    (wiki / "CLAUDE.md").write_text("# Project schema\n\nsome notes\n", encoding="utf-8")
    (wiki / "AGENTS.md").write_text("# Agents schema\n\n", encoding="utf-8")

    # One legit page.
    (wiki / "foo.md").write_text(_legit_page(), encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)

    # Neither schema file should appear in lint findings.
    assert "CLAUDE" not in result["missing_frontmatter"]
    assert "AGENTS" not in result["missing_frontmatter"]
    assert "CLAUDE" not in result["missing_tokens"]
    assert "AGENTS" not in result["missing_tokens"]
    # And not in orphans either.
    assert "CLAUDE" not in result["orphans"]
    assert "AGENTS" not in result["orphans"]


def test_schema_files_excluded_at_any_depth(tmp_path: Path) -> None:
    """Forward-compatible: CLAUDE.md and AGENTS.md nested under packages/ etc.
    are also excluded."""
    from graph_wiki_core.commands.lint_mechanical import scan

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()
    pkg_dir = wiki / "packages" / "foo"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "CLAUDE.md").write_text("nested schema\n", encoding="utf-8")
    (pkg_dir / "AGENTS.md").write_text("nested schema\n", encoding="utf-8")
    (wiki / "foo.md").write_text(_legit_page(), encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)

    for finding_list in ("missing_frontmatter", "missing_tokens", "orphans"):
        for key in result[finding_list]:
            assert "CLAUDE" not in key, f"{finding_list} unexpectedly contains schema file: {key}"
            assert "AGENTS" not in key, f"{finding_list} unexpectedly contains schema file: {key}"


def test_code_drift_recognizes_overview_md(tmp_path: Path, monkeypatch) -> None:
    """Code-drift check must match folder-shorthand overview pages
    (``packages/<slug>/overview.md``) against on-disk workspace slugs.

    Regression for the 2026-05-23 lint run, which reported all 7 packages as
    ``missing_in_vault`` and ``packages_in_vault: 0`` because the filter
    compared ``Path(k).name`` to ``"overview.md"`` after ``k`` had already
    been stripped of its ``.md`` suffix.
    """
    from graph_wiki_core.commands import lint_mechanical as lw

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    (wiki / "packages" / "alpha").mkdir(parents=True)
    (wiki / "packages" / "alpha" / "overview.md").write_text(
        "---\ntitle: alpha\ncategory: package\nsummary: alpha package\ntokens: 10\nupdated: 2099-01-01\n---\n\nBody.\n",
        encoding="utf-8",
    )

    # Pretend the on-disk monorepo has one workspace named "alpha".
    monkeypatch.setattr(lw, "_scan_discover", lambda repo, pinned_containers=None: [{"name": "alpha"}])

    result = lw.scan(wiki, stale_days=90, log_gap_days=14, repo_path=tmp_path / "repo")
    cd = result["code_drift"]

    assert cd["packages_on_disk"] == 1
    assert cd["packages_in_vault"] == 1
    assert cd["missing_in_vault"] == []
    assert cd["orphaned_in_vault"] == []


def test_code_drift_recognizes_legacy_pkg_pkg_md(tmp_path: Path, monkeypatch) -> None:
    """Legacy ``<container>/<slug>/<slug>.md`` pages (pre-overview rename) are
    still recognised so old vaults don't regress."""
    from graph_wiki_core.commands import lint_mechanical as lw

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    (wiki / "packages" / "beta").mkdir(parents=True)
    (wiki / "packages" / "beta" / "beta.md").write_text(
        "---\ntitle: beta\ncategory: package\nsummary: beta package\ntokens: 10\nupdated: 2099-01-01\n---\n\nBody.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(lw, "_scan_discover", lambda repo, pinned_containers=None: [{"name": "beta"}])

    result = lw.scan(wiki, stale_days=90, log_gap_days=14, repo_path=tmp_path / "repo")
    cd = result["code_drift"]

    assert cd["packages_in_vault"] == 1
    assert cd["missing_in_vault"] == []


def test_total_pages_excludes_schema_files(tmp_path: Path) -> None:
    """total_pages reflects content pages only, not schema files."""
    from graph_wiki_core.commands.lint_mechanical import scan

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()

    (wiki / "CLAUDE.md").write_text("schema\n", encoding="utf-8")
    (wiki / "AGENTS.md").write_text("schema\n", encoding="utf-8")
    (wiki / "foo.md").write_text(_legit_page(), encoding="utf-8")

    result = scan(wiki, stale_days=90, log_gap_days=14)

    # Only 'foo.md' is a real page.
    assert result["total_pages"] == 1


def test_code_drift_recognizes_entity_pages(tmp_path: Path, monkeypatch) -> None:
    """Code-drift must match entities/ pages (kind: package, uri: pkg:org/repo/<name>)
    against on-disk workspace slugs — the new single-entities-folder layout."""
    from graph_wiki_core.commands import lint_mechanical as lw

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "pkg_alpha.md").write_text(
        "---\ntitle: alpha\nuri: pkg:org/repo/alpha\nkind: package\n"
        "graph_name: alpha\nupdated: 2099-01-01\n---\n\n## Narrative\n_(scanner will populate on next scan)_\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(lw, "_scan_discover", lambda repo, pinned_containers=None: [{"name": "alpha"}])

    result = lw.scan(wiki, stale_days=90, log_gap_days=14, repo_path=tmp_path / "repo")
    cd = result["code_drift"]

    assert cd["packages_on_disk"] == 1
    assert cd["packages_in_vault"] == 1
    assert cd["missing_in_vault"] == []
    assert cd["orphaned_in_vault"] == []


def test_code_drift_unions_packages_across_members(tmp_path: Path, monkeypatch) -> None:
    """In a multi-repo workspace, on-disk package discovery is the UNION across
    every member root. Two members each carrying one package, both listed in the
    vault, must produce ``packages_on_disk == 2`` and no false drift — otherwise
    each sibling repo's package false-flags as ``missing_in_vault``."""
    from graph_wiki_core.commands import lint_mechanical as lw
    from workspace_io import config as ws_config

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    for name in ("alpha", "beta"):
        (wiki / "entities" / f"pkg_{name}.md").write_text(
            f"---\ntitle: {name}\nuri: pkg:org/repo/{name}\nkind: package\n"
            f"graph_name: {name}\nupdated: 2099-01-01\n---\n\n## Narrative\n_(scanner will populate)_\n",
            encoding="utf-8",
        )

    member_a = tmp_path / "repo-a"
    member_b = tmp_path / "repo-b"
    per_member = {member_a: [{"name": "alpha"}], member_b: [{"name": "beta"}]}
    monkeypatch.setattr(lw, "_scan_discover", lambda repo, pinned_containers=None: per_member.get(Path(repo), []))
    monkeypatch.setattr(
        ws_config,
        "resolve",
        lambda cwd=None, require_manifest=True: ws_config.GraphWikiConfig(
            workspace=workspace, repo_root=member_a, members=(member_a, member_b)
        ),
    )

    result = lw.scan(wiki, stale_days=90, log_gap_days=14, repo_path=member_a)
    cd = result["code_drift"]

    assert cd["packages_on_disk"] == 2
    assert cd["packages_in_vault"] == 2
    assert cd["missing_in_vault"] == []
    assert cd["orphaned_in_vault"] == []


def test_entity_pages_use_entity_frontmatter_contract(tmp_path: Path, monkeypatch) -> None:
    """A well-formed entities/ page (title/uri/kind/updated, no category/tokens)
    must NOT be flagged for missing_frontmatter or missing_tokens; a curated
    page still must carry title/category/summary/tokens."""
    from graph_wiki_core.commands import lint_mechanical as lw

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "pkg_alpha.md").write_text(
        "---\ntitle: alpha\nuri: pkg:org/repo/alpha\nkind: package\n"
        "graph_name: alpha\nupdated: 2099-01-01\n---\n\n## Narrative\n_(scanner will populate on next scan)_\n",
        encoding="utf-8",
    )
    # A curated concept page that IS missing summary + tokens — still flagged.
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "bad.md").write_text(
        "---\ntitle: Bad\ncategory: concept\nupdated: 2099-01-01\n---\n\nBody.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(lw, "_scan_discover", lambda repo, pinned_containers=None: [{"name": "alpha"}])

    result = lw.scan(wiki, stale_days=90, log_gap_days=14, repo_path=tmp_path / "repo")

    assert "entities/pkg_alpha" not in result["missing_frontmatter"]
    assert "entities/pkg_alpha" not in result["missing_tokens"]
    # The curated page is still held to the curated contract.
    assert "concepts/bad" in result["missing_frontmatter"]
    assert "concepts/bad" in result["missing_tokens"]


def test_entity_page_without_title_not_flagged_missing_frontmatter(tmp_path: Path, monkeypatch) -> None:
    """The writer never emits `title` on entity pages (the H1 carries the name);
    real pages carry uri/kind/summary/last_updated_commit/tokens and no title.
    Such a page must NOT be flagged missing_frontmatter — only uri/kind are
    required under the entity contract."""
    from graph_wiki_core.commands import lint_mechanical as lw

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    # Frontmatter as the writer actually emits it: no `title`, no `updated`.
    (wiki / "entities" / "pkg_alpha.md").write_text(
        "---\nuri: pkg:org/repo/alpha\nkind: package\nsummary: the alpha package\n"
        "last_updated_commit: abc123\ntokens: 42\n---\n\n## Narrative\n_(scanner will populate on next scan)_\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(lw, "_scan_discover", lambda repo, pinned_containers=None: [{"name": "alpha"}])

    result = lw.scan(wiki, stale_days=90, log_gap_days=14, repo_path=tmp_path / "repo")

    assert "entities/pkg_alpha" not in result["missing_frontmatter"]


def test_wiki_rooted_links_not_broken(tmp_path):
    """[[entities/x]], [[concepts/y]], [[work/z]] all resolve against the
    wiki root → zero broken links."""
    from graph_wiki_core.commands.lint_mechanical import scan

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "work").mkdir(parents=True)

    (wiki / "entities" / "x.md").write_text(
        "---\ntitle: X\nuri: pkg:o/r/x\nkind: package\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "concepts" / "y.md").write_text(
        "---\ntitle: Y\ncategory: concept\nsummary: s\ntokens: 1\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "work" / "z.md").write_text("---\ntitle: Z\ncategory: work\nsummary: s\n---\n\nbody\n", encoding="utf-8")
    (wiki / "concepts" / "hub.md").write_text(
        "---\ntitle: Hub\ncategory: concept\nsummary: s\ntokens: 1\n---\n\n[[entities/x]] [[concepts/y]] [[work/z]]\n",
        encoding="utf-8",
    )

    result = scan(wiki, stale_days=90, log_gap_days=14)

    assert result["broken_links"] == [], result["broken_links"]


def test_all_vault_categories_are_linted(tmp_path):
    """Behavior preservation: a malformed page in every real top-level vault dir
    is flagged for missing frontmatter (i.e. every category is linted)."""
    from graph_wiki_core.commands.lint_mechanical import scan

    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    curated_tops = ["concepts", "adrs", "sources"]
    for top in curated_tops:
        (wiki / top).mkdir(parents=True)
        # missing category + summary → flagged under the curated contract
        (wiki / top / "bad.md").write_text("---\ntitle: B\n---\n\nbody\n", encoding="utf-8")
    # entities/ page missing uri → flagged under the entity contract
    (wiki / "entities").mkdir(parents=True)
    (wiki / "entities" / "bad.md").write_text("---\ntitle: B\nkind: package\n---\n\nbody\n", encoding="utf-8")
    # work/ page missing category + summary → flagged (work is linted)
    (wiki / "work").mkdir(parents=True)
    (wiki / "work" / "bad.md").write_text("---\ntitle: B\n---\n\nbody\n", encoding="utf-8")
    # proposals/ use a distinct contract: kind/mode/target_slug/status.
    # A well-formed proposal is NOT flagged; a malformed one IS.
    (wiki / "proposals").mkdir(parents=True)
    (wiki / "proposals" / "adr-good.md").write_text(
        "---\nkind: adr\nmode: create_new\ntarget_slug: good\n"
        "title: Good\nstatus: proposed\ntokens: 1\norigins: []\n---\nbody\n",
        encoding="utf-8",
    )
    (wiki / "proposals" / "adr-bad.md").write_text(
        "---\nkind: adr\nmode: create_new\ntarget_slug: bad\ntitle: Bad\norigins: []\n---\nbody\n",
        encoding="utf-8",
    )

    result = scan(wiki, stale_days=90, log_gap_days=14)
    mf = set(result["missing_frontmatter"])

    for top in curated_tops:
        assert f"{top}/bad" in mf, f"{top}/bad not linted/flagged: {mf}"
    assert "entities/bad" in mf
    assert "work/bad" in mf
    # Proposal contract: malformed flagged, well-formed not flagged.
    assert "proposals/adr-bad" in mf
    assert "proposals/adr-good" not in mf


def test_proposals_not_orphaned(tmp_path):
    """proposals/ pages are intentionally unlinked; they must not appear in orphans."""
    from graph_wiki_core.commands.lint_mechanical import scan

    wiki = tmp_path / "wiki"
    (wiki / "proposals").mkdir(parents=True)
    (wiki / "proposals" / "adr-my-slug.md").write_text(
        "---\nkind: adr\nmode: create_new\ntarget_slug: my-slug\n"
        "title: My Proposal\nstatus: proposed\norigins: []\n---\nbody\n",
        encoding="utf-8",
    )
    result = scan(wiki, stale_days=90, log_gap_days=14)
    assert "proposals/adr-my-slug" not in result["orphans"]
    assert "proposals/adr-my-slug" not in result["missing_frontmatter"]


def test_proposals_invalid_schema_flagged(tmp_path):
    """proposals/ pages missing required proposal fields are flagged."""
    from graph_wiki_core.commands.lint_mechanical import scan

    wiki = tmp_path / "wiki"
    (wiki / "proposals").mkdir(parents=True)
    # Missing 'status' — a required proposal field
    (wiki / "proposals" / "adr-bad.md").write_text(
        "---\nkind: adr\nmode: create_new\ntarget_slug: bad\ntitle: Bad\norigins: []\n---\nbody\n",
        encoding="utf-8",
    )
    result = scan(wiki, stale_days=90, log_gap_days=14)
    assert "proposals/adr-bad" in result["missing_frontmatter"]
    # Proposals without a `tokens` field surface in missing_tokens (parity with curated pages).
    assert "proposals/adr-bad" in result["missing_tokens"]
