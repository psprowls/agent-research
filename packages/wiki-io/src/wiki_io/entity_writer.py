"""Entity writer — graph-driven entity page rendering for the wiki.

This module owns THREE contracts every downstream entity-writing phase
(43-46) depends on:

1. **URI-to-filename derivation (Phase 52 D-03..D-07; cleanup Phase 53 D-04..D-06).**
   `short_filename(uri, collision_set, ...)` is the pure function that maps a
   graph URI to a short, human-readable vault filename stem (e.g.
   `pkg_graph-io`, `dep_boto3`, `unit_tests_wiki-io`). Colliders across
   different URIs receive a deterministic `__<6hex>` sha256 disambiguator
   suffix. `_compute_collision_set` precomputes the colliding-URI set in a
   single graph pass; both `write_entities` and the index/link consumers
   thread that same set so every filename consumer agrees byte-for-byte on
   each entity's stem. The legacy bidirectional slug helpers
   (`encode_slug` / `decode_slug`) were removed in Phase 53 — reverse
   lookups go through `frontmatter.load(entity_path).metadata["uri"]`.

2. **Scanner-owned frontmatter whitelist (D-06..D-09).**
   `SCANNER_OWNED_KEYS` is a flat frozenset enumerating every frontmatter
   key the scanner is allowed to overwrite on the next scan. Everything
   outside this set is human-territory and preserved as-is when the
   scanner re-renders an entity page (Phase 43 `merge_frontmatter`).

   Human-only keys are NOT enumerated as a constant (D-09); the explicit
   examples documented for readers are: `status`, `last_reviewed`, `owner`,
   `notes`. A unit test asserts disjointness from these four.

3. **Narrative region marker (D-16).**
   Per-kind templates carry a `## Narrative` H2 section that the LLM
   scanner targets and overwrites; everything outside that H2 (including
   other human-authored H2 sections) is preserved. The H2 string is a hard
   convention — humans must not rename the heading.
"""

from __future__ import annotations

import hashlib

# Admitted entity kinds — the 7 graph-derived kinds the wiki materializes
# as standalone pages under `wiki/entities/`. Underscore-form per D-02 matches
# `graph_io.queries._VALID_KINDS` casing. Phase 43+ imports this constant when
# routing graph rows to the correct template / URI builder.
#
# Phase 51 PKGFAM-03 / D-04: the retired family-grouping kind is gone;
# this frozenset is complete and final (no subtraction-narrow). Re-
# introducing a family-like grouping is deferred (REQUIREMENTS.md
# "Future Requirements") and would build on domain-clustering primitives,
# not a separate kind.
#
# Phase 49 D-16: `builtin` is intentionally NOT admitted here. Stdlib modules
# are inspectable via `cg list-builtins` / `cg describe-builtin` but do not
# warrant standalone wiki pages — rendering one page per stdlib module would
# dilute the entity surface without meaningful documentation value.
#
# Phase 52 D-06: `app` is admitted alongside `package`. Apps are classified
# by Phase 50's pipeline (a package-like node that has an entry point /
# distribution / app-shape signal). The wiki renders apps as standalone
# entity pages so SC#1's literal `app_graph-wiki-agent.md` output can be
# produced from a real scan.
ADMITTED_KINDS: frozenset[str] = frozenset(
    {
        "repository",
        "domain",
        "package",
        "app",
        "plugin",
        "dependency",
        "test_suite",
    }
)

# Map admitted kind names to their URI prefix as produced by `graph_io.uri`
# builders. Two prefixes are shortened aliases of the kind name (`repository`
# -> `repo`, `package` -> `pkg`); the remaining four are identical.
#
# Phase 53 D-06: `_ADMITTED_URI_PREFIXES` was removed (it only had `decode_slug`
# as a consumer, and Phase 53 D-04 deleted that function). The forward
# `short_filename` helper consumes `_FILENAME_PREFIX_BY_URI_PREFIX` directly,
# which is the only filename-layer prefix surface that remains.
_URI_PREFIX_BY_KIND: dict[str, str] = {
    "repository": "repo",
    "domain": "domain",
    "package": "pkg",
    "app": "app",
    "plugin": "plugin",
    # Phase 52 D-05: filename-layer alias only. Graph URIs (built by
    # `graph_io.uri.dependency_uri`) continue to use the `dependency:` prefix;
    # the short-form filename for dependency entities is `dep_<name>` and is
    # produced by `short_filename` via
    # `_FILENAME_PREFIX_BY_URI_PREFIX["dependency"] = "dep"`.
    "dependency": "dep",
    "test_suite": "test_suite",
}

