"""Living Wiki M2d §5 test 10: a mid-pipeline inject failure leaves real
scanner content on disk (PTO closes the placeholder crash-window)."""

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


def _fanout_spy():
    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, f"PROSE for {it[0]}") for it in items]
        else:
            result.successes = [
                (it, json.dumps({p: f"desc {p}" for p in it[3]})) for it in items
            ]
        return result

    return _run_all


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
    _seed_one_package(workspace / ".graph" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build",
        lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(
        scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock()
    )
    monkeypatch.setattr(
        scan_mod, "build_file_map",
        lambda path, **kw: (_FILE_MAP if str(path).endswith("pkg-a") else None),
    )
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _fanout_spy())
    return workspace


def _page(wiki: Path) -> Path:
    return next(
        p for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == _PKG_A
    )


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
    monkeypatch.setattr(
        scan_mod, "changed_files_since", lambda *a: ["packages/pkg-a/mod.py"]
    )

    def _boom(*a, **k):
        raise RuntimeError("simulated mid-pipeline failure")

    monkeypatch.setattr(scan_mod, "inject_narrative", _boom)
    monkeypatch.setattr(scan_mod, "inject_file_map", _boom)

    # The scan completes (per-page failures are isolated, not fatal).
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    text2 = _page(wiki).read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text2          # prose survived
    assert "desc mod.py" in text2                            # description survived
    assert "_(scanner will populate on next scan)_" not in text2  # no placeholder exposed
