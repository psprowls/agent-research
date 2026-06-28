"""Bedrock-free graph lookups shared by ingest — core (`run_ingest_source`)
and the plugin's Claude-branch prep.

Slice 4 moved these out of `graph_wiki_core.commands.ingest` (which imports
`model_adapter` / `subagent_runtime` at module top) so the prep can resolve the
entity a source belongs to without dragging in the Bedrock stack.

`entity_filename_for_uri` is the URI→entity-filename mapping that uses the SAME
rule the scanner uses (`wiki_io.entity_writer.short_filename`), so an ingest
`[[entities/<stem>]]` wikilink resolves to the file `write_entities` produced —
replacing the legacy `slug_from_uri` for entity links.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path, PurePosixPath

from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    _compute_collision_set,
    _kind_list_fns,
    short_filename,
)

# Entity-kind nodes worth a name-fallback match (file names are noisy).
# Mirrors the former `_ENTITY_KINDS` in graph_wiki_core.commands.ingest.
ENTITY_KINDS: frozenset[str] = frozenset({"package", "class", "function", "method", "domain"})


def lookup_entity_by_path(conn: sqlite3.Connection, repo_root: Path, source_path: Path) -> tuple[str, str] | None:
    """Return (uri, name) for the package CONTAINING the source file, or None.

    Resolves source_path relative to repo_root (POSIX-style), then joins
    nodes(file) -> edges(contains) -> nodes(package). Reads URI from the
    dedicated `nodes.uri` column. Returns None when source_path is outside
    repo_root or no package contains it.
    """
    try:
        rel = source_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    row = conn.execute(
        "SELECT p.name, p.uri FROM nodes f "
        "JOIN edges e ON e.dst = f.id AND e.kind='contains' "
        "JOIN nodes p ON e.src = p.id "
        "WHERE f.kind='file' AND f.path = ? AND p.kind='package' "
        "LIMIT 1",
        (rel,),
    ).fetchone()
    if row is None:
        return None
    name, uri = row
    if not uri:
        return None
    return uri, name


def lookup_entity_by_name(conn: sqlite3.Connection, name: str) -> tuple[str, str] | None:
    """Return (uri, name) for the unique entity-kind match by name, or None.

    When more than one entity-kind node shares the name, emit one stderr
    warning and return None (fall back to the no-match path).
    """
    if not name:
        return None
    placeholders = ",".join("?" for _ in ENTITY_KINDS)
    sql = f"SELECT name, uri, kind FROM nodes WHERE name = ? AND kind IN ({placeholders}) AND uri IS NOT NULL"
    rows = conn.execute(sql, [name, *sorted(ENTITY_KINDS)]).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        uris = [r[1] for r in rows]
        sys.stderr.write(
            f"[ingest: name {name!r} matches multiple graph nodes "
            f"({', '.join(uris)}); falling back to LLM-guessed slug]\n"
        )
        return None
    matched_name, matched_uri, _kind = rows[0]
    return matched_uri, matched_name


def lookup_package_by_dir(conn: sqlite3.Connection, repo_root: Path, dir_path: Path) -> tuple[str, str, int] | None:
    """Return (uri, name, node_id) for the package/app a directory names, or None.

    Resolves dir_path relative to repo_root (POSIX-style), then matches a
    `nodes.kind IN ('package','app')` row by exact path (uses idx_nodes_path).
    On an exact miss, walks dir_path's ancestors up to repo root, returning the
    nearest enclosing package/app — so a sub-directory affects still resolves.
    Returns None when dir_path is outside repo_root or no ancestor is a
    package/app with a non-empty uri.

    This is a post-miss fallback for `resolve_path_contexts`; it does not change
    `lookup_entity_by_path`'s file-only semantics (ingest always passes a file).
    """
    try:
        rel = dir_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None
    # Candidate paths: the dir itself, then each ancestor up to (not incl.) root.
    candidates = [rel, *(p.as_posix() for p in PurePosixPath(rel).parents if p.as_posix() != ".")]
    for path in candidates:
        row = conn.execute(
            "SELECT uri, name, id FROM nodes "
            "WHERE kind IN ('package','app') AND path = ? AND uri IS NOT NULL AND uri <> '' LIMIT 1",
            (path,),
        ).fetchone()
        if row is not None:
            uri, name, node_id = row
            return str(uri), str(name), int(node_id)
    return None


def files_in_package(conn: sqlite3.Connection, node_id: int) -> list[tuple]:
    """Return the file rows (id, path, attrs_json) contained in a package/app node.

    Joins package --contains--> file (the same shape guidance_scan enumerates).
    Rows are plain tuples (graph_io connections do not set row_factory), so read
    them positionally: r[0]=id, r[1]=path, r[2]=attrs_json. Empty list when the
    node contains no file nodes.
    """
    return conn.execute(
        "SELECT f.id, f.path, f.attrs_json "
        "FROM nodes p "
        "JOIN edges e ON e.src = p.id AND e.kind = 'contains' "
        "JOIN nodes f ON e.dst = f.id AND f.kind = 'file' "
        "WHERE p.id = ? AND f.path IS NOT NULL "
        "ORDER BY f.path",
        (node_id,),
    ).fetchall()


def entity_filename_for_uri(uri: str, conn: sqlite3.Connection | None = None) -> str | None:
    """Return the scanner's on-disk entity filename stem for a graph URI, or
    None when the URI maps to no admitted entity page.

    Bedrock-free. Mirrors `write_entities` / `short_filename` so an ingest
    `[[entities/<stem>]]` wikilink resolves to a real page. When `conn` is
    given, the exact collision set is computed so colliding stems carry the
    same `__<hex>` suffix the scanner uses; otherwise an empty collision set is
    assumed (correct for the no-collision common case).

    Returns None for URI prefixes with no entity page (cls:/fn:/method:),
    since `short_filename` raises ValueError on those — ingest only matches
    package/domain entities for linkable targets.
    """
    if not uri:
        return None
    collision_set: frozenset[str] = frozenset()
    if conn is not None:
        try:
            collision_set = _compute_collision_set(conn, ADMITTED_KINDS, _kind_list_fns())
        except Exception:  # noqa: BLE001 — collision precompute is best-effort
            collision_set = frozenset()
    try:
        return short_filename(uri, collision_set)
    except ValueError:
        return None
