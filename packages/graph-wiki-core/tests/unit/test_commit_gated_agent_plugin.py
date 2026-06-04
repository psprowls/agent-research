"""Living Wiki agent_plugin M2 parity — D2.2: commit-gated narrative re-render.

Tests 8–11 from the agent-plugin parity spec (agent-plugin-m2-parity branch).

ACCEPTED LIMITATION (decision D-C, shared with package/app/test_suite):
  An *existing* agent_plugin page with NO ``last_updated_commit`` anchor is
  skipped by ``_commit_dirty_changes`` (``if not anchor: continue``). Such a
  page re-renders byte-identical on the next scan → buckets ``unchanged`` →
  not in ``needs_narrative`` → not re-narrated → anchor is never stamped by
  this path. The spec's original test-11 mechanism ("unknown-anchor branch
  treats no-anchor as dirty") was inaccurate. Per the maintainer's decision
  we do NOT add anchorless self-heal code; the limitation is accepted.
  New plugins (no page on disk at all) are unaffected: they create → bucket
  as ``needs_narrative`` → narrate → stamp → future scans are commit-gated.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes, schema
from graph_io.agent_plugins import emit as _ap_emit
from graph_io.uri import RepoContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CTX = RepoContext(org="org", repo="repo")
_PLUGIN_URI = "agent_plugin:org/repo/demo"


def _make_plugin(repo: Path, *, commands: list[str]) -> Path:
    """Lay down a plugin tree under repo/plugins/demo with the given commands."""
    pdir = repo / "plugins" / "demo"
    (pdir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (pdir / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "name": "demo", "version": "1.0.0", "description": "Demo plugin.",
    }))
    cmds_dir = pdir / "commands"
    cmds_dir.mkdir(exist_ok=True)
    for cmd in commands:
        (cmds_dir / f"{cmd}.md").write_text(
            f"---\nname: {cmd}\ndescription: Command {cmd}.\n---\n# /demo:{cmd}\n"
        )
    return pdir


def _emit_plugin(db_path: Path, repo: Path) -> None:
    """Emit (upsert) the plugin layout from repo into db_path."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        _ap_emit(conn, repo_root=repo, ctx=_CTX)
        conn.commit()
    finally:
        conn.close()


def _page(wiki: Path, uri: str = _PLUGIN_URI) -> Path:
    """Return the entity page Path for uri (searches entities/ by frontmatter)."""
    return next(
        p
        for p in (wiki / "entities").glob("*.md")
        if _fm.load(p).metadata.get("uri") == uri
    )


def _narrate_spy(heads: dict):
    """SubagentPool.run_all spy: narrates every narrator item with prose encoding the HEAD.

    The code_reader branch never actually fires for these tests: the code-reader
    fan-out is driven by `file_mapped_pages`, which is populated only for
    package/app (via fm_list_fns) and test_suite nodes. The workspace's only node
    is the agent_plugin, so no describer item is ever produced. The branch is kept
    as a harmless/defensive no-op.
    """

    async def _run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            result.successes = [
                (it, f"PROSE {it[0]} @ {heads['v']}") for it in items
            ]
        else:
            # code_reader — item == (uri, ws_dict, page_path, todo_paths)
            result.successes = [
                (it, json.dumps({p: f"desc {p}" for p in it[3]})) for it in items
            ]
        return result

    return _run_all


