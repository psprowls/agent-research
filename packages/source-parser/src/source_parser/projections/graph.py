"""Project a SourceTree into graph records aligned to lattice-graph's SQLite schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from source_parser.tree import SourceNode

NodeKey = tuple[str, str, str | None]  # (kind, name, path)


@dataclass(frozen=True)
class GraphNode:
    kind: str
    name: str
    path: str
    line: int | None
    attrs: dict[str, Any] = field(default_factory=dict)
    # Transport-only: raw source byte span, consumed by graph-io's token
    # counter at build time. NOT persisted to attrs_json. Defaults of None
    # keep every other GraphNode construction path valid.
    start_byte: int | None = None
    end_byte: int | None = None


@dataclass(frozen=True)
class GraphEdge:
    src: NodeKey
    dst: NodeKey
    kind: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphRecords:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


def _key(node: SourceNode) -> NodeKey:
    name = node.name if node.name is not None else str(node.path)
    return (node.kind, name, str(node.path))


def _emit_node(node: SourceNode) -> GraphNode:
    return GraphNode(
        kind=node.kind,
        name=node.name if node.name is not None else str(node.path),
        path=str(node.path),
        line=None if node.kind == "file" else node.span.start_line,
        attrs=dict(node.attrs),
        start_byte=node.span.start_byte,
        end_byte=node.span.end_byte,
    )


def _walk(node: SourceNode, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
    nodes.append(_emit_node(node))
    parent_key = _key(node)
    for child in node.children:
        edges.append(
            GraphEdge(
                src=parent_key,
                dst=_key(child),
                kind="contains",
                attrs={},
            )
        )
        _walk(child, nodes, edges)
    for ref in node.refs:
        if ref.kind == "call":
            edges.append(
                GraphEdge(
                    src=parent_key,
                    # Upsert stores this pathless code-symbol target as
                    # kind='unresolved_symbol' while preserving symbol_kind on
                    # the edge for resolve.sweep().
                    dst=("function", ref.target_name, None),
                    kind="calls",
                    attrs=dict(ref.attrs),
                )
            )
        elif ref.kind == "import":
            edges.append(
                GraphEdge(
                    src=parent_key,
                    dst=("file", ref.target_name, ref.target_module),
                    kind="imports",
                    attrs=dict(ref.attrs),
                )
            )
        elif ref.kind == "export":
            edges.append(
                GraphEdge(
                    src=parent_key,
                    dst=(ref.attrs.get("symbol_kind", "function"), ref.target_name, None),
                    kind="exports",
                    attrs=dict(ref.attrs),
                )
            )


def to_graph_records(tree: SourceNode) -> GraphRecords:
    """Project a parsed SourceTree onto graph records."""
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    _walk(tree, nodes, edges)
    return GraphRecords(nodes=tuple(nodes), edges=tuple(edges))
