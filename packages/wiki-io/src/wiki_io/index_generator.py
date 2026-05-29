"""Generate `wiki/index.md` from a graph + curated-lane filesystem scan.

Phase 44 — Scanner-Generated Index. New module (D-01); `update_index.py`
remains untouched in this phase (Phase 46 cutover deletes it).

Filename derivation per Phase 53 D-04..D-06: entity links go through
``wiki_io.entity_writer.short_filename`` (with a precomputed
``collision_set`` from ``_compute_collision_set``); the old bidirectional
slug machinery has been removed.

Decisions encoded here (see `.planning/phases/44-scanner-generated-index/44-CONTEXT.md`):

- D-01: This is a new module — `index_generator.py` — owning the
  generation of `wiki/index.md` end-to-end.
- D-02: `generate_index` does a FULL rewrite of `wiki/index.md`. The file
  is fully owned by this module — no HTML-comment markers, no partial
  rewrites, no per-folder `*/index.md` files written.
- D-03: Rendered section order is:
  H1 → banner → `## Domains` → `## By Kind` → `## Architecture` →
  `## ADRs` → `## Concepts` → `## Sources` → `## Work`.
- D-04: Single-placement rule for entities. An entity placed under a
  single qualifying domain renders inside that `## Domain: X` section;
  zero or multiple qualifying domains fall back to `## By Kind`.
  Plugins always fall to `## By Kind` (no qualifying-domain edges in v1.8).
- D-09: `BY_KIND_ORDER` is a hard-coded tuple, NOT derived from
  `ADMITTED_KINDS` — guarantees stable section order independent of
  schema evolution.
- D-15: Sort entities alphabetically by URI within every bucket.
- D-16: Write-if-changed — byte-compare against existing `wiki/index.md`
  and only atomic-write (temp file + `os.replace`) when bytes differ.
- D-19: All-or-nothing — exceptions inside `_place_entities` / `_render`
  propagate out of `generate_index`. No partial-success error model.
- D-20: `generate_index` is lock-agnostic — the caller (Phase 45
  `run_scan`) owns `.graph-wiki/scan.lock` acquisition.
"""

from __future__ import annotations

import dataclasses
import datetime
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from graph_io.queries import (
    NodeRecord,
    internal_dependencies_of,
    list_apps,
    list_dependencies,
    list_domains,
    list_packages,
    list_plugins,
    list_test_suites,
)

from wiki_io.entity_writer import (
    ADMITTED_KINDS as _ADMITTED_KINDS,
    _compute_collision_set,
    _kind_list_fns,
    short_filename as _short_filename,
)

# ============================================================================
# Module constants (D-09, D-12)
# ============================================================================

# Phase 57 D-01 (the crux): placement kinds are DECOUPLED from render order.
# `_PLACEABLE_KINDS` drives `_place_entities` iteration AND the by-kind sort key;
# it MUST include test_suite/dependency or those entities would never be
# discovered/placed and could not nest under their packages (breaking IDX-04/05).
# `BY_KIND_ORDER` (D-03/D-08) drives ONLY the flat `## By Kind` render groups —
# apps first, then packages, then plugins. test_suites/dependencies are no longer
# flat groups; they appear exclusively nested under the package/app that uses them
# (in both domain and By-Kind contexts per D-01), so removing them from the flat
# render order is safe precisely because every package/app now nests its own items.
_PLACEABLE_KINDS: tuple[str, ...] = (
    "app", "package", "test_suite", "dependency", "plugin",
)

BY_KIND_ORDER: tuple[str, ...] = ("app", "package", "plugin")

KIND_LABELS: dict[str, str] = {
    "app": "Apps",
    "package": "Packages",
    "test_suite": "Test Suites",
    "dependency": "Dependencies",
    "plugin": "Plugins",
}

# (stable_id, lane_dir_relative_to_wiki_root, section_label)
# Note: CONTEXT.md D-12's example showed `"wiki/architecture"`, but `wiki_root`
# IS the wiki directory, so the lane_dir is the BARE lane name to avoid
# double-prefixing. The decision intent (4 lanes, this order) is preserved.
CURATED_LANES: tuple[tuple[str, str, str], ...] = (
    ("architecture", "architecture", "Architecture"),
    ("adrs",         "adrs",         "ADRs"),
    ("concepts",     "concepts",     "Concepts"),
    ("sources",      "sources",      "Sources"),
)

