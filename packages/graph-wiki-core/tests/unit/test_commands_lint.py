"""Unit tests for commands/lint.py — LintResult shape, run_lint orchestration, and
mechanical pass behavior (placeholder filter, stale threshold, module calls).

Requirements: CMD-05
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

EDGE_CASE_VAULT = (
    Path(__file__).parent.parent.parent.parent.parent
    / "packages"
    / "wiki-io"
    / "tests"
    / "fixtures"
    / "edge-case-vault"
)


def _workspace_for(tmp_path: Path, vault: Path) -> Path:
    """Return a workspace dir whose `wiki/` is a symlink to `vault`, so
    resolve_wiki_and_repo(workspace) lands the walk on the fixture content."""
    link = tmp_path / "wiki"
    if not link.exists():
        link.symlink_to(vault, target_is_directory=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Test 1: LintResult dataclass shape
# ---------------------------------------------------------------------------


def test_lint_result_dataclass_shape() -> None:
    """LintResult has all required fields."""
    from graph_wiki_core.commands.lint import LintResult

    required_fields = {
        "wiki",
        "total_pages",
        "orphans",
        "broken_links",
        "stale",
        "missing_frontmatter",
        "duplicate_titles",
        "log_gap",
        "code_drift",
        "file_map_drift",
        "package_sync_drift",
        "domain_placement",
        "workflow_hints",
        "semantic_findings",
        "errors",
        "dependency_layer",
        "work_lint_findings",
    }
    field_names = {f.name for f in dataclasses.fields(LintResult)}
    for name in required_fields:
        assert name in field_names, f"LintResult missing field: {name}"


# ---------------------------------------------------------------------------
# Test 2: run_lint finds orphans in edge-case-vault fixture
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_mechanical_finds_orphans_in_fixture(tmp_path) -> None:
    """run_lint against edge-case-vault: result.orphans is a list."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        result = await run_lint(workspace_path=_workspace_for(tmp_path, EDGE_CASE_VAULT))

    assert isinstance(result.orphans, list)
    assert isinstance(result.total_pages, int)
    assert result.total_pages >= 0


