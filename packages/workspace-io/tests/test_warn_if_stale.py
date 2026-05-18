"""warn_if_stale: side-effecting comparison of stored applied_version vs current."""
from workspace_io import warn_if_stale
from workspace_io.init import init
from workspace_io.manifest import read
from workspace_io.paths import manifest_path


def test_no_entry_returns_false_no_write(tmp_path):
    init(tmp_path, plugin="other", version="1.0.0")
    workspace = tmp_path / "graph-wiki"
    mpath = manifest_path(workspace)
    before = mpath.read_bytes()
    assert warn_if_stale(workspace, plugin="code-wiki-agent", version="0.7.0") is False
    assert mpath.read_bytes() == before


def test_match_returns_false_no_write(tmp_path):
    init(tmp_path, plugin="code-wiki-agent", version="0.7.0")
    workspace = tmp_path / "graph-wiki"
    mpath = manifest_path(workspace)
    before = mpath.read_bytes()
    assert warn_if_stale(workspace, plugin="code-wiki-agent", version="0.7.0") is False
    assert mpath.read_bytes() == before


def test_mismatch_returns_true_writes_installed_only(tmp_path):
    init(tmp_path, plugin="code-wiki-agent", version="0.6.0")
    workspace = tmp_path / "graph-wiki"
    assert warn_if_stale(workspace, plugin="code-wiki-agent", version="0.7.0") is True
    data = read(manifest_path(workspace))
    entry = next(p for p in data["plugins"] if p["name"] == "code-wiki-agent")
    assert entry["installed_version"] == "0.7.0"
    assert entry["applied_version"] == "0.6.0"  # unchanged


def test_null_applied_version_no_signal(tmp_path):
    """An entry whose applied_version is None returns False, no write.

    Rewrite of the lattice v1-coerced-entry test (D-14): v1 reads now raise,
    so we simulate the same null-applied state by writing a v2 manifest with
    applied_version: null directly.
    """
    workspace = tmp_path / "graph-wiki"
    workspace.mkdir(parents=True)
    mpath = workspace / ".graph-wiki.yaml"
    mpath.write_text(
        "version: 2\n"
        "initialized_at: 2026-05-09\n"
        "plugins:\n"
        "  - name: code-wiki-agent\n"
        "    installed_version: null\n"
        "    applied_version: null\n",
        encoding="utf-8",
    )
    before = mpath.read_bytes()
    assert warn_if_stale(workspace, plugin="code-wiki-agent", version="0.7.0") is False
    assert mpath.read_bytes() == before