# Frontmatter keys the scanner owns and may overwrite on every scan.
# Anything outside this set is human-authored and MUST be preserved by
# `merge_frontmatter` in Phase 43.
#
# Documented human-only keys (NOT in this whitelist; do not add):
#   - status          (e.g. `deprecated`, `active`, `experimental`)
#   - last_reviewed   (ISO date, human-recorded review checkpoint)
#   - owner           (free-form owner annotation)
#   - notes           (free-form human notes)
SCANNER_OWNED_KEYS: frozenset[str] = frozenset(
    {
        # Universal
        "uri",
        "kind",
        "graph_name",
        "last_scan_at",
        # Edge-derived (package)
        "domains",
        "depends_on",
        "test_suites",
        "entry_points",
        # Node-attr-derived (package)
        "language",
        "version",
        # Node-attr-derived (app — Phase 52 D-06; mirrors package + app-specific keys)
        "app_kind",
        "app_signals",
        # Edge-derived (domain)
        "parent_domain",
        "sub_domains",
        "packages",
        # Edge-derived (test_suite)
        "tested_packages",
        "suite_kind",
        "file_count",
        # Edge-derived (dependency)
        "ecosystem",
        "used_by",
        "versions_in_use",
        # Edge-derived (repository)
        "package_count",
    }
)


# ----------------------------------------------------------------------------
# Phase 52 D-03/D-04/D-05/D-07: short_filename pure helper (WIKI-FN-04)
# ----------------------------------------------------------------------------

# Filename-layer prefix per URI prefix (D-05): "dependency" is aliased to "dep"
# at the filename layer only — the URI prefix itself remains "dependency".
# For "test_suite", this dict entry is the suite_kind=None / unknown fallback;
# the test_suite branch in `short_filename` overrides for known suite_kinds.
_FILENAME_PREFIX_BY_URI_PREFIX: dict[str, str] = {
    "repo": "repo",
    "pkg": "pkg",
    "app": "app",
    "domain": "domain",
    "plugin": "plugin",
    "dependency": "dep",
    "test_suite": "tests",
}


