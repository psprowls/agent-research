"""Living Wiki M1.5 (split scan pipeline): build_scan_worklist emit-half tests.

Covers the mechanical front-half: graph build → write_entities → deterministic
file-map injection → commit-gate → emit a commit-gated ScanWorklist. The fixture
mirrors test_commit_gated_narrative.py's m2a_workspace (stubbed cg update + state
gate + deterministic file map over a real one-package graph). The "fully
populated + stamped" precondition for the unchanged/commit-dirty cases is reached
by running a full narrated run_scan via the shared refresh_all_spy stub, which
fills the narrative, human sections, and every — TODO file-map row, so a
steady-state re-emit is genuinely empty.
"""

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

from ._spies import patch_repo_state, refresh_all_spy

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


def _page_for(wiki: Path):
    return next(p for p in (wiki / "entities").glob("*.md") if _fm.load(p).metadata.get("uri") == _PKG_A)


@pytest.fixture
def emit_workspace(tmp_path, monkeypatch):
    """One-package workspace with stubbed cg update, state gate (clean @ head1),
    and a deterministic single-row file map for pkg-a."""
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
    monkeypatch.setattr(scan_bedrock_mod, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": "head1"},
    )
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
    return workspace, repo


def test_new_package_emits_first_fill_prose_task(emit_workspace) -> None:
    """A brand-new package page emits a prose task with trigger == "first_fill"
    (placeholder narrative + — TODO rows). The page exists on disk with the
    deterministic file map injected, and prose_sections carries the template's
    human sections keyed by FULL headings."""
    workspace, repo = emit_workspace

    worklist, scan_result = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )

    alpha = next(t for t in worklist.prose_tasks if t.uri == _PKG_A)
    assert alpha.trigger == "first_fill"
    assert alpha.diff is None
    # The template seeds ## Purpose / ## Public API as TODO placeholders — the
    # prose surface hands them (and ## Narrative) to the refresher, FULL-heading
    # keyed.
    assert "## Narrative" in alpha.prose_sections
    assert "## Purpose" in alpha.prose_sections
    assert "## Public API" in alpha.prose_sections
    assert Path(alpha.page_path).exists()
    # The deterministic file map was injected (— TODO Description cell present).
    assert "| `pyproject.toml` | file | — TODO |" in Path(alpha.page_path).read_text(encoding="utf-8")
    assert alpha.file_map_rows  # rows snapshot travels with the task
    assert _PKG_A in scan_result.entities_created


def test_unchanged_package_emits_empty_worklist(emit_workspace, monkeypatch) -> None:
    """After a full narrated scan (prose + every row + human sections filled +
    anchor stamped), a steady-state re-emit (no code change) produces no
    prose_task and no drift_task — worklist.is_empty."""
    workspace, repo = emit_workspace
    wiki = workspace / "wiki"

    monkeypatch.setattr(
        _SubagentPool,
        "run_all",
        refresh_all_spy(lambda t: f"PROSE for {t.uri}"),
    )
    # Full narrated scan: fills narrative + human sections + all — TODO rows +
    # stamps last_updated_commit=head1.
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    page = _page_for(wiki)
    text = page.read_text(encoding="utf-8")
    assert "PROSE for pkg:org/repo/pkg-a" in text
    assert "| `pyproject.toml` | file | — TODO |" not in text  # rows filled

    # plan decision (B): the page narrated in scan 1 had no anchor at emit time, so
    # its drift is judged on the next scan. A second no-change scan settles
    # drift_checked_commit == last_updated_commit so the page is no longer a drift
    # candidate — only then is the worklist genuinely empty.
    patch_repo_state(monkeypatch, scan_mod, [])
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))

    # Steady-state re-emit: files clean, head unchanged, drift settled.
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    assert worklist.is_empty


