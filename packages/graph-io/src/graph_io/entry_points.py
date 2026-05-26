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
    """Parse pyproject.toml and emit EntryPoint nodes + edges.

    Handles [project.scripts] (executable, source='pyproject.scripts') and
    [project.entry-points.<group>] (executable for console_scripts, library
    otherwise; source='pyproject.entry-points.<group>'). Resolves
    implemented_by strictly: the dotted module prefix must start with the
    Package's importable name (D-05); on miss emits the EntryPoint with no
    implemented_by edge plus a stderr warning (D-06).
    """
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    pyproject = pkg_dir / "pyproject.toml"
    if not pyproject.exists():
        return [], []

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        print(
            f"[entry_points] warning: failed to parse {pyproject}: {exc}",
            file=sys.stderr,
        )
        return [], []

    project = data.get("project", {}) or {}
    importable = pkg_name.replace("-", "_")
    import_root = _resolve_import_root(pkg_dir, importable)

    pkg_key = ("package", pkg_name, pkg_rel if pkg_rel else None)

    def _resolve_callable(value: str) -> tuple[str | None, str | None]:
        """Return (file_rel_to_repo, callable_name) or (None, callable_or_None)."""
        if ":" not in value:
            return None, None
        module_part, func_name = value.split(":", 1)
        if import_root is None:
            return None, func_name
        parts = module_part.split(".")
        if not parts or parts[0] != import_root.name:
            return None, func_name
        rest = parts[1:]
        if not rest:
            candidate = import_root / "__init__.py"
        else:
            py_path = import_root.joinpath(*rest[:-1], rest[-1] + ".py")
            init_path = import_root.joinpath(*rest, "__init__.py")
            if py_path.exists():
                candidate = py_path
            elif init_path.exists():
                candidate = init_path
            else:
                return None, func_name
        if not candidate.exists():
            return None, func_name
        try:
            file_rel = candidate.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            return None, func_name
        return file_rel, func_name

    def _emit_entry(ep_name: str, value: str, *, kind: str, source: str) -> None:
        file_rel, func_name = _resolve_callable(value)
        attrs = {
            "uri": entry_point_uri(ctx, pkg_name, ep_name),
            "entry_kind": kind,
            "source": source,
            "callable": func_name,
            "is_wildcard": False,
        }
        nodes.append(
            GraphNode(
                kind="entry_point",
                name=ep_name,
                path=None,
                line=None,
                attrs=attrs,
            )
        )
        ep_key = ("entry_point", ep_name, None)
        edges.append(
            GraphEdge(
                src=pkg_key,
                dst=ep_key,
                kind="declares_entry_point",
                attrs={},
            )
        )
        if file_rel is not None:
            edges.append(
                GraphEdge(
                    src=ep_key,
                    dst=("file", file_rel, file_rel),
                    kind="implemented_by",
                    attrs={},
                )
            )
        else:
            print(
                f"[entry_points] warning: cannot resolve implemented_by "
                f"for {pkg_name} entry '{ep_name}' = '{value}' "
                f"(manifest: {pyproject})",
                file=sys.stderr,
            )

    # [project.scripts]
    scripts = project.get("scripts", {}) or {}
    if isinstance(scripts, dict):
        for ep_name, value in scripts.items():
            if isinstance(value, str):
                _emit_entry(
                    ep_name, value, kind="executable", source="pyproject.scripts"
                )

    # [project.entry-points.<group>]
    entry_points_table = project.get("entry-points", {}) or {}
    if isinstance(entry_points_table, dict):
        for group, group_entries in entry_points_table.items():
            if not isinstance(group_entries, dict):
                continue
            ep_kind = "executable" if group == "console_scripts" else "library"
            ep_source = f"pyproject.entry-points.{group}"
            for ep_name, value in group_entries.items():
                if isinstance(value, str):
                    _emit_entry(ep_name, value, kind=ep_kind, source=ep_source)

    return nodes, edges


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
