"""source-parser — tree-sitter-backed source parsing for the lattice ecosystem."""

from source_parser.errors import UnsupportedLanguageError
from source_parser.parse import parse_bytes, parse_file
from source_parser.projections.graph import (
    GraphEdge,
    GraphNode,
    GraphRecords,
    NodeKey,
    to_graph_records,
)
from source_parser.tree import Reference, SourceNode, Span

__version__ = "0.1.0"

__all__ = [
    "GraphEdge",
    "GraphNode",
    "GraphRecords",
    "NodeKey",
    "Reference",
    "SourceNode",
    "Span",
    "UnsupportedLanguageError",
    "parse_bytes",
    "parse_file",
    "to_graph_records",
    "__version__",
]
