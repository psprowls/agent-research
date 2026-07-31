"""Apply-half: per-entity result files (`--results-dir`) + provider-agnostic sanitizing.

The plugin path's subagents each write their own result JSON instead of routing
every entity's replacement prose back through the scanner's context, so apply
globs a directory. Every result — file, directory, or in-process Bedrock — goes
through sanitize_prose_result before it touches a page.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import frontmatter as _fm
import pytest
from graph_wiki_core.commands.scan import apply_scan_results, apply_scan_worklist, load_results_dir
from graph_wiki_core.commands.scan_contract import (
    ProseRefreshResult,
    ProseRefreshTask,
    ScanResults,
    ScanWorklist,
)

_URI = "pkg:org/repo/pkg-a"

_PAGE = """\
---
uri: pkg:org/repo/pkg-a
kind: package
---

# pkg-a

## Narrative
_(scanner will populate on next scan)_

## Purpose
> TODO: explain why this package exists.
"""


@pytest.fixture
def ws(tmp_path: Path, monkeypatch) -> Path:
    workspace = tmp_path / "workspace"
    wiki = workspace / "wiki"
    (wiki / "entities").mkdir(parents=True)
    (wiki / "log.md").write_text("", encoding="utf-8")
    (wiki / "index.md").write_text("---\ntitle: Index\ncategory: meta\nsummary: i\n---\n", encoding="utf-8")
    (workspace / "repo").mkdir()
    (wiki / "entities" / "pkg_pkg-a.md").write_text(_PAGE, encoding="utf-8")
    (workspace / ".graph-wiki").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(workspace))
    return workspace


def _task(ws: Path) -> ProseRefreshTask:
    return ProseRefreshTask(
        uri=_URI,
        kind="package",
        name="pkg-a",
        page_path=str(ws / "wiki" / "entities" / "pkg_pkg-a.md"),
        graph_path="packages/pkg-a",
        language="python",
        entity_root="packages/pkg-a",
        trigger="first_fill",
        prose_sections={"## Narrative": "", "## Purpose": "> TODO: explain why this package exists."},
    )


def _worklist(ws: Path) -> ScanWorklist:
    return ScanWorklist(head_commit=None, short_head=None, prose_tasks=[_task(ws)])


def _write_worklist(ws: Path) -> Path:
    path = ws / ".graph-wiki" / "worklist.json"
    path.write_text(_worklist(ws).to_json(), encoding="utf-8")
    return path


def _narrative(ws: Path) -> str:
    text = (ws / "wiki" / "entities" / "pkg_pkg-a.md").read_text(encoding="utf-8")
    return text.split("## Narrative", 1)[1].split("##", 1)[0].strip()


# --- load_results_dir -------------------------------------------------------


def test_load_results_dir_skips_malformed_files(tmp_path: Path):
    """broken.json fails to parse as JSON at all; missing_uri_key.json parses but
    has no "uri" key, so ProseRefreshResult.from_dict's ``d["uri"]`` raises
    KeyError. Both land in the generic except branch (the "unreadable" message),
    NOT the dedicated falsy-uri guard — see
    test_load_results_dir_empty_and_null_uri_hit_dedicated_guard for that path.
    """
    d = tmp_path / "results"
    d.mkdir()
    (d / "good.json").write_text(json.dumps({"uri": _URI, "sections": {"## Narrative": "ok"}}), encoding="utf-8")
    (d / "broken.json").write_text("{not json", encoding="utf-8")
    (d / "missing_uri_key.json").write_text(json.dumps({"sections": {}}), encoding="utf-8")

    results, errors = load_results_dir(d)

    assert [r.uri for r in results] == [_URI]
    assert len(errors) == 2
    broken_error = next(e for e in errors if "broken.json" in e)
    assert "unreadable prose result" in broken_error
    missing_key_error = next(e for e in errors if "missing_uri_key.json" in e)
    assert "unreadable prose result" in missing_key_error
    assert "no uri" not in missing_key_error


def test_load_results_dir_empty_and_null_uri_hit_dedicated_guard(tmp_path: Path):
    """Unlike a missing "uri" key (KeyError -> generic except), an explicit
    falsy uri parses fine and is caught by the dedicated `if not result.uri`
    guard, which reports a distinct "has no uri" message.
    """
    d = tmp_path / "results"
    d.mkdir()
    (d / "empty_uri.json").write_text(json.dumps({"uri": "", "sections": {}}), encoding="utf-8")
    (d / "null_uri.json").write_text(json.dumps({"uri": None, "sections": {}}), encoding="utf-8")

    results, errors = load_results_dir(d)

    assert results == []
    assert len(errors) == 2
    empty_error = next(e for e in errors if "empty_uri.json" in e)
    assert "prose result has no uri" in empty_error
    assert "unreadable" not in empty_error
    null_error = next(e for e in errors if "null_uri.json" in e)
    assert "prose result has no uri" in null_error
    assert "unreadable" not in null_error


def test_load_results_dir_missing_directory_is_empty(tmp_path: Path):
    assert load_results_dir(tmp_path / "nope") == ([], [])


# --- apply_scan_worklist source merging ------------------------------------


def test_results_dir_alone_applies(ws: Path):
    worklist_path = _write_worklist(ws)
    results_dir = ws / ".graph-wiki" / "results"
    results_dir.mkdir()
    (results_dir / "pkg_pkg-a.json").write_text(
        json.dumps({"uri": _URI, "sections": {"## Narrative": "From a per-entity file."}}), encoding="utf-8"
    )

    applied = asyncio.run(
        apply_scan_worklist(
            workspace_path=ws,
            repo_path=ws / "repo",
            results_path=None,
            short_head=None,
            propagate=False,
            worklist_path=worklist_path,
            results_dir=results_dir,
        )
    )

    assert applied.narrated == 1
    assert _narrative(ws) == "From a per-entity file."


def test_file_and_dir_sources_merge_with_dir_winning(ws: Path):
    worklist_path = _write_worklist(ws)
    results_path = ws / ".graph-wiki" / "results.json"
    results_path.write_text(
        ScanResults(prose=[ProseRefreshResult(uri=_URI, sections={"## Narrative": "From the file."})]).to_json(),
        encoding="utf-8",
    )
    results_dir = ws / ".graph-wiki" / "results"
    results_dir.mkdir()
    (results_dir / "pkg_pkg-a.json").write_text(
        json.dumps({"uri": _URI, "sections": {"## Narrative": "From the directory."}}), encoding="utf-8"
    )

    asyncio.run(
        apply_scan_worklist(
            workspace_path=ws,
            repo_path=ws / "repo",
            results_path=results_path,
            short_head=None,
            propagate=False,
            worklist_path=worklist_path,
            results_dir=results_dir,
        )
    )

    assert _narrative(ws) == "From the directory."


def test_malformed_result_file_surfaces_as_entity_error_not_a_crash(ws: Path):
    worklist_path = _write_worklist(ws)
    results_dir = ws / ".graph-wiki" / "results"
    results_dir.mkdir()
    (results_dir / "pkg_pkg-a.json").write_text(
        json.dumps({"uri": _URI, "sections": {"## Narrative": "Healthy."}}), encoding="utf-8"
    )
    (results_dir / "zz_broken.json").write_text("not json at all", encoding="utf-8")

    applied = asyncio.run(
        apply_scan_worklist(
            workspace_path=ws,
            repo_path=ws / "repo",
            results_path=None,
            short_head=None,
            propagate=False,
            worklist_path=worklist_path,
            results_dir=results_dir,
        )
    )

    assert applied.narrated == 1, "a sibling's bad file must not cost a healthy entity its prose"
    assert any("zz_broken.json" in e for e in applied.entity_errors)


def test_neither_source_is_a_programming_error(ws: Path):
    worklist_path = _write_worklist(ws)
    with pytest.raises(ValueError):
        asyncio.run(
            apply_scan_worklist(
                workspace_path=ws,
                repo_path=ws / "repo",
                results_path=None,
                short_head=None,
                propagate=False,
                worklist_path=worklist_path,
                results_dir=None,
            )
        )


# --- apply-side sanitizing --------------------------------------------------


def test_apply_sanitizes_deterministic_out_of_surface_and_todo_sections(ws: Path):
    """The plugin path never had this filter; now both providers get it."""
    results = ScanResults(
        prose=[
            ProseRefreshResult(
                uri=_URI,
                sections={
                    "## File map — pkg-a": "| a | b | c |",
                    "## Referenced in wiki": "- [[x]]",
                    "## Invented": "not on this page",
                    "## Narrative": "> TODO: still a placeholder.",
                },
            )
        ]
    )

    applied = asyncio.run(apply_scan_results(_worklist(ws), results, ws / "wiki", ws / "repo"))

    assert applied.narrated == 0
    assert applied.sections_filled == 0
    text = (ws / "wiki" / "entities" / "pkg_pkg-a.md").read_text(encoding="utf-8")
    assert "_(scanner will populate on next scan)_" in text
    assert "## Invented" not in text
    assert _fm.load(ws / "wiki" / "entities" / "pkg_pkg-a.md").metadata["uri"] == _URI