def test_commit_dirty_unchanged_package_emits_diff_task(emit_workspace, monkeypatch) -> None:
    """A committed source change on a stamped, healthy package re-emits a prose
    task with trigger == "diff" carrying the scoped hunks."""
    workspace, repo = emit_workspace
    wiki = workspace / "wiki"

    heads = {"v": "head1"}
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": True, "reason": "clean", "head_commit": heads["v"]},
    )
    monkeypatch.setattr(
        _SubagentPool,
        "run_all",
        refresh_all_spy(lambda t: f"PROSE for {t.uri}"),
    )
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    assert _fm.load(_page_for(wiki)).metadata.get("last_updated_commit") == "head1"

    # HEAD moved and pkg-a's source changed since head1 (no structural delta;
    # mod.py is not a described File-map row, so the page stays healthy and the
    # diff branch fires).
    heads["v"] = "head2"
    patch_repo_state(monkeypatch, scan_mod, ["packages/pkg-a/mod.py"])
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    alpha = next(t for t in worklist.prose_tasks if t.uri == _PKG_A)
    assert alpha.trigger == "diff"
    assert alpha.diff and "packages/pkg-a/mod.py" in alpha.diff
    assert alpha.changed_files == ["packages/pkg-a/mod.py"]


def test_dirty_state_gate_yields_no_head(emit_workspace, monkeypatch) -> None:
    """When compute_state_gate disallows stamping (dirty/non-allowed branch ⇒ no
    head_commit), head_commit and short_head are None in the emitted worklist."""
    workspace, repo = emit_workspace

    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda repo, **kwargs: {"allowed": False, "reason": "dirty", "head_commit": None},
    )
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    assert worklist.head_commit is None
    assert worklist.short_head is None


# ---------------------------------------------------------------------------
# Task 3: apply_scan_results back-half tests
# ---------------------------------------------------------------------------

from graph_wiki_core.commands.scan import apply_scan_results  # noqa: E402
from graph_wiki_core.commands.scan_contract import (  # noqa: E402
    ProseRefreshResult,
    ScanResults,
)
from wiki_io._workspace import resolve_wiki_and_repo  # noqa: E402
from wiki_io.entity_writer import dir_section_todo_contexts, file_map_todo_paths  # noqa: E402


def _full_result(alpha) -> ProseRefreshResult:
    """Hand-built success result covering every fill surface of the task."""
    page = Path(alpha.page_path)
    return ProseRefreshResult(
        uri=alpha.uri,
        sections={
            "## Narrative": "Alpha is a sample package.",
            "## Purpose": "The purpose.",
            "## Public API": "The API.",
        },
        file_map_descriptions={p: "Source file." for p in file_map_todo_paths(page)},
        dir_descriptions={c: "A directory." for c in dir_section_todo_contexts(page)},
        overview=None,
    )


def test_apply_injects_prose_and_stamps(emit_workspace) -> None:
    """A canned ScanResults for the package's prose task injects the narrative,
    fills every — TODO file row, replaces ## Purpose / ## Public API, and stamps
    last_updated_commit to short_head."""
    workspace, repo = emit_workspace
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    wiki, resolved_repo = resolve_wiki_and_repo(workspace, repo)
    alpha = next(t for t in worklist.prose_tasks if t.uri == _PKG_A)
    results = ScanResults(prose=[_full_result(alpha)])
    applied = asyncio.run(apply_scan_results(worklist, results, wiki, resolved_repo or repo, propagate=False))
    page = Path(alpha.page_path).read_text(encoding="utf-8")
    assert "Alpha is a sample package." in page
    assert "— TODO" not in page.split("## File map")[-1]  # all rows filled
    assert applied.narrated >= 1 and applied.stamped >= 1
    assert applied.sections_filled >= 2  # Purpose + Public API via replace_prose_sections
    assert _fm.load(alpha.page_path).metadata.get("last_updated_commit") == worklist.short_head


def test_apply_partial_leaves_page_unstamped(emit_workspace) -> None:
    """Narrative-only fill (file rows left unfilled) leaves the page not stamped:
    the M2c gate refuses to stamp while — TODO rows remain."""
    workspace, repo = emit_workspace
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    wiki, resolved_repo = resolve_wiki_and_repo(workspace, repo)
    alpha = next(t for t in worklist.prose_tasks if t.uri == _PKG_A)
    results = ScanResults(prose=[ProseRefreshResult(uri=alpha.uri, sections={"## Narrative": "Some prose."})])
    asyncio.run(apply_scan_results(worklist, results, wiki, resolved_repo or repo, propagate=False))
    assert _fm.load(alpha.page_path).metadata.get("last_updated_commit") is None


