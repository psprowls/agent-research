# packages/graph-wiki-core/tests/unit/test_scan_contract.py
from __future__ import annotations

import pytest
from graph_wiki_core.commands.scan_contract import (
    DriftSectionInput,
    DriftTask,
    FillNeeds,
    FillResult,
    FillTask,
    PropagateEntity,
    PropagateTask,
    ScanResults,
    ScanWorklist,
)


def _sample_worklist() -> ScanWorklist:
    return ScanWorklist(
        head_commit="a1b2c3d4e5",
        short_head="a1b2c3d",
        fill_tasks=[
            FillTask(
                uri="pkg:wiki-io",
                kind="package",
                name="wiki-io",
                page_path="/abs/wiki/entities/pkg_wiki-io.md",
                graph_path="packages/wiki-io",
                language="python",
                needs=FillNeeds(
                    narrative=True,
                    file_todo_paths=["src/wiki_io/scan_monorepo.py"],
                    dir_todo_contexts=["src/wiki_io/"],
                    overview=True,
                    purpose=True,
                    public_api=False,
                ),
            )
        ],
        drift_tasks=[
            DriftTask(
                uri="pkg:wiki-io",
                page_path="/abs/wiki/entities/pkg_wiki-io.md",
                anchor="a1b2c3d",
                narrative="Ground-truth prose.",
                file_map="## File map - wiki-io\n...",
                sections=[DriftSectionInput(heading="## Purpose", chunk="Old purpose body.")],
            )
        ],
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


def test_results_round_trips() -> None:
    results = ScanResults(
        fills=[
            FillResult(
                uri="pkg:wiki-io",
                narrative="New prose.",
                file_descriptions={"src/wiki_io/scan_monorepo.py": "Scan helpers."},
                dir_descriptions={"src/wiki_io/": "IO layer."},
                overview="Package overview.",
                purpose="Purpose draft.",
                public_api=None,
            )
        ],
        drift=[],
        propagate=[],
    )
    restored = ScanResults.from_json(results.to_json())
    assert restored == results


def test_results_tolerates_sparse_fill() -> None:
    # A fill carrying only a narrative — every other field absent.
    payload = {"schema": 1, "fills": [{"uri": "pkg:x", "narrative": "Only prose."}], "drift": [], "propagate": []}
    results = ScanResults.from_dict(payload)
    fill = results.fills[0]
    assert fill.narrative == "Only prose."
    assert fill.file_descriptions == {}
    assert fill.dir_descriptions == {}
    assert fill.overview is None
    assert fill.purpose is None
    assert fill.public_api is None


def test_results_rejects_bad_schema() -> None:
    with pytest.raises(ValueError):
        ScanResults.from_dict({"schema": 99, "fills": [], "drift": [], "propagate": []})
