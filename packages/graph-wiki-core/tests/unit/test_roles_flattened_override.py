"""Regression: _workspace_role_override resolves against the flattened roles: block."""

from workspace_io import manifest


def _seed_workspace(tmp_path, roles: dict) -> None:
    manifest.write(
        tmp_path / ".graph-wiki.yaml",
        {"version": 2, "initialized_at": "2026-07-04", "plugins": [], "roles": roles},
    )


def test_override_found_for_flattened_role(tmp_path, monkeypatch, real_workspace_role_override):
    _seed_workspace(tmp_path, {"scanner": {"model_id": "zai.glm-5", "max_tokens": 512}})
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    assert real_workspace_role_override("scanner") == {"model_id": "zai.glm-5", "max_tokens": 512}


def test_override_none_when_role_absent(tmp_path, monkeypatch, real_workspace_role_override):
    _seed_workspace(tmp_path, {"scanner": {"model_id": "zai.glm-5"}})
    monkeypatch.setenv("GRAPH_WIKI_WORKSPACE", str(tmp_path))
    assert real_workspace_role_override("librarian") is None
