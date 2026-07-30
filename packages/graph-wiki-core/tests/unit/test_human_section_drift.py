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

from ._spies import patch_repo_state

_PKG_A = "pkg:org/repo/pkg-a"


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
    monkeypatch.setattr(
        scan_mod, "_cg_run_build", lambda repo, ws, *, full, scope_to_repo=True: (exit_codes.SUCCESS, "", "")
    )
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


def _spy(verdict_fn, *, recorder: dict | None = None, propagate_verdict_fn=None):
    """Async SubagentPool.run_all replacement covering the post-flip roles.

    prose_refresher -> healthy ProseRefreshResult (narrative + TODO sections +
    File-map rows filled); drift_judge -> verdict_fn(item); drift_propagator ->
    propagate_verdict_fn(item) (default not-stale). When `recorder` is given,
    records the dispatched items so a test can assert a role was (not) called.
    """
    from ._spies import refresh_all_spy

    return refresh_all_spy(
        lambda t: f"PROSE for {t.uri}",
        recorder=recorder,
        verdict_fn=verdict_fn,
        propagate_verdict_fn=propagate_verdict_fn,
    )


def _add_human_section(page: Path, heading: str, body: str) -> None:
    text = page.read_text(encoding="utf-8")
    page.write_text(text.rstrip("\n") + f"\n\n{heading}\n{body}\n", encoding="utf-8")


def test_prose_refresher_fill_stamps_and_redispatches_on_unknown_anchor(ws, monkeypatch):
    wiki = ws / "wiki"
    repo = ws / "repo"
    heads = {"v": "head1"}
    rec: dict = {}
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
        _spy(lambda it: {"stale": False, "reason": ""}, recorder=rec),
    )

    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    text = page.read_text(encoding="utf-8")
    meta = _fm.load(page).metadata

    # The unified refresher filled the TODO human section and the page stamped.
    assert "## Purpose\nFilled body for Purpose." in text
    assert meta["last_updated_commit"] == "head1"
    assert "drift_review" not in meta
    pkg_tasks = [x for x in rec.get("prose_tasks", []) if x.uri == _PKG_A]
    assert len(pkg_tasks) == 1

    # plan decision (B): drift is judged against the emit-time anchor, so the page
    # narrated in scan 1 settles drift_checked_commit only on the next scan. This
    # repo is not a real git tree, so the git probes report the anchor unknown
    # every scan → the preserved-drop re-TODOs the File-map row and the page
    # re-tasks (first_fill), so scan 2 both re-dispatches the refresher and
    # settles drift_checked_commit == head1.
    _add_human_section(page, "## Behavior", "Curated behavior notes stay human-owned.")

    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    page = _page_for(wiki)
    rescan_meta = _fm.load(page).metadata
    pkg_tasks = [x for x in rec.get("prose_tasks", []) if x.uri == _PKG_A]
    assert len(pkg_tasks) == 2
    assert pkg_tasks[1].trigger == "first_fill"  # unknown anchor dropped a row -> re-fill
    assert rescan_meta["last_updated_commit"] == "head1"
    assert rescan_meta["drift_checked_commit"] == "head1"  # settled on the second scan
    assert "Curated behavior notes stay human-owned." in page.read_text(encoding="utf-8")
    assert "drift_review" not in rescan_meta


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
    patch_repo_state(monkeypatch, scan_mod, ["packages/pkg-a/mod.py"])
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
        _spy(lambda it: {"stale": True, "reason": "now async"}),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    meta = _fm.load(_page_for(wiki)).metadata
    # plan decision (B): drift is judged against the EMIT-time narrative/anchor.
    # At scan 2's emit the page's anchor was still head1 (stamped by scan 1), so
    # the stale flag + drift_checked_commit anchor to head1 while last_updated_commit
    # advances to head2 (re-narration). The next scan re-judges against head2.
    assert meta["drift_checked_commit"] == "head1"
    assert meta["last_updated_commit"] == "head2"
    review = meta["drift_review"]
    # The scanner page template seeds human sections (`## Purpose`,
    # `## Public API`); the appended `## Behavior` carries the stale prose. The
    # verdict_fn marks every section stale, so the contract under test is that
    # the Behavior section is flagged with the right fields (not an exact count).
    behavior = next(e for e in review if e["section"] == "Behavior")
    assert behavior["detected_commit"] == "head1"  # plan decision (B): emit-time anchor
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

    # plan decision (B): the page narrated in scan 1 had no anchor at emit time,
    # so its drift is judged on the NEXT scan. A no-change scan settles
    # drift_checked_commit == last_updated_commit == head1.
    patch_repo_state(monkeypatch, scan_mod, [])
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert _fm.load(_page_for(wiki)).metadata["drift_checked_commit"] == "head1"

    # Now settled: another no-change scan must NOT re-judge (§5.2/§5.4).
    rec: dict = {}
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": True, "reason": "x"}, recorder=rec))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))

    assert rec.get("drift_items", []) == []  # judge never ran
    assert "drift_review" not in _fm.load(_page_for(wiki)).metadata
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
    # plan decision (B): a page narrated this scan has no anchor at emit time, so
    # its drift is judged the NEXT scan (emit-time ground truth). A second no-change
    # scan settles drift_checked_commit.
    patch_repo_state(monkeypatch, scan_mod, [])
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
    patch_repo_state(monkeypatch, scan_mod, ["packages/pkg-a/mod.py"])
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

    # plan decision (B): scan 2 judged the EMIT-time state, so it flagged Behavior
    # at the head1 anchor while last_updated_commit advanced to head2 — the page is
    # still drift-lagging. A no-change settling scan re-judges against head2 and
    # advances drift_checked_commit to head2 (Behavior stays flagged, stale prose).
    patch_repo_state(monkeypatch, scan_mod, [])
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
    assert _fm.load(_page_for(wiki)).metadata["drift_checked_commit"] == "head2"

    # Human edits the flagged Behavior body; re-scan with no code change.
    page = _page_for(wiki)
    text = page.read_text(encoding="utf-8").replace(
        "Processes items synchronously.", "Processes items via async fan-out."
    )
    page.write_text(text, encoding="utf-8")
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
    patch_repo_state(monkeypatch, scan_mod, ["packages/pkg-a/mod.py"])
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

    # plan decision (B): scan 2 flagged Behavior at the emit-time head1 anchor while
    # last_updated_commit advanced to head2 — the page still lags. A no-change
    # settling scan re-judges against head2 and advances drift_checked_commit to
    # head2 so the page is genuinely settled before the ack.
    patch_repo_state(monkeypatch, scan_mod, [])
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert _fm.load(_page_for(wiki)).metadata["drift_checked_commit"] == "head2"

    # Ack by URI -> flags cleared, prose untouched.
    result = run_ack_drift(_PKG_A, workspace_path=ws)
    assert result.cleared == 1
    meta = _fm.load(_page_for(wiki)).metadata
    assert "drift_review" not in meta
    assert "Processes items synchronously." in _page_for(wiki).read_text(encoding="utf-8")

    # No-change re-scan -> not re-flagged (checked-commit already == anchor).
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