def short_filename(
    uri: str,
    collision_set: frozenset[str],
    *,
    suite_kind: str | None = None,
    pkg_for_suite: str | None = None,
) -> str:
    """Compute the slim vault filename stem for a graph URI (D-03, D-04, D-05, D-07).

    Pure function — no I/O, no SQL, no logging side effects from inside the
    function body. Fallback warnings (e.g. for `test_suite` URIs missing
    `suite_kind`) are logged at the call site, not here, per Phase 50 D-04.

    Parameters
    ----------
    uri
        Graph URI of an admitted entity (e.g. ``pkg:org/repo/utils``).
    collision_set
        Frozenset of URIs known to collide on the plain stem. If ``uri`` is
        in this set, a 6-hex sha256 disambiguator suffix is appended
        (D-03, D-04 — all colliders carry the suffix, not just N-1 of them).
    suite_kind
        For ``test_suite:`` URIs only — selects the prefix per D-07:
        ``unit`` → ``unit_tests``, ``integration`` → ``int_tests``,
        ``e2e`` → ``e2e_tests``, ``contract`` → ``contract_tests``,
        any other value or ``None`` → ``tests``. Ignored for non-test_suite
        URIs.
    pkg_for_suite
        For ``test_suite:`` URIs only — the package name to embed in the
        stem. If omitted, derived from the URI path: the second-to-last
        path segment if the path has ≥ 2 segments, else the last segment.

    Returns
    -------
    str
        The filename stem (without ``.md`` extension).

    Raises
    ------
    ValueError
        If ``uri`` is empty, lacks a ``:`` prefix separator, or has an
        unknown URI prefix.

    Examples
    --------
    >>> short_filename("pkg:org/repo/utils", frozenset())
    'pkg_utils'
    >>> short_filename("dependency:pypi/boto3", frozenset())
    'dep_boto3'
    >>> short_filename(
    ...     "test_suite:org/repo/wiki-io/tests",
    ...     frozenset(),
    ...     suite_kind="unit",
    ...     pkg_for_suite="wiki-io",
    ... )
    'unit_tests_wiki-io'
    >>> stem = short_filename("pkg:org/repo/utils", frozenset({"pkg:org/repo/utils"}))
    >>> stem.startswith("pkg_utils__")
    True
    >>> len(stem.rsplit("__", 1)[-1])
    6
    """
    if not uri:
        raise ValueError("short_filename: empty uri")
    if ":" not in uri:
        raise ValueError(
            f"short_filename: malformed uri {uri!r}: missing `:` prefix separator"
        )
    uri_prefix, path = uri.split(":", 1)

    if uri_prefix == "test_suite":
        kind_prefix_by_suite = {
            "unit": "unit_tests",
            "integration": "int_tests",
            "e2e": "e2e_tests",
            "contract": "contract_tests",
        }
        kind_prefix = kind_prefix_by_suite.get(suite_kind, "tests")
        if pkg_for_suite is not None:
            pkg_part = pkg_for_suite
        else:
            segments = path.split("/")
            pkg_part = segments[-2] if len(segments) >= 2 else segments[-1]
        plain_stem = f"{kind_prefix}_{pkg_part}"
    else:
        kind_prefix = _FILENAME_PREFIX_BY_URI_PREFIX.get(uri_prefix)
        if kind_prefix is None:
            raise ValueError(
                f"short_filename: unknown uri prefix {uri_prefix!r}"
            )
        name = path.split("/")[-1]
        plain_stem = f"{kind_prefix}_{name}"

    if uri in collision_set:
        suffix = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:6]
        return f"{plain_stem}__{suffix}"
    return plain_stem


# ============================================================================
# Phase 43 Plan 02: write_entities orchestrator + helpers
# ============================================================================

import datetime as _dt  # noqa: E402
import fcntl  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import sqlite3  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from importlib.resources import files as _resource_files  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable, Iterator  # noqa: E402

import frontmatter  # noqa: E402
import yaml  # noqa: E402

_logger = logging.getLogger(__name__)

from graph_io import queries as _queries


# Subset of SCANNER_OWNED_KEYS that triggers needs_narrative when changed (D-10).
# Phase 51 PKGFAM-03: `members` removed (was the sole carrier for the
# retired family-grouping kind).
STRUCTURAL_KEYS: frozenset[str] = frozenset(
    {
        "domains",
        "depends_on",
        "test_suites",
        "entry_points",
        "parent_domain",
        "sub_domains",
        "packages",
        "tested_packages",
        "used_by",
    }
)

# Defence-in-depth: enforce the STRUCTURAL_KEYS ⊂ SCANNER_OWNED_KEYS invariant at import.
assert STRUCTURAL_KEYS.issubset(SCANNER_OWNED_KEYS), \
    "STRUCTURAL_KEYS must be a subset of SCANNER_OWNED_KEYS (D-10)"


class WriteLockHeldError(RuntimeError):
    """Raised by `write_entities` when another scan holds `.graph-wiki/scan.lock`."""


@dataclass(frozen=True)
class EntityWriteError:
    """A per-page failure during `write_entities` (D-09 / D-21)."""
    uri: str
    slug: str
    exception: str  # repr() of the caught exception


