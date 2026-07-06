"""Scan auto-wires token stamping (bug: token-count-field-never-populated).

The narrated path must call `update_vault` over the resolved wiki so freshly
written pages get real `tokens` counts; the structural-only (`narrate=False`)
plugin path must NOT — token counting uses Bedrock CountTokens and that branch
runs without AWS access.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from graph_io import exit_codes
from graph_wiki_core.commands import scan as scan_module


def _seed_minimal_graph(db_path: Path) -> None:
    """One package node pkg-a, uri pkg:org/repo/pkg-a."""
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
            "('package', 'pkg-a', 'packages/pkg-a', NULL, '{\"language\": \"python\"}', "
            "'pkg:org/repo/pkg-a')"
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def tmp_workspace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n\nNo pinned containers.\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    return workspace


def _stub_pipeline(monkeypatch):
    """Stub the cg build, state gate, and Bedrock fan-out so run_scan completes offline."""
    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, ws, *, full, scope_to_repo=True: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )

    async def _empty_run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        return FanOutResult()

    monkeypatch.setattr(scan_module.SubagentPool, "run_all", _empty_run_all)
    monkeypatch.setattr(scan_module, "make_llm", lambda role, *, model_override=None: MagicMock())


def test_narrated_scan_stamps_tokens(tmp_workspace, monkeypatch):
    """run_scan(narrate=True) calls update_vault over the resolved wiki."""
    workspace = tmp_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    _seed_minimal_graph(workspace / ".graph-wiki" / "code.db")
    _stub_pipeline(monkeypatch)

    calls: list = []
    monkeypatch.setattr(
        scan_module,
        "update_vault",
        lambda w, ct, **kw: calls.append(w) or {"updated": [], "unchanged": [], "skipped": []},
        raising=False,
    )

    asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    assert calls == [wiki]


def test_structural_scan_does_not_stamp_tokens(tmp_workspace, monkeypatch):
    """run_scan(narrate=False) never calls update_vault (no Bedrock on the plugin path)."""
    workspace = tmp_workspace
    repo = workspace / "repo"
    _seed_minimal_graph(workspace / ".graph-wiki" / "code.db")
    monkeypatch.setattr(
        scan_module, "_cg_run_build", lambda repo, ws, *, full, scope_to_repo=True: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(
        scan_module,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "x"},
    )

    calls: list = []
    monkeypatch.setattr(scan_module, "update_vault", lambda w, ct, **kw: calls.append(w), raising=False)

    asyncio.run(scan_module.run_scan(workspace_path=workspace, repo_path=repo, narrate=False))

    assert calls == []


@pytest.fixture(autouse=True)
def _offline_count_tokens():
    """Shadow the parent conftest's autouse `_offline_count_tokens` fixture for
    this file only: the two identity tests below need the *real*, unpatched
    `count_tokens` binding to verify it. Safe to skip the stub here — the two
    scan-behavior tests above replace `update_vault` wholesale, so they never
    invoke the real (possibly live-Bedrock) counter regardless."""
    yield


def test_scan_module_uses_graph_io_count_tokens() -> None:
    """scan.py's `count_tokens` binding is the real graph-io offline tiktoken
    counter, not a stand-in — the only thing enforcing this is import-time
    identity, since every other test here monkeypatches it before running."""
    from graph_io.tokens import count_tokens

    assert scan_module.count_tokens is count_tokens


def test_query_module_uses_graph_io_count_tokens() -> None:
    """query.py's `count_tokens` binding (prompt/context budgeting) is the real
    graph-io offline tiktoken counter, not a stand-in."""
    from graph_io.tokens import count_tokens
    from graph_wiki_core.commands import query as query_module

    assert query_module.count_tokens is count_tokens
