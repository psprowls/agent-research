"""Living Wiki M4: drift propagation to backlinks (spec §5)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from graph_io.store import read_only_connect


# --- fixture helpers -------------------------------------------------------

def _seed_one_package(db_path: Path, *, uri: str, node_path: str) -> None:
    """One package node so _entity_paths_by_uri maps uri -> node_path."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', 'pkg-a', ?, NULL, '{\"language\": \"python\"}', ?)",
            (node_path, uri),
        )
        conn.commit()
    finally:
        conn.close()


def _write_entity_page(
    wiki: Path,
    *,
    stem: str,
    uri: str,
    last_updated_commit: str,
    drift_propagated_commit: str | None = None,
    narrative: str = "Now uses async fan-out.",
) -> Path:
    fm = [f"uri: {uri}", "kind: package", f"last_updated_commit: {last_updated_commit}"]
    if drift_propagated_commit is not None:
        fm.append(f"drift_propagated_commit: {drift_propagated_commit}")
    page = wiki / "entities" / f"{stem}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n" + "\n".join(fm) + "\n---\n"
        f"## Narrative\n\n{narrative}\n\n## Purpose\n\nTODO\n",
        encoding="utf-8",
    )
    return page


def _write_curated(wiki: Path, category: str, slug: str, body: str, title: str = "T") -> Path:
    page = wiki / category / f"{slug}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"---\ntitle: {title}\n---\n{body}\n", encoding="utf-8")
    return page


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """workspace/{wiki, repo} + one-package graph DB + GRAPH_WIKI_WORKSPACE."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / "entities").mkdir(parents=True)
    (wiki / ".graph-wiki").mkdir(parents=True)
    repo.mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_one_package(
        workspace / ".graph-wiki" / "code.db",
        uri="pkg:org/repo/pkg-a",
        node_path="packages/pkg-a",
    )
    return workspace


@pytest.fixture
def conn(ws):
    c = read_only_connect(ws / ".graph-wiki" / "code.db")
    yield c
    c.close()


# --- candidate-gate tests --------------------------------------------------

def test_candidate_when_anchors_differ(ws, conn, monkeypatch):
    """[§5 test 3] drift_propagated_commit != last_updated_commit -> candidate;
    changed_files come from changed_files_since(repo, drift_propagated_commit, path)."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a",
        last_updated_commit="head2", drift_propagated_commit="head1",
    )
    monkeypatch.setattr(
        pd, "changed_files_since",
        lambda repo, sha, sub: ["packages/pkg-a/pool.py"] if sha == "head1" else None,
    )

    cands = pd.propagation_candidates(wiki, repo, conn)
    assert len(cands) == 1
    c = cands[0]
    assert c.uri == "pkg:org/repo/pkg-a"
    assert c.stem == "pkg_a"
    assert c.last_updated_commit == "head2"
    assert c.drift_propagated_commit == "head1"
    assert c.changed_files == ["packages/pkg-a/pool.py"]


def test_not_a_candidate_when_anchors_equal(ws, conn):
    """[§5 test 3] equal anchors -> already propagated at this narrative -> skip."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a",
        last_updated_commit="head2", drift_propagated_commit="head2",
    )
    assert pd.propagation_candidates(wiki, repo, conn) == []


def test_absent_anchor_is_candidate(ws, conn, monkeypatch):
    """[§5 test 3] absent drift_propagated_commit -> candidate; empty since_sha
    yields no specific changed files (None -> [])."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="head2",
    )
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: None)
    cands = pd.propagation_candidates(wiki, repo, conn)
    assert len(cands) == 1
    assert cands[0].drift_propagated_commit is None
    assert cands[0].changed_files == []


# --- happy-path (run_propagate_drift) tests --------------------------------

import asyncio
from unittest.mock import MagicMock

import graph_wiki_core.commands.propagate_drift as pd
from wiki_io.proposals import list_proposals, proposal_path, read_proposal


