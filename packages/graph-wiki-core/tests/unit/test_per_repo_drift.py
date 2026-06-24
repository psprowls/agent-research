"""Multi-repo M4: per-repo cross-page drift gating (Task 7).

Each candidate ENTITY's owning member repo path drives ``changed_files_since``
so an entity in member A is judged against member A's git, not the resolved
single ``repo``. Single-repo (``repo_paths`` empty/None) is byte-identical.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from graph_io.store import read_only_connect


def _seed_two_packages(db_path: Path) -> None:
    """Two package nodes in two repos so _entity_paths_by_uri maps both URIs."""
    from graph_io import schema

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        schema.apply_schema(conn)
        conn.executemany(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('package', ?, ?, NULL, '{\"language\": \"python\"}', ?)",
            [
                ("pkg-a", "packages/pkg-a", "pkg:org/repo-a/pkg-a"),
                ("pkg-b", "packages/pkg-b", "pkg:org/repo-b/pkg-b"),
            ],
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
        "---\n" + "\n".join(fm) + f"\n---\n## Narrative\n\n{narrative}\n\n## Purpose\n\nTODO\n",
        encoding="utf-8",
    )
    return page


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """workspace/{wiki, repo, repo-a, repo-b} + two-package graph DB."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / ".graph-wiki").mkdir(parents=True)
    (workspace / "repo").mkdir()
    (workspace / "repo-a").mkdir()
    (workspace / "repo-b").mkdir()
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_two_packages(workspace / ".graph-wiki" / "code.db")
    return workspace


@pytest.fixture
def conn(ws):
    c = read_only_connect(ws / ".graph-wiki" / "code.db")
    yield c
    c.close()


