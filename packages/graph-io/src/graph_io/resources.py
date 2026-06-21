"""Resource emitter (architecture nodes).

Consumes a `resources_config` dict ({resource_name: info_dict}) resolved by the
caller from `<workspace>/.graph-wiki.yaml` graph.resources and emits:
  - resource nodes (one per top-level key)
  - provides edges (package/app -> resource)
  - consumes edges (package/app | dependency -> resource)

scope: explicit `scope:` wins; otherwise derived — a resource whose config
carries a `provided_by` defaults to 'internal', else 'external'. Unknown
consumer/provider names are warned (logger 'graph_io.resources') and skipped,
mirroring domains.emit orphan handling. Idempotent: upsert dedupes on
(src, dst, kind) and the node identity tuple.
"""

from __future__ import annotations

import logging
import sqlite3

from source_parser.projections.graph import GraphEdge, GraphNode

from graph_io import upsert
from graph_io.records import as_graph_records
from graph_io.uri import RepoContext, resource_uri

_LOG = logging.getLogger("graph_io.resources")

_KNOWN_KEYS = frozenset({"resource_kind", "scope", "description", "provider", "owner", "provided_by", "consumed_by"})
_VALID_SCOPES = frozenset({"internal", "external"})
_RESOURCE_KIND = "resource"
_PROVIDES_KIND = "provides"
_CONSUMES_KIND = "consumes"
_SOURCE_PATH = ".graph-wiki.yaml"


def _resource_key(name: str) -> tuple[str, str, str]:
    return (_RESOURCE_KIND, name, _SOURCE_PATH)


def _resolve_node(
    conn: sqlite3.Connection,
    entry,
    *,
    resource_name: str,
    role: str,
    allow_dependency: bool,
) -> tuple[str, str, str | None] | None:
    """Resolve a consumer/provider entry to a node-key tuple (kind, name, path).

    `entry` is a bare name string, or a typed mapping {"package": name} /
    {"dependency": name}. Providers pass allow_dependency=False (a resource is
    provided by in-repo code, never a 3rd-party lib). Returns None (after a
    warning) when the entry is malformed or names no known node.
    """
    restrict_dep_only = False
    restrict_pkg_only = False
    if isinstance(entry, dict):
        if len(entry) != 1:
            _LOG.warning(
                "resources: resource '%s' %s entry %r must have exactly one key — skipping",
                resource_name,
                role,
                entry,
            )
            return None
        ((typ, val),) = entry.items()
        if typ not in ("package", "dependency") or not isinstance(val, str):
            _LOG.warning("resources: resource '%s' %s entry %r is malformed — skipping", resource_name, role, entry)
            return None
        if typ == "dependency" and not allow_dependency:
            _LOG.warning("resources: resource '%s' provider cannot be a dependency (%r) — skipping", resource_name, val)
            return None
        name = val
        restrict_dep_only = typ == "dependency"
        restrict_pkg_only = typ == "package"
    elif isinstance(entry, str):
        name = entry
    else:
        _LOG.warning("resources: resource '%s' has non-string %s entry %r — skipping", resource_name, role, entry)
        return None

    if restrict_dep_only:
        kinds = ("dependency",)
    elif restrict_pkg_only or not allow_dependency:
        kinds = ("package", "app")
    else:
        kinds = ("package", "app", "dependency")

    placeholders = ",".join("?" for _ in kinds)
    # Prefer package, then app, then dependency on a name collision.
    rows = conn.execute(
        f"SELECT kind, name, path FROM nodes WHERE name = ? AND kind IN ({placeholders}) "
        "ORDER BY CASE kind WHEN 'package' THEN 0 WHEN 'app' THEN 1 ELSE 2 END",
        (name, *kinds),
    ).fetchall()
    if not rows:
        _LOG.warning(
            "resources: resource '%s' %s '%s' is not a known package/app/dependency — skipping edge",
            resource_name,
            role,
            name,
        )
        return None
    return (rows[0][0], rows[0][1], rows[0][2])


def emit(conn: sqlite3.Connection, *, resources_config: dict | None, ctx: RepoContext) -> None:
    """Emit resource nodes + provides/consumes edges. None/empty emits nothing."""
    if not resources_config:
        return

    nodes_out: list[GraphNode] = []
    edges_out: list[GraphEdge] = []

    for res_name, res_attrs in resources_config.items():
        if not isinstance(res_attrs, dict):
            _LOG.warning(
                "resources: resource '%s' must be a mapping, got %s — skipping",
                res_name,
                type(res_attrs).__name__,
            )
            continue

        for key in sorted(set(res_attrs.keys()) - _KNOWN_KEYS):
            _LOG.warning("resources: resource '%s' has unknown key '%s' — ignored", res_name, key)

        # scope: explicit override wins; else derive from provided_by presence.
        explicit = res_attrs.get("scope")
        if explicit in _VALID_SCOPES:
            scope = explicit
        else:
            if explicit is not None:
                _LOG.warning("resources: resource '%s' has invalid scope %r — deriving instead", res_name, explicit)
            scope = "internal" if res_attrs.get("provided_by") else "external"

        node_attrs: dict = {"uri": resource_uri(ctx, res_name), "scope": scope}
        for k in ("resource_kind", "description", "provider", "owner"):
            if k in res_attrs and res_attrs[k] is not None:
                node_attrs[k] = res_attrs[k]
        nodes_out.append(GraphNode(kind=_RESOURCE_KIND, name=res_name, path=_SOURCE_PATH, line=None, attrs=node_attrs))

        # provides edge (single provider; package/app only)
        provided_by = res_attrs.get("provided_by")
        if provided_by is not None:
            provider_key = _resolve_node(
                conn, provided_by, resource_name=res_name, role="provided_by", allow_dependency=False
            )
            if provider_key is not None:
                edges_out.append(
                    GraphEdge(src=provider_key, dst=_resource_key(res_name), kind=_PROVIDES_KIND, attrs={})
                )

        # consumes edges (list; package/app/dependency)
        consumed_by = res_attrs.get("consumed_by") or []
        if not isinstance(consumed_by, list):
            _LOG.warning("resources: resource '%s' consumed_by must be a list — skipping consumers", res_name)
            consumed_by = []
        for entry in consumed_by:
            consumer_key = _resolve_node(conn, entry, resource_name=res_name, role="consumed_by", allow_dependency=True)
            if consumer_key is not None:
                edges_out.append(
                    GraphEdge(src=consumer_key, dst=_resource_key(res_name), kind=_CONSUMES_KIND, attrs={})
                )

    with conn:
        upsert.upsert_records(conn, as_graph_records(nodes=nodes_out, edges=edges_out))
