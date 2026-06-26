from __future__ import annotations

import pytest
from work_io.frontmatter import emit, parse


def test_parse_roundtrip() -> None:
    text = "---\ntitle: Fix the bug\nstatus: open\n---\n\n## Body\nContent here.\n"
    fm, body = parse(text)
    assert fm == {"title": "Fix the bug", "status": "open"}
    assert body.strip() == "## Body\nContent here."


def test_parse_list_field() -> None:
    text = "---\naffects:\n  - packages/foo\n  - packages/bar\n---\n"
    fm, body = parse(text)
    assert fm["affects"] == ["packages/foo", "packages/bar"]
    assert body == ""


def test_parse_missing_open_fence_raises() -> None:
    with pytest.raises(ValueError, match="no frontmatter block"):
        parse("title: foo\n")


def test_parse_unclosed_fence_raises() -> None:
    with pytest.raises(ValueError, match="unclosed frontmatter"):
        parse("---\ntitle: foo\n")


def test_parse_broken_yaml_raises_value_error() -> None:
    with pytest.raises(ValueError, match="malformed frontmatter YAML"):
        parse("---\nbad: [unclosed\n---\n")


def test_parse_non_mapping_raises() -> None:
    with pytest.raises(ValueError, match="YAML mapping"):
        parse("---\n- item1\n- item2\n---\n")


def test_parse_empty_frontmatter() -> None:
    text = "---\n---\n\nbody text\n"
    fm, body = parse(text)
    assert fm == {}
    assert body.strip() == "body text"


def test_emit_produces_fenced_block() -> None:
    fm = {"title": "My item", "status": "open"}
    result = emit(fm)
    assert result.startswith("---\n")
    assert result.endswith("---")
    assert "title: My item" in result
    assert "status: open" in result


def test_emit_parse_roundtrip() -> None:
    fm = {"title": "Test", "kind": "bug", "affects": ["packages/foo"]}
    emitted = emit(fm)
    parsed_fm, _ = parse(emitted + "\n\nbody\n")
    assert parsed_fm == fm


def test_parent_and_depends_on_round_trip() -> None:
    src = (
        "---\n"
        "title: Child A\n"
        "kind: feature\n"
        "status: open\n"
        "parent: 2026-06-26-some-epic\n"
        "depends_on:\n"
        "- 2026-06-26-child-b\n"
        "---\n"
        "body\n"
    )
    fm, _body = parse(src)
    assert fm["parent"] == "2026-06-26-some-epic"
    assert fm["depends_on"] == ["2026-06-26-child-b"]
    # re-emit then re-parse: keys survive
    fm2, _ = parse(emit(fm) + "\nbody\n")
    assert fm2["parent"] == "2026-06-26-some-epic"
    assert fm2["depends_on"] == ["2026-06-26-child-b"]