GENERATED_FILES: frozenset[str] = frozenset({
    "index.md", "log.md",
    "concepts/index.md", "adrs/index.md", "sources/index.md",
    "architecture/index.md", "dependencies/index.md",
})

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ============================================================================
# Public dataclasses
# ============================================================================


@dataclass(frozen=True)
class IndexWriteResult:
    """Return value of `generate_index` (D-18)."""

    path: Path
    bytes_written: int
    changed: bool
    entity_count: int
    curated_count: int
    domain_count: int
    by_kind_count: int


@dataclass(frozen=True)
class PlacedEntity:
    """An entity placed under a domain or in the by-kind fallback.

    `parent_pkg_names` is populated for dependencies/test_suites under a
    single-domain placement so `_render_domain_section` can nest them under
    consumer/tested-package bullets (D-06).

    `suite_kind` / `pkg_for_suite` are populated for test_suite entities so
    Phase 53's `short_filename` can derive kind-aware names like
    `unit_tests_<pkg>`; they are `None` for non-test_suite kinds.

    `summary` (Phase 57 D-06/D-07) is the entity page's own frontmatter
    `summary:` value — NOT the graph node attr. Phase 56 makes `summary:`
    fill-when-empty so a human can edit it; reading the page file (like the
    curated-lane scan) keeps the index in sync with the editable source.
    Empty when the entity page / frontmatter is missing.
    """

    kind: str
    name: str
    uri: str
    parent_pkg_names: tuple[str, ...] = ()
    suite_kind: str | None = None
    pkg_for_suite: str | None = None
    summary: str = ""


# ============================================================================
# Graph-read helpers (D-04)
# ============================================================================


def _compute_qualifying_domains(
    conn: sqlite3.Connection, *, kind: str, name: str
) -> set[str]:
    """Return the set of domain names that qualify for this entity (D-04).

    - package:    direct `belongs_to_domain` edges.
    - app:        direct `belongs_to_domain` edges (Phase 57 D-03/D-04 —
                  apps route identically to packages: single qualifying
                  domain → that domain section; zero/multi → By-Kind).
    - test_suite: one-hop transitive via `tests -> package -> belongs_to_domain`.
    - dependency: one-hop transitive via `used_by` -> `package` -> `belongs_to_domain`.
                  Edge direction: package -[used_by]-> dependency.
    - plugin:     always empty (D-04 — plugins have no domain edges in v1.8).
    """
    if kind in ("package", "app"):
        rows = conn.execute(
            "SELECT d.name FROM edges e "
            "JOIN nodes p ON e.src = p.id "
            "JOIN nodes d ON e.dst = d.id "
            "WHERE e.kind='belongs_to_domain' "
            "AND p.kind = ? AND p.name = ? "
            "AND d.kind='domain' "
            "ORDER BY d.name",
            (kind, name),
        ).fetchall()
        return {r[0] for r in rows}
    if kind == "test_suite":
        rows = conn.execute(
            "SELECT DISTINCT d.name FROM edges t "
            "JOIN nodes ts ON t.src = ts.id "
            "JOIN nodes p ON t.dst = p.id "
            "JOIN edges bt ON bt.src = p.id AND bt.kind='belongs_to_domain' "
            "JOIN nodes d ON d.id = bt.dst "
            "WHERE t.kind='tests' "
            "AND ts.kind='test_suite' AND ts.name = ? "
            "AND p.kind='package' AND d.kind='domain' "
            "ORDER BY d.name",
            (name,),
        ).fetchall()
        return {r[0] for r in rows}
    if kind == "dependency":
        rows = conn.execute(
            "SELECT DISTINCT d.name FROM edges u "
            "JOIN nodes p ON u.src = p.id "
            "JOIN nodes dep ON u.dst = dep.id "
            "JOIN edges bt ON bt.src = p.id AND bt.kind='belongs_to_domain' "
            "JOIN nodes d ON d.id = bt.dst "
            "WHERE u.kind='used_by' "
            "AND p.kind='package' AND dep.kind='dependency' AND dep.name = ? "
            "AND d.kind='domain' "
            "ORDER BY d.name",
            (name,),
        ).fetchall()
        return {r[0] for r in rows}
    if kind == "plugin":
        return set()
    raise ValueError(
        f"Only app/package/test_suite/dependency/plugin are placeable; got {kind!r}"
    )


