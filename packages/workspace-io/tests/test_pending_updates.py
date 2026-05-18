"""pending_updates: pure read; only mismatched entries returned."""
from workspace_io import PendingUpdate, pending_updates
from workspace_io.manifest import write


def _seed(workspace, plugins):
    workspace.mkdir(parents=True, exist_ok=True)
    write(
        workspace / ".graph-wiki.yaml",
        {"version": 2, "initialized_at": "2026-05-09", "plugins": plugins},
    )


def test_returns_only_mismatched(tmp_path):
    workspace = tmp_path / "graph-wiki"
    _seed(
        workspace,
        [
            {"name": "matched", "installed_version": "1.0", "applied_version": "1.0"},
            {"name": "stale", "installed_version": "2.0", "applied_version": "1.0"},
            {"name": "v1coerced", "installed_version": None, "applied_version": None},
        ],
    )
    result = pending_updates(workspace)
    assert result == [PendingUpdate(plugin="stale", applied_version="1.0", installed_version="2.0")]


def test_pending_updates_does_not_mutate(tmp_path):
    workspace = tmp_path / "graph-wiki"
    _seed(
        workspace,
        [{"name": "stale", "installed_version": "2.0", "applied_version": "1.0"}],
    )
    mpath = workspace / ".graph-wiki.yaml"
    before = mpath.read_bytes()
    pending_updates(workspace)
    assert mpath.read_bytes() == before


def test_pendingupdate_is_frozen():
    pu = PendingUpdate(plugin="x", applied_version="1.0", installed_version="2.0")
    import dataclasses
    assert dataclasses.is_dataclass(pu)
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        pu.plugin = "y"  # type: ignore[misc]


def test_no_manifest_returns_empty(tmp_path):
    assert pending_updates(tmp_path / "missing") == []
