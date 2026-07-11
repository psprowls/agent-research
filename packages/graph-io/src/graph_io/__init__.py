"""graph-io: SQLite-backed code graph for the graph-wiki ecosystem.

The package owns the SQLite store, manifest scanning, and read-only queries.
The public access surface is the GraphReader / GraphStore handle pair and the
open_reader / open_writer openers re-exported below.
"""

__version__ = "0.1.1"

from graph_io.cluster import Cluster, ClusterResult, CrossCuttingHub
from graph_io.handle import GraphReader, GraphStore, open_reader, open_writer
from graph_io.queries import _VALID_KINDS as VALID_KINDS
from graph_io.queries import (
    AgentPluginDescription,
    AppDescription,
    BuiltinDescription,
    CallRecord,
    ChildNode,
    DependencyDescription,
    DomainDescription,
    EntryPointDescription,
    ExporterRecord,
    ExportRecord,
    ImporterRecord,
    ImportRecord,
    MatchRecord,
    NodeRecord,
    PackageDescription,
    PathDescription,
    RepoDescription,
    SuiteDescription,
    SymbolDescription,
)
from graph_io.schema import SCHEMA_VERSION
from graph_io.source_meta import extension_languages
from graph_io.store import GraphNotInitializedError, SchemaMismatchError
from graph_io.sync_wiki import DriftReport, run_sync_wiki

__all__ = [
    "open_reader",
    "open_writer",
    "run_sync_wiki",
    "DriftReport",
    "extension_languages",
    "GraphReader",
    "GraphStore",
    "GraphNotInitializedError",
    "SchemaMismatchError",
    "SCHEMA_VERSION",
    "Cluster",
    "ClusterResult",
    "CrossCuttingHub",
    "VALID_KINDS",
    "AgentPluginDescription",
    "AppDescription",
    "BuiltinDescription",
    "CallRecord",
    "ChildNode",
    "DependencyDescription",
    "DomainDescription",
    "EntryPointDescription",
    "ExporterRecord",
    "ExportRecord",
    "ImporterRecord",
    "ImportRecord",
    "MatchRecord",
    "NodeRecord",
    "PackageDescription",
    "PathDescription",
    "RepoDescription",
    "SuiteDescription",
    "SymbolDescription",
]
