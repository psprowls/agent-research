from __future__ import annotations

import pytest
from guidance_io.frontmatter import emit, parse


def test_parse_roundtrip() -> None:
    text = "---\ntitle: Use a Virtualizer\ncategory: guidance\n---\n\n## Guidance\nContent.\n"
    fm, body = parse(text)
    assert fm == {"title": "Use a Virtualizer", "category": "guidance"}
    assert body.strip() == "## Guidance\nContent."


def test_parse_nested_triggers_block() -> None:
    text = "---\ntriggers:\n  globs: ['**/*.tsx']\n  keywords: [ScrollView, FlatList]\n---\n"
    fm, _ = parse(text)
    assert fm["triggers"]["globs"] == ["**/*.tsx"]
    assert fm["triggers"]["keywords"] == ["ScrollView", "FlatList"]


def test_parse_missing_open_fence_raises() -> None:
    with pytest.raises(ValueError, match="no frontmatter block"):
        parse("title: foo\n")


def test_parse_unclosed_fence_raises() -> None:
    with pytest.raises(ValueError, match="unclosed frontmatter"):
        parse("---\ntitle: foo\n")


def test_parse_non_mapping_raises() -> None:
    with pytest.raises(ValueError, match="YAML mapping"):
        parse("---\n- item1\n- item2\n---\n")


def test_emit_parse_roundtrip() -> None:
    fm = {"title": "Test", "category": "guidance", "tags": ["performance", "lists"]}
    emitted = emit(fm)
    parsed_fm, _ = parse(emitted + "\n\nbody\n")
    assert parsed_fm == fm
