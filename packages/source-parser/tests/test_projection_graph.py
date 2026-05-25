import json
from pathlib import Path

import pytest

from _fixture_loader import FIXTURES_ROOT
from source_parser import parse_file, to_graph_records


def _serialize_records(records) -> dict:
    return {
        "nodes": [
            {
                "kind": n.kind,
                "name": n.name,
                "path": n.path,
                "line": n.line,
                "attrs": n.attrs,
            }
            for n in records.nodes
        ],
        "edges": [{"src": list(e.src), "dst": list(e.dst), "kind": e.kind, "attrs": e.attrs} for e in records.edges],
    }


def _substitute(obj, path_str):
    if isinstance(obj, dict):
        return {k: _substitute(v, path_str) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute(v, path_str) for v in obj]
    if obj == "PATH":
        return path_str
    return obj


GRAPH_FIXTURES = [
    ("python", "basic_function.py"),
    ("python", "class_with_decorator.py"),
    ("javascript", "basic_function.js"),
    ("javascript", "esm_module.mjs"),
    ("typescript", "basic_function.ts"),
    ("typescript", "interface_call.ts"),
]


@pytest.mark.parametrize(
    ("language", "fname"),
    GRAPH_FIXTURES,
    ids=[f"{lang}-{Path(f).stem}" for lang, f in GRAPH_FIXTURES],
)
def test_graph_projection(language, fname):
    fixture = FIXTURES_ROOT / language / fname
    expected_path = fixture.with_name(fixture.stem + ".graph.expected.json")
    tree = parse_file(fixture, package="fixtures")
    actual = _serialize_records(to_graph_records(tree))
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    expected = _substitute(expected, str(fixture))
    assert actual["nodes"] == expected["nodes"]
    assert sorted(map(json.dumps, actual["edges"])) == sorted(map(json.dumps, expected["edges"]))