# ---------------------------------------------------------------------------
# Test 3: broken_links skips placeholder targets ([[wiki/...]], [[work/<slug>]])
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_broken_links_skip_placeholder_targets(tmp_path: Path) -> None:
    """Placeholder wikilinks [[wiki/...]] and [[work/...]] do not appear in broken_links."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")
    concepts_dir = wiki / "concepts"
    concepts_dir.mkdir()
    # Use the exact placeholder formats: [[wiki/packages/...]] (contains ...) and
    # [[work/<slug>]] (contains < and >). Per _is_placeholder_target(), these are
    # filtered because they contain "...", "<", or ">" tokens.
    (concepts_dir / "test-page.md").write_text(
        "---\ntitle: Test Page\ncategory: concept\nsummary: test\nupdated: 2026-05-14\n---\n\n"
        "[[wiki/packages/...]] placeholder should be ignored (contains ...)\n"
        "[[work/<slug>]] placeholder should be ignored (contains <)\n"
        "[[real-broken]] this is really broken\n",
        encoding="utf-8",
    )

    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        # resolve_wiki_and_repo appends /wiki, so pass the parent.
        result = await run_lint(workspace_path=tmp_path)

    broken_targets = [t for _, t in result.broken_links]
    # Placeholder targets (... or < or >) must NOT appear in broken_links
    for t in broken_targets:
        assert "..." not in t, f"Placeholder target with '...' leaked into broken_links: {t}"
        assert "<" not in t, f"Placeholder target with '<' leaked into broken_links: {t}"
    # The real broken link should appear
    assert any("real-broken" in t for t in broken_targets), (
        f"Expected 'real-broken' in broken_links, got: {result.broken_links}"
    )


# ---------------------------------------------------------------------------
# Test 4: stale_days defaults to 90
# ---------------------------------------------------------------------------


def test_run_lint_stale_days_threshold_default_90() -> None:
    """run_lint has stale_days: int = 90 default."""
    from graph_wiki_core.commands.lint import run_lint

    sig = inspect.signature(run_lint)
    assert "stale_days" in sig.parameters
    assert sig.parameters["stale_days"].default == 90


# ---------------------------------------------------------------------------
# Test 5: log_gap_days defaults to 14
# ---------------------------------------------------------------------------


def test_run_lint_log_gap_days_threshold_default_14() -> None:
    """run_lint has log_gap_days: int = 14 default."""
    from graph_wiki_core.commands.lint import run_lint

    sig = inspect.signature(run_lint)
    assert "log_gap_days" in sig.parameters
    assert sig.parameters["log_gap_days"].default == 14


# ---------------------------------------------------------------------------
# Test 6: all module check() functions are called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_calls_all_module_check_functions(tmp_path: Path) -> None:
    """run_lint calls all lint module check() functions.

    We mock resolve_wiki_and_repo to return a non-None repo path so that all
    module checks are exercised (the repo-dependent checks are guarded by
    repo is not None in _module_pass).
    """
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    mock_dependency = MagicMock(return_value=[])
    mock_domain = MagicMock(return_value=[])
    mock_file_map = MagicMock(return_value=[])
    mock_package_sync = MagicMock(return_value=[])
    mock_workflow = MagicMock(return_value=[])

    with (
        patch("graph_wiki_core.commands.lint.resolve_wiki_and_repo", return_value=(wiki, repo)),
        patch("graph_wiki_core.commands.lint.check_dependency_layer", mock_dependency),
        patch("graph_wiki_core.commands.lint.check_domain_placement", mock_domain),
        patch("graph_wiki_core.commands.lint.check_file_map_drift", mock_file_map),
        patch("graph_wiki_core.commands.lint.check_package_sync_drift", mock_package_sync),
        patch("graph_wiki_core.commands.lint.check_workflow_hints", mock_workflow),
        patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool,
    ):
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        await run_lint(workspace_path=wiki)

    assert mock_dependency.called, "check_dependency_layer not called"
    assert mock_domain.called, "check_domain_placement not called"
    assert mock_file_map.called, "check_file_map_drift not called"
    assert mock_package_sync.called, "check_package_sync_drift not called"
    assert mock_workflow.called, "check_workflow_hints not called"


# ---------------------------------------------------------------------------
# Test 7: semantic fan-out runs 3 groups with role="linter"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_semantic_fanout_3_groups(tmp_path: Path) -> None:
    """SubagentPool.run_all is called once with 3 items and role='linter'."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    captured_calls: list[dict] = []

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool

        async def capture_run_all(items, task, role, *, model_id, max_concurrency, **kwargs):
            captured_calls.append({"items": list(items), "role": role})
            return FanOutResult(
                successes=[(item, []) for item in items],
                errors=[],
            )

        mock_pool.run_all = capture_run_all
        await run_lint(workspace_path=wiki)

    assert len(captured_calls) == 1, f"Expected 1 run_all call, got {len(captured_calls)}"
    assert captured_calls[0]["role"] == "linter"
    assert len(captured_calls[0]["items"]) == 3, f"Expected 3 semantic groups, got {len(captured_calls[0]['items'])}"


# ---------------------------------------------------------------------------
# Test 8: semantic errors surface in result.errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_semantic_errors_surface_in_result_errors(tmp_path: Path) -> None:
    """If semantic fan-out has PerItemError entries, they appear in result.errors."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")

    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult, PerItemError

    stale_group = ("stale_claims", "sys", [])

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(
            return_value=FanOutResult(
                successes=[],
                errors=[PerItemError(item=stale_group, exception=RuntimeError("Bedrock error"))],
            )
        )
        result = await run_lint(workspace_path=wiki)

    assert len(result.errors) >= 1
    # Error message should contain something about the failure
    assert any("Bedrock error" in e or "stale_claims" in e for e in result.errors), (
        f"Expected error message containing 'Bedrock error' or 'stale_claims', got: {result.errors}"
    )


# ---------------------------------------------------------------------------
# Test 9: no write-back to vault
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_no_write_back_to_vault(tmp_path: Path) -> None:
    """Vault directory contents are unchanged after run_lint (D-10)."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(
        "# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n",
        encoding="utf-8",
    )
    (wiki / "index.md").write_text("# Index\n", encoding="utf-8")
    concepts_dir = wiki / "concepts"
    concepts_dir.mkdir()
    (concepts_dir / "my-page.md").write_text(
        "---\ntitle: My Page\ncategory: concept\nsummary: test\n---\n\nContent.\n",
        encoding="utf-8",
    )

    def _dir_hash(directory: Path) -> str:
        h = hashlib.sha256()
        for p in sorted(directory.rglob("*")):
            if p.is_file():
                h.update(str(p.relative_to(directory)).encode())
                h.update(p.read_bytes())
        return h.hexdigest()

    before_hash = _dir_hash(wiki)

    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        await run_lint(workspace_path=wiki)

    after_hash = _dir_hash(wiki)
    assert before_hash == after_hash, "Vault was modified by run_lint (D-10 violation)"


