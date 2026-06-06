"""Living Wiki M4: cross-page drift propagator prompt + verdict parser (spec §3.4)."""

from __future__ import annotations

from graph_wiki_core.prompts.drift_propagator import (
    build_drift_propagator_prompt,
    parse_drift_propagator_verdict,
)


def test_prompt_includes_kind_rubric_and_each_entity():
    entities = [
        ("pkg_a", "Now uses async fan-out.", ["packages/pkg_a/pool.py"]),
        ("pkg_b", "Still synchronous.", []),
    ]
    system, human = build_drift_propagator_prompt(
        "concept", "Async fan-out", "The system processes items synchronously.", entities
    )
    assert "CONCEPT" in system or "concept" in human
    assert "pkg_a" in human and "pkg_b" in human
    assert "packages/pkg_a/pool.py" in human
    # An entity with no changed files renders a placeholder, never an empty line.
    assert "(no specific files identified)" in human


def test_adr_rubric_is_annotate_only():
    system, human = build_drift_propagator_prompt("adr", "0007 Use async", "...", [])
    assert "ANNOTATE-ONLY" in system.upper() or "annotate" in human.lower()


def test_parse_valid_stale_verdict_keeps_findings_with_entity_stem():
    text = '{"stale": true, "findings": [{"entity_stem": "pkg_a", "stale_claim": "sync", "rationale": "now async"}]}'
    v = parse_drift_propagator_verdict(text)
    assert v["stale"] is True
    assert v["findings"][0]["entity_stem"] == "pkg_a"
    assert v["findings"][0]["rationale"] == "now async"


def test_parse_strips_code_fence():
    text = '```json\n{"stale": false, "findings": []}\n```'
    assert parse_drift_propagator_verdict(text) == {"stale": False, "findings": []}


def test_parse_fails_safe_on_garbage():
    assert parse_drift_propagator_verdict("not json at all") == {"stale": False, "findings": []}
    assert parse_drift_propagator_verdict("") == {"stale": False, "findings": []}


def test_parse_drops_findings_without_entity_stem_and_collapses_to_not_stale():
    text = '{"stale": true, "findings": [{"stale_claim": "x", "rationale": "y"}]}'
    # No usable entity attribution -> not actionable -> not stale.
    assert parse_drift_propagator_verdict(text) == {"stale": False, "findings": []}