def _patch_judge(monkeypatch, verdict_fn, *, recorder: dict | None = None):
    """Replace make_llm + SubagentPool.run_all. `verdict_fn(item)` returns the
    parsed verdict dict for one item; `item` is
    (kind, target_slug, title, page_body, entities, entry)."""
    monkeypatch.setattr(pd, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(pd, "load_role_config", lambda role: {"model_id": "m", "max_concurrency": 4})

    async def _run_all(self, items, task, role, *, model_id, max_concurrency, recursion_limit=None):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        if recorder is not None:
            recorder.setdefault("items", []).extend(items)
        result.successes = [(it, verdict_fn(it)) for it in items]
        return result

    monkeypatch.setattr(pd.SubagentPool, "run_all", _run_all)


def test_stale_page_with_two_entities_yields_one_note_two_origins(ws, conn, monkeypatch):
    """[§5 test 7] one page backlinked by two changed entities, both stale ->
    ONE ledger note with TWO source:drift origins (detected_commit + hash set)."""
    wiki, repo = ws / "wiki", ws / "repo"
    # Second package node so both entities map to a node_path.
    c2 = sqlite3.connect(ws / ".graph-wiki" / "code.db")
    c2.execute(
        "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
        "('package','pkg-b','packages/pkg-b',NULL,'{}','pkg:org/repo/pkg-b')"
    )
    c2.commit()
    c2.close()
    conn2 = read_only_connect(ws / ".graph-wiki" / "code.db")

    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a",
                       last_updated_commit="h2", narrative="A is async now.")
    _write_entity_page(wiki, stem="pkg_b", uri="pkg:org/repo/pkg-b",
                       last_updated_commit="h9", narrative="B is async now.")
    _write_curated(wiki, "concepts", "fanout",
                   "Both pkg_a [[entities/pkg_a]] and pkg_b [[entities/pkg_b]] are synchronous.")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])

    def verdict(item):
        kind, slug, title, body, entities, entry = item
        return {"stale": True, "findings": [
            {"entity_stem": stem, "stale_claim": "sync", "rationale": f"{stem} now async"}
            for stem, _narr, _files in entities
        ]}

    _patch_judge(monkeypatch, verdict)
    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn2))
    conn2.close()

    assert res.pages_judged == 1
    assert res.entities_considered == 2
    assert res.notes_written == 1
    assert res.pages_stale == 1

    rec = read_proposal(proposal_path(wiki, "concept", "fanout"))
    assert rec["status"] == "proposed"
    assert rec["mode"] == "update_existing"
    assert len(rec["origins"]) == 2
    refs = {o["ref"] for o in rec["origins"]}
    assert refs == {"entities/pkg_a", "entities/pkg_b"}
    for o in rec["origins"]:
        assert o["source"] == "drift"
        assert o["detected_commit"] in {"h2", "h9"}
        assert o["hash"]  # sha256 of the entity narrative


def test_non_stale_page_writes_no_note(ws, conn, monkeypatch):
    """[§5 test 10] judge says not stale -> no ledger note."""
    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))
    assert res.notes_written == 0
    assert list_proposals(wiki) == []


def test_anchor_stamped_and_second_run_is_idempotent(ws, conn, monkeypatch):
    """[§5 test 4] every processed candidate's drift_propagated_commit is stamped
    to last_updated_commit; a second run with no code change judges nothing."""
    wiki, repo = ws / "wiki", ws / "repo"
    page = _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))
    import frontmatter as _fm
    assert _fm.load(page).metadata.get("drift_propagated_commit") == "h2"

    rec = {"items": []}
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []}, recorder=rec)
    res2 = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))
    assert res2.entities_considered == 0
    assert rec["items"] == []  # judge never invoked


def test_entity_with_no_curated_backlink_is_still_stamped(ws, conn, monkeypatch):
    """[§3.5] a candidate whose only backlinkers are non-curated (or none) is
    still stamped, so it is not reconsidered until its narrative changes."""
    wiki, repo = ws / "wiki", ws / "repo"
    page = _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "sources", "spec", "About [[entities/pkg_a]].")  # sources excluded
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))
    assert res.pages_judged == 0  # no curated target
    import frontmatter as _fm
    assert _fm.load(page).metadata.get("drift_propagated_commit") == "h2"


# --- guardrail tests (Task 6) -----------------------------------------------


def test_settled_target_is_skipped(ws, conn, monkeypatch):
    """[§5 test 6] a rejected/created note on a target -> not judged; a proposed
    note (or none) -> judged."""
    wiki, repo = ws / "wiki", ws / "repo"
    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    # Pre-seed a rejected note for this exact target.
    from wiki_io.proposals import upsert_proposal, set_proposal_status
    upsert_proposal(wiki, {"kind": "concept", "mode": "update_existing",
                           "target_slug": "fanout", "title": "T",
                           "origin": {"ref": "entities/pkg_a", "source": "ingest"}})
    set_proposal_status(wiki, "concept", "fanout", "rejected")

    rec = {"items": []}
    _patch_judge(monkeypatch, lambda item: {"stale": True, "findings": [
        {"entity_stem": "pkg_a", "stale_claim": "x", "rationale": "y"}]}, recorder=rec)
    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))

    assert res.pages_judged == 0
    assert res.pages_skipped_settled == 1
    assert rec["items"] == []  # judge never saw the settled target
    # The rejected note is untouched.
    assert read_proposal(proposal_path(wiki, "concept", "fanout"))["status"] == "rejected"


