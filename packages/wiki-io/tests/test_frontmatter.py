"""Tests for the shared real-YAML frontmatter parser."""

import datetime as dt

from wiki_io.frontmatter import FRONTMATTER_RE, parse


def test_parse_typed_values():
    text = (
        "---\n"
        "title: Some Page\n"
        "updated: 2026-08-02\n"
        "tokens: 983\n"
        "load_bearing: true\n"
        "supersedes: null\n"
        "tags:\n"
        "- yaml\n"
        "- parser\n"
        "affects: [pkg-a, pkg-b]\n"
        "---\n"
        "\nbody\n"
    )
    fm, err = parse(text)
    assert err is None
    assert fm["title"] == "Some Page"
    assert fm["updated"] == dt.date(2026, 8, 2)
    assert fm["tokens"] == 983
    assert fm["load_bearing"] is True
    assert fm["supersedes"] is None
    assert fm["tags"] == ["yaml", "parser"]
    assert fm["affects"] == ["pkg-a", "pkg-b"]  # flow style, invisible to the old parser


def test_parse_no_frontmatter_is_not_an_error():
    fm, err = parse("# Just a heading\n\nbody\n")
    assert fm == {}
    assert err is None


def test_parse_malformed_yaml_fails_soft():
    text = "---\ntitle: [unclosed\n---\n\nbody\n"
    fm, err = parse(text)
    assert fm == {}
    assert err is not None
    assert isinstance(err, str)


def test_parse_non_mapping_frontmatter_fails_soft():
    text = "---\n- a\n- b\n---\n\nbody\n"
    fm, err = parse(text)
    assert fm == {}
    assert err is not None


def test_parse_never_raises_on_empty_input():
    assert parse("") == ({}, None)


def test_frontmatter_re_matches_standard_block():
    assert FRONTMATTER_RE.match("---\ntitle: x\n---\nbody") is not None
    assert FRONTMATTER_RE.match("body only") is None
