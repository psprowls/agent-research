"""Tests for the config.json projection of the workspace manifest."""

import hashlib
import json

from workspace_io import manifest
from workspace_io.projection import projection_path, write_projection


def _seed(tmp_path, extra: dict | None = None):
    data = {"version": 2, "initialized_at": "2026-07-04", "plugins": []}
    data.update(extra or {})
    manifest.write(tmp_path / ".graph-wiki.yaml", data)


def test_projection_contains_explicit_values_only(tmp_path):
    _seed(tmp_path)  # no workflow block on disk
    write_projection(tmp_path)
    payload = json.loads(projection_path(tmp_path).read_text(encoding="utf-8"))
    assert "workflow" not in payload  # defaults are NOT merged
    assert payload["version"] == 2


def test_projection_renders_workflow_block(tmp_path):
    _seed(tmp_path, {"workflow": {"commit_strategy": "at-end", "model_routing": {"mechanical": "haiku"}}})
    write_projection(tmp_path)
    payload = json.loads(projection_path(tmp_path).read_text(encoding="utf-8"))
    assert payload["workflow"]["model_routing"] == {"mechanical": "haiku"}
    assert payload["workflow"]["commit_strategy"] == "at-end"


def test_projection_embeds_manifest_hash(tmp_path):
    _seed(tmp_path)
    write_projection(tmp_path)
    payload = json.loads(projection_path(tmp_path).read_text(encoding="utf-8"))
    expected = hashlib.sha256((tmp_path / ".graph-wiki.yaml").read_bytes()).hexdigest()
    assert payload["_meta"]["manifest_sha256"] == expected
    assert payload["_meta"]["manifest_mtime"] is not None


def test_missing_manifest_meta_fields_both_none(tmp_path):
    # No .graph-wiki.yaml at all: both _meta fields must agree (None), so the
    # session-start staleness check never compares against an empty-bytes hash.
    write_projection(tmp_path)
    payload = json.loads(projection_path(tmp_path).read_text(encoding="utf-8"))
    assert payload["_meta"]["manifest_sha256"] is None
    assert payload["_meta"]["manifest_mtime"] is None
    assert set(payload.keys()) == {"_meta"}


def test_empty_manifest_file_projects_only_meta(tmp_path):
    # A zero-byte manifest must not crash; the projection carries only _meta,
    # with real (non-None) provenance since the file exists.
    (tmp_path / ".graph-wiki.yaml").write_bytes(b"")
    write_projection(tmp_path)
    payload = json.loads(projection_path(tmp_path).read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"_meta"}
    assert payload["_meta"]["manifest_sha256"] == hashlib.sha256(b"").hexdigest()
    assert payload["_meta"]["manifest_mtime"] is not None


def test_init_regenerates_projection(tmp_path):
    from workspace_io.init import init

    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    init(repo, plugin="graph-wiki-agent", version="1.0")
    assert projection_path(repo / "graph-wiki").exists()


def test_warn_if_stale_write_regenerates_projection(tmp_path):
    from workspace_io.versions import warn_if_stale

    _seed(tmp_path, {"plugins": [{"name": "p", "installed_version": "1.0", "applied_version": "1.0"}]})
    write_projection(tmp_path)
    before = projection_path(tmp_path).read_text(encoding="utf-8")
    assert warn_if_stale(tmp_path, plugin="p", version="2.0") is True
    after = json.loads(projection_path(tmp_path).read_text(encoding="utf-8"))
    assert after["plugins"][0]["installed_version"] == "2.0"
    assert projection_path(tmp_path).read_text(encoding="utf-8") != before