def test_dry_run_judges_but_writes_nothing_and_does_not_stamp(ws, conn, monkeypatch):
    """[§5 tests 5, 12] --dry-run populates the report, writes zero notes, and
    leaves drift_propagated_commit unstamped (re-runnable)."""
    wiki, repo = ws / "wiki", ws / "repo"
    page = _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": True, "findings": [
        {"entity_stem": "pkg_a", "stale_claim": "x", "rationale": "now async"}]})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn, dry_run=True))
    assert res.dry_run is True
    assert res.pages_judged == 1
    assert res.pages_stale == 1
    assert res.notes_written == 0
    assert len(res.proposals) == 1  # report shows what WOULD be proposed
    assert list_proposals(wiki) == []  # nothing written
    import frontmatter as _fm
    assert "drift_propagated_commit" not in _fm.load(page).metadata


def test_only_entity_restricts_candidate_set(ws, conn, monkeypatch):
    """[§5 test 13] --only <entity> restricts the candidate set to that entity."""
    wiki, repo = ws / "wiki", ws / "repo"
    import sqlite3
    c2 = sqlite3.connect(ws / ".graph-wiki" / "code.db")
    c2.execute("INSERT INTO nodes(kind,name,path,line,attrs_json,uri) VALUES "
               "('package','pkg-b','packages/pkg-b',NULL,'{}','pkg:org/repo/pkg-b')")
    c2.commit()
    c2.close()
    conn2 = read_only_connect(ws / ".graph-wiki" / "code.db")

    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_entity_page(wiki, stem="pkg_b", uri="pkg:org/repo/pkg-b", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "ca", "About [[entities/pkg_a]].")
    _write_curated(wiki, "concepts", "cb", "About [[entities/pkg_b]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn2, only="pkg_a"))
    conn2.close()
    assert res.entities_considered == 1  # only pkg_a
    assert res.pages_judged == 1         # only its target


def test_only_page_restricts_target_set(ws, conn, monkeypatch):
    """[§5 test 13] --only <page-slug> restricts the target set to that page."""
    wiki, repo = ws / "wiki", ws / "repo"
    import sqlite3
    c2 = sqlite3.connect(ws / ".graph-wiki" / "code.db")
    c2.execute("INSERT INTO nodes(kind,name,path,line,attrs_json,uri) VALUES "
               "('package','pkg-b','packages/pkg-b',NULL,'{}','pkg:org/repo/pkg-b')")
    c2.commit()
    c2.close()
    conn2 = read_only_connect(ws / ".graph-wiki" / "code.db")

    _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_entity_page(wiki, stem="pkg_b", uri="pkg:org/repo/pkg-b", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "ca", "About [[entities/pkg_a]].")
    _write_curated(wiki, "concepts", "cb", "About [[entities/pkg_b]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": False, "findings": []})

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn2, only="ca"))
    conn2.close()
    assert res.pages_judged == 1  # only the "ca" target page


def test_refire_same_entity_updates_origin_in_place(ws, conn, monkeypatch):
    """[§5 test 8] re-firing the same entity on the same target updates that
    origin in place (no duplicate); detected_commit advances; status stays
    proposed."""
    wiki, repo = ws / "wiki", ws / "repo"
    page = _write_entity_page(wiki, stem="pkg_a", uri="pkg:org/repo/pkg-a", last_updated_commit="h2")
    _write_curated(wiki, "concepts", "fanout", "About [[entities/pkg_a]].")
    monkeypatch.setattr(pd, "changed_files_since", lambda repo, sha, sub: [])
    _patch_judge(monkeypatch, lambda item: {"stale": True, "findings": [
        {"entity_stem": "pkg_a", "stale_claim": "x", "rationale": "r1"}]})
    asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))

    # Entity re-narrated at a new commit -> candidate again.
    page.write_text(page.read_text().replace("last_updated_commit: h2", "last_updated_commit: h3"),
                    encoding="utf-8")
    _patch_judge(monkeypatch, lambda item: {"stale": True, "findings": [
        {"entity_stem": "pkg_a", "stale_claim": "x", "rationale": "r2"}]})
    asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo, conn=conn))

    rec = read_proposal(proposal_path(wiki, "concept", "fanout"))
    assert rec["status"] == "proposed"
    assert len(rec["origins"]) == 1  # merged in place by ref
    assert rec["origins"][0]["detected_commit"] == "h3"
    assert rec["origins"][0]["rationale"] == "r2"