def _consumer_pkgs_in_domain(
    conn: sqlite3.Connection, *, kind: str, entity_name: str, domain_name: str
) -> tuple[str, ...]:
    """Return the package names (in `domain_name`) that consume or are tested by
    this dependency / test_suite. Used by `_place_entities` to populate
    `PlacedEntity.parent_pkg_names` for intra-domain nesting (D-06)."""
    if kind == "dependency":
        rows = conn.execute(
            "SELECT DISTINCT p.name FROM edges u "
            "JOIN nodes p ON u.src = p.id "
            "JOIN nodes dep ON u.dst = dep.id "
            "JOIN edges bt ON bt.src = p.id AND bt.kind='belongs_to_domain' "
            "JOIN nodes d ON d.id = bt.dst "
            "WHERE u.kind='used_by' AND p.kind='package' "
            "AND dep.kind='dependency' AND dep.name = ? "
            "AND d.kind='domain' AND d.name = ? "
            "ORDER BY p.name",
            (entity_name, domain_name),
        ).fetchall()
        return tuple(r[0] for r in rows)
    if kind == "test_suite":
        rows = conn.execute(
            "SELECT DISTINCT p.name FROM edges t "
            "JOIN nodes ts ON t.src = ts.id "
            "JOIN nodes p ON t.dst = p.id "
            "JOIN edges bt ON bt.src = p.id AND bt.kind='belongs_to_domain' "
            "JOIN nodes d ON d.id = bt.dst "
            "WHERE t.kind='tests' AND ts.kind='test_suite' AND ts.name = ? "
            "AND p.kind='package' AND d.kind='domain' AND d.name = ? "
            "ORDER BY p.name",
            (entity_name, domain_name),
        ).fetchall()
        return tuple(r[0] for r in rows)
    return ()


def _consumer_pkgs(
    conn: sqlite3.Connection, *, kind: str, entity_name: str
) -> tuple[str, ...]:
    """DOMAIN-AGNOSTIC consumer/tested package (and app) names (Phase 57 D-01).

    The superset of `_consumer_pkgs_in_domain` across all domains: every
    package/app that uses this dependency (`used_by`) or is tested by this
    test_suite (`tests`), regardless of domain. `_render_by_kind` uses these
    names so a by-kind-placed (multi/zero-domain) dependency or test_suite
    still nests under every package/app that consumes it — the fix that makes
    flat-section removal safe. Sorted alphabetically for determinism."""
    if kind == "dependency":
        rows = conn.execute(
            "SELECT DISTINCT p.name FROM edges u "
            "JOIN nodes p ON u.src = p.id "
            "JOIN nodes dep ON u.dst = dep.id "
            "WHERE u.kind='used_by' AND p.kind IN ('package', 'app') "
            "AND dep.kind='dependency' AND dep.name = ? "
            "ORDER BY p.name",
            (entity_name,),
        ).fetchall()
        return tuple(r[0] for r in rows)
    if kind == "test_suite":
        rows = conn.execute(
            "SELECT DISTINCT p.name FROM edges t "
            "JOIN nodes ts ON t.src = ts.id "
            "JOIN nodes p ON t.dst = p.id "
            "WHERE t.kind='tests' AND ts.kind='test_suite' AND ts.name = ? "
            "AND p.kind IN ('package', 'app') "
            "ORDER BY p.name",
            (entity_name,),
        ).fetchall()
        return tuple(r[0] for r in rows)
    return ()


def _read_entity_summary(
    wiki_root: Path, entity: PlacedEntity, collision_set: frozenset[str]
) -> str:
    """Read the `summary:` frontmatter from the entity's own page (D-06).

    The stem is derived with the SAME `_short_filename` call `_entity_wikilink`
    makes, so the file looked up agrees with the rendered link. Tolerant like
    `_scan_curated_lane`: missing entities dir / file / frontmatter → "" (no
    crash). Reads the page file (not the graph attr) because Phase 56 makes
    `summary:` fill-when-empty / human-editable."""
    if not entity.uri:
        return ""
    stem = _short_filename(
        entity.uri,
        collision_set,
        suite_kind=entity.suite_kind,
        pkg_for_suite=entity.pkg_for_suite,
    )
    page = wiki_root / "entities" / (stem + ".md")
    if not page.exists():
        return ""
    text = page.read_text(encoding="utf-8", errors="replace")
    return _parse_frontmatter(text).get("summary", "")


