"""Tests for workspace_io.manifest — .graph-wiki.yaml read/write."""
import pytest

from workspace_io.manifest import read, write


def _v2(plugins):
    return {
        "version": 2,
        "initialized_at": "2026-05-08",
        "plugins": [
            {"name": p, "installed_version": None, "applied_version": None}
            for p in plugins
        ],
    }


def test_write_then_read_roundtrip(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    write(mpath, _v2(["code-wiki-agent", "code-wiki-second"]))
    result = read(mpath)
    assert result["version"] == 2
    assert result["initialized_at"] == "2026-05-08"
    assert [p["name"] for p in result["plugins"]] == ["code-wiki-agent", "code-wiki-second"]


def test_read_returns_empty_dict_when_missing(tmp_path):
    assert read(tmp_path / ".graph-wiki.yaml") == {}


def test_write_creates_parent_dirs(tmp_path):
    mpath = tmp_path / "graph-wiki" / ".graph-wiki.yaml"
    write(mpath, _v2([]))
    assert mpath.exists()


def test_empty_plugins_list(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    write(mpath, _v2([]))
    assert read(mpath)["plugins"] == []


def test_written_file_contains_expected_keys(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    write(mpath, _v2(["foo"]))
    text = mpath.read_text()
    assert "version: 2" in text
    assert "initialized_at:" in text
    assert "2026-05-08" in text
    assert "name: foo" in text


def test_read_raises_on_v1(tmp_path):
    """D-14: manifest.read() raises on v1 format (no coercion path)."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 1\ninitialized_at: 2026-05-17\nplugins:\n  - code-wiki-agent\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError):
        read(mpath)
