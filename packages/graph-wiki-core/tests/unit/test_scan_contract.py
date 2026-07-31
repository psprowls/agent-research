# packages/graph-wiki-core/tests/unit/test_scan_contract.py
from __future__ import annotations

import pytest
from graph_wiki_core.commands.scan_contract import (
    PropagateEntity,
    PropagateTask,
    ProseRefreshResult,
    ProseRefreshTask,
    ScanResults,
    ScanWorklist,
)


def _prose_task(**over):
    base = dict(
        uri="pkg:demo",
        kind="package",
        name="demo",
        page_path="/w/entities/pkg_demo.md",
        graph_path="packages/demo",
        language="python",
        entity_root="packages/demo",
        trigger="diff",
        diff="diff --git a/x b/x\n@@ -1 +1 @@\n+x\n",
        changed_files=["packages/demo/x.py"],
        page_content="---\n---\n# demo\n",
        file_map_rows="| `x.py` | file | — TODO |",
        prose_sections={"## Narrative": "old"},
        graph_context="Language: python",
        owning_short_head="abc1234",
    )
    base.update(over)
    return ProseRefreshTask(**base)


def _sample_worklist() -> ScanWorklist:
    return ScanWorklist(
        head_commit="a1b2c3d4e5",
        short_head="a1b2c3d",
        prose_tasks=[_prose_task(uri="pkg:wiki-io", name="wiki-io")],
        propagate_tasks=[
            PropagateTask(
                kind="concept",
                target_slug="fanout",
                title="Fan-out",
                page_path="/abs/wiki/concepts/fanout.md",
                entities=[
                    PropagateEntity(
                        stem="pkg_wiki-io",
                        narrative="Now async.",
                        changed_files=["src/wiki_io/pool.py"],
                    )
                ],
            )
        ],
        propagate_anchors={"pkg:wiki-io": "a1b2c3d"},
        propagate_pages={"pkg:wiki-io": "/abs/wiki/entities/pkg_wiki-io.md"},
    )


def test_worklist_round_trips() -> None:
    wl = _sample_worklist()
    restored = ScanWorklist.from_json(wl.to_json())
    assert restored == wl


def test_worklist_is_empty_tracks_prose_tasks() -> None:
    assert ScanWorklist(head_commit=None, short_head=None).is_empty
    assert not ScanWorklist(head_commit=None, short_head=None, prose_tasks=[_prose_task()]).is_empty


def test_results_round_trips() -> None:
    results = ScanResults(
        prose=[
            ProseRefreshResult(
                uri="pkg:wiki-io",
                sections={"## Narrative": "New prose.", "## Purpose": "Purpose draft."},
                file_map_descriptions={"src/wiki_io/scan_monorepo.py": "Scan helpers."},
                dir_descriptions={"src/wiki_io/": "IO layer."},
                overview="Package overview.",
                error=None,
            )
        ],
        propagate=[],
    )
    restored = ScanResults.from_json(results.to_json())
    assert restored == results


def test_results_tolerates_sparse_prose() -> None:
    # A prose result carrying only sections — every other field absent.
    payload = {
        "schema": 2,
        "prose": [{"uri": "pkg:x", "sections": {"## Narrative": "Only prose."}}],
        "propagate": [],
    }
    results = ScanResults.from_dict(payload)
    result = results.prose[0]
    assert result.sections == {"## Narrative": "Only prose."}
    assert result.file_map_descriptions == {}
    assert result.dir_descriptions == {}
    assert result.overview is None
    assert result.error is None


def test_results_rejects_bad_schema() -> None:
    with pytest.raises(ValueError):
        ScanResults.from_dict({"schema": 99, "prose": [], "propagate": []})


def test_v1_worklist_payload_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported worklist schema: 1"):
        ScanWorklist.from_dict({"schema": 1, "head_commit": None, "short_head": None, "fill_tasks": []})


def test_v1_results_payload_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported results schema: 1"):
        ScanResults.from_dict({"schema": 1, "fills": [], "propagate": []})


def test_prose_refresh_task_round_trip():
    task = _prose_task()
    assert ProseRefreshTask.from_dict(task.to_dict()) == task


def test_prose_refresh_task_none_diff_first_fill():
    task = _prose_task(trigger="first_fill", diff=None, changed_files=[])
    restored = ProseRefreshTask.from_dict(task.to_dict())
    assert restored.diff is None and restored.trigger == "first_fill"


def test_prose_refresh_result_round_trip():
    result = ProseRefreshResult(
        uri="pkg:demo",
        sections={"## Narrative": "new"},
        file_map_descriptions={"src/x.py": "does x"},
        dir_descriptions={"src": "sources"},
        overview="pkg overview",
        error=None,
    )
    assert ProseRefreshResult.from_dict(result.to_dict()) == result


def test_prose_refresh_result_defaults():
    r = ProseRefreshResult.from_dict({"uri": "pkg:demo"})
    assert r.sections == {} and r.file_map_descriptions == {} and r.dir_descriptions == {}
    assert r.overview is None and r.error is None