def _place_entities(
    conn: sqlite3.Connection,
    wiki_root: Path,
    collision_set: frozenset[str],
) -> tuple[dict[str, list[PlacedEntity]], list[PlacedEntity], dict[str, PlacedEntity]]:
    """Walk all placeable kinds. Return (domain_buckets, by_kind, name_to_entity).

    D-04 single-placement rule:
      qualifying_count == 1 -> domain_buckets[that_domain]
      qualifying_count != 1 -> by_kind_fallback (covers 0 and >=2 cases)

    `name_to_entity` maps package/app names → their PlacedEntity so internal
    dependencies (resolved by name via `internal_dependencies_of`) can be
    turned into wikilinks to the internal package/app entity page (D-09/D-11).

    Iterates `_PLACEABLE_KINDS` (NOT `BY_KIND_ORDER`) so test_suites and
    dependencies are discovered and can nest (D-01 crux).
    """
    domain_buckets: dict[str, list[PlacedEntity]] = {}
    by_kind: list[PlacedEntity] = []
    name_to_entity: dict[str, PlacedEntity] = {}

    kind_to_list_fn = {
        "app":        list_apps,
        "package":    list_packages,
        "test_suite": list_test_suites,
        "dependency": list_dependencies,
        "plugin":     list_plugins,
    }
    for kind in _PLACEABLE_KINDS:
        list_fn = kind_to_list_fn[kind]
        for node in list_fn(conn):
            uri = node.attrs.get("uri") or ""
            qualifying = _compute_qualifying_domains(conn, kind=kind, name=node.name)
            # D-01: populate parent_pkg_names with the DOMAIN-AGNOSTIC consumer
            # set for every dep/test_suite (not only single-domain ones), so a
            # by-kind-placed dep/suite still nests under its consumer packages.
            parent_pkgs: tuple[str, ...] = ()
            if kind in ("dependency", "test_suite"):
                parent_pkgs = _consumer_pkgs(conn, kind=kind, entity_name=node.name)
            suite_kind: str | None = None
            pkg_for_suite: str | None = None
            if kind == "test_suite":
                attrs = node.attrs if isinstance(node.attrs, dict) else {}
                suite_kind = attrs.get("suite_kind") or None
                suite_path = attrs.get("path")
                if suite_path:
                    pkg_for_suite = Path(suite_path).parent.name or None
                if not pkg_for_suite:
                    pkg_for_suite = None
            entity = PlacedEntity(
                kind=kind,
                name=node.name,
                uri=uri,
                parent_pkg_names=parent_pkgs,
                suite_kind=suite_kind,
                pkg_for_suite=pkg_for_suite,
            )
            entity = dataclasses.replace(
                entity,
                summary=_read_entity_summary(wiki_root, entity, collision_set),
            )
            if kind in ("package", "app"):
                name_to_entity[entity.name] = entity
            if len(qualifying) == 1:
                the_domain = next(iter(qualifying))
                domain_buckets.setdefault(the_domain, []).append(entity)
            else:
                by_kind.append(entity)

    for d in domain_buckets:
        domain_buckets[d].sort(key=lambda e: e.uri)
    by_kind.sort(key=lambda e: (_PLACEABLE_KINDS.index(e.kind), e.uri))
    return domain_buckets, by_kind, name_to_entity


# ============================================================================
# Curated-lane / work scan (D-11, D-12, D-13)
# ============================================================================


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Port of `update_index.py::parse_frontmatter` (regex subset)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


def _infer_title(path: Path, fm: dict) -> str:
    if "title" in fm:
        return fm["title"]
    return path.stem.replace("-", " ").replace("_", " ").title()


def _entry_link(path: str, title: str) -> str:
    """Port of `update_index.py::_entry_link`.

    Wiki entries (rel paths not starting with `work/`) get a `wiki/` prefix
    so Obsidian (rooted at the workspace) resolves the link. Work entries
    arrive workspace-rooted and pass through.
    """
    stem = path[:-3] if path.endswith(".md") else path
    target = stem if stem.startswith("work/") else f"wiki/{stem}"
    return f"[[{target}|{title}]]"


