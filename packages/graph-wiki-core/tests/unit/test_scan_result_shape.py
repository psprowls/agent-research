"""Phase 45 D-15: locks the ScanResult v1.8 contract for downstream consumers."""

from __future__ import annotations

import dataclasses

from graph_wiki_core.commands.scan import ScanResult


def test_scan_result_default_construction():
    r = ScanResult()
    assert r.state_gate == {}
    # Entity reporting fields
    assert r.entities_created == []
    assert r.entities_updated == []
    assert r.entities_deleted == []
    assert r.entities_narrated == []
    assert r.entity_errors == []


def test_scan_result_field_set_locked():
    """If this test fails because a field was removed, you broke the
    contract — downstream consumers (CLI, MCP tool) read these fields."""
    expected = {
        "state_gate",
        "entities_created",
        "entities_updated",
        "entities_deleted",
        "entities_narrated",
        "entity_errors",
    }
    actual = {f.name for f in dataclasses.fields(ScanResult)}
    assert actual == expected, f"ScanResult field set drift: {expected ^ actual}"


def test_scan_result_populated_construction():
    r = ScanResult(
        entities_created=["pkg:foo/bar"],
        entities_narrated=["pkg:foo/bar"],
    )
    assert r.entities_created == ["pkg:foo/bar"]
    assert r.entities_narrated == ["pkg:foo/bar"]
    # Defaults for unspecified
    assert r.entities_updated == []


def test_scan_result_fully_populated_construction_round_trips_all_fields():
    """Every field populated at once — entity reporting fields have the
    correct types and hold the exact values passed in."""
    r = ScanResult(
        state_gate={"allowed": True, "reason": "clean", "head_commit": "abc123"},
        entities_created=["pkg:a"],
        entities_updated=["pkg:b"],
        entities_deleted=["pkg:c"],
        entities_narrated=["pkg:a"],
        entity_errors=["pkg:d: some error"],
    )

    assert isinstance(r.state_gate, dict)
    assert isinstance(r.entities_created, list)
    assert isinstance(r.entities_updated, list)
    assert isinstance(r.entities_deleted, list)
    assert isinstance(r.entities_narrated, list)
    assert isinstance(r.entity_errors, list)

    assert r.entities_created == ["pkg:a"]
    assert r.entities_updated == ["pkg:b"]
    assert r.entities_deleted == ["pkg:c"]
    assert r.entities_narrated == ["pkg:a"]
    assert r.entity_errors == ["pkg:d: some error"]
    assert r.state_gate["allowed"] is True
