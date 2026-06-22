"""Deterministic resource matchers (general cross-stack vocabulary).

Given matcher rules (graph.resource_matchers) and a built graph, return resource
suggestions — paste-ready material for graph.resources. Pure, read-only over the
graph; no file-content reads. One unified rule shape:

  - name:    rule id (provenance)
    when:    closed set of predicates, AND-ed together (PREDICATE_NAMES)
    capture: {from: <CAPTURE_SOURCES>, segment?: int, transform?: [...]}
    emit:    {kind: <CANONICAL_KINDS>, subtype?: str, role: provides|consumes}

Rules are validated up front (validate_matchers); an invalid rule is a hard
config error surfaced by the command (exit 2, nothing written).
"""

from __future__ import annotations

import fnmatch
import sqlite3
from dataclasses import dataclass

# Canonical architecture-role kinds. emit.kind must be one of these.
CANONICAL_KINDS: frozenset[str] = frozenset(
    {
        "queue",
        "topic",
        "table",
        "store",
        "bucket",
        "cache",
        "endpoint",
        "service",
        "function",
        "inference",
        "secret",
        "schedule",
    }
)

# Closed predicate vocabulary for `when` (all keys in a rule AND together).
PREDICATE_NAMES: frozenset[str] = frozenset(
    {
        "package_glob",
        "depends_on",
        "imports_module",
        "instantiates_symbol",
        "defines_symbol",
        "has_file",
        "declares_entry_point",
    }
)

# Capture sources for `capture.from`.
CAPTURE_SOURCES: frozenset[str] = frozenset({"literal", "dependency", "symbol", "file_stem", "path_segment"})

_VALID_ROLES: frozenset[str] = frozenset({"provides", "consumes"})

# Which predicate(s) must be present for a given capture.from to ever yield a token.
_CAPTURE_REQUIRES: dict[str, frozenset[str]] = {
    "dependency": frozenset({"depends_on"}),
    "symbol": frozenset({"instantiates_symbol", "defines_symbol"}),
    "file_stem": frozenset({"has_file"}),
    # literal / path_segment are always satisfiable from the rule / anchor.
}


def validate_matchers(matchers: list[dict]) -> list[str]:
    """Return one error string per invalid rule (empty list = all valid).

    Invalid = unknown emit.kind, no matchable predicate in `when`, missing/unknown
    capture, an unsatisfiable capture.from, or an invalid emit.role.
    """
    errors: list[str] = []
    for rule in matchers:
        name = rule.get("name", "<unnamed>")
        when = rule.get("when") or {}
        capture = rule.get("capture") or {}
        emit = rule.get("emit") or {}

        kind = emit.get("kind")
        if kind not in CANONICAL_KINDS:
            errors.append(f"rule '{name}': unknown emit.kind {kind!r} (expected: {', '.join(sorted(CANONICAL_KINDS))})")

        role = emit.get("role", "provides")
        if role not in _VALID_ROLES:
            errors.append(f"rule '{name}': invalid emit.role {role!r} (expected: provides, consumes)")

        present_preds = set(when) & PREDICATE_NAMES
        if not present_preds:
            errors.append(
                f"rule '{name}': no matchable predicate in `when` (need one of: {', '.join(sorted(PREDICATE_NAMES))})"
            )

        cap_from = capture.get("from")
        if cap_from not in CAPTURE_SOURCES:
            errors.append(
                f"rule '{name}': unknown capture.from {cap_from!r} (expected: {', '.join(sorted(CAPTURE_SOURCES))})"
            )
        else:
            required = _CAPTURE_REQUIRES.get(cap_from)
            if required and not (required & present_preds):
                errors.append(
                    f"rule '{name}': capture.from {cap_from!r} requires one of "
                    f"these predicates in `when`: {', '.join(sorted(required))}"
                )
    return errors


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