def _scan_curated_lane(wiki_root: Path, lane_dir_rel: str) -> list[dict[str, str]]:
    """Walk `wiki_root / lane_dir_rel` for *.md pages; return sorted entries.

    Returns [] if the directory does not exist. Skips GENERATED_FILES,
    dotfile-prefix paths. Sort: alphabetical by title (case-insensitive).
    """
    lane_dir = wiki_root / lane_dir_rel
    if not lane_dir.exists():
        return []
    entries: list[dict[str, str]] = []
    for md in sorted(lane_dir.rglob("*.md")):
        rel = md.relative_to(wiki_root)
        rel_str = str(rel).replace("\\", "/")
        if rel_str in GENERATED_FILES or rel.name in GENERATED_FILES:
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        entries.append({
            "path": rel_str,
            "title": _infer_title(md, fm),
            "summary": fm.get("summary", ""),
        })
    entries.sort(key=lambda e: e["title"].lower())
    return entries


def _scan_work(workspace_root: Path) -> list[dict[str, str]]:
    """Walk `workspace_root / 'work'` for *.md pages; workspace-rooted paths.

    Returns [] if `work/` does not exist. Skips `index.md`, dotfiles, and
    the `archived/` sub-namespace.
    """
    work_dir = workspace_root / "work"
    if not work_dir.exists():
        return []
    entries: list[dict[str, str]] = []
    for md in sorted(work_dir.rglob("*.md")):
        rel = md.relative_to(workspace_root)
        if rel.name == "index.md":
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        if len(rel.parts) >= 2 and rel.parts[1] == "archived":
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        entries.append({
            "path": str(rel).replace("\\", "/"),
            "title": _infer_title(md, fm),
            "summary": fm.get("summary", ""),
        })
    entries.sort(key=lambda e: e["title"].lower())
    return entries


# ============================================================================
# Rendering helpers (D-03, D-05..D-09)
# ============================================================================


def _list_subdomains(conn: sqlite3.Connection, parent_name: str) -> list[str]:
    """Return child domain names for `parent_name` (via `domain_contains_domain`)."""
    rows = conn.execute(
        "SELECT child.name FROM edges e "
        "JOIN nodes parent ON e.src = parent.id "
        "JOIN nodes child ON e.dst = child.id "
        "WHERE e.kind='domain_contains_domain' "
        "AND parent.kind='domain' AND parent.name = ? "
        "AND child.kind='domain' "
        "ORDER BY child.name",
        (parent_name,),
    ).fetchall()
    return [r[0] for r in rows]


def _is_top_level_domain(conn: sqlite3.Connection, name: str) -> bool:
    """True if `name` has NO inbound `domain_contains_domain` edge."""
    row = conn.execute(
        "SELECT 1 FROM edges e "
        "JOIN nodes child ON e.dst = child.id "
        "WHERE e.kind='domain_contains_domain' "
        "AND child.kind='domain' AND child.name = ? "
        "LIMIT 1",
        (name,),
    ).fetchone()
    return row is None


def _entity_wikilink(entity: PlacedEntity, collision_set: frozenset[str]) -> str:
    """Forward-derive the piped `[[wiki/entities/<stem>|<name>]]` wikilink.

    Phase 53 D-05: uses `short_filename` from Phase 52 with the precomputed
    collision_set so the index agrees with `write_entities` on filenames
    (including the `__<6hex>` disambiguator for colliders).

    Phase 57 IDX-02/D-05: the link is PIPED with display text = `entity.name`
    (human-readable) — the bare stem is the link target, not the visible text.
    """
    stem = _short_filename(
        entity.uri,
        collision_set,
        suite_kind=entity.suite_kind,
        pkg_for_suite=entity.pkg_for_suite,
    )
    return f"[[wiki/entities/{stem}|{entity.name}]]"


def _entity_bullet(entity: PlacedEntity, collision_set: frozenset[str], indent: str) -> str:
    """Render one entity bullet `{indent}- {link} — {summary}` (D-03/D-07).

    The ` — {summary}` suffix is omitted when the entity has no summary,
    matching `_render_curated_section`'s inline shape."""
    link = _entity_wikilink(entity, collision_set)
    summary = f" — {entity.summary}" if entity.summary else ""
    return f"{indent}- {link}{summary}"


