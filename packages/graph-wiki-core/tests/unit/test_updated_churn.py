"""Living Wiki M2c #3: a no-op rescan buckets populated pages `unchanged`
(scanner-body churn no longer forces `updated`)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes

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
            "('package', 'pkg-a', 'packages/pkg-a', NULL, "
            "'{\"language\": \"python\"}', 'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


def _fanout_spy(*, prose):
    """narrator items -> prose(item); code_reader items -> JSON filling each
    TODO path (so file maps reach a steady, fully-described state)."""

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, prose(it)) for it in items]
        else:
            result.successes = [(it, json.dumps({p: f"desc {p}" for p in it[3]})) for it in items]
        return result

    return _run_all


@pytest.fixture
def churn_workspace(tmp_path, monkeypatch):
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
        lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock())
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
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
        _fanout_spy(prose=lambda it: f"PROSE for {it[0]}"),
    )
    return workspace


def _page(wiki: Path, uri: str = _PKG_A) -> Path:
    return next(p for p in (wiki / "entities").glob("*.md") if _fm.load(p).metadata.get("uri") == uri)


def test_no_op_rescan_reports_zero_updated(churn_workspace, monkeypatch) -> None:
    """[spec test 5] A second scan with no repo change buckets the populated
    page `unchanged`; its content is byte-identical (not rewritten to
    placeholder)."""
    workspace = churn_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    # Scan 1 fills Narrative + File-map row.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text1 = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text1
    assert "desc mod.py" in text1

    # Scan 2: nothing changed since head1.
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    result = asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert result.entities_updated == []  # the fix: no churn
    text2 = _page(wiki).read_text(encoding="utf-8")
    assert text2 == text1  # byte-identical, not rewritten
    assert "_(scanner will populate on next scan)_" not in text2


def test_human_section_edit_is_preserved_not_churned(churn_workspace, monkeypatch) -> None:
    """[spec test 6, adapted] A hand-edit to a human-owned `## Purpose` body
    SURVIVES a no-op rescan and is never churned back to the template
    placeholder.

    DEVIATION from the plan's literal assertion (`updated` is set): in the full
    scan pipeline `_merge_preserved_sections` losslessly re-syncs human-owned
    sections from disk into the freshly-rendered page, so a hand-edited
    `## Purpose` body makes the new render byte-identical to disk (modulo scanner
    bodies) → the page correctly buckets `unchanged` and the write is skipped.
    The genuine anti-data-loss intent of spec test 6 — the human edit is not
    lost and not overwritten by the placeholder — is what is asserted here.
    Under M2d PTO the page renders byte-identical to disk (the merge preserves
    every section), so the plain `old_bytes == new_bytes` compare buckets it
    `unchanged` and skips the write.
    """
    workspace = churn_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    # Hand-edit the human-owned `## Purpose` body on disk.
    page = _page(wiki)
    edited = page.read_text(encoding="utf-8").replace("## Purpose", "## Purpose\nHUMAN EDIT MARKER", 1)
    page.write_text(edited, encoding="utf-8")

    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    text = _page(wiki).read_text(encoding="utf-8")
    assert "HUMAN EDIT MARKER" in text  # edit survives
    assert "_(scanner will populate on next scan)_" not in text  # not churned to placeholder


def test_frontmatter_only_change_forces_updated(churn_workspace, monkeypatch) -> None:
    """[spec test 7] A scanner-frontmatter delta forces `updated` even with
    identical bodies."""
    workspace = churn_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    # Mutate the graph: change the package language (a scanner-owned fm key).
    conn = sqlite3.connect(workspace / ".graph-wiki" / "code.db")
    try:
        conn.execute("UPDATE nodes SET attrs_json='{\"language\": \"rust\"}' WHERE uri='pkg:org/repo/pkg-a'")
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    result = asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _PKG_A in result.entities_updated
    assert _fm.load(_page(wiki)).metadata.get("language") == "rust"


def test_idempotence_across_all_three_scanner_sections(churn_workspace, monkeypatch) -> None:
    """[spec test 8] A page with a filled Narrative + File map (the two
    expensive scanner sections) rescans to `unchanged`; prose + descriptions
    survive."""
    workspace = churn_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    result = asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert result.entities_updated == []
    text = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text
    assert "desc mod.py" in text
