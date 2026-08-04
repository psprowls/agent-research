"""Tests for workspace_io.manifest — .graph-wiki.yaml read/write."""

import pytest
from workspace_io.manifest import (
    read,
    read_graph_domains,
    read_guidance,
    read_state_gate,
    write,
)


def _v2(plugins):
    return {
        "version": 2,
        "initialized_at": "2026-05-08",
        "plugins": [{"name": p, "installed_version": None, "applied_version": None} for p in plugins],
    }


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
        "version: 1\ninitialized_at: 2026-05-17\nplugins:\n  - graph-wiki-agent\n",
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
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nplugin:\n  foo: bar\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unknown keys"):
        read(mpath)


def test_plugin_block_raises_on_invalid_backend(tmp_path):
    """D-02: invalid backend values raise RuntimeError."""
    mpath = tmp_path / ".graph-wiki.yaml"
    # backend_default with invalid value
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nplugin:\n  backend_default: aws\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be one of"):
        read(mpath)
    # backend_overrides with invalid value
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nplugin:\n  backend_overrides:\n    lint: gpt\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be one of"):
        read(mpath)


def test_plugin_block_raises_when_not_mapping(tmp_path):
    """D-02: plugin value that is not a mapping raises RuntimeError."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nplugin: claude\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a mapping"):
        read(mpath)


def test_state_gate_default_when_missing(tmp_path):
    """Block absent → defaults to {enabled: True, branches: ['main']}."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n",
        encoding="utf-8",
    )
    assert read(mpath)["state_gate"] == {"enabled": True, "branches": ["main"]}


def test_state_gate_explicit_values(tmp_path):
    """Explicit enabled + branches are returned verbatim."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "state_gate:\n  enabled: false\n  branches:\n    - main\n    - develop\n",
        encoding="utf-8",
    )
    assert read(mpath)["state_gate"] == {"enabled": False, "branches": ["main", "develop"]}


def test_state_gate_scalar_branches_coerced(tmp_path):
    """A scalar branches value is coerced to a one-element list."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  branches: develop\n",
        encoding="utf-8",
    )
    assert read(mpath)["state_gate"] == {"enabled": True, "branches": ["develop"]}


def test_state_gate_partial_block_uses_defaults(tmp_path):
    """A present block with only enabled keeps the default branches."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  enabled: false\n",
        encoding="utf-8",
    )
    assert read(mpath)["state_gate"] == {"enabled": False, "branches": ["main"]}


def test_state_gate_raises_when_not_mapping(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate: main\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a mapping"):
        read(mpath)


def test_state_gate_raises_on_unknown_key(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  foo: bar\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unknown keys"):
        read(mpath)


def test_state_gate_raises_on_non_bool_enabled(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  enabled: yes_please\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a bool"):
        read(mpath)


def test_state_gate_raises_on_empty_branches(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  branches: []\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="non-empty list"):
        read(mpath)


def test_state_gate_raises_on_non_string_branch_item(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nstate_gate:\n  branches:\n    - main\n    - 7\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="strings"):
        read(mpath)


def test_read_state_gate_returns_tuple(tmp_path):
    """read_state_gate returns (enabled, branches) from the normalized block."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "state_gate:\n  enabled: false\n  branches:\n    - develop\n",
        encoding="utf-8",
    )
    assert read_state_gate(mpath) == (False, ["develop"])


def test_read_state_gate_defaults_when_block_absent(tmp_path):
    """Block absent on an existing manifest → (True, ['main'])."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n",
        encoding="utf-8",
    )
    assert read_state_gate(mpath) == (True, ["main"])


def test_read_state_gate_defaults_when_manifest_missing(tmp_path):
    """Missing manifest → (True, ['main']) (matches read() empty-dict contract)."""
    assert read_state_gate(tmp_path / ".graph-wiki.yaml") == (True, ["main"])


# ---------------------------------------------------------------------------
# graph.domains block normalization (D5)
# ---------------------------------------------------------------------------


def test_graph_block_default_when_missing(tmp_path):
    """Block absent → read() returns {'graph': {'domains': {}}}."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n",
        encoding="utf-8",
    )
    assert read(mpath)["graph"] == {"domains": {}}


