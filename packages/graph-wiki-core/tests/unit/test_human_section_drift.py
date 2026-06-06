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
    return next(p for p in (wiki / "entities").glob("*.md") if _fm.load(p).metadata.get("uri") == uri)


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
    _seed_one_package(workspace / ".graph-wiki" / "code.db")
    monkeypatch.setattr(scan_mod, "_cg_run_build", lambda repo, ws, *, full: (exit_codes.SUCCESS, "", ""))
    monkeypatch.setattr(scan_mod, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(
        scan_mod,
        "build_file_map",
        lambda path, **kw: (
            "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
            "| Path | Kind | Description |\n|---|---|---|\n"
            "| `pyproject.toml` | file | — TODO |\n"
            if str(path).endswith("pkg-a")
            else None
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

            result.successes = [(it, _json.dumps({p: f"desc {p}" for p in it[3]})) for it in items]
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
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))

    # Scan 1: page created + narrated + anchored at head1.
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    # Use a heading distinct from the template-seeded human sections
    # (`## Purpose`, `## Public API`) so the appended curated section survives the
    # preserve-merge instead of colliding with the duplicate template heading.
    _add_human_section(page, "## Behavior", "Processes items synchronously.")

    # Scan 2: code changed (head2) -> re-narrate -> judge says stale.
    heads["v"] = "head2"
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda repo, sha, sub: ["packages/pkg-a/mod.py"])
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
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
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    _add_human_section(_page_for(wiki), "## Purpose", "p")

    # Re-scan, no code change -> narrative not regenerated.
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    rec: dict = {}
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": True, "reason": "x"}, recorder=rec))
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
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    meta = _fm.load(_page_for(wiki)).metadata
    assert "drift_review" not in meta
    assert meta["drift_checked_commit"] == meta["last_updated_commit"] == "head1"


def test_auto_clear_on_edit_no_judge_call(ws, monkeypatch):
    """[§5.5] editing a flagged section's body clears its flag next scan with NO
    drift_judge call; an emptied drift_review key is removed."""
    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    _add_human_section(page, "## Behavior", "Processes items synchronously.")

    # Code change -> re-narrate -> stale flag written at head2. Flag ONLY the
    # appended Behavior section (the template also seeds Purpose/Public API).
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head2"},
    )
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda repo, sha, sub: ["packages/pkg-a/mod.py"])
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
        _spy(
            lambda it: (
                {"stale": True, "reason": "now async"} if it[2] == "## Behavior" else {"stale": False, "reason": ""}
            )
        ),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    review = _fm.load(_page_for(wiki)).metadata.get("drift_review")
    assert review and any(e["section"] == "Behavior" for e in review)

    # Human edits the flagged Behavior body; re-scan with no code change.
    page = _page_for(wiki)
    text = page.read_text(encoding="utf-8").replace(
        "Processes items synchronously.", "Processes items via async fan-out."
    )
    page.write_text(text, encoding="utf-8")
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    rec: dict = {}
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": True, "reason": "x"}, recorder=rec))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    assert rec.get("drift_items", []) == []  # clear pass is free; no judge
    # The only flagged section (Behavior) was edited, so the key is now removed.
    assert "drift_review" not in _fm.load(_page_for(wiki)).metadata


def test_dependency_and_narrativeless_never_flagged(ws, monkeypatch):
    """[§5.8] a non-target kind and a page without a narrative produce no judge
    calls and no drift keys.

    ADAPTED (per plan NOTE): a full ``run_scan`` deletes a hand-written
    ``dep-foo.md`` as an orphan (it is not a graph node), so the dep page no
    longer exists to assert against. We instead exercise the candidate filter
    and flag pass DIRECTLY (mirroring the Task-7 direct-call style), which is the
    actual gate §5.8 governs: the ``dependency`` page (non-target kind) and a
    narrative-less ``package`` page must NOT be candidates, must produce no judge
    item, and must gain no drift keys.
    """
    wiki = ws / "wiki"
    rec: dict = {}
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": True, "reason": "x"}, recorder=rec))

    # A hand-written dependency page (non-target kind) + a narrative-less package.
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    dep = wiki / "entities" / "dep-foo.md"
    dep.write_text(
        "---\nuri: dep:foo\nkind: dependency\nlast_updated_commit: head1\n---\n"
        "# dep:foo\n\n## Purpose\nA dependency.\n",
        encoding="utf-8",
    )
    narrativeless = wiki / "entities" / "pkg-b.md"
    narrativeless.write_text(
        "---\nuri: pkg:b\nkind: package\nlast_updated_commit: head1\n---\n"
        "# pkg:b\n\n## Purpose\nA package with no narrative.\n",
        encoding="utf-8",
    )

    # Neither hand-written page qualifies as a drift candidate.
    candidate_paths = [c[0] for c in scan_mod._drift_candidates(wiki)]
    assert dep not in candidate_paths  # non-target kind
    assert narrativeless not in candidate_paths  # no `## Narrative`

    # The flag pass judges no items for them and writes no drift keys.
    asyncio.run(scan_mod._drift_flag_pass(wiki, None))

    dep_meta = _fm.load(dep).metadata
    assert "drift_review" not in dep_meta
    assert "drift_checked_commit" not in dep_meta
    nl_meta = _fm.load(narrativeless).metadata
    assert "drift_review" not in nl_meta
    assert "drift_checked_commit" not in nl_meta
    # Neither page ever produced a judge item.
    assert all(it[0] not in (dep, narrativeless) for it in rec.get("drift_items", []))


