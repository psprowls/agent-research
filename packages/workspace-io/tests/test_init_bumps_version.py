"""Second init() with a newer version bumps installed and applied versions."""

from workspace_io.init import init
from workspace_io.manifest import read, write
from workspace_io.paths import manifest_path


def test_init_bumps_both_versions(tmp_path):
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    init(tmp_path, plugin="graph-wiki-agent", version="1.1.0")
    data = read(manifest_path(tmp_path / "graph-wiki"))
    entry = next(p for p in data["plugins"] if p["name"] == "graph-wiki-agent")
    assert entry["installed_version"] == "1.1.0"
    assert entry["applied_version"] == "1.1.0"


def test_init_rerun_preserves_link_file_keys(tmp_path):
    """A version-bump re-run (which forces a manifest write()) must not drop
    hand-edited multi-repo/repo-directory keys."""
    init(tmp_path, plugin="graph-wiki-agent", version="1.0.0")
    mpath = manifest_path(tmp_path / "graph-wiki")
    data = read(mpath)
    data["multi-repo"] = True
    data["repo-directory"] = "../other-repo"
    write(mpath, data)

    init(tmp_path, plugin="graph-wiki-agent", version="1.1.0")

    result = read(mpath)
    assert result["multi-repo"] is True
    assert result["repo-directory"] == "../other-repo"
