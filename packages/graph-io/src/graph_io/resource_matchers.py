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
import re
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


def _apply_transforms(value: str, transforms: list[dict] | None) -> str:
    """Apply ordered, optional string transforms. Deterministic; regex passes
    through unchanged when it does not match. Returns the (possibly empty) result."""
    out = value
    for step in transforms or []:
        if "strip_prefix" in step:
            prefix = step["strip_prefix"]
            if out.startswith(prefix):
                out = out[len(prefix) :]
        if "strip_suffix" in step:
            suffix = step["strip_suffix"]
            if suffix and out.endswith(suffix):
                out = out[: -len(suffix)]
        if "regex" in step:
            m = re.search(step["regex"], out)
            if m:
                out = next((g for g in m.groups() if g is not None), m.group(0))
        if step.get("lowercase"):
            out = out.lower()
    return out


def _load_packages(conn: sqlite3.Connection) -> dict[int, tuple[str, str | None]]:
    """All package/app nodes keyed by id → (name, path)."""
    rows = conn.execute("SELECT id, name, path FROM nodes WHERE kind IN ('package','app')").fetchall()
    return {pid: (name, path) for pid, name, path in rows}


def _owner_pkg_by_path(conn: sqlite3.Connection) -> dict[str, int]:
    """Map each file path → the id of the package/app that physically_contains it."""
    rows = conn.execute(
        "SELECT f.path, p.id FROM edges e "
        "JOIN nodes p ON e.src = p.id JOIN nodes f ON e.dst = f.id "
        "WHERE e.kind = 'physically_contains' AND p.kind IN ('package','app') "
        "AND f.kind = 'file' AND f.path IS NOT NULL"
    ).fetchall()
    return {path: pid for path, pid in rows}


def _dep_matches(dep_name: str, glob: str) -> bool:
    # Forgiving *-prefix matching (so 'client-sqs' matches '@aws-sdk/client-sqs').
    return fnmatch.fnmatch(dep_name, glob) or fnmatch.fnmatch(dep_name, f"*{glob}")


def _eval_predicate(
    conn: sqlite3.Connection,
    key: str,
    arg: str,
    pkgs: dict[int, tuple[str, str | None]],
) -> dict[int, set[str]]:
    """Evaluate one predicate → {anchor_pkg_id: {capture tokens}}.

    Filter-only predicates (package_glob, imports_module, declares_entry_point)
    map matching anchors to an empty token set; token-bearing predicates record
    the matched string for capture.from to read.
    """
    out: dict[int, set[str]] = {}

    def _add(pid: int, token: str | None) -> None:
        bucket = out.setdefault(pid, set())
        if token:
            bucket.add(token)

    if key == "package_glob":
        for pid, (name, _path) in pkgs.items():
            if fnmatch.fnmatch(name, arg):
                out.setdefault(pid, set())
        return out

    if key == "depends_on":
        rows = conn.execute(
            "SELECT c.id, d.name FROM edges e "
            "JOIN nodes c ON e.src = c.id JOIN nodes d ON e.dst = d.id "
            "WHERE e.kind = 'used_by' AND d.kind IN ('dependency','builtin') "
            "AND c.kind IN ('package','app')"
        ).fetchall()
        for cid, dname in rows:
            if cid in pkgs and _dep_matches(dname, arg):
                _add(cid, dname)
        return out

    if key == "has_file":
        rows = conn.execute(
            "SELECT e.src, f.path FROM edges e JOIN nodes f ON e.dst = f.id "
            "WHERE e.kind = 'physically_contains' AND f.kind = 'file' AND f.path IS NOT NULL"
        ).fetchall()
        for pid, fpath in rows:
            if pid in pkgs and _matches_file(fpath, arg):
                stem = fpath.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                _add(pid, stem)
        return out

    if key == "defines_symbol":
        owner = _owner_pkg_by_path(conn)
        rows = conn.execute(
            "SELECT name, path FROM nodes WHERE kind IN ('class','type','function') AND path IS NOT NULL"
        ).fetchall()
        for sname, spath in rows:
            if fnmatch.fnmatch(sname, arg) and owner.get(spath) in pkgs:
                _add(owner[spath], sname)
        return out

    if key == "instantiates_symbol":
        owner = _owner_pkg_by_path(conn)
        rows = conn.execute(
            "SELECT src.path, tgt.name FROM edges e "
            "JOIN nodes src ON e.src = src.id JOIN nodes tgt ON e.dst = tgt.id "
            "WHERE e.kind = 'calls' AND src.path IS NOT NULL"
        ).fetchall()
        for spath, tname in rows:
            if tname and fnmatch.fnmatch(tname, arg) and owner.get(spath) in pkgs:
                _add(owner[spath], tname)
        return out

    if key == "imports_module":
        owner = _owner_pkg_by_path(conn)
        rows = conn.execute(
            "SELECT src.path, dst.path, dst.name FROM edges e "
            "JOIN nodes src ON e.src = src.id JOIN nodes dst ON e.dst = dst.id "
            "WHERE e.kind = 'imports' AND src.kind = 'file' AND src.path IS NOT NULL"
        ).fetchall()
        for spath, dpath, dname in rows:
            target = dpath or dname or ""
            pid = owner.get(spath)
            if target and _matches_file(target, arg) and pid in pkgs:
                out.setdefault(pid, set())
        return out

    if key == "declares_entry_point":
        rows = conn.execute(
            "SELECT e.src, ep.name FROM edges e JOIN nodes ep ON e.dst = ep.id WHERE e.kind = 'declares_entry_point'"
        ).fetchall()
        for pid, epname in rows:
            if pid in pkgs and (arg in ("*", "") or fnmatch.fnmatch(epname or "", arg)):
                out.setdefault(pid, set())
        return out

    return out  # unknown predicate key (already rejected by validate_matchers)


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