def test_apply_failed_narration_leaves_page_unstamped(emit_workspace) -> None:
    """Decision A: a fill that injects no narrative (placeholder remains) is not
    stamped even when every file row is filled (failed-narration guard)."""
    workspace, repo = emit_workspace
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    wiki, resolved_repo = resolve_wiki_and_repo(workspace, repo)
    alpha = next(t for t in worklist.prose_tasks if t.uri == _PKG_A)
    # Fill every file row + human sections, but NO narrative -> placeholder stays.
    results = ScanResults(
        prose=[
            ProseRefreshResult(
                uri=alpha.uri,
                sections={"## Purpose": "The purpose.", "## Public API": "The API."},
                file_map_descriptions={p: "Source file." for p in file_map_todo_paths(Path(alpha.page_path))},
            )
        ]
    )
    applied = asyncio.run(apply_scan_results(worklist, results, wiki, resolved_repo or repo, propagate=False))
    assert _fm.load(alpha.page_path).metadata.get("last_updated_commit") is None
    assert applied.stamped == 0


def test_apply_empty_results_is_noop(emit_workspace) -> None:
    """Empty ScanResults on a worklist stamps nothing and narrates nothing
    (index/backlink/log still run, but no entity is touched)."""
    workspace, repo = emit_workspace
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    wiki, resolved_repo = resolve_wiki_and_repo(workspace, repo)
    applied = asyncio.run(apply_scan_results(worklist, ScanResults(), wiki, resolved_repo or repo, propagate=False))
    assert applied.stamped == 0 and applied.narrated == 0


# ---------------------------------------------------------------------------
# Task 4: emit/apply_scan_worklist round-trip-via-disk test
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402

from graph_wiki_core.commands.scan import apply_scan_worklist, emit_scan_worklist  # noqa: E402
from graph_wiki_core.commands.scan_contract import ScanWorklist  # noqa: E402


async def test_emit_apply_round_trip_via_disk(emit_workspace, tmp_path) -> None:
    """emit_scan_worklist writes worklist.json; after hand-authoring results.json,
    apply_scan_worklist injects narrative and stamps the anchor — full out-of-process
    round-trip."""
    workspace, repo = emit_workspace
    wl_path = tmp_path / "worklist.json"
    res_path = tmp_path / "results.json"

    scan_result = await emit_scan_worklist(
        workspace_path=workspace,
        repo_path=repo,
        no_file_map=False,
        max_depth=3,
        propagate=False,
        out_path=wl_path,
    )
    assert wl_path.exists(), "emit_scan_worklist must write worklist.json"
    assert scan_result is not None

    worklist = ScanWorklist.from_json(wl_path.read_text(encoding="utf-8"))
    alpha = next(t for t in worklist.prose_tasks if t.uri == _PKG_A)

    # Hand-author a results.json as the Claude agent would assemble it.
    res_path.write_text(
        _json.dumps(
            {
                "schema": 2,
                "prose": [
                    {
                        "uri": alpha.uri,
                        "sections": {
                            "## Narrative": "Alpha is a sample package.",
                            "## Purpose": "the purpose",
                            "## Public API": "the api",
                        },
                        "file_map_descriptions": {p: "src file" for p in file_map_todo_paths(Path(alpha.page_path))},
                        "dir_descriptions": {c: "a dir" for c in dir_section_todo_contexts(Path(alpha.page_path))},
                        "overview": None,
                    }
                ],
                "drift": [],
                "propagate": [],
            }
        ),
        encoding="utf-8",
    )

    applied = await apply_scan_worklist(
        workspace_path=workspace,
        repo_path=repo,
        results_path=res_path,
        short_head=worklist.short_head,
        propagate=False,
        worklist_path=wl_path,
    )
    assert applied.narrated >= 1
    page = Path(alpha.page_path).read_text(encoding="utf-8")
    assert "Alpha is a sample package." in page
    # The disk apply path's distinctive behavior: stamp the anchor from the
    # passed-in short_head (the only state crossing the process boundary).
    assert applied.stamped >= 1
    assert _fm.load(alpha.page_path).metadata.get("last_updated_commit") == worklist.short_head


# ---------------------------------------------------------------------------
# Task 9: opt-in M4 cross-page propagate-drift through the contract
# ---------------------------------------------------------------------------

from graph_wiki_core.commands.scan_contract import (  # noqa: E402
    PropagateFinding,
    PropagateResultItem,
)
from wiki_io.proposals import list_proposals  # noqa: E402


