"""Unified prose-refresh gating matrix + anchor-stamp guard (plan Task 6).

Emit-side rows drive ``build_scan_worklist`` against a real tmp workspace +
graph + git repo and inspect ``worklist.prose_tasks``; stamp-guard rows drive
``apply_scan_results`` directly with hand-built worklist/results.

Note on the staleness matrix: the File-map preserved-drop runs BEFORE task
assembly, so a commit that touches a *described* File-map row re-TODOs it and
the page re-tasks as ``first_fill`` (health check fires first). The pure
``diff`` trigger therefore covers changes that leave the page healthy (new
files, non-row files, dependency manifests) — the rows below are built that
way.
"""

from __future__ import annotations

import asyncio
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes
from graph_wiki_core.commands import scan_bedrock as scan_bedrock_mod
from graph_wiki_core.commands.scan import apply_scan_results
from graph_wiki_core.commands.scan_contract import (
    ProseRefreshResult,
    ProseRefreshTask,
    ScanResults,
    ScanWorklist,
)
from wiki_io.entity_writer import (
    LAST_UPDATED_COMMIT_KEY,
    file_map_todo_paths,
    fill_file_map_descriptions,
    is_todo_like_body,
    prose_section_bodies,
    replace_prose_sections,
    set_frontmatter_value,
)
from wiki_io.git_state import truncate_diff as _real_truncate_diff

_PKG_A = "pkg:org/repo/pkg-a"
_REPO_URI = "repo:org/repo"
_DOMAIN_URI = "domain:org/repo/core"
_DEP_URI = "dependency:pypi/requests"

