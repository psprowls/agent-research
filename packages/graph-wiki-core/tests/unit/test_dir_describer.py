"""Unit tests for build_dir_describer_prompt and parse_dir_describer_output."""

from __future__ import annotations

from graph_wiki_core.prompts.dir_describer import (
    DIR_DESCRIBER_SYSTEM,
    build_dir_describer_prompt,
    parse_dir_describer_output,
)

# --- parse_dir_describer_output ---


def test_parse_plain_json():
    out = parse_dir_describer_output('{"": "root files", "src": "source code"}')
    assert out == {"": "root files", "src": "source code"}


def test_parse_strips_json_fence():
    text = '```json\n{"src": "module code"}\n```'
    assert parse_dir_describer_output(text) == {"src": "module code"}


def test_parse_extracts_from_surrounding_prose():
    text = 'Here are the descriptions:\n{"src": "main source"}\nDone.'
    assert parse_dir_describer_output(text) == {"src": "main source"}


def test_parse_drops_non_string_values():
    out = parse_dir_describer_output('{"src": "ok", "tests": 42, "docs": null}')
    assert out == {"src": "ok"}


def test_parse_returns_empty_on_failure():
    assert parse_dir_describer_output("not json") == {}
    assert parse_dir_describer_output("") == {}
    assert parse_dir_describer_output("[1, 2]") == {}


# --- build_dir_describer_prompt ---


def test_build_prompt_uses_system_constant():
    system, _ = build_dir_describer_prompt({"name": "foo"}, [""], {}, needs_overview=False)
    assert system is DIR_DESCRIBER_SYSTEM


def test_build_prompt_lists_context_keys():
    _, human = build_dir_describer_prompt({"name": "foo"}, ["", "src"], {}, needs_overview=False)
    assert "''" in human
    assert "'src'" in human


def test_build_prompt_includes_overview_when_needed():
    _, human = build_dir_describer_prompt({"name": "foo"}, [""], {}, needs_overview=True)
    assert "_overview" in human


def test_build_prompt_omits_overview_when_not_needed():
    _, human = build_dir_describer_prompt({"name": "foo"}, [""], {}, needs_overview=False)
    assert "_overview" not in human


def test_build_prompt_groups_files_by_context():
    file_descs = {
        "pyproject.toml": "package manifest",
        "src/core.py": "core module",
        "src/utils.py": "utility functions",
    }
    _, human = build_dir_describer_prompt({"name": "foo"}, ["", "src"], file_descs, needs_overview=False)
    assert "pyproject.toml" in human
    assert "src/core.py" in human


def test_build_prompt_deepest_first_ordering():
    _, human = build_dir_describer_prompt({"name": "foo"}, ["", "src", "src/internal"], {}, needs_overview=False)
    # "src/internal" (deeper) appears before "src" (shallower) in the output
    assert human.index("'src/internal'") < human.index("'src'")


def test_build_prompt_includes_files_for_overview_only():
    file_descs = {"foo.py": "main module", "bar.py": "utility functions"}
    _, human = build_dir_describer_prompt({"name": "pkg"}, [], file_descs, needs_overview=True)
    assert "foo.py" in human
    assert "bar.py" in human
