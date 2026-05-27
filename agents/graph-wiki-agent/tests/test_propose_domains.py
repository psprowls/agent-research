"""Phase 48 Plan 02 — unit tests for `commands/propose_domains.py`.

Covers (10 tests):
  - tool-call parsing (D-05)
  - grounding strips unknown packages (D-09)
  - grounding drops empty domain (D-09 + claude-discretion lean "yes")
  - cycle-strip basic case (D-10/D-12)
  - cycle-strip deterministic (D-15 byte-identical)
  - cycle-strip existing-edge immunity (D-11)
  - cycle-strip no-cycle no-op (D-10)
  - cross-cutting builder (D-07/D-08)
  - YAML schema (top-level proposed_domains + metadata + banner; D-14/D-15)
  - YAML differentiation (no top-level `domains:` key; D-14, PROPOSE-04)
  - existing-domains loader: missing-ok + nested-extract (D-04 + RESEARCH F-6)
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


# ---------------------------------------------------------------------------
# Tool-call parsing (D-05)
# ---------------------------------------------------------------------------


def test_parse_tool_call_extracts_proposed_domain():
    """Given a stub AIMessage with tool_calls, _parse_tool_call returns a
    ProposedDomain with llm_origin='fan_out'."""
    from graph_wiki_agent.commands.propose_domains import (
        ProposedDomain,
        _parse_tool_call,
    )

    resp = SimpleNamespace(
        tool_calls=[
            {
                "name": "propose_domain",
                "args": {
                    "name": "graph-io",
                    "packages": ["graph-io", "wiki-io"],
                    "parent": None,
                    "description": "Graph and wiki I/O.",
                    "confidence": 0.85,
                },
            }
        ]
    )

    domain = _parse_tool_call(resp)
    assert isinstance(domain, ProposedDomain)
    assert domain.name == "graph-io"
    assert domain.packages == ("graph-io", "wiki-io")
    assert domain.parent is None
    assert domain.description == "Graph and wiki I/O."
    assert domain.confidence == 0.85
    assert domain.llm_origin == "fan_out"


# ---------------------------------------------------------------------------
# Grounding (D-09)
# ---------------------------------------------------------------------------


def test_strip_unknown_packages_filters_invalid(capsys):
    """Packages not in `valid_packages` are stripped; stderr warning emitted
    per stripped name; result preserves only valid packages, sorted."""
    from graph_wiki_agent.commands.propose_domains import (
        ProposedDomain,
        _strip_unknown_packages,
    )

    proposed = (
        ProposedDomain(
            name="core",
            packages=("bar", "baz", "made_up"),
            parent=None,
            description="x",
            confidence=0.9,
            llm_origin="fan_out",
        ),
    )

    kept, stripped = _strip_unknown_packages(proposed, valid_packages={"bar", "baz"})
    assert len(kept) == 1
    assert kept[0].packages == ("bar", "baz")
    assert stripped == ("made_up",)

    err = capsys.readouterr().err
    assert "warning: stripping unknown package 'made_up'" in err
    assert "domain 'core'" in err
    assert "not in list_packages output" in err


def test_strip_unknown_packages_drops_empty_domain():
    """If ALL of a domain's packages are stripped, the domain itself is dropped."""
    from graph_wiki_agent.commands.propose_domains import (
        ProposedDomain,
        _strip_unknown_packages,
    )

    proposed = (
        ProposedDomain(
            name="ghost",
            packages=("nope1", "nope2"),
            parent=None,
            description="x",
            confidence=0.5,
            llm_origin="fan_out",
        ),
    )

    kept, stripped = _strip_unknown_packages(proposed, valid_packages={"bar"})
    assert kept == ()
    assert sorted(stripped) == ["nope1", "nope2"]


# ---------------------------------------------------------------------------
# Cycle detection (D-10, D-11, D-12, D-15)
# ---------------------------------------------------------------------------


