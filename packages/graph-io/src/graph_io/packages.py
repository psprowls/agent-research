"""Manifest scanning: pyproject.toml + package.json → kind:package nodes."""

from __future__ import annotations

import json
import sqlite3
import sys
import tomllib
from pathlib import Path
from typing import Any

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import _ignore, upsert

_SKIP_REPO_PREFIXES = ("lattice/",)


def _should_skip(manifest_path: Path, repo_root: Path, skip_dirs: frozenset[str]) -> bool:
    if _ignore.should_skip(str(manifest_path), skip_dirs):
        return True
    try:
        rel = manifest_path.relative_to(repo_root).as_posix()
    except ValueError:
        return False
    return any(rel.startswith(p) for p in _SKIP_REPO_PREFIXES)


def _read_pyproject(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        print(f"warning: skipping {path} ({exc})", file=sys.stderr)
        return None
    project = data.get("project") or {}
    name = project.get("name")
    if not name:
        return None
    return {
        "name": name,
        "version": project.get("version", ""),
        "dependencies": list(project.get("dependencies", [])),
        "language": "python",
    }


def _read_package_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open() as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"warning: skipping {path} ({exc})", file=sys.stderr)
        return None
    name = data.get("name")
    if not name:
        return None
    deps = data.get("dependencies") or {}
    return {
        "name": name,
        "version": data.get("version", ""),
        "dependencies": sorted(deps.keys()) if isinstance(deps, dict) else list(deps),
        "language": "javascript",
    }


def _discover_manifests(
    repo_root: Path, skip_dirs: frozenset[str]
) -> list[tuple[Path, dict[str, Any]]]:
    found: list[tuple[Path, dict[str, Any]]] = []
    for manifest_path in repo_root.rglob("pyproject.toml"):
        if _should_skip(manifest_path, repo_root, skip_dirs):
            continue
        info = _read_pyproject(manifest_path)
        if info:
            found.append((manifest_path.parent, info))
    for manifest_path in repo_root.rglob("package.json"):
        if _should_skip(manifest_path, repo_root, skip_dirs):
            continue
        info = _read_package_json(manifest_path)
        if info:
            found.append((manifest_path.parent, info))
    return found


def _file_nodes_under(conn: sqlite3.Connection, prefix: str) -> list[str]:
    rows = conn.execute(
        "SELECT path FROM nodes WHERE kind='file' AND path LIKE ?",
        (f"{prefix}%",),
    ).fetchall()
    return [row[0] for row in rows]


def refresh(conn: sqlite3.Connection, *, repo_root: Path) -> None:
    """Rescan manifests under `repo_root` and upsert kind:package nodes + contains edges.

    Containment is by directory-prefix: every file under a package's directory
    subtree gets a `contains` edge from that package. A manifest at the repo
    root therefore "owns" every file in the graph; sub-package manifests
    create additional `contains` edges, so a file inside a sub-package will
    have edges from BOTH the sub-package and the root package. Query callers
    that want a single owner should pick longest-prefix-wins.
    """
    repo_root = Path(repo_root).resolve()
    skip_dirs = _ignore.load_skip_dirs(repo_root)
    for pkg_dir, info in _discover_manifests(repo_root, skip_dirs):
        rel_prefix = pkg_dir.resolve().relative_to(repo_root).as_posix()
        if rel_prefix == ".":
            rel_prefix = ""
        nodes = [
            GraphNode(
                kind="package",
                name=info["name"],
                path=rel_prefix or None,
                line=None,
                attrs={
                    "version": info["version"],
                    "dependencies": info["dependencies"],
                    "language": info["language"],
                },
            )
        ]
        edges = []
        prefix = f"{rel_prefix}/" if rel_prefix else ""
        for file_path in _file_nodes_under(conn, prefix):
            edges.append(
                GraphEdge(
                    src=("package", info["name"], rel_prefix or None),
                    dst=("file", file_path, file_path),
                    kind="contains",
                    attrs={},
                )
            )
        upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))