def _narrate_and_stamp_pkg_a(workspace, repo, monkeypatch) -> Path:
    """Full narrated scan so pkg-a's entity page exists + is stamped
    (last_updated_commit=head1, no drift_propagated_commit -> a propagate
    candidate). Returns the entity page path."""
    monkeypatch.setattr(
        _SubagentPool,
        "run_all",
        refresh_all_spy(lambda t: f"PROSE for {t.uri}"),
    )
    patch_repo_state(monkeypatch, scan_mod, [])
    asyncio.run(scan_mod.run_scan(workspace_path=workspace, repo_path=repo, narrate=True))
    return _page_for(workspace / "wiki")


def test_m4_emit_produces_target_and_apply_writes_ledger(emit_workspace, monkeypatch) -> None:
    """[Task 9] A concept page backlinking a changed entity emits one propagate_task
    (kind concept); apply with a stale verdict writes a source:drift ledger note and
    stamps drift_propagated_commit on the entity page (idempotence anchor)."""
    workspace, repo = emit_workspace
    wiki = workspace / "wiki"

    page = _narrate_and_stamp_pkg_a(workspace, repo, monkeypatch)
    stem = page.stem
    assert _fm.load(page).metadata.get("last_updated_commit") == "head1"
    assert "drift_propagated_commit" not in _fm.load(page).metadata  # candidate

    # A concept page backlinking the entity -> a curated propagate target.
    concept = wiki / "concepts" / "fanout.md"
    concept.parent.mkdir(parents=True, exist_ok=True)
    concept.write_text(
        f"---\ntitle: Fan-out\n---\nThe [[entities/{stem}]] package is synchronous.\n",
        encoding="utf-8",
    )

    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=True
        )
    )
    assert any(t.kind == "concept" for t in worklist.propagate_tasks)
    target = next(t for t in worklist.propagate_tasks if t.kind == "concept")
    assert target.target_slug == "fanout"
    assert target.entities and target.entities[0].stem == stem
    # Anchors + pages populated for every considered candidate (idempotence stamp).
    assert worklist.propagate_anchors  # uri -> last_updated_commit
    assert worklist.propagate_pages  # uri -> page_path

    wiki_resolved, resolved_repo = resolve_wiki_and_repo(workspace, repo)
    results = ScanResults(
        propagate=[
            PropagateResultItem(
                kind="concept",
                target_slug=target.target_slug,
                stale=True,
                findings=[
                    PropagateFinding(entity_stem=stem, claim="sync", reason="now async"),
                ],
            )
        ]
    )
    applied = asyncio.run(apply_scan_results(worklist, results, wiki_resolved, resolved_repo or repo, propagate=True))
    assert applied.propagated == 1

    notes = [r for r in list_proposals(wiki) if any(o.get("source") == "drift" for o in r.get("origins", []))]
    assert notes  # one source:drift ledger proposal written
    note = notes[0]
    assert note["kind"] == "concept"
    assert note["target_slug"] == "fanout"
    assert {o["ref"] for o in note["origins"]} == {f"entities/{stem}"}
    # The entity page's idempotence anchor was stamped to its last_updated_commit.
    assert _fm.load(page).metadata.get("drift_propagated_commit") == "head1"


def test_m4_off_by_default_emits_no_propagate_tasks(emit_workspace, monkeypatch) -> None:
    """[Task 9] propagate_drift=False -> no propagate_tasks, no anchors, and a
    concept backlinker triggers zero ledger writes (off by default)."""
    workspace, repo = emit_workspace
    wiki = workspace / "wiki"

    page = _narrate_and_stamp_pkg_a(workspace, repo, monkeypatch)
    concept = wiki / "concepts" / "fanout.md"
    concept.parent.mkdir(parents=True, exist_ok=True)
    concept.write_text(
        f"---\ntitle: Fan-out\n---\nThe [[entities/{page.stem}]] package is synchronous.\n",
        encoding="utf-8",
    )

    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    assert worklist.propagate_tasks == []
    assert worklist.propagate_anchors == {}
    assert worklist.propagate_pages == {}

    wiki_resolved, resolved_repo = resolve_wiki_and_repo(workspace, repo)
    asyncio.run(apply_scan_results(worklist, ScanResults(), wiki_resolved, resolved_repo or repo, propagate=False))
    assert list_proposals(wiki) == []
