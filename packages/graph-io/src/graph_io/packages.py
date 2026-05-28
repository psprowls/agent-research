"""Manifest scanning: pyproject.toml + package.json → kind:package nodes."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import tomllib
from pathlib import Path
from typing import Any

from source_parser.projections.graph import GraphEdge, GraphNode, GraphRecords

from graph_io import _ignore, upsert
from graph_io.classification import classify
from graph_io.uri import RepoContext, app_uri, dependency_uri, pkg_uri

# PEP 508 bare-name prefix: identifier characters before any version/extra/marker.
_DEP_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+")


def _extract_dep_name(pep508_str: str) -> str | None:
    """Extract the bare package name from a PEP 508 specifier.

    Returns lowercase name, or None if the string doesn't begin with a
    valid identifier. Strips bracketed extras (`[bedrock]`), version
    specifiers, environment markers, and URL forms (`git+...#egg=...`
    is NOT supported — returns None).

    Phase 43 D-02. PEP 503 full normalization (`Foo.bar` -> `foo-bar`)
    is intentionally NOT applied in v1.8 — see RESEARCH.md Open Question Q1.
    """
    s = pep508_str.strip()
    if not s or s.startswith(("git+", "http://", "https://", "-e ", ".")):
        return None
    m = _DEP_NAME_RE.match(s)
    return m.group(0).lower() if m else None

def _should_skip(manifest_path: Path, repo_root: Path, skip_dirs: frozenset[str]) -> bool:
    if _ignore.should_skip(str(manifest_path), skip_dirs):
        return True
    return False


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
    dep_groups_raw = data.get("dependency-groups") or {}
    dep_groups: dict[str, list[str]] = {}
    if isinstance(dep_groups_raw, dict):
        for group, entries in dep_groups_raw.items():
            if isinstance(entries, list):
                dep_groups[group] = [e for e in entries if isinstance(e, str)]
    # Phase 50 D-03: surface [project.scripts] presence as a classify() signal.
    scripts = project.get("scripts") or {}
    return {
        "name": name,
        "version": project.get("version", ""),
        "dependencies": list(project.get("dependencies", [])),
        "dep_groups": dep_groups,  # PEP 735 — Phase 43 D-02
        "language": "python",
        "scripts_present": bool(scripts),  # Phase 50 D-03
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
    # Phase 50 D-03: surface package.json "bin" presence as a classify() signal.
    # Truthy when bin is a non-empty string OR a dict with at least one truthy value.
    bin_val = data.get("bin")
    bin_present = bool(bin_val) and (
        (isinstance(bin_val, str) and bool(bin_val))
        or (isinstance(bin_val, dict) and any(bin_val.values()))
    )
    return {
        "name": name,
        "version": data.get("version", ""),
        "dependencies": sorted(deps.keys()) if isinstance(deps, dict) else list(deps),
        "language": "javascript",
        "bin_present": bin_present,  # Phase 50 D-03
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


def refresh(conn: sqlite3.Connection, *, repo_root: Path, ctx: RepoContext) -> None:
    """Rescan manifests under `repo_root` and upsert kind:package nodes + contains edges.

    `ctx` carries the (org, repo) identifiers used to compose the
    `pkg:org/repo/name` URI written onto every Package node (D-09/D-10).

    Containment is by directory-prefix: every file under a package's directory
    subtree gets a `contains` edge from that package. A manifest at the repo
    root therefore "owns" every file in the graph; sub-package manifests
    create additional `contains` edges, so a file inside a sub-package will
    have edges from BOTH the sub-package and the root package. Query callers
    that want a single owner should pick longest-prefix-wins.
    """
    repo_root = Path(repo_root).resolve()
    skip_dirs = _ignore.load_skip_dirs(repo_root)
    # Accumulator for Phase 43 dependency ingestion: (ecosystem, name) -> {versions_in_use}
    dep_acc: dict[tuple[str, str], dict[str, list[str]]] = {}
    # Phase 50 D-04: track consumer kind so used_by edges from App nodes use src=("app", ...).
    used_by_pairs: list[tuple[str, str | None, str, str]] = []
    for pkg_dir, info in _discover_manifests(repo_root, skip_dirs):
        rel_prefix = pkg_dir.resolve().relative_to(repo_root).as_posix()
        if rel_prefix == ".":
            rel_prefix = ""

        # Phase 50 D-04/D-07: derive kind, URI, and attrs in one inline pass.
        new_kind, app_kind, app_signals = classify(info, pkg_dir)
        new_uri = (
            app_uri(ctx, info["name"]) if new_kind == "app"
            else pkg_uri(ctx, info["name"])
        )
        attrs: dict[str, Any] = {
            "version": info["version"],
            "dependencies": info["dependencies"],
            "language": info["language"],
            "uri": new_uri,
        }
        if new_kind == "app":
            # D-03 invariant: only App nodes carry app_kind / app_signals.
            attrs["app_kind"] = app_kind
            attrs["app_signals"] = app_signals

        # Phase 50 D-06: probe the opposite-kind row from a prior run and flip
        # it in place so the row id is preserved (every inbound edge FK stays
        # valid). The outer store.transaction() boundary set by update.run()
        # gives this UPDATE read-your-own-writes semantics for the subsequent
        # upsert_records call.
        other_kind = "package" if new_kind == "app" else "app"
        other_id = upsert._node_id(
            conn, (other_kind, info["name"], rel_prefix or None)
        )
        if other_id is not None:
            # Mirror _upsert_node's convention: the "uri" key lives in the
            # nodes.uri column, not attrs_json.
            attrs_for_db = {k: v for k, v in attrs.items() if k != "uri"}
            conn.execute(
                "UPDATE nodes SET kind=?, uri=?, attrs_json=? WHERE id=?",
                (
                    new_kind,
                    new_uri,
                    json.dumps(attrs_for_db, sort_keys=True),
                    other_id,
                ),
            )

        nodes = [
            GraphNode(
                kind=new_kind,
                name=info["name"],
                path=rel_prefix or None,
                line=None,
                attrs=attrs,
            )
        ]
        edges = []
        prefix = f"{rel_prefix}/" if rel_prefix else ""
        for file_path in _file_nodes_under(conn, prefix):
            edges.append(
                GraphEdge(
                    src=(new_kind, info["name"], rel_prefix or None),
                    dst=("file", file_path, file_path),
                    kind="contains",
                    attrs={},
                )
            )
        upsert.upsert_records(conn, GraphRecords(nodes=nodes, edges=edges))

        # Phase 43 D-02: collect Python deps from project.dependencies + dependency-groups.
        # Only python manifests have dep_groups; package.json deps live under different keys
        # and we treat them as already-flat name strings (no PEP 508 specifier syntax).
        if info["language"] == "python":
            all_dep_strs: list[str] = list(info["dependencies"])
            for group_entries in info.get("dep_groups", {}).values():
                all_dep_strs.extend(group_entries)
            consumer_name = info["name"]
            consumer_rel_path = rel_prefix or None
            consumer_kind = new_kind
            for s in all_dep_strs:
                dep_name = _extract_dep_name(s)
                if dep_name is None:
                    continue
                key = ("pypi", dep_name)
                bucket = dep_acc.setdefault(key, {"versions_in_use": []})
                if s not in bucket["versions_in_use"]:
                    bucket["versions_in_use"].append(s)
                used_by_pairs.append(
                    (consumer_name, consumer_rel_path, consumer_kind, dep_name)
                )

    # Emit dependency nodes (one per (ecosystem, name)) + used_by edges.
    dep_nodes: list[GraphNode] = []
    for (ecosystem, name), bucket in sorted(dep_acc.items()):
        versions = sorted(set(bucket["versions_in_use"]))
        dep_nodes.append(
            GraphNode(
                kind="dependency",
                name=name,
                path=None,
                line=None,
                attrs={
                    "uri": dependency_uri(ecosystem, name),
                    "ecosystem": ecosystem,
                    "name": name,
                    "versions_in_use": versions,
                },
            )
        )
    # used_by edges: dedupe per (consumer_name, dep_name) so a dep listed
    # twice in one manifest (e.g. once in [project.dependencies], once in
    # [dependency-groups]) collapses to exactly one edge. Phase 50 D-04:
    # src uses consumer_kind so App consumers emit src=("app", ...).
    dep_edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str]] = set()
    for consumer_name, consumer_rel_path, consumer_kind, dep_name in used_by_pairs:
        if (consumer_name, dep_name) in seen_edges:
            continue
        seen_edges.add((consumer_name, dep_name))
        dep_edges.append(
            GraphEdge(
                src=(consumer_kind, consumer_name, consumer_rel_path),
                dst=("dependency", dep_name, None),
                kind="used_by",
                attrs={},
            )
        )
    if dep_nodes or dep_edges:
        upsert.upsert_records(conn, GraphRecords(nodes=dep_nodes, edges=dep_edges))
