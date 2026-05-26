"""Entry-point emitter: EntryPoint + declares_entry_point + implemented_by (ENTRY-01..05).

Reads declared entry points from pyproject.toml ([project.scripts],
[project.entry-points.<group>]) and package.json (bin, main, module,
exports) for every Package row written by packages.refresh. Emits
EntryPoint nodes with strict path-qualified implemented_by resolution
(D-05); on miss, emits the EntryPoint with implemented_by=NULL plus a
stderr warning (D-06).

Conventional executable files (shebang scripts) do NOT produce EntryPoint
nodes — they ride on File.is_executable from Phase 29 (ENTRY-05).
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tomllib
from pathlib import Path

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import upsert
from graph_io.structural_nodes import _resolve_import_root
from graph_io.uri import RepoContext, entry_point_uri

# --- Module-private constants (D-07) ---

# Conditional-export keys per the Node.js exports spec — any key inside
# `exports` matching this set is a condition selector, not a sub-path.
_EXPORT_CONDITION_KEYS: frozenset[str] = frozenset({
    "import", "require", "default", "node", "browser", "types",
    "deno", "worker",
})


# --- Helpers (stubs at this task; filled in subsequent tasks) ---


def _emit_pyproject_entries(
    pkg_name: str,
    pkg_rel: str,
    pkg_dir: Path,
    ctx: RepoContext,
    repo_root: Path,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Parse pyproject.toml and emit EntryPoint nodes + edges (Task 2)."""
    return [], []


def _emit_packagejson_entries(
    pkg_name: str,
    pkg_rel: str,
    pkg_dir: Path,
    ctx: RepoContext,
    repo_root: Path,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Parse package.json and emit EntryPoint nodes + edges (Task 3)."""
    return [], []


# --- Public emit() ---


def emit(
    conn: sqlite3.Connection,
    *,
    repo_root: Path,
    ctx: RepoContext,
    skip_dirs: frozenset[str],
) -> None:
    """Emit EntryPoint nodes, declares_entry_point edges, implemented_by edges
    for every declared entry across every Package's manifest. ENTRY-01..05."""
    repo_root = Path(repo_root).resolve()

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    pkg_rows = conn.execute(
        "SELECT name, path, attrs_json FROM nodes WHERE kind='package'"
    ).fetchall()

    for pkg_name, pkg_rel, pkg_attrs_json in pkg_rows:
        pkg_attrs = json.loads(pkg_attrs_json) if pkg_attrs_json else {}
        language = pkg_attrs.get("language")
        pkg_dir = (repo_root / pkg_rel).resolve() if pkg_rel else repo_root

        if language == "python":
            pp_nodes, pp_edges = _emit_pyproject_entries(
                pkg_name, pkg_rel or "", pkg_dir, ctx, repo_root
            )
            nodes.extend(pp_nodes)
            edges.extend(pp_edges)
        elif language in {"javascript", "typescript"}:
            pj_nodes, pj_edges = _emit_packagejson_entries(
                pkg_name, pkg_rel or "", pkg_dir, ctx, repo_root
            )
            nodes.extend(pj_nodes)
            edges.extend(pj_edges)
        # Unknown languages: skip silently (no EntryPoint emission).

    upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