@pytest.fixture
def plugin_workspace(tmp_path, monkeypatch):
    """Workspace with a single agent_plugin 'demo' (one command: 'alpha')."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))

    _make_plugin(repo, commands=["alpha"])
    _emit_plugin(workspace / ".graph" / "code.db", repo)

    monkeypatch.setattr(
        scan_mod, "_cg_run_build",
        lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""),
    )
    monkeypatch.setattr(
        scan_mod, "make_llm",
        lambda role, *, model_override=None: MagicMock(),
    )
    return workspace


# ---------------------------------------------------------------------------
# Test 8 — command added → table refresh + re-narrate + anchor advance
# ---------------------------------------------------------------------------


def test_command_added_refreshes_table_and_renarrates(
    plugin_workspace, monkeypatch
) -> None:
    """[Test 8] Scan 1 (head1): plugin has command 'alpha'.
    Add command 'beta'; re-emit graph; head2; changed_files_since non-empty.
    Scan 2: '## Commands' table refreshed (Gap A / D1), prose updated to
    @ head2 (Gap B), last_updated_commit == 'head2' (Gap C).
    """
    workspace = plugin_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    db_path = workspace / ".graph" / "code.db"

    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _narrate_spy(heads),
    )

    # --- Scan 1 ---
    asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )
    text1 = _page(wiki).read_text(encoding="utf-8")
    assert "alpha" in text1, "alpha command should appear in ## Commands"
    assert "beta" not in text1
    assert f"PROSE {_PLUGIN_URI} @ head1" in text1
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    # --- Add command 'beta'; re-emit; advance HEAD ---
    _make_plugin(repo, commands=["alpha", "beta"])
    _emit_plugin(db_path, repo)
    heads["v"] = "head2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["plugins/demo/commands/beta.md"],
    )

    # --- Scan 2 ---
    asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )
    text2 = _page(wiki).read_text(encoding="utf-8")

    # Gap A / D1: table refreshed
    assert "beta" in text2, "beta command should appear in ## Commands after scan 2"
    # Gap B: prose re-narrated at head2
    assert f"PROSE {_PLUGIN_URI} @ head2" in text2
    assert f"PROSE {_PLUGIN_URI} @ head1" not in text2
    # Gap C: anchor advanced
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head2"


# ---------------------------------------------------------------------------
# Test 9 — no-op rescan stays unchanged
# ---------------------------------------------------------------------------


def test_noop_rescan_stays_unchanged(plugin_workspace, monkeypatch) -> None:
    """[Test 9] Scan 1 (head1) creates + narrates + stamps.
    Scan 2 with same HEAD, no file change, unchanged graph → byte-identical
    page; narrator NOT called for the plugin; anchor still 'head1'.
    """
    workspace = plugin_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    narrator_calls: list = []

    async def _spy_run_all(self, *, items, task, role, model_id, max_concurrency):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if role == "narrator":
            narrator_calls.append([it[0] for it in items])
            result.successes = [
                (it, f"PROSE {it[0]} @ {heads['v']}") for it in items
            ]
        else:
            result.successes = [
                (it, json.dumps({p: f"desc {p}" for p in it[3]})) for it in items
            ]
        return result

    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy_run_all)

    # --- Scan 1 ---
    asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )
    page_bytes_after_scan1 = _page(wiki).read_bytes()
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"
    calls_after_scan1 = len(narrator_calls)
    assert calls_after_scan1 >= 1  # plugin was narrated in scan 1

    # Reset calls tracking for scan 2
    narrator_calls.clear()

    # --- Scan 2: same HEAD, no file changes ---
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: [],
    )
    asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )

    # Page bytes must be byte-identical
    assert _page(wiki).read_bytes() == page_bytes_after_scan1

    # Narrator must NOT have been called for the plugin URI in scan 2
    plugin_uris_narrated_scan2 = [
        uri for call in narrator_calls for uri in call if _PLUGIN_URI in uri
    ]
    assert plugin_uris_narrated_scan2 == [], (
        f"narrator should not re-narrate {_PLUGIN_URI} on a no-op scan; "
        f"got calls: {narrator_calls}"
    )

    # Anchor unchanged
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"


# ---------------------------------------------------------------------------
# Test 10 — --no-narrate regenerates tables but not narrative
# ---------------------------------------------------------------------------


def test_no_narrate_refreshes_tables_not_narrative(
    plugin_workspace, monkeypatch
) -> None:
    """[Test 10] Scan 1 (narrate=True, head1): establishes prose + anchor.
    Add a command; re-emit. Scan 2 (narrate=False): ## Commands table refreshed
    (tables come from write_entities regardless of narrate flag), but
    ## Narrative is unchanged (still @ head1) and anchor stays 'head1'.
    """
    workspace = plugin_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    db_path = workspace / ".graph" / "code.db"

    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _narrate_spy(heads),
    )

    # --- Scan 1 ---
    asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )
    assert f"PROSE {_PLUGIN_URI} @ head1" in _page(wiki).read_text(encoding="utf-8")
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"

    # Add command 'gamma'; re-emit
    _make_plugin(repo, commands=["alpha", "gamma"])
    _emit_plugin(db_path, repo)
    heads["v"] = "head2"
    monkeypatch.setattr(
        scan_mod, "changed_files_since",
        lambda repo, sha, sub: ["plugins/demo/commands/gamma.md"],
    )

    # --- Scan 2: narrate=False ---
    asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=False)
    )
    text2 = _page(wiki).read_text(encoding="utf-8")

    # Tables refresh from write_entities regardless of narrate
    assert "gamma" in text2, "gamma command should appear in ## Commands (table refresh)"

    # Narrative unchanged (no narrator call)
    assert f"PROSE {_PLUGIN_URI} @ head1" in text2
    assert f"PROSE {_PLUGIN_URI} @ head2" not in text2

    # Anchor unchanged
    assert _fm.load(_page(wiki)).metadata.get("last_updated_commit") == "head1"


# ---------------------------------------------------------------------------
# Test 11 — new plugin bootstraps anchor
# ---------------------------------------------------------------------------


def test_new_agent_plugin_bootstraps_anchor(plugin_workspace, monkeypatch) -> None:
    """[Test 11] A brand-new plugin (no page on disk) → single scan (narrate=True,
    head1) → page created, narrated (PROSE ... @ head1), last_updated_commit
    stamped to 'head1'.

    Proves the create → needs_narrative → narrate → stamp path, so the
    commit-gate works correctly for all subsequent scans.
    """
    workspace = plugin_workspace
    wiki = workspace / "wiki"
    repo = workspace / "repo"

    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod, "compute_state_gate",
        lambda repo: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool, "run_all",
        _narrate_spy(heads),
    )

    asyncio.run(
        scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True)
    )

    page = _page(wiki)
    text = page.read_text(encoding="utf-8")
    meta = _fm.load(page).metadata

    assert f"PROSE {_PLUGIN_URI} @ head1" in text
    assert meta.get("last_updated_commit") == "head1"
