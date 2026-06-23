from __future__ import annotations

import pytest
from guidance_io.frontmatter import emit, keyword_shape_warnings, parse, tag_violations, validate
from guidance_io.vocab import Vocab


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


def _valid_fm() -> dict:
    return {
        "title": "Use a List Virtualizer for Any List",
        "category": "guidance",
        "summary": "Use a virtualizer instead of ScrollView for lists.",
        "topic": "react-native",
        "applies_when": "Rendering any scrollable list in React Native.",
        "impact": "high",
        "updated": "2026-06-08",
        "tokens": 0,
    }


def test_validate_accepts_minimal_valid_fm() -> None:
    assert validate(_valid_fm()) == []


def test_validate_accepts_full_triggers_block() -> None:
    fm = _valid_fm()
    fm["triggers"] = {
        "globs": ["**/*.tsx"],
        "keywords": ["ScrollView", "FlatList"],
        "entities": ["[[entities/pkg_foo]]"],
    }
    assert validate(fm) == []


def test_validate_flags_missing_required_key() -> None:
    fm = _valid_fm()
    del fm["summary"]
    errors = validate(fm)
    assert any("summary" in e for e in errors)


def test_validate_flags_wrong_category() -> None:
    fm = _valid_fm()
    fm["category"] = "concept"
    errors = validate(fm)
    assert any("category" in e for e in errors)


def test_validate_flags_bad_impact() -> None:
    fm = _valid_fm()
    fm["impact"] = "HIGH"  # uppercase is invalid; enum is lowercased
    errors = validate(fm)
    assert any("impact" in e for e in errors)


def test_validate_flags_empty_topic() -> None:
    fm = _valid_fm()
    fm["topic"] = "  "
    errors = validate(fm)
    assert any("topic" in e for e in errors)


def test_validate_flags_non_mapping_triggers() -> None:
    fm = _valid_fm()
    fm["triggers"] = ["**/*.tsx"]
    errors = validate(fm)
    assert any("triggers" in e for e in errors)


def test_validate_flags_non_list_trigger_value() -> None:
    fm = _valid_fm()
    fm["triggers"] = {"globs": "**/*.tsx"}  # should be a list
    errors = validate(fm)
    assert any("globs" in e for e in errors)


def _vocab() -> Vocab:
    return Vocab(
        topics=frozenset({"python"}),
        tags=frozenset({"retry", "styling"}),
        aliases={"retries": "retry"},
        vocab_hash="h",
    )


def test_tag_violations_accepts_allowlisted_and_alias() -> None:
    fm = {"tags": ["retry", "Retries", "styling"]}
    assert tag_violations(fm, _vocab()) == []


def test_tag_violations_flags_off_vocab() -> None:
    fm = {"tags": ["retry", "made-up"]}
    errors = tag_violations(fm, _vocab())
    assert len(errors) == 1
    assert "made-up" in errors[0]


def test_tag_violations_no_tags_key() -> None:
    assert tag_violations({}, _vocab()) == []


def test_keyword_shape_warns_on_prose() -> None:
    fm = {"triggers": {"keywords": ["FlatList", "use a virtualizer for lists"]}}
    warnings = keyword_shape_warnings(fm)
    assert len(warnings) == 1
    assert "use a virtualizer" in warnings[0]


def test_keyword_shape_ok_for_identifiers() -> None:
    fm = {"triggers": {"keywords": ["ScrollView", "recursion_limit", "metro.config.js"]}}
    assert keyword_shape_warnings(fm) == []


def test_workflow_round_trips_through_parse_emit():
    fm = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": "python",
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-23",
        "tokens": 0,
        "workflow": ["design", "plan"],
    }
    text = emit(fm) + "\nbody\n"
    parsed_fm, body = parse(text)
    assert parsed_fm["workflow"] == ["design", "plan"]
    assert body.strip() == "body"


def test_validate_flags_non_list_workflow():
    fm = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": "python",
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-23",
        "tokens": 0,
        "workflow": "design",  # wrong type
    }
    errors = validate(fm)
    assert any("workflow" in e for e in errors)


def test_validate_allows_absent_empty_or_unknown_workflow_values():
    base = {
        "title": "T",
        "category": "guidance",
        "summary": "s",
        "topic": "python",
        "applies_when": "w",
        "impact": "high",
        "updated": "2026-06-23",
        "tokens": 0,
    }
    # absent
    assert not any("workflow" in e for e in validate(base))
    # empty list
    assert not any("workflow" in e for e in validate({**base, "workflow": []}))
    # unknown value strings are NOT validated here
    assert not any("workflow" in e for e in validate({**base, "workflow": ["banana"]}))