def test_strip_cycle_edges_basic_three_cycle():
    """Three-edge cycle (a->b->c->a) — exactly ONE proposed edge removed;
    result is acyclic."""
    from graph_wiki_agent.commands.propose_domains import _strip_cycle_edges

    proposed = [("a", "b"), ("b", "c"), ("c", "a")]
    kept, stripped = _strip_cycle_edges(proposed, existing_edges=[])
    assert len(stripped) == 1
    assert len(kept) == 2
    # Result must be acyclic — verify by re-running cycle detection on `kept`
    # and asserting nothing more gets stripped.
    kept2, stripped2 = _strip_cycle_edges(kept, existing_edges=[])
    assert stripped2 == []
    assert sorted(kept2) == sorted(kept)


def test_strip_cycle_edges_deterministic():
    """Same input twice → byte-identical (kept, stripped). (D-15 determinism
    contract for the cycle path.)"""
    from graph_wiki_agent.commands.propose_domains import _strip_cycle_edges

    proposed = [("c", "a"), ("a", "b"), ("b", "c")]
    a_kept, a_stripped = _strip_cycle_edges(list(proposed), existing_edges=[])
    b_kept, b_stripped = _strip_cycle_edges(list(proposed), existing_edges=[])
    assert a_kept == b_kept
    assert a_stripped == b_stripped


def test_strip_cycle_edges_existing_immune():
    """Existing edges are never stripped — only the proposed edge gets cut."""
    from graph_wiki_agent.commands.propose_domains import _strip_cycle_edges

    existing = [("a", "b")]
    proposed = [("b", "a")]
    kept, stripped = _strip_cycle_edges(proposed, existing_edges=existing)
    assert kept == []
    assert stripped == [("b", "a")]


def test_strip_cycle_edges_no_cycle_keeps_everything():
    """No cycle → no edges stripped; kept == input."""
    from graph_wiki_agent.commands.propose_domains import _strip_cycle_edges

    proposed = [("a", "b"), ("c", "d")]
    kept, stripped = _strip_cycle_edges(proposed, existing_edges=[])
    assert sorted(kept) == sorted(proposed)
    assert stripped == []


# ---------------------------------------------------------------------------
# Cross-cutting builder (D-07, D-08)
# ---------------------------------------------------------------------------


def test_build_cross_cutting_domain_aggregates_hubs():
    """Given 2 hubs, builds ONE ProposedDomain named 'cross-cutting' with
    packages = sorted hub names, confidence=1.0, llm_origin='cross_cutting'."""
    from graph_io.cluster import CrossCuttingHub

    from graph_wiki_agent.commands.propose_domains import (
        ProposedDomain,
        _build_cross_cutting_domain,
    )

    hubs = (
        CrossCuttingHub(
            name="pytest", imported_by_count=10, imported_by_fraction=0.86,
            connects_clusters=(0, 1),
        ),
        CrossCuttingHub(
            name="click", imported_by_count=8, imported_by_fraction=0.57,
            connects_clusters=(0,),
        ),
    )
    domain = _build_cross_cutting_domain(hubs)
    assert isinstance(domain, ProposedDomain)
    assert domain.name == "cross-cutting"
    assert domain.packages == ("click", "pytest")  # sorted
    assert domain.parent is None
    assert domain.confidence == 1.0
    assert domain.llm_origin == "cross_cutting"


def test_build_cross_cutting_domain_empty_returns_none():
    """Empty hub tuple → returns None (Claude-discretion lean: skip if empty)."""
    from graph_wiki_agent.commands.propose_domains import _build_cross_cutting_domain

    assert _build_cross_cutting_domain(()) is None


# ---------------------------------------------------------------------------
# YAML writer (D-14, D-15, D-16)
# ---------------------------------------------------------------------------


def _make_proposed_result(*, domains, stripped_unknown=(), stripped_cycle=(),
                          llm_failures=(), total_cost=0.0):
    from graph_wiki_agent.commands.propose_domains import ProposeResult
    return ProposeResult(
        proposed_domains=tuple(domains),
        stripped_unknown_packages=tuple(stripped_unknown),
        stripped_cycle_edges=tuple(stripped_cycle),
        llm_failures=tuple(llm_failures),
        total_cost_usd=total_cost,
    )


