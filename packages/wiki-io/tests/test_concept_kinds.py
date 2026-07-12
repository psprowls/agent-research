"""Tests for wiki_io.concept_kinds — the concept-page kind registry."""

from __future__ import annotations

from wiki_io.concept_kinds import (
    CONCEPT_KINDS,
    DEFAULT_CONCEPT_KIND,
    KIND_GROUP_LABELS,
    KIND_GROUP_ORDER,
    KIND_TEMPLATES,
    effective_kind,
    kind_group,
)


def test_registry_constants():
    assert CONCEPT_KINDS == ("concept", "pattern", "architecture")
    assert DEFAULT_CONCEPT_KIND == "concept"
    assert KIND_TEMPLATES == {
        "concept": "concept.md",
        "pattern": "concept-pattern.md",
        "architecture": "concept-architecture.md",
    }
    assert KIND_GROUP_ORDER == ("architecture", "pattern", "concept")
    assert set(KIND_GROUP_LABELS) == set(CONCEPT_KINDS)


def test_effective_kind_defaults_when_absent_or_blank():
    assert effective_kind({}) == "concept"
    assert effective_kind({"kind": ""}) == "concept"
    assert effective_kind({"kind": None}) == "concept"
    assert effective_kind({"kind": "   "}) == "concept"


def test_effective_kind_explicit():
    assert effective_kind({"kind": "architecture"}) == "architecture"
    assert effective_kind({"kind": "pattern"}) == "pattern"


def test_effective_kind_unknown_passthrough():
    # Validation is lint's job — rendering/routing never crash on a bad kind.
    assert effective_kind({"kind": "bogus"}) == "bogus"


def test_kind_group_folds_unknown_into_default():
    assert kind_group({"kind": "bogus"}) == "concept"
    assert kind_group({"kind": "architecture"}) == "architecture"
    assert kind_group({}) == "concept"
