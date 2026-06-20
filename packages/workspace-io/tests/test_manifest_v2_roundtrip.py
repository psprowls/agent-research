"""v2 manifest write → read preserves all fields and structure."""

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
        graph={"domains": {}},
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