def _render_pkg_nested(
    conn: sqlite3.Connection,
    pkg: PlacedEntity,
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
    name_to_entity: dict[str, PlacedEntity],
    collision_set: frozenset[str],
) -> list[str]:
    """Render the THREE nested sub-lists under one package/app bullet (D-09).

    Shared by `_render_domain_section` and `_render_by_kind` so both contexts
    stay byte-identical (D-01 — by-kind packages now nest, making flat-section
    removal safe). Each sub-list is omitted when empty (D-08):

      1. Test Suites          — test_suites that test this package (`tests`)
      2. Dependencies         — external deps this package uses (`used_by`)
      3. Internal dependencies — workspace packages/apps this one depends on
                                 (the internal-dependency edge, resolved via
                                 graph-io's `internal_dependencies_of` — D-11
                                 reuse, NOT parallel SQL); links to the internal
                                 entity page, kept SEPARATE from external deps.
    """
    lines: list[str] = []
    sub = sub_for_pkg.get(pkg.name, {})
    suites = sub.get("test_suite", [])
    deps = sub.get("dependency", [])
    if suites:
        lines.append("  - Test Suites")
        for ts in sorted(suites, key=lambda x: x.uri):
            lines.append(_entity_bullet(ts, collision_set, "    "))
    if deps:
        lines.append("  - Dependencies")
        for d in sorted(deps, key=lambda x: x.uri):
            lines.append(_entity_bullet(d, collision_set, "    "))
    # Internal dependencies (D-09/D-11): resolve names → internal package/app
    # entities; skip any name with no matching placed entity (defensive).
    internal_names = internal_dependencies_of(conn, name=pkg.name)
    internal_entities = [
        name_to_entity[n] for n in internal_names if n in name_to_entity
    ]
    if internal_entities:
        lines.append("  - Internal dependencies")
        for ie in sorted(internal_entities, key=lambda x: x.name):
            lines.append(_entity_bullet(ie, collision_set, "    "))
    return lines


def _build_sub_for_pkg(
    entities: list[PlacedEntity],
) -> dict[str, dict[str, list[PlacedEntity]]]:
    """Group dependencies/test_suites under each consumer/tested package name
    via their (domain-agnostic) `parent_pkg_names` (Phase 57 D-01/D-10).

    Built ONCE over ALL placed entities (domain buckets + by_kind) in `_render`
    and shared by `_render_domain_section` and `_render_by_kind`, so a by-kind
    dep/suite still nests under a package that renders in a domain section, and
    vice-versa — duplication across packages is expected (D-10)."""
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]] = {}
    for e in entities:
        if e.kind not in ("test_suite", "dependency"):
            continue
        for parent in e.parent_pkg_names:
            sub_for_pkg.setdefault(parent, {"test_suite": [], "dependency": []})
            sub_for_pkg[parent][e.kind].append(e)
    return sub_for_pkg


def _render_domain_section(
    conn: sqlite3.Connection,
    domain_buckets: dict[str, list[PlacedEntity]],
    *,
    domain_name: str,
    depth: int,
    collision_set: frozenset[str],
    name_to_entity: dict[str, PlacedEntity],
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
) -> list[str]:
    """Recursively render one domain section.

    `depth == 0` -> top-level `## Domain: X`; deeper -> `### Sub-Domain: X`.
    Returns [] (D-08 fully-empty omission) if the section has zero placed
    entities AND every sub-domain is also empty.
    """
    heading_prefix = "##" if depth == 0 else ("##" + "#" * depth)
    label = f"Domain: {domain_name}" if depth == 0 else f"Sub-Domain: {domain_name}"

    entities = domain_buckets.get(domain_name, [])
    # Apps render identically to packages within a domain (Phase 57 D-02/D-04).
    packages = [e for e in entities if e.kind in ("package", "app")]

    lines_pkg: list[str] = []
    for pkg in packages:
        lines_pkg.append(_entity_bullet(pkg, collision_set, ""))
        lines_pkg.extend(
            _render_pkg_nested(conn, pkg, sub_for_pkg, name_to_entity, collision_set)
        )

    # Sub-domain recursion (D-07)
    sub_domain_blocks: list[str] = []
    for sub_name in _list_subdomains(conn, domain_name):
        sub_lines = _render_domain_section(
            conn, domain_buckets, domain_name=sub_name, depth=depth + 1,
            collision_set=collision_set, name_to_entity=name_to_entity,
            sub_for_pkg=sub_for_pkg,
        )
        if sub_lines:
            sub_domain_blocks.extend(sub_lines)

    if not lines_pkg and not sub_domain_blocks:
        return []  # D-08 fully-empty omission

    block: list[str] = [f"{heading_prefix} {label}", ""]
    block.extend(lines_pkg)
    if lines_pkg and sub_domain_blocks:
        block.append("")
    block.extend(sub_domain_blocks)
    block.append("")
    return block


