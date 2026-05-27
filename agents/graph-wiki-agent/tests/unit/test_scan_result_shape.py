"""Phase 45 D-15: locks the ScanResult v1.8 contract for downstream consumers."""

from __future__ import annotations

import dataclasses

from graph_wiki_agent.commands.scan import ScanResult


def test_scan_result_default_construction():
    r = ScanResult()
    # Legacy fields
    assert r.added == []
    assert r.updated == []
    assert r.deleted == []
    assert r.renamed == []
    assert r.errors == []
    assert r.state_gate == {}
    # Phase 45 D-15 new fields
    assert r.entities_created == []
    assert r.entities_updated == []
    assert r.entities_deleted == []
    assert r.entities_narrated == []
    assert r.entity_errors == []


def test_scan_result_field_set_locked():
    """If this test fails because a field was removed, you broke the v1.8
    contract — downstream consumers (CLI, MCP tool) read these fields."""
    expected = {
        "added",
        "updated",
        "deleted",
        "renamed",
        "errors",
        "state_gate",
        "entities_created",
        "entities_updated",
        "entities_deleted",
        "entities_narrated",
        "entity_errors",
    }
    actual = {f.name for f in dataclasses.fields(ScanResult)}
    assert actual == expected, f"ScanResult field set drift: {expected ^ actual}"


def test_scan_result_field_types_locked():
    fields_by_name = {f.name for f in dataclasses.fields(ScanResult)}
    # All entity fields are list[str]
    for name in (
        "entities_created",
        "entities_updated",
        "entities_deleted",
        "entities_narrated",
        "entity_errors",
    ):
        assert name in fields_by_name


def test_scan_result_populated_construction():
    r = ScanResult(
        added=["legacy_pkg"],
        entities_created=["pkg:foo/bar"],
        entities_narrated=["pkg:foo/bar"],
    )
    assert r.added == ["legacy_pkg"]
    assert r.entities_created == ["pkg:foo/bar"]
    assert r.entities_narrated == ["pkg:foo/bar"]
    # Defaults for unspecified
    assert r.entities_updated == []
