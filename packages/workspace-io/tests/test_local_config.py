"""Tests for workspace_io._local_config — .graph-wiki.local.yaml parser."""
from workspace_io._local_config import read


def test_missing_file_returns_empty_dict(tmp_path):
    assert read(tmp_path / "absent.yaml") == {}


def test_reads_lattice_directory_key(tmp_path):
    p = tmp_path / ".graph-wiki.local.yaml"
    p.write_text("graph-wiki-directory: /tmp/foo\n")
    assert read(p) == {"graph-wiki-directory": "/tmp/foo"}


def test_strips_inline_comment(tmp_path):
    p = tmp_path / ".graph-wiki.local.yaml"
    p.write_text("graph-wiki-directory: /tmp/foo  # personal path\n")
    assert read(p)["graph-wiki-directory"] == "/tmp/foo"


def test_strips_surrounding_quotes(tmp_path):
    p = tmp_path / ".graph-wiki.local.yaml"
    p.write_text('graph-wiki-directory: "/tmp/foo bar"\n')
    assert read(p)["graph-wiki-directory"] == "/tmp/foo bar"


def test_strips_surrounding_single_quotes(tmp_path):
    p = tmp_path / ".graph-wiki.local.yaml"
    p.write_text("graph-wiki-directory: '/tmp/foo bar'\n")
    assert read(p)["graph-wiki-directory"] == "/tmp/foo bar"


def test_skips_blank_and_comment_lines(tmp_path):
    p = tmp_path / ".graph-wiki.local.yaml"
    p.write_text("# top comment\n\ngraph-wiki-directory: /tmp/foo\n# trailing\n")
    assert read(p) == {"graph-wiki-directory": "/tmp/foo"}


def test_skips_malformed_lines(tmp_path):
    p = tmp_path / ".graph-wiki.local.yaml"
    p.write_text("not a key value line\ngraph-wiki-directory: /tmp/foo\n")
    assert read(p) == {"graph-wiki-directory": "/tmp/foo"}


def test_returns_unknown_keys(tmp_path):
    p = tmp_path / ".graph-wiki.local.yaml"
    p.write_text("future-key: value\ngraph-wiki-directory: /tmp/foo\n")
    result = read(p)
    assert result["graph-wiki-directory"] == "/tmp/foo"
    assert result["future-key"] == "value"


def test_empty_value_returns_empty_string(tmp_path):
    p = tmp_path / ".graph-wiki.local.yaml"
    p.write_text("graph-wiki-directory:\n")
    assert read(p)["graph-wiki-directory"] == ""