def _render_domains(
    conn: sqlite3.Connection,
    domain_buckets: dict[str, list[PlacedEntity]],
    wiki_root: Path,
    collision_set: frozenset[str],
    name_to_entity: dict[str, PlacedEntity],
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
) -> tuple[list[str], int]:
    """Render the full `## Domains` block. Returns (lines, domain_count)."""
    all_domains = sorted(
        {n.name for n in list_domains(conn)} | set(domain_buckets.keys())
    )
    top_level_domains = [d for d in all_domains if _is_top_level_domain(conn, d)]
    lines: list[str] = []
    rendered_count = 0
    for d in top_level_domains:
        section = _render_domain_section(
            conn, domain_buckets, domain_name=d, depth=0,
            collision_set=collision_set, name_to_entity=name_to_entity,
            sub_for_pkg=sub_for_pkg,
        )
        if section:
            lines.extend(section)
            rendered_count += 1
    if not lines:
        return [], 0
    repo_row = conn.execute(
        "SELECT name FROM nodes WHERE kind='repository' ORDER BY name LIMIT 1"
    ).fetchone()
    repo_label = f" — {repo_row[0]}" if repo_row else ""
    header = [f"## Domains{repo_label}", ""]
    return header + lines, rendered_count


def _render_by_kind(
    conn: sqlite3.Connection,
    by_kind_entities: list[PlacedEntity],
    collision_set: frozenset[str],
    name_to_entity: dict[str, PlacedEntity],
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
) -> tuple[list[str], int]:
    """Render the full `## By Kind` block. Returns (lines, by_kind_count).

    Phase 57 D-01/D-08: flat groups are ONLY app/package/plugin (apps first).
    test_suites and dependencies are no longer flat groups — they nest under
    the package/app that uses them via `_render_pkg_nested`, exactly like the
    domain sections. This is the cross-cutting fix: a multi/zero-domain
    package placed here still shows its Test Suites / Dependencies / Internal
    dependencies, so removing the flat sections never loses them. `sub_for_pkg`
    is the SAME global grouping the domain sections use (built in `_render`).
    """
    if not by_kind_entities:
        return [], 0

    lines: list[str] = ["## By Kind", ""]
    total = 0
    for kind in BY_KIND_ORDER:
        group = sorted(
            (e for e in by_kind_entities if e.kind == kind),
            key=lambda x: x.uri,
        )
        if not group:
            continue
        lines.append(f"### {KIND_LABELS[kind]}")
        lines.append("")
        for e in group:
            lines.append(_entity_bullet(e, collision_set, ""))
            total += 1
            if e.kind in ("package", "app"):
                lines.extend(
                    _render_pkg_nested(
                        conn, e, sub_for_pkg, name_to_entity, collision_set
                    )
                )
        lines.append("")
    if total == 0:
        return [], 0
    return lines, total


def _render_curated_section(label: str, entries: list[dict]) -> list[str]:
    """Render one curated lane (D-08 omission of empty sections)."""
    if not entries:
        return []
    lines = [f"## {label}", ""]
    for e in entries:
        link = _entry_link(e["path"], e["title"])
        summary = f" — {e['summary']}" if e.get("summary") else ""
        lines.append(f"- {link}{summary}")
    lines.append("")
    return lines


# ============================================================================
# Orchestrators (D-03, D-16, D-19)
# ============================================================================


