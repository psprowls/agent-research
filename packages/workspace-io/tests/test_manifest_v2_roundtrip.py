"""v2 manifest write → read preserves all fields and structure."""

from workspace_io import warn_if_stale
from workspace_io.manifest import read, write


def test_v2_write_then_read(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-05-09",
        "plugins": [
            {"name": "graph-wiki-agent", "installed_version": "0.7.0", "applied_version": "0.7.0"},
            {"name": "code-wiki-second", "installed_version": "0.3.1", "applied_version": "0.3.0"},
        ],
    }
    write(mpath, data)
    result = read(mpath)
    # read() fills in defaults for plugin, state_gate, and graph when absent from disk.
    expected = dict(
        data,
        plugin={"backend_default": "claude", "backend_overrides": {}},
        state_gate={"enabled": True, "branches": ["main"]},
        graph={"domains": {}, "resources": {}, "resource_matchers": []},
    )
    assert result == expected


def test_v2_write_preserves_top_level_key_order(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    write(
        mpath,
        {
            "version": 2,
            "initialized_at": "2026-05-09",
            "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        },
    )
    text = mpath.read_text(encoding="utf-8")
    v_pos = text.index("version:")
    i_pos = text.index("initialized_at:")
    p_pos = text.index("plugins:")
    assert v_pos < i_pos < p_pos


def test_v2_block_style_no_flow(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    write(
        mpath,
        {
            "version": 2,
            "initialized_at": "2026-05-09",
            "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        },
    )
    text = mpath.read_text(encoding="utf-8")
    # Block style: no `[`/`{` in body
    assert "[" not in text
    assert "{" not in text


def test_v2_roles_roundtrip(tmp_path):
    """Populated per-plugin roles[] survives write → read verbatim (order + fields)."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-05-19",
        "plugins": [
            {
                "name": "graph-wiki-agent",
                "installed_version": "0.7.0",
                "applied_version": "0.7.0",
                "roles": [
                    {
                        "name": "preflight",
                        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                        "region": "us-east-1",
                        "max_tokens": 64,
                        "max_concurrency": 1,
                    },
                    {
                        "name": "librarian",
                        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                        "region": "us-east-1",
                        "max_tokens": 2048,
                        "max_concurrency": 5,
                    },
                ],
            }
        ],
    }
    write(mpath, data)
    result = read(mpath)
    assert result["plugins"][0]["roles"] == data["plugins"][0]["roles"]


def test_v2_roles_absent_round_trips_cleanly(tmp_path):
    """Plugin with no roles key produces no roles key on read (no roles: [] artifact)."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-05-19",
        "plugins": [
            {"name": "graph-wiki-agent", "installed_version": "0.7.0", "applied_version": "0.7.0"},
        ],
    }
    write(mpath, data)
    result = read(mpath)
    assert "roles" not in result["plugins"][0]
    # .get() must not raise
    assert result["plugins"][0].get("roles") is None


def test_v2_topic_roundtrips(tmp_path):
    """The wiki display name (topic) survives write → read verbatim."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-04",
        "topic": "Agent Research",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
    }
    write(mpath, data)
    assert read(mpath)["topic"] == "Agent Research"


def test_v2_topic_absent_round_trips_cleanly(tmp_path):
    """A manifest with no topic produces no topic key on disk or on read."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-04",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
    }
    write(mpath, data)
    assert "topic:" not in mpath.read_text(encoding="utf-8")
    assert "topic" not in read(mpath)


def test_v2_topic_renders_after_initialized_at(tmp_path):
    """When present, topic sits between initialized_at and plugins."""
    mpath = tmp_path / ".graph-wiki.yaml"
    write(
        mpath,
        {
            "version": 2,
            "initialized_at": "2026-06-04",
            "topic": "Agent Research",
            "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        },
    )
    text = mpath.read_text(encoding="utf-8")
    assert text.index("initialized_at:") < text.index("topic:") < text.index("plugins:")


# --- graph / state_gate / plugin round-trip tests ---


def test_v2_graph_domains_roundtrip(tmp_path):
    """graph.domains block survives write → read verbatim."""
    mpath = tmp_path / ".graph-wiki.yaml"
    domains = {"core": {"description": "Core packages"}, "infra": {"description": "Infra"}}
    data = {
        "version": 2,
        "initialized_at": "2026-06-20",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        "graph": {"domains": domains, "resources": {}, "resource_matchers": []},
    }
    write(mpath, data)
    result = read(mpath)
    assert result["graph"]["domains"] == domains


def test_v2_state_gate_roundtrip(tmp_path):
    """Non-default state_gate block survives write → read verbatim."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-20",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        "state_gate": {"enabled": False, "branches": ["main", "develop"]},
    }
    write(mpath, data)
    result = read(mpath)
    assert result["state_gate"] == {"enabled": False, "branches": ["main", "develop"]}


def test_v2_plugin_roundtrip(tmp_path):
    """Non-default plugin block (bedrock backend) survives write → read verbatim."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-20",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        "plugin": {"backend_default": "bedrock", "backend_overrides": {}},
    }
    write(mpath, data)
    result = read(mpath)
    assert result["plugin"] == {"backend_default": "bedrock", "backend_overrides": {}}


def test_v2_absent_blocks_stay_clean(tmp_path):
    """Vanilla data (no graph/state_gate/plugin keys) writes no block keys on disk."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-20",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
    }
    write(mpath, data)
    text = mpath.read_text(encoding="utf-8")
    assert "graph:" not in text
    assert "state_gate:" not in text
    assert "plugin:" not in text


def test_v2_default_valued_blocks_omitted(tmp_path):
    """Blocks equal to read() defaults are not emitted to disk."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-20",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        "plugin": {"backend_default": "claude", "backend_overrides": {}},
        "state_gate": {"enabled": True, "branches": ["main"]},
        "graph": {"domains": {}, "resources": {}, "resource_matchers": []},
    }
    write(mpath, data)
    text = mpath.read_text(encoding="utf-8")
    assert "graph:" not in text
    assert "state_gate:" not in text
    assert "plugin:" not in text


def test_v2_graph_partial_no_empty_siblings(tmp_path):
    """graph with only domains populated writes graph/domains but no empty resources or resource_matchers."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-20",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        "graph": {"domains": {"core": {}}, "resources": {}, "resource_matchers": []},
    }
    write(mpath, data)
    text = mpath.read_text(encoding="utf-8")
    assert "graph:" in text
    assert "domains:" in text
    assert "resources:" not in text
    assert "resource_matchers:" not in text


def test_v2_warn_if_stale_preserves_graph_domains(tmp_path):
    """warn_if_stale version-drift write round-trip preserves graph.domains (regression)."""
    workspace = tmp_path / "graph-wiki"
    workspace.mkdir(parents=True)
    mpath = workspace / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\n"
        "initialized_at: 2026-06-20\n"
        "plugins:\n"
        "  - name: graph-wiki-agent\n"
        "    installed_version: '0.6.0'\n"
        "    applied_version: '0.6.0'\n"
        "graph:\n"
        "  domains:\n"
        "    core:\n"
        "      description: Core packages\n",
        encoding="utf-8",
    )
    assert warn_if_stale(workspace, plugin="graph-wiki-agent", version="0.7.0") is True
    result = read(mpath)
    assert result["graph"]["domains"] == {"core": {"description": "Core packages"}}