@dataclass(frozen=True)
class EntityWriteResult:
    """Bucketed URIs + per-page errors from one `write_entities` invocation (D-09).

    Lists are sorted alphabetically for deterministic comparison in tests.
    `needs_narrative` is a `set` of URIs requiring LLM prose generation
    (new pages OR pages whose STRUCTURAL_KEYS changed since last write).
    """
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    needs_narrative: set[str] = field(default_factory=set)
    errors: list[EntityWriteError] = field(default_factory=list)


# ----------------------------------------------------------------------------
# merge_frontmatter (D-12, D-13, D-14)
# ----------------------------------------------------------------------------


def _sort_dedupe(value: Any) -> Any:
    """Return a sorted, deduped list if value is a list; otherwise return as-is.

    Mixed-type lists are sorted by (type_name, repr) to keep behavior total.
    """
    if isinstance(value, list):
        try:
            return sorted(set(value), key=lambda x: (str(type(x)), str(x)))
        except TypeError:
            # Unhashable items (e.g. dicts) — leave order alone but drop None? No.
            return value
    return value


def _is_empty(value: Any) -> bool:
    """Filter for D-14 step 3: scanner keys with these values are omitted."""
    return value is None or value == "" or value == [] or value == {}


def merge_frontmatter(existing: dict, scanner_update: dict) -> dict:
    """Merge scanner-computed frontmatter into an existing page's frontmatter.

    Semantics per CONTEXT.md D-12..D-14:
    - Scanner-owned keys (SCANNER_OWNED_KEYS) = full replacement from
      `scanner_update`. Empty values omitted (kept compact).
    - Non-scanner keys (human-authored) preserved verbatim, in original
      encountered order.
    - Key order on output: uri, kind, then scanner keys alphabetical
      (non-empty only), then human keys in original encountered order.
    - Collection values inside scanner-owned keys are sorted + deduped.
    """
    out: dict = {}
    # 1. uri (always present; may come from existing if scanner_update omits it)
    if "uri" in scanner_update:
        out["uri"] = scanner_update["uri"]
    elif "uri" in existing:
        out["uri"] = existing["uri"]
    # 2. kind
    if "kind" in scanner_update:
        out["kind"] = scanner_update["kind"]
    elif "kind" in existing:
        out["kind"] = existing["kind"]
    # 3. Scanner-owned keys, alphabetical, non-empty only
    for key in sorted(SCANNER_OWNED_KEYS - {"uri", "kind"}):
        if key in scanner_update:
            val = scanner_update[key]
            if not _is_empty(val):
                out[key] = _sort_dedupe(val) if isinstance(val, list) else val
    # 4. Human keys preserved in original encountered order from `existing`
    for key, val in existing.items():
        if key not in SCANNER_OWNED_KEYS and key not in out:
            out[key] = val
    return out


# ----------------------------------------------------------------------------
# _acquire_scan_lock (D-19, D-20, D-21)
# ----------------------------------------------------------------------------


@contextmanager
def _acquire_scan_lock(workspace_root: Path) -> Iterator[None]:
    """Acquire an exclusive non-blocking advisory lock at
    `<workspace_root>/.graph-wiki/scan.lock` for the duration of the with-block.

    Raises `WriteLockHeldError` on contention (no wait). Releases the lock
    even on exception paths (D-19, D-21).

    POSIX-only — Phase 43 RESEARCH.md notes the rest of the stack is also
    POSIX-only; on Windows users should run inside WSL.
    """
    lock_path = workspace_root / ".graph-wiki" / "scan.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WriteLockHeldError(
                f"another scan in progress for this workspace: {workspace_root}"
            ) from exc
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


# ----------------------------------------------------------------------------
# deletions.log helpers (D-17, D-18)
# ----------------------------------------------------------------------------


def _rotate_deletions_log(log_path: Path, max_bytes: int = 10_000_000) -> None:
    """If `log_path` exceeds `max_bytes`, rename to `.log.1` (overwriting any
    prior `.log.1`). Two-file scheme per D-18. No-op if file is small or
    doesn't exist.
    """
    if not log_path.exists():
        return
    if log_path.stat().st_size < max_bytes:
        return
    rotated = log_path.with_suffix(".log.1")
    if rotated.exists():
        rotated.unlink()
    log_path.rename(rotated)


