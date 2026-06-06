"""Helpers for building immutable parser graph records from mutable emitters."""

from __future__ import annotations

from collections.abc import Iterable

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords


def as_graph_records(
    nodes: Iterable[GraphNode] = (),
    edges: Iterable[GraphEdge] = (),
) -> GraphRecords:
    """Return GraphRecords with the tuple boundary expected by source-parser."""
    return GraphRecords(nodes=tuple(nodes), edges=tuple(edges))
