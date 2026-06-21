"""Deterministic resource matchers (architecture-resource-nodes Phase 2).

Given matcher rules (from graph.resource_matchers) and a built graph, return
resource suggestions — paste-ready material for graph.resources. Pure, read-only
over the graph; no writes. Seed rule vocabulary:

  - {"name": ..., "when": {"consumer_depends_on": <dep>},
     "emit": {"resource": <name>, "resource_kind": ..., "scope": ..., "role": "consumes"}}
  - {"name": ..., "when": {"package_glob": <glob>, "has_file": <glob>},
     "emit": {"resource_kind": ..., "scope": ..., "role": "provides"}}  # resource = file stem
"""

from __future__ import annotations

import fnmatch
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceSuggestion:
    resource: str
    resource_kind: str | None
    scope: str | None
    role: str  # "provides" | "consumes"
    source_name: str  # the package/app/dependency node name on the edge
    rule: str


def _matches_file(fpath: str, file_glob: str) -> bool:
    return (
        fnmatch.fnmatch(fpath, file_glob)
        or fnmatch.fnmatch(fpath, f"*{file_glob}")
        or fnmatch.fnmatch(fpath, f"*/{file_glob}")
    )


def compute_suggestions(conn: sqlite3.Connection, matchers: list[dict]) -> list[ResourceSuggestion]:
    """Apply matcher rules over existing graph facts → deduped suggestions.

    Deduped on (resource, role, source_name).
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[ResourceSuggestion] = []

    def _add(s: ResourceSuggestion) -> None:
        key = (s.resource, s.role, s.source_name)
        if key not in seen:
            seen.add(key)
            out.append(s)

    for rule in matchers:
        when = rule.get("when", {}) or {}
        emit = rule.get("emit", {}) or {}
        name = rule.get("name", "<unnamed>")

        if "consumer_depends_on" in when:
            dep = when["consumer_depends_on"]
            rows = conn.execute(
                "SELECT c.name FROM edges e "
                "JOIN nodes c ON e.src = c.id JOIN nodes d ON e.dst = d.id "
                "WHERE e.kind = 'used_by' AND d.kind IN ('dependency','builtin') AND d.name = ? "
                "AND c.kind IN ('package','app') ORDER BY c.name",
                (dep,),
            ).fetchall()
            for (consumer,) in rows:
                _add(
                    ResourceSuggestion(
                        resource=emit.get("resource", dep),
                        resource_kind=emit.get("resource_kind"),
                        scope=emit.get("scope"),
                        role=emit.get("role", "consumes"),
                        source_name=consumer,
                        rule=name,
                    )
                )

        elif "package_glob" in when and "has_file" in when:
            pkg_glob = when["package_glob"]
            file_glob = when["has_file"]
            pkgs = conn.execute("SELECT id, name FROM nodes WHERE kind IN ('package','app') ORDER BY name").fetchall()
            for pkg_id, pkg_name in pkgs:
                if not fnmatch.fnmatch(pkg_name, pkg_glob):
                    continue
                files = conn.execute(
                    "SELECT n.path FROM edges e JOIN nodes n ON e.dst = n.id "
                    "WHERE e.src = ? AND e.kind = 'physically_contains' AND n.kind = 'file'",
                    (pkg_id,),
                ).fetchall()
                for (fpath,) in files:
                    if not fpath or not _matches_file(fpath, file_glob):
                        continue
                    stem = fpath.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    _add(
                        ResourceSuggestion(
                            resource=stem,
                            resource_kind=emit.get("resource_kind"),
                            scope=emit.get("scope"),
                            role=emit.get("role", "provides"),
                            source_name=pkg_name,
                            rule=name,
                        )
                    )
    return out
