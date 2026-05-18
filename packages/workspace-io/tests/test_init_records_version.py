"""init() writes installed_version and applied_version."""
from workspace_io.init import init
from workspace_io.manifest import read
from workspace_io.paths import manifest_path


def test_init_records_both_versions(tmp_path):
    init(tmp_path, plugin="code-wiki-agent", version="1.0.0")
    data = read(manifest_path(tmp_path / "graph-wiki"))
    entry = next(p for p in data["plugins"] if p["name"] == "code-wiki-agent")
    assert entry["installed_version"] == "1.0.0"
    assert entry["applied_version"] == "1.0.0"


def test_idempotent_same_version_no_rewrite(tmp_path):
    init(tmp_path, plugin="code-wiki-agent", version="1.0.0")
    mpath = manifest_path(tmp_path / "graph-wiki")
    before_mtime = mpath.stat().st_mtime_ns
    before_bytes = mpath.read_bytes()
    init(tmp_path, plugin="code-wiki-agent", version="1.0.0")
    assert mpath.read_bytes() == before_bytes
    assert mpath.stat().st_mtime_ns == before_mtime


def test_missing_version_kwarg_raises(tmp_path):
    import pytest
    with pytest.raises(TypeError):
        init(tmp_path, plugin="code-wiki-agent")  # type: ignore[call-arg]
