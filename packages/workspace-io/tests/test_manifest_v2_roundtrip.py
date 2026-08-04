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
    # read() fills in defaults for plugin, state_gate, guidance, workflow, and roles when absent from disk.
    expected = dict(
        data,
        plugin={"backend_default": "claude", "backend_overrides": {}},
        state_gate={"enabled": True, "branches": ["main"]},
        guidance={"enabled": False},
        workflow={"commit_strategy": "per-task", "model_routing": {}},
        roles={},
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
    """Populated top-level roles: mapping survives write → read verbatim (fields + values)."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-05-19",
        "plugins": [
            {"name": "graph-wiki-agent", "installed_version": "0.7.0", "applied_version": "0.7.0"},
        ],
        "roles": {
            "preflight": {
                "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                "region": "us-east-1",
                "max_tokens": 64,
                "max_concurrency": 1,
            },
            "librarian": {
                "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                "region": "us-east-1",
                "max_tokens": 2048,
                "max_concurrency": 5,
            },
        },
    }
    write(mpath, data)
    result = read(mpath)
    assert result["roles"] == data["roles"]
    assert "roles" not in result["plugins"][0]


def test_v2_roles_absent_round_trips_cleanly(tmp_path):
    """Manifest with no roles key produces {} on read (no roles: {} artifact on disk)."""
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
    assert result["roles"] == {}
    assert "roles:" not in mpath.read_text(encoding="utf-8")


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


# --- state_gate / plugin round-trip tests ---


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
    """Vanilla data (no state_gate/plugin/workflow/roles keys) writes no block keys on disk."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-20",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
    }
    write(mpath, data)
    text = mpath.read_text(encoding="utf-8")
    assert "state_gate:" not in text
    assert "plugin:" not in text
    assert "workflow:" not in text
    assert "roles:" not in text


def test_v2_default_valued_blocks_omitted(tmp_path):
    """Blocks equal to read() defaults are not emitted to disk."""
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-06-20",
        "plugins": [{"name": "x", "installed_version": "1.0", "applied_version": "1.0"}],
        "plugin": {"backend_default": "claude", "backend_overrides": {}},
        "state_gate": {"enabled": True, "branches": ["main"]},
        "workflow": {"commit_strategy": "per-task", "model_routing": {}},
        "roles": {},
    }
    write(mpath, data)
    text = mpath.read_text(encoding="utf-8")
    assert "state_gate:" not in text
    assert "plugin:" not in text
    assert "workflow:" not in text
    assert "roles:" not in text


def test_write_preserves_link_file_keys(tmp_path):
    """A read()->write() round trip must not drop the hand-edited link-file keys."""
    mpath = tmp_path / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\n"
        "initialized_at: '2026-05-17'\n"
        "plugins: []\n"
        "multi-repo: true\n"
        "repo-directory: ../other-repo\n"
        "repos-root: ../checkouts\n"
        "repos: alpha,beta\n"
        "exclude: staging\n",
        encoding="utf-8",
    )
    data = read(mpath)
    write(mpath, data)
    raw = read(mpath)
    assert raw["multi-repo"] is True
    assert raw["repo-directory"] == "../other-repo"
    assert raw["repos-root"] == "../checkouts"
    assert raw["repos"] == "alpha,beta"
    assert raw["exclude"] == "staging"


def test_v2_warn_if_stale_preserves_state_gate(tmp_path):
    """warn_if_stale version-drift write round-trip preserves a non-default state_gate (regression)."""
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
        "state_gate:\n"
        "  enabled: false\n"
        "  branches:\n"
        "    - main\n"
        "    - develop\n",
        encoding="utf-8",
    )
    assert warn_if_stale(workspace, plugin="graph-wiki-agent", version="0.7.0") is True
    result = read(mpath)
    assert result["state_gate"] == {"enabled": False, "branches": ["main", "develop"]}