def _render(
    conn: sqlite3.Connection, wiki_root: Path
) -> tuple[str, int, int, int, int]:
    """Render the full index.

    Returns (text, entity_count, curated_count, domain_count, by_kind_count).
    """
    # Phase 53 D-05: one-shot collision pre-pass, threaded through every
    # entity-link derivation so the index agrees with `write_entities`.
    collision_set = _compute_collision_set(conn, _ADMITTED_KINDS, _kind_list_fns())

    domain_buckets, by_kind, name_to_entity = _place_entities(
        conn, wiki_root, collision_set
    )
    entity_count = sum(len(v) for v in domain_buckets.values()) + len(by_kind)

    # D-01/D-10: one global dep/suite-under-package grouping over ALL placed
    # entities, so a by-kind dep/suite nests under a package that renders in a
    # domain section (and vice-versa). Shared by both render contexts.
    all_placed = [e for v in domain_buckets.values() for e in v] + by_kind
    sub_for_pkg = _build_sub_for_pkg(all_placed)

    workspace_root = wiki_root.parent

    curated_entries_by_lane: dict[str, list[dict]] = {}
    for stable_id, lane_dir, _label in CURATED_LANES:
        curated_entries_by_lane[stable_id] = _scan_curated_lane(wiki_root, lane_dir)
    work_entries = _scan_work(workspace_root)
    curated_count = (
        sum(len(v) for v in curated_entries_by_lane.values()) + len(work_entries)
    )

    today = datetime.date.today().isoformat()
    lines: list[str] = [
        f"# Index — {wiki_root.name}",
        "",
        f"_Auto-generated {today} • {entity_count} entities • "
        f"{curated_count} curated pages_",
        "",
    ]

    domains_lines, domain_count = _render_domains(
        conn, domain_buckets, wiki_root, collision_set, name_to_entity,
        sub_for_pkg,
    )
    lines.extend(domains_lines)

    by_kind_lines, by_kind_count = _render_by_kind(
        conn, by_kind, collision_set, name_to_entity, sub_for_pkg,
    )
    lines.extend(by_kind_lines)

    for stable_id, _lane_dir, section_label in CURATED_LANES:
        lines.extend(
            _render_curated_section(
                section_label, curated_entries_by_lane[stable_id]
            )
        )
    lines.extend(_render_curated_section("Work", work_entries))

    text = "\n".join(lines).rstrip("\n") + "\n"  # POSIX trailing newline
    return text, entity_count, curated_count, domain_count, by_kind_count


def generate_index(
    conn: sqlite3.Connection, wiki_root: Path
) -> IndexWriteResult:
    """Render `wiki/index.md` and write-if-changed. Atomic on POSIX.

    D-16: byte-compare against the existing file; only `os.replace` when
    bytes differ. D-19: all-or-nothing — exceptions in render/place
    propagate out untouched.
    """
    text, entity_count, curated_count, domain_count, by_kind_count = _render(
        conn, wiki_root
    )
    path = wiki_root / "index.md"
    new_bytes = text.encode("utf-8")
    existing_bytes: bytes | None
    if path.exists():
        existing_bytes = path.read_bytes()
    else:
        existing_bytes = None
    if existing_bytes == new_bytes:
        return IndexWriteResult(
            path=path,
            bytes_written=0,
            changed=False,
            entity_count=entity_count,
            curated_count=curated_count,
            domain_count=domain_count,
            by_kind_count=by_kind_count,
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(new_bytes)
    os.replace(tmp, path)
    return IndexWriteResult(
        path=path,
        bytes_written=len(new_bytes),
        changed=True,
        entity_count=entity_count,
        curated_count=curated_count,
        domain_count=domain_count,
        by_kind_count=by_kind_count,
    )


# Re-export for tests that want to assert frozen-ness via dataclasses.FrozenInstanceError
__all__ = [
    "BY_KIND_ORDER",
    "CURATED_LANES",
    "GENERATED_FILES",
    "IndexWriteResult",
    "KIND_LABELS",
    "PlacedEntity",
    "_PLACEABLE_KINDS",
    "_build_sub_for_pkg",
    "_compute_qualifying_domains",
    "_consumer_pkgs",
    "_consumer_pkgs_in_domain",
    "_entity_bullet",
    "_entry_link",
    "_infer_title",
    "_parse_frontmatter",
    "_place_entities",
    "_read_entity_summary",
    "_render",
    "_render_by_kind",
    "_render_curated_section",
    "_render_domain_section",
    "_render_domains",
    "_render_pkg_nested",
    "_scan_curated_lane",
    "_scan_work",
    "generate_index",
    "dataclasses",  # exported so tests can do `from wiki_io.index_generator import dataclasses`
]
