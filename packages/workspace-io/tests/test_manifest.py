"""Tests for workspace_io.manifest — .graph-wiki.yaml read/write."""
import pytest

from workspace_io.manifest import read, read_roles, write


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


def test_plugin_block_default_when_missing(tmp_path):
    """D-02: plugin block absent → returns {backend_default: 'claude', backend_overrides: {}}."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n",
        encoding="utf-8",
    )
    result = read(mpath)
    assert result["plugin"] == {"backend_default": "claude", "backend_overrides": {}}


def test_plugin_block_passthrough(tmp_path):
    """D-02: known plugin keys are returned verbatim."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "plugin:\n  backend_default: bedrock\n  backend_overrides:\n    ingest: bedrock\n",
        encoding="utf-8",
    )
    result = read(mpath)
    assert result["plugin"] == {"backend_default": "bedrock", "backend_overrides": {"ingest": "bedrock"}}


def test_plugin_block_raises_on_unknown_key(tmp_path):
    """D-02: unknown keys in plugin block raise RuntimeError."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "plugin:\n  foo: bar\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unknown keys"):
        read(mpath)


def test_plugin_block_raises_on_invalid_backend(tmp_path):
    """D-02: invalid backend values raise RuntimeError."""
    mpath = tmp_path / ".graph-wiki.yaml"
    # backend_default with invalid value
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "plugin:\n  backend_default: aws\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be one of"):
        read(mpath)
    # backend_overrides with invalid value
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "plugin:\n  backend_overrides:\n    lint: gpt\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be one of"):
        read(mpath)


def test_plugin_block_raises_when_not_mapping(tmp_path):
    """D-02: plugin value that is not a mapping raises RuntimeError."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "plugin: claude\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a mapping"):
        read(mpath)


def _v2_with_roles(plugin_name, roles):
    return {
        "version": 2,
        "initialized_at": "2026-05-19",
        "plugins": [
            {
                "name": plugin_name,
                "installed_version": "0.7.0",
                "applied_version": "0.7.0",
                "roles": roles,
            }
        ],
    }


def test_read_roles_returns_list_for_named_plugin(tmp_path):
    """read_roles returns the role-dict list for the named plugin."""
    mpath = tmp_path / ".graph-wiki.yaml"
    roles = [
        {
            "name": "preflight",
            "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "region": "us-east-1",
            "max_tokens": 64,
            "max_concurrency": 1,
        }
    ]
    write(mpath, _v2_with_roles("code-wiki-agent", roles))
    assert read_roles("code-wiki-agent", mpath) == roles


def test_read_roles_returns_empty_for_missing_plugin(tmp_path):
    """read_roles returns [] (not raises) when the plugin name is not in the manifest."""
    mpath = tmp_path / ".graph-wiki.yaml"
    write(mpath, _v2_with_roles("code-wiki-agent", [{"name": "preflight"}]))
    assert read_roles("does-not-exist", mpath) == []


def test_read_roles_returns_empty_when_plugin_has_no_roles_key(tmp_path):
    """read_roles returns [] when the plugin entry exists but has no roles key."""
    mpath = tmp_path / ".graph-wiki.yaml"
    write(
        mpath,
        {
            "version": 2,
            "initialized_at": "2026-05-19",
            "plugins": [
                {"name": "code-wiki-agent", "installed_version": "0.7.0", "applied_version": "0.7.0"}
            ],
        },
    )
    assert read_roles("code-wiki-agent", mpath) == []


def test_read_roles_returns_empty_when_manifest_missing(tmp_path):
    """read_roles returns [] when the manifest file does not exist (matches read() contract)."""
    assert read_roles("code-wiki-agent", tmp_path / ".graph-wiki.yaml") == []