def _add_concept_backlink(wiki, stem, slug="fanout"):
    """A curated concept page backlinking entities/<stem> -> an M4 propagate target."""
    page = wiki / "concepts" / f"{slug}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        f"---\ntitle: Fan-out\n---\nThe [[entities/{stem}]] package is synchronous.\n",
        encoding="utf-8",
    )
    return page


def test_scan_propagate_drift_off_by_default(ws, monkeypatch):
    """[M4 §3.7 / §5 test 15] without the flag, scan emits no propagate task, the
    drift_propagator role is never dispatched, and no source:drift note is written
    even when a concept backlinks the entity."""
    from wiki_io.proposals import list_proposals

    repo = ws / "repo"
    wiki = ws / "wiki"
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
    patch_repo_state(monkeypatch, scan_mod, [])
    rec = {}
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
        _spy(
            lambda it: {"stale": False, "reason": ""},
            recorder=rec,
            propagate_verdict_fn=lambda it: {
                "stale": True,
                "findings": [{"entity_stem": it[4][0][0], "stale_claim": "x", "rationale": "y"}],
            },
        ),
    )
    # Create + stamp the entity page first, then add a concept backlinking it.
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    _add_concept_backlink(wiki, _page_for(wiki).stem)

    # Re-scan WITHOUT the flag: no propagate fan-out, no ledger write.
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    assert rec.get("propagate_items", []) == []  # drift_propagator never dispatched
    assert list_proposals(wiki) == []


def test_scan_propagate_drift_on_runs_producer(ws, monkeypatch):
    """[M4 §3.7 / §5 test 15] with the flag, M4 flows through the contract once: a
    concept backlinking a changed entity is judged stale -> one source:drift ledger
    note is written and the entity's drift_propagated_commit is stamped."""
    from wiki_io.proposals import list_proposals

    repo = ws / "repo"
    wiki = ws / "wiki"
    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    patch_repo_state(monkeypatch, scan_mod, [])

    # Scan 1: create + stamp the entity page (last_updated_commit=head1).
    monkeypatch.setattr(scan_mod.SubagentPool, "run_all", _spy(lambda it: {"stale": False, "reason": ""}))
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    stem = page.stem
    _add_concept_backlink(wiki, stem)
    # Entity re-narrated at a new commit so it is a fresh propagate candidate.
    heads["v"] = "head2"
    page.write_text(
        page.read_text(encoding="utf-8").replace("last_updated_commit: head1", "last_updated_commit: head1_old"),
        encoding="utf-8",
    )

    def _propagate_verdict(item):
        # item = (kind, slug, title, body, entity_tuples)
        return {
            "stale": True,
            "findings": [{"entity_stem": item[4][0][0], "stale_claim": "sync", "rationale": "now async"}],
        }

    rec = {}
    monkeypatch.setattr(
        scan_mod.SubagentPool,
        "run_all",
        _spy(
            lambda it: {"stale": False, "reason": ""},
            recorder=rec,
            propagate_verdict_fn=_propagate_verdict,
        ),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=ws, repo_path=repo, narrate=True, propagate_drift=True))

    assert rec.get("propagate_items")  # drift_propagator dispatched through the contract
    drift_notes = [r for r in list_proposals(wiki) if any(o.get("source") == "drift" for o in r.get("origins", []))]
    assert drift_notes  # one source:drift ledger note
    assert drift_notes[0]["kind"] == "concept"
    assert _fm.load(page).metadata.get("drift_propagated_commit")  # idempotence anchor stamped
