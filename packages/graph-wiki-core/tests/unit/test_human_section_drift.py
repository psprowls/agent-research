"""Living Wiki M2e: intra-page human-section drift flagging (spec §5)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes

_PKG_A = "pkg:org/repo/pkg-a"


def _seed_one_package(db_path: Path) -> None:
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\": \"python\"}', "
            "'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


def _page_for(wiki: Path, uri: str = _PKG_A):
    return next(
        p for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == uri
    )


@pytest.fixture
def ws(tmp_path, monkeypatch):
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
        scan_mod, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(
        scan_mod, "build_file_map",
        lambda path, **kw: (
            "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
            "| Path | Kind | Description |\n|---|---|---|\n"
            "| `pyproject.toml` | file | — TODO |\n"
            if str(path).endswith("pkg-a") else None
        ),
    )
    return workspace


def _spy(verdict_fn, *, recorder: dict | None = None):
    """Async SubagentPool.run_all replacement covering all three roles.

    narrator -> prose; code_reader -> JSON filling every TODO row; drift_judge ->
    verdict_fn(item). When `recorder` is given, records the drift_judge items so a
    test can assert the judge was (not) called.
    """
    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [(it, f"PROSE for {it[0]}") for it in items]
        elif role == "code_reader":
            import json as _json
            result.successes = [
                (it, _json.dumps({p: f"desc {p}" for p in it[3]})) for it in items
            ]
        elif role == "drift_judge":
            if recorder is not None:
                recorder.setdefault("drift_items", []).extend(items)
            result.successes = [(it, verdict_fn(it)) for it in items]
        return result

    return _run_all


def _add_human_section(page: Path, heading: str, body: str) -> None:
    text = page.read_text(encoding="utf-8")
    page.write_text(text.rstrip("\n") + f"\n\n{heading}\n{body}\n", encoding="utf-8")


def test_renarrated_stale_section_is_flagged(ws, monkeypatch):
    """[§5.1] commit-dirty entity + stale human section -> drift_review entry;
    drift_checked_commit advances to last_updated_commit."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))

    # Scan 1: page created + narrated + anchored at head1.
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    # Use a heading distinct from the template-seeded human sections
    # (`## Purpose`, `## Public API`) so the appended curated section survives the
    # preserve-merge instead of colliding with the duplicate template heading.
    _add_human_section(page, "## Behavior", "Processes items synchronously.")

    # Scan 2: code changed (head2) -> re-narrate -> judge says stale.
    heads["v"] = "head2"
    monkeypatch.setattr(scan_mod, "changed_files_since",
                        lambda repo, sha, sub: ["packages/pkg-a/mod.py"])
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _spy(lambda it: {"stale": True, "reason": "now async"}),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    meta = _fm.load(_page_for(wiki)).metadata
    assert meta["drift_checked_commit"] == "head2"
    assert meta["last_updated_commit"] == "head2"
    review = meta["drift_review"]
    # The scanner page template seeds human sections (`## Purpose`,
    # `## Public API`); the appended `## Behavior` carries the stale prose. The
    # verdict_fn marks every section stale, so the contract under test is that
    # the Behavior section is flagged with the right fields (not an exact count).
    behavior = next(e for e in review if e["section"] == "Behavior")
    assert behavior["detected_commit"] == "head2"
    assert behavior["reason"] == "now async"
    assert behavior["hash"]  # non-empty sha
    # Prose itself is untouched (flag-only).
    assert "Processes items synchronously." in _page_for(wiki).read_text(encoding="utf-8")


def test_already_checked_entity_skips_judge(ws, monkeypatch):
    """[§5.2/§5.4] narrative unchanged + drift_checked_commit == last_updated_commit
    -> no drift_judge call, no frontmatter change."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    _add_human_section(_page_for(wiki), "## Purpose", "p")

    # Re-scan, no code change -> narrative not regenerated.
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    rec: dict = {}
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": True, "reason": "x"}, recorder=rec))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    assert rec.get("drift_items", []) == []  # judge never ran
    assert "drift_review" not in _fm.load(_page_for(wiki)).metadata
    # First scan set drift_checked_commit == last_updated_commit already.
    assert _fm.load(_page_for(wiki)).metadata["drift_checked_commit"] == "head1"


def test_fresh_verdict_no_flag_but_checked_advances(ws, monkeypatch):
    """[§5.3] not-stale verdict -> no drift_review entry, but drift_checked_commit
    == last_updated_commit (so it won't re-judge next scan)."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all",
                        _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    meta = _fm.load(_page_for(wiki)).metadata
    assert "drift_review" not in meta
    assert meta["drift_checked_commit"] == meta["last_updated_commit"] == "head1"