# Single described row (pyproject.toml) so source-file commits (mod.py etc.)
# never drop a File-map row — keeps the page healthy for the pure-diff rows.
_FILE_MAP = (
    "## File map - pkg-a\nTODO\n\n### pkg-a/\nTODO\n\n"
    "| Path | Kind | Description |\n|---|---|---|\n"
    "| `pyproject.toml` | file | — TODO |\n"
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _head(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()


def _seed_graph(db_path: Path) -> None:
    """repository + package pkg-a + domain core + dependency pypi/requests
    (used_by pkg-a)."""
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
        pkg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('domain', 'core', NULL, NULL, '{}', 'domain:org/repo/core')"
        )
        conn.execute(
            "INSERT INTO nodes(kind, name, path, line, attrs_json, uri) VALUES "
            "('dependency', 'requests', NULL, NULL, '{\"ecosystem\": \"pypi\"}', "
            "'dependency:pypi/requests')"
        )
        dep_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO edges(src, dst, kind, attrs_json) VALUES (?, ?, 'used_by', NULL)",
            (pkg_id, dep_id),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def gating_ws(tmp_path, monkeypatch):
    """Workspace with a REAL one-commit git repo so diff_since works unpatched."""
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    repo = workspace / "repo"
    (wiki / ".graph-wiki").mkdir(parents=True)
    (wiki / "CLAUDE.md").write_text("# Wiki\n")
    (wiki / "log.md").write_text("", encoding="utf-8")
    (repo / "packages" / "pkg-a").mkdir(parents=True)
    (repo / "packages" / "pkg-a" / "mod.py").write_text("one\n", encoding="utf-8")
    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text('[project]\nname = "pkg-a"\n', encoding="utf-8")
    (repo / "uv.lock").write_text("lock v1\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")

    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    _seed_graph(workspace / ".graph-wiki" / "code.db")
    monkeypatch.setattr(
        scan_mod, "_cg_run_build", lambda repo, ws, *, full, scope_to_repo=True: (exit_codes.SUCCESS, "", "")
    )
    monkeypatch.setattr(scan_bedrock_mod, "make_llm", lambda role, *, model_override=None: MagicMock())
    monkeypatch.setattr(
        scan_mod,
        "build_file_map",
        lambda path, **kw: _FILE_MAP if str(path).endswith("pkg-a") else None,
    )
    monkeypatch.setattr(
        scan_mod,
        "compute_state_gate",
        lambda r, **kw: {"allowed": True, "reason": "clean", "head_commit": _head(repo)},
    )
    return workspace, repo


def _emit(workspace: Path, repo: Path) -> ScanWorklist:
    worklist, _ = asyncio.run(
        scan_mod.build_scan_worklist(
            workspace_path=workspace, repo_path=repo, no_file_map=False, max_depth=3, propagate_drift=False
        )
    )
    return worklist


def _tasks(worklist: ScanWorklist) -> dict[str, ProseRefreshTask]:
    return {t.uri: t for t in worklist.prose_tasks}


def _page_for(wiki: Path, uri: str) -> Path:
    return next(p for p in (wiki / "entities").glob("*.md") if _fm.load(p).metadata.get("uri") == uri)


def _fill_page(page: Path, *, anchor: str | None) -> None:
    """Make the on-disk page healthy (prose in every TODO-ish prose section,
    every File-map row described) and optionally set the anchor."""
    post = _fm.load(str(page))
    bodies = prose_section_bodies(post.content)
    replace_prose_sections(
        page,
        {h: "Real prose." for h, b in bodies.items() if h == "## Narrative" or is_todo_like_body(b)},
    )
    fill_file_map_descriptions(page, {p: "desc" for p in file_map_todo_paths(page)})
    if anchor:
        set_frontmatter_value(page, LAST_UPDATED_COMMIT_KEY, anchor)


# ---------------------------------------------------------------------------
# Staleness matrix (rows 1-10)
# ---------------------------------------------------------------------------


def test_placeholder_package_first_fill(gating_ws) -> None:
    """[row 1] A placeholder ## Narrative on a fresh package page emits one
    prose task with trigger == "first_fill"."""
    workspace, repo = gating_ws
    tasks = _tasks(_emit(workspace, repo))
    assert _PKG_A in tasks
    assert tasks[_PKG_A].trigger == "first_fill"
    assert tasks[_PKG_A].diff is None


def test_missing_anchor_first_fill(gating_ws) -> None:
    """[row 2] A healthy package page with NO last_updated_commit re-tasks as
    first_fill (missing anchor)."""
    workspace, repo = gating_ws
    wiki = workspace / "wiki"
    _emit(workspace, repo)  # create pages
    _fill_page(_page_for(wiki, _PKG_A), anchor=None)
    tasks = _tasks(_emit(workspace, repo))
    assert _PKG_A in tasks
    assert tasks[_PKG_A].trigger == "first_fill"


def test_anchor_at_head_no_task(gating_ws) -> None:
    """[row 3] A healthy page anchored at HEAD (no commits since) emits zero
    tasks for that entity."""
    workspace, repo = gating_ws
    wiki = workspace / "wiki"
    _emit(workspace, repo)
    _fill_page(_page_for(wiki, _PKG_A), anchor=_head(repo))
    tasks = _tasks(_emit(workspace, repo))
    assert _PKG_A not in tasks


def test_diff_trigger_carries_hunks_and_changed_files(gating_ws) -> None:
    """[row 4] Anchor behind HEAD + a commit touching the package -> one task
    with trigger == "diff", the hunk text, and a non-empty changed_files."""
    workspace, repo = gating_ws
    wiki = workspace / "wiki"
    _emit(workspace, repo)
    _fill_page(_page_for(wiki, _PKG_A), anchor=_head(repo))

    # New file (NOT a described File-map row) so the preserved-drop leaves the
    # page healthy and the diff branch fires.
    (repo / "packages" / "pkg-a" / "new_helper.py").write_text("helper = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "add helper")

    tasks = _tasks(_emit(workspace, repo))
    assert _PKG_A in tasks
    task = tasks[_PKG_A]
    assert task.trigger == "diff"
    assert task.diff is not None and "new_helper.py" in task.diff and "+helper = 1" in task.diff
    assert task.changed_files == ["packages/pkg-a/new_helper.py"]


def test_unknown_anchor_yields_diff_task_with_none_diff(gating_ws, monkeypatch) -> None:
    """[row 5] An anchor SHA unknown to the repo (history rewrite) yields a
    trigger == "diff" task with diff None. The probes are patched so the
    commit_dirty side (preserved-drop) stays clean and only the prose gate sees
    the unknown anchor."""
    workspace, repo = gating_ws
    wiki = workspace / "wiki"
    _emit(workspace, repo)
    _fill_page(_page_for(wiki, _PKG_A), anchor="0000000000000000000000000000000000000000")

    monkeypatch.setattr(scan_mod, "changed_files_since", lambda r, sha, sub: [])
    monkeypatch.setattr(scan_mod, "diff_since", lambda r, sha, subs: None)
    monkeypatch.setattr(scan_mod, "changed_names_since", lambda r, sha, subs: None)

    tasks = _tasks(_emit(workspace, repo))
    assert _PKG_A in tasks
    assert tasks[_PKG_A].trigger == "diff"
    assert tasks[_PKG_A].diff is None


def test_filled_repository_and_domain_never_restale(gating_ws) -> None:
    """[row 6] Filled repository/domain pages emit no tasks even with new
    commits (first-fill-only kinds)."""
    workspace, repo = gating_ws
    wiki = workspace / "wiki"
    _emit(workspace, repo)
    _fill_page(_page_for(wiki, _REPO_URI), anchor=None)
    _fill_page(_page_for(wiki, _DOMAIN_URI), anchor=None)

    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "touch repo")

    tasks = _tasks(_emit(workspace, repo))
    assert _REPO_URI not in tasks
    assert _DOMAIN_URI not in tasks


def test_dependency_manifest_change_triggers_diff(gating_ws) -> None:
    """[row 7] A dependency page with an anchor re-tasks (trigger "diff") when a
    used_by package's pyproject.toml changes."""
    workspace, repo = gating_ws
    wiki = workspace / "wiki"
    _emit(workspace, repo)
    _fill_page(_page_for(wiki, _DEP_URI), anchor=_head(repo))

    (repo / "packages" / "pkg-a" / "pyproject.toml").write_text(
        '[project]\nname = "pkg-a"\ndependencies = ["requests>=2"]\n', encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "bump dep")

    tasks = _tasks(_emit(workspace, repo))
    assert _DEP_URI in tasks
    task = tasks[_DEP_URI]
    assert task.trigger == "diff"
    assert task.diff is not None and "pyproject.toml" in task.diff


def test_dependency_unrelated_source_change_no_task(gating_ws) -> None:
    """[row 8] A dependency page with an anchor stays quiet when the commit only
    touches an unrelated source file."""
    workspace, repo = gating_ws
    wiki = workspace / "wiki"
    _emit(workspace, repo)
    _fill_page(_page_for(wiki, _DEP_URI), anchor=_head(repo))

    (repo / "packages" / "pkg-a" / "mod.py").write_text("two\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "source change")

    tasks = _tasks(_emit(workspace, repo))
    assert _DEP_URI not in tasks


def test_prose_sections_exclude_deterministic_and_file_map(gating_ws) -> None:
    """[row 9] task.prose_sections carries only prose headings — no
    DETERMINISTIC_SECTIONS members, no ## File map."""
    workspace, repo = gating_ws
    tasks = _tasks(_emit(workspace, repo))
    sections = tasks[_PKG_A].prose_sections
    assert "## Narrative" in sections
    assert "## Purpose" in sections
    assert "## Public API" in sections
    assert "## Referenced in wiki" not in sections
    assert not any(h.startswith("## File map") for h in sections)


def test_oversized_diff_is_truncated_with_tail(gating_ws, monkeypatch) -> None:
    """[row 10] A diff past the budget is cut at a hunk boundary with the
    "(diff truncated; also changed: ...)" name-list tail."""
    workspace, repo = gating_ws
    wiki = workspace / "wiki"
    _emit(workspace, repo)
    _fill_page(_page_for(wiki, _PKG_A), anchor=_head(repo))

    (repo / "packages" / "pkg-a" / "aaa_big.py").write_text("line\n" * 80, encoding="utf-8")
    (repo / "packages" / "pkg-a" / "zzz_tail.py").write_text("tail\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "big change")

    monkeypatch.setattr(scan_mod, "truncate_diff", lambda d: _real_truncate_diff(d, budget=120))

    tasks = _tasks(_emit(workspace, repo))
    task = tasks[_PKG_A]
    assert task.trigger == "diff"
    assert task.diff is not None
    assert "(diff truncated; also changed:" in task.diff
    assert task.diff.rstrip().endswith(")")
    assert "zzz_tail.py" in task.diff.rsplit("(diff truncated; also changed:", 1)[1]


def test_one_bad_entity_does_not_abort_worklist_assembly(gating_ws, monkeypatch) -> None:
    """[fault isolation] A reader/graph-context failure on ONE entity skips just
    that entity — every other stale entity still emits its task (pre-flip these
    calls ran inside the per-item fan-out task and landed in fan.errors)."""
    workspace, repo = gating_ws
    real_build_graph_context = scan_mod._build_graph_context

    def _exploding_graph_context(reader, kind, node):
        if node.attrs.get("uri") == _PKG_A:
            raise RuntimeError("simulated reader failure")
        return real_build_graph_context(reader, kind, node)

    monkeypatch.setattr(scan_mod, "_build_graph_context", _exploding_graph_context)

    tasks = _tasks(_emit(workspace, repo))
    assert _PKG_A not in tasks  # the bad entity was skipped, not fatal
    # The other placeholder entities still emitted their first_fill tasks.
    for uri in (_REPO_URI, _DOMAIN_URI, _DEP_URI):
        assert uri in tasks, f"{uri} task missing — one bad entity aborted assembly"


# ---------------------------------------------------------------------------
# Stamp guard (rows 11-15) — hand-built worklist/results
# ---------------------------------------------------------------------------


def _healthy_page(tmp_path: Path, *, uri: str = "pkg:demo", kind: str = "package", todo_row: bool = False) -> Path:
    (tmp_path / "pages").mkdir(exist_ok=True)
    page = tmp_path / "pages" / "pkg_demo.md"
    body = "# demo\n\n## Narrative\nReal prose.\n\n## Purpose\nReal purpose.\n"
    if todo_row:
        body += (
            "\n## File map - demo\nTree overview.\n\n### demo/\nDir prose.\n\n"
            "| Path | Kind | Description |\n|---|---|---|\n"
            "| `x.py` | file | — TODO |\n"
        )
    page.write_text(f"---\nuri: {uri}\nkind: {kind}\n---\n{body}", encoding="utf-8")
    return page


def _task_for(page: Path, *, uri: str = "pkg:demo", kind: str = "package", owning_short_head: str | None = None):
    return ProseRefreshTask(
        uri=uri,
        kind=kind,
        name="demo",
        page_path=str(page),
        graph_path="packages/demo",
        language="python",
        entity_root="packages/demo",
        trigger="first_fill",
        prose_sections={"## Narrative": "old"},
        owning_short_head=owning_short_head,
    )


async def _apply(tmp_path: Path, worklist: ScanWorklist, results: ScanResults):
    wiki = tmp_path / "wiki"
    (wiki / "entities").mkdir(parents=True, exist_ok=True)
    return await apply_scan_results(worklist, results, wiki, tmp_path / "repo")


async def test_stamp_on_successful_result_and_healthy_page(tmp_path) -> None:
    """[row 11] successful result + healthy page -> last_updated_commit stamped
    with owning_short_head or the worklist short_head."""
    page = _healthy_page(tmp_path)
    task = _task_for(page)
    worklist = ScanWorklist(head_commit="deadbeef", short_head="deadbee", prose_tasks=[task])
    results = ScanResults(prose=[ProseRefreshResult(uri="pkg:demo", sections={"## Narrative": "New prose."})])
    out = await _apply(tmp_path, worklist, results)
    assert out.stamped == 1
    assert _fm.load(str(page)).metadata.get(LAST_UPDATED_COMMIT_KEY) == "deadbee"
    assert "New prose." in page.read_text(encoding="utf-8")


async def test_stamp_uses_owning_short_head_when_present(tmp_path) -> None:
    """[row 11b] task.owning_short_head wins over the worklist short_head."""
    page = _healthy_page(tmp_path)
    task = _task_for(page, owning_short_head="abc1234")
    worklist = ScanWorklist(head_commit="deadbeef", short_head="deadbee", prose_tasks=[task])
    results = ScanResults(prose=[ProseRefreshResult(uri="pkg:demo")])
    out = await _apply(tmp_path, worklist, results)
    assert out.stamped == 1
    assert _fm.load(str(page)).metadata.get(LAST_UPDATED_COMMIT_KEY) == "abc1234"


async def test_stamp_skipped_when_result_failed(tmp_path) -> None:
    """[row 12] A result with error set leaves the anchor untouched."""
    page = _healthy_page(tmp_path)
    task = _task_for(page)
    worklist = ScanWorklist(head_commit="deadbeef", short_head="deadbee", prose_tasks=[task])
    results = ScanResults(prose=[ProseRefreshResult(uri="pkg:demo", error="tool loop capped")])
    out = await _apply(tmp_path, worklist, results)
    assert out.stamped == 0
    assert LAST_UPDATED_COMMIT_KEY not in _fm.load(str(page)).metadata


async def test_stamp_skipped_when_result_absent(tmp_path) -> None:
    """[row 13] No result for the task's uri -> anchor untouched."""
    page = _healthy_page(tmp_path)
    task = _task_for(page)
    worklist = ScanWorklist(head_commit="deadbeef", short_head="deadbee", prose_tasks=[task])
    out = await _apply(tmp_path, worklist, ScanResults())
    assert out.stamped == 0
    assert LAST_UPDATED_COMMIT_KEY not in _fm.load(str(page)).metadata


async def test_stamp_skipped_when_todo_row_remains(tmp_path) -> None:
    """[row 14] Successful result but a `— TODO` File-map row remains ->
    anchor untouched (the page stays stale so the next scan retries)."""
    page = _healthy_page(tmp_path, todo_row=True)
    task = _task_for(page)
    worklist = ScanWorklist(head_commit="deadbeef", short_head="deadbee", prose_tasks=[task])
    results = ScanResults(prose=[ProseRefreshResult(uri="pkg:demo", sections={"## Narrative": "New prose."})])
    out = await _apply(tmp_path, worklist, results)
    assert out.stamped == 0
    assert LAST_UPDATED_COMMIT_KEY not in _fm.load(str(page)).metadata


async def test_dependency_page_stamped_on_success(tmp_path) -> None:
    """[row 15] A dependency page joins the stamp on success (new kinds)."""
    page = _healthy_page(tmp_path, uri="dependency:pypi/requests", kind="dependency")
    task = _task_for(page, uri="dependency:pypi/requests", kind="dependency")
    worklist = ScanWorklist(head_commit="deadbeef", short_head="deadbee", prose_tasks=[task])
    results = ScanResults(prose=[ProseRefreshResult(uri="dependency:pypi/requests")])
    out = await _apply(tmp_path, worklist, results)
    assert out.stamped == 1
    assert _fm.load(str(page)).metadata.get(LAST_UPDATED_COMMIT_KEY) == "deadbee"
