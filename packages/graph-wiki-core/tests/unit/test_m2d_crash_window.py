"""Living Wiki M2d §5 test 10: a mid-pipeline inject failure leaves real
scanner content on disk (PTO closes the placeholder crash-window)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes
from graph_wiki_core.commands import scan_bedrock as scan_bedrock_mod
from subagent_runtime.pool import SubagentPool as _SubagentPool

from ._spies import patch_repo_state

_PKG_A = "pkg:org/repo/pkg-a"

_FILE_MAP = (
    "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
    "| Path | Kind | Description |\n|---|---|---|\n"
    "| `mod.py` | file | — TODO |\n"
)


def _seed_one_package(db_path: Path) -> None:
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('repository', 'repo', NULL, NULL, '{\"uri\": \"repo:org/repo\"}', 'repo:org/repo')"
        )
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, "
            "'{\"language\": \"python\"}', 'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


def _fanout_spy():
    from ._spies import refresh_all_spy

    return refresh_all_spy(lambda t: f"PROSE for {t.uri}")


@pytest.fixture
def crash_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(workspace / ".graph-wiki" / "code.db")
    monkeypatch.setattr(
        scan_mod,
        "_cg_run_build",
        lambda repo, ws, *, full, scope_to_repo=True: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(scan_bedrock_mod, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(
        scan_mod,
        "build_file_map",
        lambda path, **kw: _FILE_MAP if str(path).endswith("pkg-a") else None,
    )
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(_SubagentPool, "run_all", _fanout_spy())
    return workspace


def _page(wiki: Path) -> Path:
    return next(p for p in (wiki / "entities").glob("*.md") if _fm.load(p).metadata.get("uri") == _PKG_A)


def test_mid_pipeline_inject_failure_leaves_real_content(crash_workspace, monkeypatch):
    """[spec §5 test 10] After scan 1 fills the page, a scan 2 whose inject
    steps all raise must leave the scan-1 prose + descriptions intact — no
    `## Narrative` placeholder is ever exposed on disk."""
    workspace = crash_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    # Scan 1: fill Narrative + File-map row.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text1 = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text1
    assert "desc mod.py" in text1

    # Scan 2: force the page commit-dirty (so the inject steps run) and make
    # BOTH inject steps raise mid-pipeline.
    patch_repo_state(monkeypatch, scan_mod, ["packages/pkg-a/mod.py"])

    def _boom(*a, **k):
        raise RuntimeError("simulated mid-pipeline failure")

    monkeypatch.setattr(scan_mod, "replace_prose_sections", _boom)
    monkeypatch.setattr(scan_mod, "inject_file_map", _boom)

    # The scan completes (per-page failures are isolated, not fatal).
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    text2 = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text2  # prose survived
    assert "desc mod.py" in text2  # description survived
    assert "_(scanner will populate on next scan)_" not in text2  # no placeholder exposed


def test_crash_before_stamp_retasks_via_first_fill(crash_workspace, monkeypatch):
    """[Task 6 stamp gate] A scan-1 apply crash between inject and stamp leaves
    the page with its placeholder narrative and NO anchor; the NEXT scan
    re-tasks the entity as first_fill (missing anchor / placeholder page)."""
    workspace = crash_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    # Scan 1: the prose injection raises for every page -> no prose lands, and
    # the stamp gate must not mint an anchor for the unhealthy page.
    boom = {"on": True}

    def _maybe_boom(*a, **k):
        if boom["on"]:
            raise RuntimeError("simulated crash before stamp")
        raise AssertionError("unexpected call")

    monkeypatch.setattr(scan_mod, "replace_prose_sections", _maybe_boom)
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    page = _page(wiki)
    text = page.read_text(encoding="utf-8")
    assert "_(scanner will populate on next scan)_" in text  # placeholder still exposed
    assert _fm.load(page).metadata.get("last_updated_commit") is None  # no anchor minted

    # The NEXT emit re-tasks the entity via first_fill.
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    task = next(t for t in worklist.prose_tasks if t.uri == _PKG_A)
    assert task.trigger == "first_fill"