# ---------------------------------------------------------------------------
# Test 10: open_proposals count in LintResult
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_lint_reports_open_proposals_count(tmp_path: Path) -> None:
    """LintResult.open_proposals counts notes at status: proposed (spec §3.7)."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult
    from wiki_io.proposals import set_proposal_status, upsert_proposal

    workspace = tmp_path / "wiki"
    workspace.mkdir()
    wiki = workspace / "wiki"
    wiki.mkdir()
    (workspace / "CLAUDE.md").write_text("# wiki\n\n```yaml\nversion: 1\ncontainers: []\n```\n", encoding="utf-8")
    (workspace / "index.md").write_text("# Index\n", encoding="utf-8")

    # Two proposed + one approved → open count is 2.
    # proposals must be written into the resolved wiki dir (workspace/wiki/).
    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "a",
            "title": "A",
            "origin": {"ref": "sources/s", "source": "ingest", "rationale": "r"},
        },
    )
    upsert_proposal(
        wiki,
        {
            "kind": "adr",
            "mode": "create_new",
            "target_slug": "b",
            "title": "B",
            "origin": {"ref": "sources/s", "source": "ingest", "rationale": "r"},
        },
    )
    upsert_proposal(
        wiki,
        {
            "kind": "concept",
            "mode": "create_new",
            "target_slug": "c",
            "title": "C",
            "origin": {"ref": "sources/s", "source": "ingest", "rationale": "r"},
        },
    )
    set_proposal_status(wiki, "concept", "c", "approved")

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        result = await run_lint(workspace_path=workspace)

    assert result.open_proposals == 2


def test_lint_result_has_open_proposals_field() -> None:
    import dataclasses

    from graph_wiki_core.commands.lint import LintResult

    fields = {f.name for f in dataclasses.fields(LintResult)}
    assert "open_proposals" in fields


@pytest.mark.asyncio
async def test_run_lint_wiki_rooted_links_not_broken(tmp_path) -> None:
    """[[entities/x]] / [[concepts/y]] / [[work/z]] resolve against the wiki
    root → result.broken_links is empty."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "work").mkdir(parents=True)
    (wiki / "entities" / "x.md").write_text(
        "---\ntitle: X\ncategory: entity\nsummary: s\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "concepts" / "y.md").write_text(
        "---\ntitle: Y\ncategory: concept\nsummary: s\n---\n\nbody\n", encoding="utf-8"
    )
    (wiki / "work" / "z.md").write_text("---\ntitle: Z\ncategory: work\nsummary: s\n---\n\nbody\n", encoding="utf-8")
    (wiki / "concepts" / "hub.md").write_text(
        "---\ntitle: Hub\ncategory: concept\nsummary: s\n---\n\n[[entities/x]] [[concepts/y]] [[work/z]]\n",
        encoding="utf-8",
    )

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        # workspace_path=tmp_path → resolve appends /wiki → wiki dir above.
        result = await run_lint(workspace_path=tmp_path)

    assert result.broken_links == [], result.broken_links


