"""Unit tests for the scan-side file-map description fan-out helpers:
build_file_describer_prompt + parse_file_describer_output.
"""

from __future__ import annotations

from graph_wiki_core.commands.scan import (
    build_file_describer_prompt,
    parse_file_describer_output,
)
from graph_wiki_core.prompts.file_describer import FILE_DESCRIBER_SYSTEM

# ---------------------------------------------------------------------------
# parse_file_describer_output
# ---------------------------------------------------------------------------


def test_parse_plain_json_object():
    out = parse_file_describer_output(
        '{"pyproject.toml": "package manifest", "src/core.py": "the engine"}'
    )
    assert out == {
        "pyproject.toml": "package manifest",
        "src/core.py": "the engine",
    }


def test_parse_strips_json_code_fence():
    text = '```json\n{"a.py": "module a"}\n```'
    assert parse_file_describer_output(text) == {"a.py": "module a"}


def test_parse_extracts_object_from_surrounding_prose():
    text = 'Here are the descriptions:\n{"a.py": "module a"}\nHope that helps!'
    assert parse_file_describer_output(text) == {"a.py": "module a"}


def test_parse_collapses_multiline_and_whitespace():
    out = parse_file_describer_output('{"a.py": "  module   a\\n  helper  "}')
    assert out == {"a.py": "module a helper"}


def test_parse_drops_non_string_values():
    out = parse_file_describer_output('{"a.py": "ok", "b.py": 42, "c.py": null}')
    assert out == {"a.py": "ok"}


def test_parse_invalid_returns_empty():
    assert parse_file_describer_output("not json at all") == {}
    assert parse_file_describer_output("") == {}
    assert parse_file_describer_output("[1, 2, 3]") == {}


# ---------------------------------------------------------------------------
# build_file_describer_prompt
# ---------------------------------------------------------------------------


def test_build_prompt_uses_describer_system_and_lists_paths():
    pkg = {"name": "foo", "path": "packages/foo", "type": "library", "language": "python"}
    todo = ["pyproject.toml", "src/foo/__init__.py"]
    system, human = build_file_describer_prompt(pkg, todo, repo_root=None)

    assert system == FILE_DESCRIBER_SYSTEM
    assert "Package name: foo" in human
    # Each TODO path appears verbatim as a bullet for the model to key on.
    assert "- pyproject.toml" in human
    assert "- src/foo/__init__.py" in human
    assert "JSON" in human
