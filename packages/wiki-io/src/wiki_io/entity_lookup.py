from __future__ import annotations

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

import sys
from pathlib import Path

from wiki_io.entity_writer import (
    ADMITTED_KINDS,
    _compute_collision_set,
    _kind_list_fns,
    short_filename,
)

# Entity-kind nodes worth a name-fallback match (file names are noisy).
# Mirrors the former `_ENTITY_KINDS` in graph_wiki_core.commands.ingest.
ENTITY_KINDS: frozenset[str] = frozenset(
    {"package", "class", "function", "method", "domain"}
)


def lookup_entity_by_path(conn, repo_root: Path, source_path: Path):
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


def lookup_entity_by_name(conn, name: str):
    """Return (uri, name) for the unique entity-kind match by name, or None.

    When more than one entity-kind node shares the name, emit one stderr
    warning and return None (fall back to the no-match path).
    """
    if not name:
        return None
    placeholders = ",".join("?" for _ in ENTITY_KINDS)
    sql = (
        f"SELECT name, uri, kind FROM nodes "
        f"WHERE name = ? AND kind IN ({placeholders}) AND uri IS NOT NULL"
    )
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


def entity_filename_for_uri(uri: str, conn=None) -> str | None:
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
            collision_set = _compute_collision_set(
                conn, ADMITTED_KINDS, _kind_list_fns()
            )
        except Exception:  # noqa: BLE001 — collision precompute is best-effort
            collision_set = frozenset()
    try:
        return short_filename(uri, collision_set)
    except ValueError:
        return None
