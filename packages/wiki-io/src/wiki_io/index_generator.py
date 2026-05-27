"""Generate `wiki/index.md` from a graph + curated-lane filesystem scan.

Phase 44 — Scanner-Generated Index. New module (D-01); `update_index.py`
remains untouched in this phase (Phase 46 cutover deletes it).

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
    list_dependencies,
    list_domains,
    list_packages,
    list_plugins,
    list_test_suites,
)

from wiki_io.entity_writer import encode_slug

# ============================================================================
# Module constants (D-09, D-12)
# ============================================================================

BY_KIND_ORDER: tuple[str, ...] = ("package", "test_suite", "dependency", "plugin")

KIND_LABELS: dict[str, str] = {
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
    """

    kind: str
    name: str
    uri: str
    parent_pkg_names: tuple[str, ...] = ()


# ============================================================================
# Graph-read helpers (D-04)
# ============================================================================


def _compute_qualifying_domains(
    conn: sqlite3.Connection, *, kind: str, name: str
) -> set[str]:
    """Return the set of domain names that qualify for this entity (D-04).

    - package:    direct `belongs_to_domain` edges.
    - test_suite: one-hop transitive via `tests -> package -> belongs_to_domain`.
    - dependency: one-hop transitive via `used_by` -> `package` -> `belongs_to_domain`.
                  Edge direction: package -[used_by]-> dependency.
    - plugin:     always empty (D-04 — plugins have no domain edges in v1.8).
    """
    if kind == "package":
        rows = conn.execute(
            "SELECT d.name FROM edges e "
            "JOIN nodes p ON e.src = p.id "
            "JOIN nodes d ON e.dst = d.id "
            "WHERE e.kind='belongs_to_domain' "
            "AND p.kind='package' AND p.name = ? "
            "AND d.kind='domain' "
            "ORDER BY d.name",
            (name,),
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
        f"Only package/test_suite/dependency/plugin are placeable; got {kind!r}"
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


def _place_entities(
    conn: sqlite3.Connection,
) -> tuple[dict[str, list[PlacedEntity]], list[PlacedEntity]]:
    """Walk all admitted kinds. Return (domain_buckets, by_kind_fallback).

    D-04 single-placement rule:
      qualifying_count == 1 -> domain_buckets[that_domain]
      qualifying_count != 1 -> by_kind_fallback (covers 0 and >=2 cases)
    """
    domain_buckets: dict[str, list[PlacedEntity]] = {}
    by_kind: list[PlacedEntity] = []

    kind_to_list_fn = {
        "package":    list_packages,
        "test_suite": list_test_suites,
        "dependency": list_dependencies,
        "plugin":     list_plugins,
    }
    for kind in BY_KIND_ORDER:
        list_fn = kind_to_list_fn[kind]
        for node in list_fn(conn):
            uri = node.attrs.get("uri") or ""
            qualifying = _compute_qualifying_domains(conn, kind=kind, name=node.name)
            parent_pkgs: tuple[str, ...] = ()
            if len(qualifying) == 1 and kind in ("dependency", "test_suite"):
                the_domain = next(iter(qualifying))
                parent_pkgs = _consumer_pkgs_in_domain(
                    conn, kind=kind, entity_name=node.name, domain_name=the_domain
                )
            entity = PlacedEntity(
                kind=kind, name=node.name, uri=uri, parent_pkg_names=parent_pkgs
            )
            if len(qualifying) == 1:
                the_domain = next(iter(qualifying))
                domain_buckets.setdefault(the_domain, []).append(entity)
            else:
                by_kind.append(entity)

    for d in domain_buckets:
        domain_buckets[d].sort(key=lambda e: e.uri)
    by_kind.sort(key=lambda e: (BY_KIND_ORDER.index(e.kind), e.uri))
    return domain_buckets, by_kind


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


def _render_domain_section(
    conn: sqlite3.Connection,
    domain_buckets: dict[str, list[PlacedEntity]],
    *,
    domain_name: str,
    depth: int,
) -> list[str]:
    """Recursively render one domain section.

    `depth == 0` -> top-level `## Domain: X`; deeper -> `### Sub-Domain: X`.
    Returns [] (D-08 fully-empty omission) if the section has zero placed
    entities AND every sub-domain is also empty.
    """
    heading_prefix = "##" if depth == 0 else ("##" + "#" * depth)
    label = f"Domain: {domain_name}" if depth == 0 else f"Sub-Domain: {domain_name}"

    entities = domain_buckets.get(domain_name, [])
    packages = [e for e in entities if e.kind == "package"]
    deps_and_suites = [e for e in entities if e.kind in ("test_suite", "dependency")]

    # Group deps and suites by their parent_pkg_names (D-06)
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]] = {}
    for e in deps_and_suites:
        for parent in e.parent_pkg_names:
            sub_for_pkg.setdefault(parent, {"test_suite": [], "dependency": []})
            sub_for_pkg[parent][e.kind].append(e)

    lines_pkg: list[str] = []
    for pkg in packages:
        pkg_link = f"[[wiki/entities/{encode_slug(pkg.uri)}]]"
        lines_pkg.append(f"- {pkg_link}")
        sub = sub_for_pkg.get(pkg.name, {})
        suites = sub.get("test_suite", [])
        deps = sub.get("dependency", [])
        if suites:
            lines_pkg.append("  - Test Suites")
            for ts in sorted(suites, key=lambda x: x.uri):
                ts_link = f"[[wiki/entities/{encode_slug(ts.uri)}]]"
                lines_pkg.append(f"    - {ts_link}")
        if deps:
            lines_pkg.append("  - Dependencies")
            for d in sorted(deps, key=lambda x: x.uri):
                d_link = f"[[wiki/entities/{encode_slug(d.uri)}]]"
                lines_pkg.append(f"    - {d_link}")

    # Sub-domain recursion (D-07)
    sub_domain_blocks: list[str] = []
    for sub_name in _list_subdomains(conn, domain_name):
        sub_lines = _render_domain_section(
            conn, domain_buckets, domain_name=sub_name, depth=depth + 1
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
            conn, domain_buckets, domain_name=d, depth=0
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


def _render_by_kind(by_kind_entities: list[PlacedEntity]) -> tuple[list[str], int]:
    """Render the full `## By Kind` block. Returns (lines, by_kind_count)."""
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
            link = f"[[wiki/entities/{encode_slug(e.uri)}]]"
            lines.append(f"- {link}")
            total += 1
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
    domain_buckets, by_kind = _place_entities(conn)
    entity_count = sum(len(v) for v in domain_buckets.values()) + len(by_kind)

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

    domains_lines, domain_count = _render_domains(conn, domain_buckets, wiki_root)
    lines.extend(domains_lines)

    by_kind_lines, by_kind_count = _render_by_kind(by_kind)
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
    "_compute_qualifying_domains",
    "_consumer_pkgs_in_domain",
    "_entry_link",
    "_infer_title",
    "_parse_frontmatter",
    "_place_entities",
    "_render",
    "_render_by_kind",
    "_render_curated_section",
    "_render_domain_section",
    "_render_domains",
    "_scan_curated_lane",
    "_scan_work",
    "generate_index",
    "dataclasses",  # exported so tests can do `from wiki_io.index_generator import dataclasses`
]
