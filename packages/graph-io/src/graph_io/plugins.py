"""Plugin ingestion: .graph-wiki.yaml plugins[] -> kind:plugin nodes (Phase 43 D-03)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from source_parser.projections.graph import GraphNode, GraphRecords

from graph_io import upsert
from graph_io.uri import RepoContext, plugin_uri
from workspace_io.manifest import read as read_manifest


def emit(
    conn: sqlite3.Connection,
    *,
    workspace_root: Path,
    ctx: RepoContext,
) -> None:
    """Read `<workspace_root>/.graph-wiki.yaml` and emit one `kind:plugin`
    node per entry in the `plugins[]` array.

    Plugin nodes have NO inbound edges in v1.8 (D-03): plugins aren't
    'used by' packages in the import sense — they're entities for
    documentation, not graph reasoning.

    Silently tolerates a missing `.graph-wiki.yaml` (returns without
    emitting anything). Honors the workspace-io v2 manifest schema.

    `ctx` is unused for plugin URIs (plugin URIs are concept-level per
    Phase 42 D-04 — not repo-scoped) but accepted for symmetry with the
    other emitters and to leave room for future repo-scoped plugin attrs.
    """
    manifest_path = workspace_root / ".graph-wiki.yaml"
    if not manifest_path.exists():
        return
    manifest = read_manifest(manifest_path)
    plugins_list = manifest.get("plugins") or []
    if not plugins_list:
        return
    nodes: list[GraphNode] = []
    for entry in plugins_list:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not name:
            continue
        attrs: dict = {
            "uri": plugin_uri(name),
            "ecosystem": "claude-code",
            "name": name,
        }
        if entry.get("installed_version") is not None:
            attrs["installed_version"] = entry["installed_version"]
        if entry.get("applied_version") is not None:
            attrs["applied_version"] = entry["applied_version"]
        nodes.append(GraphNode(kind="plugin", name=name, path=None, line=None, attrs=attrs))
    if nodes:
        upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=[]))