def test_graph_domains_passthrough(tmp_path):
    """A valid graph.domains mapping is returned verbatim."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "graph:\n"
        "  domains:\n"
        "    financial:\n"
        "      packages: ['@psprowls/financial-domain-ts']\n"
        "      description: Financial domain\n",
        encoding="utf-8",
    )
    result = read(mpath)
    assert result["graph"]["domains"]["financial"]["packages"] == ["@psprowls/financial-domain-ts"]
    assert result["graph"]["domains"]["financial"]["description"] == "Financial domain"


def test_graph_block_raises_when_not_mapping(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\ngraph: nope\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a mapping"):
        read(mpath)


def test_graph_domains_raises_when_not_mapping(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\ngraph:\n  domains: notamap\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a mapping"):
        read(mpath)


def test_graph_block_raises_on_unknown_key(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\ngraph:\n  bogus: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unknown keys"):
        read(mpath)


def test_read_graph_domains_returns_mapping(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n"
        "graph:\n"
        "  domains:\n"
        "    core:\n"
        "      packages: [foo]\n"
        "      parent: product\n",
        encoding="utf-8",
    )
    out = read_graph_domains(mpath)
    assert set(out.keys()) == {"core"}
    assert out["core"]["packages"] == ["foo"]
    assert out["core"]["parent"] == "product"


def test_read_graph_domains_defaults_when_block_absent(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n",
        encoding="utf-8",
    )
    assert read_graph_domains(mpath) == {}


def test_read_graph_domains_defaults_when_manifest_missing(tmp_path):
    assert read_graph_domains(tmp_path / ".graph-wiki.yaml") == {}


# ---------------------------------------------------------------------------
# guidance block normalization (opt-in gating for gw next)
# ---------------------------------------------------------------------------


def test_guidance_default_when_missing(tmp_path):
    """Block absent → defaults to {enabled: False}. Opt-in, unlike state_gate."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\n",
        encoding="utf-8",
    )
    assert read(mpath)["guidance"] == {"enabled": False}


def test_guidance_explicit_enabled(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nguidance:\n  enabled: true\n",
        encoding="utf-8",
    )
    assert read(mpath)["guidance"] == {"enabled": True}


def test_guidance_empty_block_uses_default(tmp_path):
    """A present but empty block still defaults enabled to False."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nguidance: {}\n",
        encoding="utf-8",
    )
    assert read(mpath)["guidance"] == {"enabled": False}


def test_guidance_raises_when_not_mapping(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nguidance: true\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="must be a mapping"):
        read(mpath)


def test_guidance_raises_on_non_bool_enabled(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nguidance:\n  enabled: yes-please\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="guidance.enabled must be a bool"):
        read(mpath)


def test_guidance_raises_on_unknown_key(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nguidance:\n  enabled: true\n  top: 5\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unknown keys in guidance block"):
        read(mpath)


def test_guidance_write_roundtrip_when_enabled(tmp_path):
    """enabled: true survives write() → read()."""
    mpath = tmp_path / ".graph-wiki.yaml"
    write(mpath, {"version": 2, "initialized_at": "2026-05-08", "plugins": [], "guidance": {"enabled": True}})
    assert "guidance:" in mpath.read_text(encoding="utf-8")
    assert read(mpath)["guidance"] == {"enabled": True}


def test_guidance_write_omits_default_block(tmp_path):
    """enabled: false is the default → write() emits no guidance block."""
    mpath = tmp_path / ".graph-wiki.yaml"
    write(mpath, {"version": 2, "initialized_at": "2026-05-08", "plugins": [], "guidance": {"enabled": False}})
    assert "guidance:" not in mpath.read_text(encoding="utf-8")
    assert read(mpath)["guidance"] == {"enabled": False}


def test_read_guidance_accessor(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\ninitialized_at: 2026-05-08\nplugins: []\nguidance:\n  enabled: true\n",
        encoding="utf-8",
    )
    assert read_guidance(mpath) is True


def test_read_guidance_accessor_defaults_false(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text("version: 2\ninitialized_at: 2026-05-08\nplugins: []\n", encoding="utf-8")
    assert read_guidance(mpath) is False


def test_read_guidance_accessor_no_manifest_file(tmp_path):
    """Missing manifest → read() returns {} → accessor still returns False, not KeyError."""
    assert read_guidance(tmp_path / "nope.yaml") is False


def test_read_guidance_exported_from_package():
    from workspace_io import read_guidance as exported

    assert exported is read_guidance
