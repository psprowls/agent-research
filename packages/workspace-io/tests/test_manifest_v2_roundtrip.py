"""v2 manifest write → read preserves all fields and structure."""
from workspace_io.manifest import read, write


def test_v2_write_then_read(tmp_path):
    mpath = tmp_path / ".graph-wiki.yaml"
    data = {
        "version": 2,
        "initialized_at": "2026-05-09",
        "plugins": [
            {"name": "code-wiki-agent", "installed_version": "0.7.0", "applied_version": "0.7.0"},
            {"name": "code-wiki-second", "installed_version": "0.3.1", "applied_version": "0.3.0"},
        ],
    }
    write(mpath, data)
    result = read(mpath)
    assert result == data


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