def test_ack_drift_clears_without_edit(ws, monkeypatch):
    """[§5.6] ack-drift removes all drift_review entries; a subsequent no-change
    scan does not re-flag (drift_checked_commit already current)."""
    from graph_wiki_core.commands.ack_drift import run_ack_drift

    wiki = ws / "wiki"
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    _add_human_section(page, "## Behavior", "Processes items synchronously.")
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head2"},
    )
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda repo, sha, sub: ["packages/pkg-a/mod.py"])
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
        _spy(
            lambda it: (
                {"stale": True, "reason": "now async"} if it[2] == "## Behavior" else {"stale": False, "reason": ""}
            )
        ),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert _fm.load(_page_for(wiki)).metadata.get("drift_review")

    # Ack by URI -> flags cleared, prose untouched.
    result = run_ack_drift(_PKG_A, workspace_path=ws)
    assert result.cleared == 1
    meta = _fm.load(_page_for(wiki)).metadata
    assert "drift_review" not in meta
    assert "Processes items synchronously." in _page_for(wiki).read_text(encoding="utf-8")

    # No-change re-scan -> not re-flagged (checked-commit already == anchor).
    monkeypatch.setattr(scan_mod, "changed_files_since", lambda *a: [])
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": True, "reason": "x"}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert "drift_review" not in _fm.load(_page_for(wiki)).metadata


def test_ack_drift_unknown_entity_raises(ws):
    from graph_wiki_core.commands.ack_drift import run_ack_drift

    with pytest.raises(ValueError):
        run_ack_drift("pkg:does/not/exist", workspace_path=ws)


def test_agent_plugin_judged_without_file_map(ws, monkeypatch):
    """[§5.9] an agent_plugin page (narrative present, NO file map) has its human
    sections judged against its narrative; file_map passed to the judge is None;
    a stale verdict flags it."""
    wiki = ws / "wiki"
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    page = wiki / "entities" / "agent-plugin-foo.md"
    page.write_text(
        "---\nuri: agent_plugin:org/repo/foo\nkind: agent_plugin\n"
        "last_updated_commit: head1\n---\n"
        "# foo\n\n## Narrative\nProvides three slash commands via async hooks.\n\n"
        "## Commands\nExposes a single synchronous command.\n",
        encoding="utf-8",
    )

    captured: dict = {}

    def _verdict(item):
        # item = (page_path, anchor, heading, chunk, narrative, file_map)
        captured["file_map"] = item[5]
        captured["heading"] = item[2]
        return {"stale": True, "reason": "command count drifted"}

    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(_verdict))
    asyncio.run(scan_mod._drift_flag_pass(wiki, None))

    assert captured["file_map"] is None  # agent_plugin has no File map
    assert captured["heading"] == "## Commands"
    meta = _fm.load(page).metadata
    assert meta["drift_checked_commit"] == "head1"
    assert meta["drift_review"][0]["section"] == "Commands"


def test_scan_propagate_drift_off_by_default(ws, monkeypatch):
    """[M4 §3.7 / §5 test 15] without the flag, scan never runs the M4 producer."""
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))
    calls = {"n": 0}

    async def _pd(**kwargs):
        calls["n"] += 1
        from graph_wiki_core.commands.propagate_drift import PropagateDriftResult

        return PropagateDriftResult(0, 0, 0, 0, 0, False, [])

    monkeypatch.setattr(scan_mod, "run_propagate_drift", _pd)
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert calls["n"] == 0


def test_scan_propagate_drift_on_runs_producer(ws, monkeypatch):
    """[M4 §3.7 / §5 test 15] with the flag, the producer runs once after narration,
    called with the open conn + resolved wiki/repo."""
    repo = ws / "repo"
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))
    captured: dict = {}

    async def _pd(**kwargs):
        captured.update(kwargs)
        from graph_wiki_core.commands.propagate_drift import PropagateDriftResult

        return PropagateDriftResult(0, 0, 0, 0, 0, False, [])

    monkeypatch.setattr(scan_mod, "run_propagate_drift", _pd)
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True, propagate_drift=True))
    assert set(captured) >= {"wiki", "repo", "conn"}  # producer invoked with state
    assert captured["conn"] is not None