def test_write_proposed_yaml_schema(tmp_path):
    """Output file: banner first line, then yaml with top-level
    `proposed_domains` AND `metadata` keys. Metadata carries all six fields
    from CONTEXT D-14."""
    from graph_wiki_agent.commands.propose_domains import (
        ProposedDomain,
        _write_proposed_yaml,
    )

    result = _make_proposed_result(
        domains=[
            ProposedDomain(
                name="cross-cutting",
                packages=("click", "pytest"),
                parent=None,
                description="Cross-cutting utility packages.",
                confidence=1.0,
                llm_origin="cross_cutting",
            ),
            ProposedDomain(
                name="graph-io",
                packages=("graph-io", "wiki-io"),
                parent=None,
                description="Graph I/O.",
                confidence=0.85,
                llm_origin="fan_out",
            ),
        ],
        stripped_unknown=("foo",),
        stripped_cycle=(("child", "parent"),),
        llm_failures=(),
        total_cost=0.034,
    )

    out = tmp_path / "domains.proposed.yaml"
    _write_proposed_yaml(
        result,
        out,
        cluster_command="cg domain-clusters --hub-threshold 0.5",
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )

    text = out.read_text(encoding="utf-8")
    first_line = text.splitlines()[0]
    assert first_line.startswith("# Generated by graph-wiki-agent graph propose-domains")
    assert "Review before promoting to domains.yaml" in first_line

    data = yaml.safe_load(text)
    assert "proposed_domains" in data
    assert "metadata" in data
    md = data["metadata"]
    for key in [
        "generated_at",
        "cluster_command",
        "model",
        "total_cost_usd",
        "stripped_unknown_packages",
        "stripped_cycle_edges",
        "llm_failures",
    ]:
        assert key in md, f"metadata missing key: {key}"
    assert md["cluster_command"] == "cg domain-clusters --hub-threshold 0.5"
    assert md["model"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert md["total_cost_usd"] == pytest.approx(0.034)
    assert md["stripped_unknown_packages"] == ["foo"]
    # stripped_cycle_edges should be a list of [child, parent] pairs.
    assert md["stripped_cycle_edges"] == [["child", "parent"]]
    assert md["llm_failures"] == []

    pd = data["proposed_domains"]
    assert isinstance(pd, dict)
    assert set(pd.keys()) == {"cross-cutting", "graph-io"}
    cc = pd["cross-cutting"]
    assert cc["packages"] == ["click", "pytest"]
    assert cc["parent"] is None
    assert cc["confidence"] == 1.0
    assert cc["llm_origin"] == "cross_cutting"


def test_write_proposed_yaml_no_domains_key(tmp_path):
    """Output MUST NOT have a top-level `domains:` key (PROPOSE-04 schema
    differentiation). This prevents accidental ingestion as authoritative."""
    from graph_wiki_agent.commands.propose_domains import (
        ProposedDomain,
        _write_proposed_yaml,
    )

    result = _make_proposed_result(
        domains=[
            ProposedDomain(
                name="x",
                packages=("foo",),
                parent=None,
                description="x",
                confidence=0.5,
                llm_origin="fan_out",
            ),
        ],
    )
    out = tmp_path / "domains.proposed.yaml"
    _write_proposed_yaml(
        result, out, cluster_command="cg domain-clusters", model="haiku"
    )
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "domains" not in data, (
        "top-level `domains:` key would risk accidental ingestion (PROPOSE-04)"
    )


# ---------------------------------------------------------------------------
# Existing-domains loader (RESEARCH F-6)
# ---------------------------------------------------------------------------


def test_load_existing_domains_missing_returns_empty(tmp_path):
    from graph_wiki_agent.commands.propose_domains import _load_existing_domains

    assert _load_existing_domains(tmp_path) == {}


def test_load_existing_domains_extracts_nested(tmp_path):
    """Given a domains.yaml shaped as {domains: {name: {...}}}, the loader
    returns the inner mapping."""
    from graph_wiki_agent.commands.propose_domains import _load_existing_domains

    (tmp_path / "domains.yaml").write_text(
        yaml.safe_dump(
            {
                "domains": {
                    "core": {"packages": ["foo"], "parent": None},
                    "data": {"packages": ["bar"], "parent": "core"},
                }
            }
        ),
        encoding="utf-8",
    )

    out = _load_existing_domains(tmp_path)
    assert set(out.keys()) == {"core", "data"}
    assert out["core"]["packages"] == ["foo"]
    assert out["data"]["parent"] == "core"