@pytest.mark.asyncio
async def test_run_lint_all_vault_categories_linted(tmp_path) -> None:
    """A malformed page in every real top-level vault dir is flagged for
    missing frontmatter (every category is linted after the rebase)."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    wiki = tmp_path / "wiki"
    tops = ["concepts", "adrs", "sources", "entities", "proposals", "work"]
    for top in tops:
        (wiki / top).mkdir(parents=True)
        (wiki / top / "bad.md").write_text("---\ntitle: B\n---\n\nbody\n", encoding="utf-8")

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        result = await run_lint(workspace_path=tmp_path)

    mf = set(result.missing_frontmatter)
    for top in tops:
        assert f"{top}/bad" in mf, f"{top}/bad not flagged (not linted): {mf}"


@pytest.mark.asyncio
async def test_run_lint_excludes_archived_curated_pages_from_orphans_and_stale(tmp_path) -> None:
    """Archived adrs/concepts/proposals pages are valid wikilink targets but are
    NOT flagged as orphans or stale by the live lint path (run_lint -> _mechanical_pass).
    Regression for the work-only `_archive/` guard that left curated archives linted."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    wiki = tmp_path / "wiki"
    (wiki / "adrs" / "_archive").mkdir(parents=True)
    (wiki / "concepts" / "_archive").mkdir(parents=True)
    # Active ADR links to an archived ADR by its archived path.
    (wiki / "adrs" / "0009-live.md").write_text(
        "---\ntitle: Live\ncategory: adr\nsummary: x\nupdated: 2026-06-01\n---\n\nSee [[adrs/_archive/0003-old]].\n",
        encoding="utf-8",
    )
    # Archived ADR with an ancient `updated` — would be stale-checked if still linted.
    (wiki / "adrs" / "_archive" / "0003-old.md").write_text(
        "---\ntitle: Old\ncategory: adr\nsummary: x\nupdated: 2000-01-01\n---\n\nbody\n",
        encoding="utf-8",
    )
    # Archived concept with no inbound link — would be flagged orphan if still linted.
    (wiki / "concepts" / "_archive" / "retired.md").write_text(
        "---\ntitle: Retired\ncategory: concept\nsummary: x\nupdated: 2026-06-01\n---\n\nbody\n",
        encoding="utf-8",
    )

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        result = await run_lint(workspace_path=tmp_path)

    # Excluded from orphan enumeration (absent from the pages dict).
    assert "concepts/_archive/retired" not in result.orphans
    # Excluded from stale enumeration despite the ancient `updated`.
    assert all("_archive" not in str(p) for p, _ in result.stale)
    # Still a valid wikilink target → the inbound link is not broken.
    assert not any("0003-old" in t for _, t in result.broken_links)


@pytest.mark.asyncio
async def test_run_lint_surfaces_guidance_findings(tmp_path) -> None:
    """An invalid guidance page is reported in LintResult.guidance_lint_findings."""
    from graph_wiki_core.commands.lint import run_lint
    from subagent_runtime.pool import FanOutResult

    g = tmp_path / "wiki" / "guidance" / "model-adapter"
    g.mkdir(parents=True)
    # Missing required keys + wrong category -> guidance-invalid-frontmatter.
    (g / "bad.md").write_text("---\ntitle: X\ncategory: concept\n---\n\nbody\n", encoding="utf-8")

    with patch("graph_wiki_core.commands.lint.SubagentPool") as MockPool:
        mock_pool = MagicMock()
        MockPool.return_value = mock_pool
        mock_pool.run_all = AsyncMock(return_value=FanOutResult(successes=[], errors=[]))
        result = await run_lint(workspace_path=tmp_path)

    rule_ids = {f["rule_id"] for f in result.guidance_lint_findings}
    assert "guidance-invalid-frontmatter" in rule_ids
    # error-severity guidance findings escalate into result.errors
    assert any("model-adapter/bad" in e for e in result.errors)


def test_mechanical_pass_flags_stale_raw_source_path(tmp_path: Path) -> None:
    from graph_wiki_core.commands.lint import _mechanical_pass

    ws = tmp_path
    wiki = ws / "wiki"
    (wiki / "sources").mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")
    (ws / "raw" / "_archive" / "specs").mkdir(parents=True)
    (ws / "raw" / "_archive" / "specs" / "live.md").write_text("x", encoding="utf-8")

    def _page(slug: str, source_path: str) -> None:
        (wiki / "sources" / f"{slug}.md").write_text(
            f"---\ntitle: {slug}\ncategory: source\nsummary: s\nsource_path: {source_path}\n---\n\nbody\n",
            encoding="utf-8",
        )

    _page("stale", "raw/specs/gone.md")  # raw/ path, missing -> flagged
    _page("archived", "raw/_archive/specs/live.md")  # archived, exists -> not flagged
    _page("indoc", "docs/architecture.md")  # repo-relative doc -> not flagged

    mech = _mechanical_pass(wiki, stale_days=9999, log_gap_days=9999)
    assert mech["source_path_drift"] == ["sources/stale"]