def _append_deletion(log_path: Path, record: dict) -> None:
    """Append one JSONL record to `.graph-wiki/deletions.log` (D-17).

    Rotates first (D-18). Creates parent dir if missing. Uses compact JSON
    (no extra whitespace) so log lines are unambiguous.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _rotate_deletions_log(log_path)
    line = json.dumps(record, separators=(",", ":"), sort_keys=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ----------------------------------------------------------------------------
# Structural change detection + page rendering (D-10, D-11, D-14, D-15)
# ----------------------------------------------------------------------------


def _detect_structural_change(existing_fm: dict, new_fm: dict) -> bool:
    """Return True iff any STRUCTURAL_KEYS value differs (sort+dedupe lists).

    Used to populate `needs_narrative` per D-10: pages with structural drift
    must re-run the LLM narrative generator.
    """
    for key in STRUCTURAL_KEYS:
        old = existing_fm.get(key)
        new = new_fm.get(key)
        if isinstance(old, list) and isinstance(new, list):
            if sorted(set(old), key=str) != sorted(set(new), key=str):
                return True
        elif old != new:
            return True
    return False


def _render_entity_page(template_path: Path, frontmatter_dict: dict) -> str:
    """Render an entity page: template body + given frontmatter dict.

    Frontmatter is emitted with `sort_keys=False` because key order has
    already been determined by `merge_frontmatter` (D-14). Output ends with
    exactly one trailing newline for byte-stability (D-15).
    """
    template = frontmatter.load(template_path)
    body = template.content
    yaml_block = yaml.safe_dump(
        frontmatter_dict,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,
    )
    yaml_block = yaml_block.rstrip("\n")
    rendered = f"---\n{yaml_block}\n---\n{body}".rstrip("\n") + "\n"
    return rendered


# ----------------------------------------------------------------------------
# write_entities orchestrator (D-08, D-15, D-16, D-21, D-22)
# ----------------------------------------------------------------------------


# Mapping from kind to list_fn — closes over graph_io.queries module so tests
# can monkeypatch via `setattr(_queries, "list_packages", ...)`.
def _kind_list_fns() -> dict[str, Callable]:
    return {
        "repository": lambda conn: _queries.list_repositories(conn),
        "package": lambda conn: _queries.list_packages(conn),
        "app": lambda conn: _queries.list_apps(conn),
        "domain": lambda conn: _queries.list_domains(conn),
        "test_suite": lambda conn: _queries.list_test_suites(conn),
        "dependency": lambda conn: _queries.list_dependencies(conn),
        "plugin": lambda conn: _queries.list_plugins(conn),
    }


def _template_path_for_kind(kind: str) -> Path:
    """Return the on-disk path to the entity-<kind>.md template (Phase 42 Plan 02)."""
    fname = f"entity-{kind.replace('_', '-')}.md"
    return Path(str(_resource_files("wiki_io.assets.page-templates").joinpath(fname)))


def scanner_frontmatter_for_node(conn: Any, kind: str, node: Any) -> dict:
    """Build the scanner-update frontmatter dict from a graph node + its description.

    Returns a dict ready for `merge_frontmatter`. Always populates `uri`,
    `kind`. Per-kind logic pulls relation lists from `describe_*` and
    attrs from the node.
    """
    # Node URI: prefer the node's nodes.uri column (NodeRecord may carry it
    # in attrs because describe_* surfaces use the column at projection time).
    uri = node.attrs.get("uri", "") if isinstance(node.attrs, dict) else ""
    fm: dict = {
        "uri": uri,
        "kind": kind,
    }
    if kind == "repository":
        d = _queries.describe_repository(conn)
        if d is not None:
            fm["package_count"] = d.package_count
    elif kind == "package":
        d = _queries.describe_package(conn, name=node.name)
        if d is not None:
            fm["language"] = d.language
            fm["version"] = d.version
            fm["domains"] = list(d.domains)
            fm["test_suites"] = [s.name for s in d.test_suites]
            fm["entry_points"] = [e.name for e in d.entry_points]
    elif kind == "app":
        d = _queries.describe_app(conn, name=node.name)
        if d is not None:
            # AppDescription mirrors PackageDescription field-for-field with
            # two additions: `app_kind` (one of `_VALID_APP_KINDS`) and
            # `app_signals` (sorted list of classification signals) — both
            # surfaced as scanner-owned keys (D-06).
            fm["language"] = d.language
            fm["version"] = d.version
            fm["domains"] = list(d.domains)
            fm["test_suites"] = [s.name for s in d.test_suites]
            fm["entry_points"] = [e.name for e in d.entry_points]
            fm["app_kind"] = d.app_kind
            fm["app_signals"] = list(d.app_signals)
    elif kind == "domain":
        d = _queries.describe_domain(conn, name=node.name)
        if d is not None and d.parent:
            fm["parent_domain"] = d.parent
    elif kind == "test_suite":
        d = _queries.describe_test_suite(conn, suite_name=node.name)
        if d is not None:
            fm["suite_kind"] = d.kind
            fm["file_count"] = d.file_count
    elif kind == "dependency":
        ecosystem = node.attrs.get("ecosystem", "pypi") if isinstance(node.attrs, dict) else "pypi"
        d = _queries.describe_dependency(conn, ecosystem=ecosystem, name=node.name)
        if d is not None:
            fm["ecosystem"] = d.ecosystem
            fm["versions_in_use"] = list(d.versions_in_use)
            fm["used_by"] = list(d.used_by)
    elif kind == "plugin":
        d = _queries.describe_plugin(conn, name=node.name)
        if d is not None:
            fm["ecosystem"] = d.ecosystem
    return fm


def _is_template_body_default(body: str, template_body: str) -> bool:
    """Heuristic: True if the body equals the unmodified template body."""
    return body.rstrip() == template_body.rstrip()


def _compute_collision_set(
    conn: sqlite3.Connection,
    admitted_kinds: frozenset[str],
    list_fns: dict[str, Callable],
) -> frozenset[str]:
    """Pre-pass that returns the set of URIs whose plain short stem collides.

    Iterates every admitted-kind node once, computes each node's *plain*
    short filename via ``short_filename(uri, collision_set=frozenset(), ...)``
    (i.e. with an empty collision set so no suffix is added), groups by stem,
    and returns the set of URIs whose stem appears more than once across the
    whole admitted-kind enumeration.

    D-01 + D-02: extends to TestSuite kind-aware names by reading
    ``suite_kind`` from ``node.attrs["suite_kind"]`` and ``pkg_for_suite``
    from ``Path(node.attrs["path"]).parent.name`` (or last segment fallback)
    when ``kind == "test_suite"``. This means two test_suites with the same
    kind + same package name (e.g. two ``unit`` suites for the same package
    name) will be flagged as colliding and both receive a ``__<6hex>``
    disambiguator — matching the all-colliders D-04 semantics for the rest
    of the entity surface.

    Internal helper (single-leading-underscore): exists to keep
    ``write_entities`` readable + unit-testable in isolation. Reads the
    SQLite connection in a read-only fashion; does not write or mutate
    global state.
    """
    stem_to_uris: dict[str, list[str]] = {}
    for kind in sorted(admitted_kinds):
        list_fn = list_fns.get(kind)
        if list_fn is None:
            continue
        for node in list_fn(conn):
            uri = node.attrs.get("uri") if isinstance(node.attrs, dict) else None
            if not uri:
                continue
            if kind == "test_suite":
                attrs = node.attrs if isinstance(node.attrs, dict) else {}
                suite_kind = attrs.get("suite_kind") or None
                suite_path = attrs.get("path")
                pkg_for_suite: str | None = None
                if suite_path:
                    pkg_for_suite = Path(suite_path).parent.name or None
                if not pkg_for_suite:
                    pkg_for_suite = None
                stem = short_filename(
                    uri,
                    frozenset(),
                    suite_kind=suite_kind,
                    pkg_for_suite=pkg_for_suite,
                )
            else:
                stem = short_filename(uri, frozenset())
            stem_to_uris.setdefault(stem, []).append(uri)
    return frozenset(
        uri
        for uris in stem_to_uris.values()
        if len(uris) > 1
        for uri in uris
    )


def write_entities(
    conn: sqlite3.Connection,
    wiki_root: Path,
    admitted_kinds: frozenset[str],
) -> EntityWriteResult:
    """Create / merge / hard-delete entity pages from the graph.

    See `.planning/phases/43-entity-writer/43-CONTEXT.md` for the locked
    decisions (D-08..D-22). Acquires `.graph-wiki/scan.lock` on entry;
    releases in `finally` (including exception paths) (D-19, D-21).

    Returns `EntityWriteResult` with per-state URI buckets + `needs_narrative`
    for the Phase 45 LLM fan-out + per-page errors for partial-success.
    """
    workspace_root = wiki_root.parent  # `.graph-wiki/` sits next to `wiki/`
    entities_dir = wiki_root / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    deletions_log = workspace_root / ".graph-wiki" / "deletions.log"

    created: list[str] = []
    updated: list[str] = []
    deleted: list[str] = []
    unchanged: list[str] = []
    needs_narrative: set[str] = set()
    errors: list[EntityWriteError] = []
    admitted_uris: set[str] = set()

    list_fns = _kind_list_fns()
    # Phase 52 D-01: one-shot collision pre-pass; reads conn read-only, no lock needed
    collision_set = _compute_collision_set(conn, admitted_kinds, list_fns)

    with _acquire_scan_lock(workspace_root):
        # --- Per-kind create / merge ---
        for kind in sorted(admitted_kinds):
            list_fn = list_fns.get(kind)
            if list_fn is None:
                continue  # unknown admitted kind without a list_fn — skip
            template_path = _template_path_for_kind(kind)
            if not template_path.exists():
                errors.append(EntityWriteError(
                    uri=f"<missing-template:{kind}>",
                    slug="",
                    exception=repr(FileNotFoundError(str(template_path))),
                ))
                continue
            for node in list_fn(conn):
                uri = node.attrs.get("uri") if isinstance(node.attrs, dict) else None
                if not uri:
                    continue
                admitted_uris.add(uri)
                # Phase 52 D-01..D-07: derive short filename, handling test_suite kind-aware naming.
                suite_kind_for_node: str | None = None
                pkg_for_suite_for_node: str | None = None
                if kind == "test_suite":
                    attrs_for_node = node.attrs if isinstance(node.attrs, dict) else {}
                    suite_kind_for_node = attrs_for_node.get("suite_kind") or None
                    suite_path = attrs_for_node.get("path")
                    if suite_path:
                        pkg_for_suite_for_node = Path(suite_path).parent.name or None
                    if not suite_kind_for_node:
                        _logger.warning(
                            "test_suite node has no suite_kind attr (uri=%s); "
                            "falling back to tests_<pkg> short filename",
                            uri,
                        )
                slug = short_filename(
                    uri,
                    collision_set,
                    suite_kind=suite_kind_for_node,
                    pkg_for_suite=pkg_for_suite_for_node,
                )
                page_path = entities_dir / f"{slug}.md"
                try:
                    scanner_fm = scanner_frontmatter_for_node(conn, kind, node)
                    existing_fm: dict = {}
                    existed = page_path.exists()
                    if existed:
                        post = frontmatter.load(page_path)
                        existing_fm = dict(post.metadata)
                    merged_fm = merge_frontmatter(existing_fm, scanner_fm)
                    new_content = _render_entity_page(template_path, merged_fm)
                    new_bytes = new_content.encode("utf-8")
                    if existed:
                        old_bytes = page_path.read_bytes()
                        if old_bytes == new_bytes:
                            unchanged.append(uri)
                            continue
                        page_path.write_text(new_content, encoding="utf-8")
                        page_path.chmod(0o644)
                        updated.append(uri)
                        if _detect_structural_change(existing_fm, merged_fm):
                            needs_narrative.add(uri)
                    else:
                        page_path.write_text(new_content, encoding="utf-8")
                        page_path.chmod(0o644)
                        created.append(uri)
                        needs_narrative.add(uri)
                except Exception as exc:  # noqa: BLE001 — D-21 partial-failure isolation
                    errors.append(EntityWriteError(
                        uri=uri, slug=slug, exception=repr(exc),
                    ))

        # --- Deletion sweep ---
        for page_path in sorted(entities_dir.glob("*.md")):
            if page_path.name == "_index.md":
                continue
            try:
                post = frontmatter.load(page_path)
                uri = post.metadata.get("uri")
                if not uri or uri in admitted_uris:
                    continue
                kind_from_fm = post.metadata.get("kind") or uri.split(":", 1)[0]
                template_path = _template_path_for_kind(kind_from_fm)
                template_body = ""
                if template_path.exists():
                    template_body = frontmatter.load(template_path).content
                body_was_empty = _is_template_body_default(post.content, template_body)
                record = {
                    "timestamp": _dt.datetime.now(_dt.timezone.utc)
                                  .isoformat(timespec="seconds").replace("+00:00", "Z"),
                    "uri": uri,
                    "slug": page_path.stem,
                    "path": str(page_path.relative_to(workspace_root)),
                    "kind": kind_from_fm,
                    "body_was_empty": body_was_empty,
                }
                _append_deletion(deletions_log, record)
                page_path.unlink()
                deleted.append(uri)
            except Exception as exc:  # noqa: BLE001
                errors.append(EntityWriteError(
                    uri=str(page_path.name), slug=page_path.stem, exception=repr(exc),
                ))

    return EntityWriteResult(
        created=sorted(created),
        updated=sorted(updated),
        deleted=sorted(deleted),
        unchanged=sorted(unchanged),
        needs_narrative=needs_narrative,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Phase 45 D-07: inject_narrative — overwrite the `## Narrative` body region
# ---------------------------------------------------------------------------

# Hard convention per Phase 42 D-16: humans must not rename this heading.
_NARRATIVE_HEADING = "## Narrative"

# Match `## Narrative` at column 0 followed only by optional trailing whitespace
# and a newline (so `### Narrative` and `## Narrative Foo` do NOT match).
_NARRATIVE_HEADING_RE = re.compile(r"^## Narrative[ \t]*\n", re.MULTILINE)

# Match the next H2 heading at column 0 (used to locate the end of the
# narrative body region).
_NEXT_H2_RE = re.compile(r"^## ", re.MULTILINE)


def inject_narrative(page_path: Path, prose: str) -> None:
    """Replace the body of the `## Narrative` section with `prose`.

    Phase 45 D-07: locates the FIRST `## Narrative` H2 heading at column 0;
    replaces the body region from end-of-that-heading up to the next H2 (or
    EOF) with `prose.strip()`. Writes atomically via temp-file + `os.replace`.

    Idempotent: calling with the same arguments twice produces byte-identical
    output on the second call.

    Logs a WARNING and returns without writing when the page is missing the
    `## Narrative` heading (defensive — entity templates always carry it).

    Raises:
        FileNotFoundError: when `page_path` does not exist.
    """
    text = page_path.read_text(encoding="utf-8")  # raises FileNotFoundError naturally

    match = _NARRATIVE_HEADING_RE.search(text)
    if match is None:
        _logger.warning(
            "inject_narrative: no `## Narrative` heading found at %s", page_path
        )
        return

    body_start = match.end()  # index immediately after the heading's newline

    next_h2 = _NEXT_H2_RE.search(text, body_start)
    body_end = next_h2.start() if next_h2 is not None else len(text)

    cleaned = prose.strip()
    new_body = f"\n{cleaned}\n\n" if cleaned else "\n\n"
    new_content = text[:body_start] + new_body + text[body_end:]

    tmp_path = page_path.with_suffix(page_path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, page_path)
