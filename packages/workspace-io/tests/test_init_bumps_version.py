"""Second init() with a newer version bumps installed and applied versions."""
from workspace_io.init import init
from workspace_io.manifest import read
from workspace_io.paths import manifest_path


def test_init_bumps_both_versions(tmp_path):
    init(tmp_path, plugin="code-wiki-agent", version="1.0.0")
    init(tmp_path, plugin="code-wiki-agent", version="1.1.0")
    data = read(manifest_path(tmp_path / "graph-wiki"))
    entry = next(p for p in data["plugins"] if p["name"] == "code-wiki-agent")
    assert entry["installed_version"] == "1.1.0"
    assert entry["applied_version"] == "1.1.0"