def test_each_candidate_uses_its_own_repo(ws, conn, monkeypatch):
    """[Task 7] In multi-repo, each candidate's changed_files are diffed against
    ITS OWNING member repo, not the single resolved ``repo``."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki = ws / "wiki"
    repo = ws / "repo"  # the resolved single repo — must NOT be used for diffs
    repo_a = ws / "repo-a"
    repo_b = ws / "repo-b"

    _write_entity_page(
        wiki,
        stem="pkg_a",
        uri="pkg:org/repo-a/pkg-a",
        last_updated_commit="a2",
        drift_propagated_commit="a1",
    )
    _write_entity_page(
        wiki,
        stem="pkg_b",
        uri="pkg:org/repo-b/pkg-b",
        last_updated_commit="b2",
        drift_propagated_commit="b1",
    )

    # changed_files_since keyed on the repo path it was called with.
    def fake_changed(repo_arg: Path, sha: str, sub: str):
        if Path(repo_arg) == repo_a:
            return ["packages/pkg-a/a.py"]
        if Path(repo_arg) == repo_b:
            return ["packages/pkg-b/b.py"]
        return ["WRONG_REPO_USED"]

    monkeypatch.setattr(pd, "changed_files_since", fake_changed)

    repo_paths = {"org/repo-a": repo_a, "org/repo-b": repo_b}
    cands = pd.propagation_candidates(wiki, repo, conn, repo_paths=repo_paths)

    by_stem = {c.stem: c for c in cands}
    assert by_stem["pkg_a"].changed_files == ["packages/pkg-a/a.py"]
    assert by_stem["pkg_b"].changed_files == ["packages/pkg-b/b.py"]


def test_single_repo_uses_resolved_repo(ws, conn, monkeypatch):
    """[Task 7] repo_paths=None (single-repo) -> every candidate diffs against
    the resolved ``repo`` (byte-identical to the legacy 3-arg signature)."""
    import graph_wiki_core.commands.propagate_drift as pd

    wiki = ws / "wiki"
    repo = ws / "repo"

    _write_entity_page(
        wiki,
        stem="pkg_a",
        uri="pkg:org/repo-a/pkg-a",
        last_updated_commit="a2",
        drift_propagated_commit="a1",
    )

    seen: list[Path] = []

    def fake_changed(repo_arg: Path, sha: str, sub: str):
        seen.append(Path(repo_arg))
        return ["x.py"]

    monkeypatch.setattr(pd, "changed_files_since", fake_changed)

    cands = pd.propagation_candidates(wiki, repo, conn)  # 3-arg, no repo_paths
    assert len(cands) == 1
    assert seen == [repo]
    assert cands[0].changed_files == ["x.py"]


# --- surface regression: run_propagate_drift itself ------------------------


def _patch_judge(monkeypatch, pd, verdict_fn):
    """Replace make_llm + SubagentPool.run_all so run_propagate_drift judges
    without Bedrock; `verdict_fn(item)` returns the parsed verdict dict."""
    from unittest.mock import MagicMock

    monkeypatch.setattr(pd, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(pd, "load_role_config", lambda role: {"model_id": "m", "max_concurrency": 4})

    async def _run_all(self, items, task, role, *, model_id, max_concurrency, recursion_limit=None):
        from subagent_runtime.pool import FanOutResult

        result = FanOutResult()
        result.successes = [(it, verdict_fn(it)) for it in items]
        return result

    monkeypatch.setattr(pd.SubagentPool, "run_all", _run_all)


def test_run_propagate_drift_gates_each_member_on_its_own_repo(ws, conn, monkeypatch):
    """[Task 7 regression] run_propagate_drift (the CLI/MCP entry point) rebuilds
    the member map and diffs each candidate against its OWNING member repo — not
    the resolved members[0]. Locks the surface that was silently under-firing."""
    import asyncio

    import graph_wiki_core.commands.propagate_drift as pd
    import workspace_io.config as wcfg

    pytest.importorskip("subagent_runtime.pool")

    wiki = ws / "wiki"
    repo_a = ws / "repo-a"  # members[0] — what `repo` resolves to
    repo_b = ws / "repo-b"

    _write_entity_page(
        wiki, stem="pkg_a", uri="pkg:org/repo-a/pkg-a", last_updated_commit="a2", drift_propagated_commit="a1"
    )
    _write_entity_page(
        wiki, stem="pkg_b", uri="pkg:org/repo-b/pkg-b", last_updated_commit="b2", drift_propagated_commit="b1"
    )
    # Curated page backlinked by BOTH entities so both become judge candidates.
    curated = wiki / "concepts" / "fanout.md"
    curated.parent.mkdir(parents=True, exist_ok=True)
    curated.write_text("---\ntitle: Fanout\n---\nUses [[entities/pkg_a]] and [[entities/pkg_b]].\n", encoding="utf-8")

    # Two members; resolve() yields them with repo_root == members[0] (repo-a).
    monkeypatch.setattr(
        wcfg,
        "resolve",
        lambda cwd=None, require_manifest=True: wcfg.GraphWikiConfig(
            workspace=ws, repo_root=repo_a, members=(repo_a, repo_b)
        ),
    )
    # Deterministic member map (avoids needing real git remotes for _derive_repo_context).
    monkeypatch.setattr(pd, "build_repo_paths", lambda members: {"org/repo-a": repo_a, "org/repo-b": repo_b})

    # changed_files_since keyed on the repo path it was called with.
    calls: list[tuple[Path, str]] = []

    def fake_changed(repo_arg: Path, sha: str, sub: str):
        calls.append((Path(repo_arg), sha))
        if Path(repo_arg) == repo_a and sha == "a1":
            return ["packages/pkg-a/a.py"]
        if Path(repo_arg) == repo_b and sha == "b1":
            return ["packages/pkg-b/b.py"]
        return None  # wrong repo for the sha -> empty signal (the bug's footprint)

    monkeypatch.setattr(pd, "changed_files_since", fake_changed)

    captured: dict[str, list] = {}

    def verdict(item):
        _kind, _slug, _title, _body, entities, _entry = item
        captured["entities"] = entities  # [(stem, narrative, changed_files), ...]
        return {"stale": False, "findings": []}

    _patch_judge(monkeypatch, pd, verdict)

    res = asyncio.run(pd.run_propagate_drift(wiki=wiki, repo=repo_a, conn=conn))
    assert res.entities_considered == 2

    # Each entity's diff ran against ITS OWN repo+sha, not members[0] for both.
    assert (repo_a, "a1") in calls
    assert (repo_b, "b1") in calls
    # pkg_b was NOT diffed against members[0] (repo-a) — the regression.
    assert (repo_a, "b1") not in calls

    by_stem = {stem: files for stem, _narr, files in captured["entities"]}
    assert by_stem["pkg_a"] == ["packages/pkg-a/a.py"]
    assert by_stem["pkg_b"] == ["packages/pkg-b/b.py"]
