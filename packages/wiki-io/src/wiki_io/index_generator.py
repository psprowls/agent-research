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
- D-03 (amended 2026-06-12 — repository grouping; further amended when
  domain bucketing was removed): rendered section order is H1 → banner →
  one `## Repository: <name>` section per repository node (entities as
  kind-prefixed headings, directly under the repository heading; replaces
  the old `## Domains` → `## By Kind` slot) → `## ADRs` → `## Concepts` →
  `## Sources` → `## Work`.
- D-04 (historical; domain bucketing removed): every placeable entity now
  renders directly under its repository header — there is no longer a
  single-vs-multi-qualifying-domain distinction to make.
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
from dataclasses import dataclass
from pathlib import Path

from workspace_io.paths import wiki_dir, work_dir

from wiki_io._graph_protocol import GraphReaderLike
from wiki_io.concept_kinds import DEFAULT_CONCEPT_KIND, KIND_GROUP_LABELS, KIND_GROUP_ORDER, kind_group
from wiki_io.entity_writer import (
    ADMITTED_KINDS as _ADMITTED_KINDS,
)
from wiki_io.entity_writer import (
    _compute_collision_set,
    _kind_list_fns,
)
from wiki_io.entity_writer import (
    short_filename as _short_filename,
)
from wiki_io.frontmatter import parse as _parse_page_frontmatter
from wiki_io.md_escape import escape_angle_brackets
from wiki_io.wikilinks import vault_wikilink

# ============================================================================
# Module constants (D-09, D-12)
# ============================================================================

# Phase 57 D-01 (the crux): placement kinds are DECOUPLED from render order.
# `_PLACEABLE_KINDS` drives `_place_entities` iteration AND the direct-list sort
# key; it MUST include test_suite/dependency or those entities would never be
# discovered/placed and could not nest under their packages (breaking IDX-04/05).
# `BY_KIND_ORDER` (D-03/D-08, kept as the D-R6 kind-major order) drives the
# kind-major heading order for entities (via `_kind_major`) directly under a
# repository heading — apps first, then packages, then plugins.
# test_suites/dependencies are never headings; they appear exclusively nested
# under the package/app that uses them (per D-01), which is what makes dropping
# them from the heading order safe — every package/app nests its own items.
_PLACEABLE_KINDS: tuple[str, ...] = (
    "app",
    "package",
    "test_suite",
    "dependency",
    "agent_plugin",
)

BY_KIND_ORDER: tuple[str, ...] = ("app", "package", "agent_plugin")

# D-R5: singular kind labels for entity headings. Only heading kinds appear —
# test_suite/dependency render exclusively as nested sub-list bullets.
KIND_HEADING_LABELS: dict[str, str] = {
    "app": "App",
    "package": "Package",
    "agent_plugin": "Agent Plugin",
}

# (stable_id, lane_dir_relative_to_wiki_root, section_label)
# Note: CONTEXT.md D-12's example showed `"wiki/architecture"`, but `wiki_root`
# IS the wiki directory, so the lane_dir is the BARE lane name to avoid
# double-prefixing. 3 lanes (architecture folded into concepts via `kind:`
# frontmatter — pages with `kind: architecture` render under a sub-group).
CURATED_LANES: tuple[tuple[str, str, str], ...] = (
    ("adrs", "adrs", "ADRs"),
    ("concepts", "concepts", "Concepts"),
    ("sources", "sources", "Sources"),
)

GENERATED_FILES: frozenset[str] = frozenset(
    {
        "index.md",
        "log.md",
        "concepts/index.md",
        "adrs/index.md",
        "sources/index.md",
        # Documentation value: guidance/<topic>/index.md paths are dynamic and
        # rely on the rel.name check in _scan_curated_lane / scan_vault.
        "guidance/index.md",
    }
)

# 2026-06-12 repository grouping D-R7: schemes that are ecosystem-scoped
# rather than repo-scoped — they never carry an {org}/{repo} segment.
_REPO_LESS_SCHEMES: frozenset[str] = frozenset({"dependency", "builtin"})


def _parse_repo_key(uri: str) -> str | None:
    """Extract the '{org}/{repo}' segment from a graph URI (D-R7).

    URI shapes locked since Phase 28 (the graph's URI scheme):

      repo:{org}/{repo}                            -> exactly 2 segments
      pkg: app: agent_plugin: domain: test_suite:           -> {org}/{repo}/{...}, >= 3 segments
      dependency:{ecosystem}/{name}, builtin:{lang}/{module} -> repo-less

    Returns None for repo-less schemes and malformed URIs (no scheme,
    too few segments). Unknown repo-scoped schemes with >= 3 segments
    are treated as repo-scoped.
    """
    scheme, sep, rest = uri.partition(":")
    if not sep or not scheme or not rest:
        return None
    if scheme in _REPO_LESS_SCHEMES:
        return None
    parts = [p for p in rest.split("/") if p]
    if scheme == "repo":
        return "/".join(parts) if len(parts) == 2 else None
    if len(parts) >= 3:
        return f"{parts[0]}/{parts[1]}"
    return None


# ============================================================================
# Public dataclasses
# ============================================================================


@dataclass(frozen=True)
class IndexWriteResult:
    """Return value of `generate_index` (D-18; fields per 2026-06-12 D-R8).

    `direct_count` = heading entities rendered directly under a repo header
    (the old `by_kind_count` slot); `repo_count` = rendered `## Repository:`
    sections.
    """

    path: Path
    bytes_written: int
    changed: bool
    entity_count: int
    curated_count: int
    direct_count: int
    repo_count: int


@dataclass(frozen=True)
class PlacedEntity:
    """An entity placed directly under its repository section.

    `parent_pkg_names` is populated for dependencies/test_suites so
    `_render_pkg_nested` can nest them under consumer/tested-package
    bullets (D-06).

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


def _consumer_pkgs(
    reader: GraphReaderLike,
    *,
    kind: str,
    entity_uri: str = "",
    entity_name: str = "",
) -> tuple[str, ...]:
    """Consumer/tested package (and app) names (Phase 57 D-01).

    Every package/app that uses this dependency (`used_by`) or is tested by
    this test_suite (`tests`). Used by `_render_repository_section` so a
    placed dependency or test_suite still nests under every package/app
    that consumes it. Sorted alphabetically for determinism.

    Thin wrapper over `reader.consumer_packages` (SQL ported verbatim).
    For test_suite: resolved by `ts.uri` (unique, stable) not `ts.name` (D-08).
    For dependency: resolved by `dep.name` (dependencies are name-unique)."""
    return reader.consumer_packages(kind=kind, entity_uri=entity_uri, entity_name=entity_name)


def _read_entity_summary(wiki_root: Path, entity: PlacedEntity, collision_set: frozenset[str]) -> str:
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
    return str(_parse_frontmatter(text).get("summary") or "")


def _place_entities(
    reader: GraphReaderLike,
    wiki_root: Path,
    collision_set: frozenset[str],
) -> tuple[
    dict[str, list[PlacedEntity]],  # per_repo
    dict[str, PlacedEntity],  # name_to_entity
]:
    """Walk all placeable kinds. Return (per_repo, name_to_entity).

    2026-06-12 repository grouping (D-R1/D-R7), domain bucketing removed:
      per_repo[repo_node_name] = direct_entities

    Every entity renders directly under its own repository section
    (D-R7) — there is no longer a domain tier to route through.

    Repo resolution: parse `{org}/{repo}` from the URI (`_parse_repo_key`)
    and match a repository node's own `repo:` URI. Unresolvable URIs
    (repo-less schemes, malformed, or no matching repository node) fall
    into the single repository when exactly ONE repository node exists
    (defensive — matches the single-repo reality); with zero or multiple
    repository nodes they raise ValueError (all-or-nothing D-19, no silent
    drops).

    `name_to_entity` keeps its global meaning (D-09/D-11).

    Iterates `_PLACEABLE_KINDS` (NOT the heading-kind order) so test_suites
    and dependencies are discovered and can nest (D-01 crux).
    """
    repos = reader.list_repositories()
    repo_key_to_name: dict[str, str] = {}
    for r in repos:
        key = _parse_repo_key(r.attrs.get("uri") or "")
        if key:
            repo_key_to_name[key] = r.name

    def _repo_for_or_none(uri: str, *, repo: str = "") -> str | None:
        # Non-raising core resolver: the entity's own URI carries the
        # {org}/{repo} segment. Secondary: the authoritative `nodes.repo`
        # column (every admitted node carries one post-Task-2), which resolves
        # stray nodes whose URI is repo-less or empty. Single-repo fallback
        # last. Returns None when none of those resolve (the caller decides
        # whether that's fatal or has a fallback — e.g. global dependencies
        # route to their consumer repos instead).
        key = _parse_repo_key(uri)
        if key and key in repo_key_to_name:
            return repo_key_to_name[key]
        repo_key = _parse_repo_key(repo)
        if repo_key and repo_key in repo_key_to_name:
            return repo_key_to_name[repo_key]
        if len(repos) == 1:
            return repos[0].name
        return None

    def _repo_for(uri: str, *, kind: str, name: str, repo: str = "") -> str:
        resolved = _repo_for_or_none(uri, repo=repo)
        if resolved is not None:
            return resolved
        raise ValueError(
            f"cannot resolve repository for {kind} {name!r} "
            f"(uri={uri!r}, repo={repo!r}): "
            f"{len(repos)} repository nodes and no URI/repo-column match"
        )

    per_repo: dict[str, list[PlacedEntity]] = {}
    name_to_entity: dict[str, PlacedEntity] = {}

    def _direct_for(repo_name: str) -> list[PlacedEntity]:
        return per_repo.setdefault(repo_name, [])

    kind_to_list_fn = {
        "app": reader.list_apps,
        "package": reader.list_packages,
        "test_suite": reader.list_test_suites,
        "dependency": reader.list_dependencies,
        "agent_plugin": reader.list_agent_plugins,
    }
    for kind in _PLACEABLE_KINDS:
        list_fn = kind_to_list_fn[kind]
        for node in list_fn():
            uri = node.attrs.get("uri") or ""
            # D-01: populate parent_pkg_names with the DOMAIN-AGNOSTIC consumer
            # set for every dep/test_suite, so a placed dep/suite nests under
            # its consumer packages. For test_suite: pass entity_uri (unique,
            # stable); for dependency: pass entity_name (D-08).
            parent_pkgs: tuple[str, ...] = ()
            if kind == "test_suite":
                parent_pkgs = _consumer_pkgs(reader, kind=kind, entity_uri=uri)
            elif kind == "dependency":
                parent_pkgs = _consumer_pkgs(reader, kind=kind, entity_name=node.name)
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
            node_repo = node.attrs.get("repo") or ""
            resolved = _repo_for_or_none(uri, repo=node_repo)
            if resolved is not None:
                _direct_for(resolved).append(entity)
            elif kind == "dependency":
                # Global dependency (the StickerGiant case): an external dep
                # is ONE ecosystem-global graph node (repo=NULL, repo-less
                # URI) shared across repos. It has no repo of its own; its
                # natural home is the repository(ies) of the package(s) that
                # CONSUME it (D-01 nesting model). Place a copy into each
                # distinct consumer repo's direct list so it nests under its
                # consumer in every consuming repo section. An unconsumed
                # global dep (no consumer_repos) is skipped — it has no
                # natural home and would never render (deps only render
                # nested under consumers).
                consumer_repos: set[str] = set()
                for pkg_name in parent_pkgs:
                    pkg_entity = name_to_entity.get(pkg_name)
                    if pkg_entity is None:
                        continue
                    pkg_repo = _repo_for_or_none(pkg_entity.uri)
                    if pkg_repo is not None:
                        consumer_repos.add(pkg_repo)
                for repo_name in consumer_repos:
                    _direct_for(repo_name).append(entity)
            else:
                # Genuinely unplaceable NON-dependency entity — preserve the
                # strict all-or-nothing raise (D-19; no silent drops).
                _repo_for(uri, kind=kind, name=node.name, repo=node_repo)

    for entities in per_repo.values():
        entities.sort(key=lambda e: (_PLACEABLE_KINDS.index(e.kind), e.uri))
    return per_repo, name_to_entity


# ============================================================================
# Curated-lane / work scan (D-11, D-12, D-13)
# ============================================================================


def _parse_frontmatter(text: str) -> dict:
    """Dict-only shim over wiki_io.frontmatter.parse (fail-soft; error dropped)."""
    fm, _err = _parse_page_frontmatter(text)
    return fm


def _infer_title(path: Path, fm: dict) -> str:
    if "title" in fm:
        return str(fm["title"])
    return path.stem.replace("-", " ").replace("_", " ").title()


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
        entries.append(
            {
                "path": rel_str,
                "title": _infer_title(md, fm),
                "summary": str(fm.get("summary") or ""),
                "kind": str(fm.get("kind") or ""),
            }
        )
    entries.sort(key=lambda e: str(e["title"]).lower())
    return entries


def _scan_work(workspace_root: Path) -> list[dict[str, str]]:
    """Walk `workspace_root / 'wiki' / 'work'` for *.md pages; wiki-rooted paths.

    Returns [] if `work/` does not exist. Skips `index.md`, dotfiles, and
    the `_archive/` sub-namespace. Non-recursive: only top-level `work/<slug>.md`
    pages are work items — `work/<slug>/<file>.md` is a per-item working dir
    (design-spec/plan/results artifacts), not a page in its own right.
    """
    work_root = work_dir(workspace_root)
    if not work_root.exists():
        return []
    wiki = wiki_dir(workspace_root)
    entries: list[dict[str, str]] = []
    for md in sorted(work_root.glob("*.md")):
        rel = md.relative_to(wiki)
        if rel.name == "index.md":
            continue
        if any(part.startswith(".") for part in rel.parts):
            continue
        if len(rel.parts) >= 2 and rel.parts[1] == "_archive":
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(text)
        entries.append(
            {
                "path": str(rel).replace("\\", "/"),
                "title": _infer_title(md, fm),
                "summary": str(fm.get("summary") or ""),
            }
        )
    entries.sort(key=lambda e: str(e["title"]).lower())
    return entries


def _scan_guidance_topics(wiki_root: Path) -> list[tuple[str, int]]:
    """Topic dirs under wiki/guidance/ with their content-page counts.

    Filesystem scan, no graph involvement (like the curated lanes). Skips
    dot-dirs, generated index.md files, and topics with zero content pages.
    Sorted alphabetically by topic slug.
    """
    guidance = wiki_root / "guidance"
    if not guidance.is_dir():
        return []
    topics: list[tuple[str, int]] = []
    for topic_dir in sorted(guidance.iterdir()):
        if not topic_dir.is_dir() or topic_dir.name.startswith("."):
            continue
        count = sum(1 for md in topic_dir.glob("*.md") if md.name != "index.md")
        if count:
            topics.append((topic_dir.name, count))
    return topics


# ============================================================================
# Rendering helpers (D-03, D-05..D-09)
# ============================================================================


def _entity_wikilink(entity: PlacedEntity, collision_set: frozenset[str], label: str | None = None) -> str:
    """Forward-derive the piped `[[entities/<stem>|<text>]]` wikilink.

    Phase 53 D-05: uses `short_filename` from Phase 52 with the precomputed
    collision_set so the index agrees with `write_entities` on filenames
    (including the `__<6hex>` disambiguator for colliders).

    Phase 57 IDX-02/D-05: the link is PIPED with display text = `entity.name`
    (human-readable) — the bare stem is the link target, not the visible text.
    `label` overrides the display text (e.g. "open page") when the entity name
    already lives in a `####` header above the link (Item 2 / By-Kind).
    """
    stem = _short_filename(
        entity.uri,
        collision_set,
        suite_kind=entity.suite_kind,
        pkg_for_suite=entity.pkg_for_suite,
    )
    text = label if label is not None else entity.name
    return vault_wikilink(f"entities/{stem}", text)


def _entity_bullet(entity: PlacedEntity, collision_set: frozenset[str], indent: str) -> str:
    """Render one entity bullet `{indent}- {link} — {summary}` (D-03/D-07).

    The ` — {summary}` suffix is omitted when the entity has no summary,
    matching `_render_curated_section`'s inline shape."""
    link = _entity_wikilink(entity, collision_set)
    summary = f" — {escape_angle_brackets(entity.summary)}" if entity.summary else ""
    return f"{indent}- {link}{summary}"


def _render_pkg_nested(
    reader: GraphReaderLike,
    pkg: PlacedEntity,
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
    name_to_entity: dict[str, PlacedEntity],
    collision_set: frozenset[str],
) -> list[str]:
    """Render the THREE nested sub-lists under one package/app entity heading (D-09).

    Used by `_render_repository_section`. Each sub-list is omitted when empty (D-08):

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
    internal_names = reader.internal_dependencies_of(name=pkg.name)
    internal_entities = [name_to_entity[n] for n in internal_names if n in name_to_entity]
    if internal_entities:
        lines.append("  - Internal dependencies")
        for ie in sorted(internal_entities, key=lambda x: x.name):
            lines.append(_entity_bullet(ie, collision_set, "    "))
    return lines


def _build_sub_for_pkg(
    entities: list[PlacedEntity],
) -> dict[str, dict[str, list[PlacedEntity]]]:
    """Group dependencies/test_suites under each consumer/tested package name
    via their `parent_pkg_names` (Phase 57 D-01/D-10).

    Built ONCE over ALL placed entities in `_render` and shared across all
    repository sections, so a dep/suite nests under every consumer package
    regardless of which repository section that package renders in —
    duplication across packages is expected (D-10)."""
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]] = {}
    for e in entities:
        if e.kind not in ("test_suite", "dependency"):
            continue
        for parent in e.parent_pkg_names:
            sub_for_pkg.setdefault(parent, {"test_suite": [], "dependency": []})
            sub_for_pkg[parent][e.kind].append(e)
    return sub_for_pkg


def _kind_major(entities: list[PlacedEntity]) -> list[PlacedEntity]:
    """Heading entities in kind-major order (D-R6): apps, then packages, then
    agent plugins (`BY_KIND_ORDER`), alphabetical by URI within each kind.
    Non-heading kinds (test_suite/dependency — they only nest) are dropped."""
    return sorted(
        (e for e in entities if e.kind in BY_KIND_ORDER),
        key=lambda e: (BY_KIND_ORDER.index(e.kind), e.uri),
    )


def _render_entity_heading(
    reader: GraphReaderLike,
    entity: PlacedEntity,
    *,
    level: int,
    collision_set: frozenset[str],
    name_to_entity: dict[str, PlacedEntity],
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
) -> list[str]:
    """Render one entity as a kind-prefixed heading block (D-R4/D-R5).

    `level` is the markdown heading depth: always 3, directly under the
    repository heading (domain bucketing removed). Body is the
    `{summary} — [[entities/<stem>|open page]]` line plus the
    `_render_pkg_nested` sub-lists (packages/apps only — unchanged shape).
    """
    label = KIND_HEADING_LABELS[entity.kind]
    lines = [f"{'#' * level} {label}: {entity.name}", ""]
    link = _entity_wikilink(entity, collision_set, label="open page")
    summary = f"{escape_angle_brackets(entity.summary)} — " if entity.summary else ""
    lines.append(f"{summary}{link}")
    if entity.kind in ("package", "app"):
        lines.extend(_render_pkg_nested(reader, entity, sub_for_pkg, name_to_entity, collision_set))
    lines.append("")
    return lines


def _render_repository_section(
    reader: GraphReaderLike,
    *,
    repo_name: str,
    repo_uri: str = "",
    direct: list[PlacedEntity],
    collision_set: frozenset[str],
    name_to_entity: dict[str, PlacedEntity],
    sub_for_pkg: dict[str, dict[str, list[PlacedEntity]]],
) -> tuple[list[str], int]:
    """Render one `## Repository: <name>` section (D-R1).

    All member entities render as direct, kind-major (D-R6) headings —
    domain bucketing has been removed; there is only this single tier.
    Returns (lines, direct_heading_count) — ([], 0) when the section is
    empty (D-08).
    """
    lines: list[str] = []
    direct_count = 0
    for e in _kind_major(direct):
        lines.extend(
            _render_entity_heading(
                reader,
                e,
                level=3,
                collision_set=collision_set,
                name_to_entity=name_to_entity,
                sub_for_pkg=sub_for_pkg,
            )
        )
        direct_count += 1
    # Orphan test suites (no single consumer package -- e.g. a repo-root
    # cross-package integration suite) never nest under any package's
    # `sub_for_pkg` entry and `_kind_major` drops test_suite from headings
    # (D-R5), so without this they'd be placed but never rendered/linked
    # anywhere. Surface them as a plain bullet list, not a heading -- test
    # suites still never get their own heading.
    orphan_suites = [e for e in direct if e.kind == "test_suite" and not e.parent_pkg_names]
    if orphan_suites:
        lines.append("- Other Test Suites")
        for ts in sorted(orphan_suites, key=lambda x: x.uri):
            lines.append(_entity_bullet(ts, collision_set, "  "))
    if not lines:
        return [], 0
    heading = f"## Repository: {repo_name}"
    if repo_uri:
        stem = _short_filename(repo_uri, collision_set)
        heading = f"{heading} — {vault_wikilink(f'entities/{stem}', 'open page')}"
    return [heading, "", *lines], direct_count


def _render_curated_section(label: str, entries: list[dict]) -> list[str]:
    """Render one curated lane (D-08 omission of empty sections)."""
    if not entries:
        return []
    lines = [f"## {label}", ""]
    for e in entries:
        link = vault_wikilink(e["path"], e["title"])
        summary = f" — {escape_angle_brackets(e['summary'])}" if e.get("summary") else ""
        lines.append(f"- {link}{summary}")
    lines.append("")
    return lines


def _render_concepts_section(entries: list[dict]) -> list[str]:
    """Render the Concepts lane grouped by effective kind.

    Sub-headings (Architecture / Patterns / Concepts, fixed order, empty
    groups omitted) appear only when at least one page has a non-default
    kind group; an all-default lane renders flat, byte-identical to the old
    shape. Unknown kinds fold into the default group — never dropped.
    """
    if not entries:
        return []
    if all(kind_group({"kind": e.get("kind")}) == DEFAULT_CONCEPT_KIND for e in entries):
        return _render_curated_section("Concepts", entries)
    lines = ["## Concepts", ""]
    for kind in KIND_GROUP_ORDER:
        group = [e for e in entries if kind_group({"kind": e.get("kind")}) == kind]
        if not group:
            continue
        lines.append(f"### {KIND_GROUP_LABELS[kind]}")
        lines.append("")
        for e in group:
            link = vault_wikilink(e["path"], e["title"])
            summary = f" — {escape_angle_brackets(e['summary'])}" if e.get("summary") else ""
            lines.append(f"- {link}{summary}")
        lines.append("")
    return lines


def _render_guidance_section(topics: list[tuple[str, int]]) -> list[str]:
    """Render the navigational `## Guidance` section (omitted when empty).

    One lead link to guidance/index plus one link per topic with a page
    count. Guidance pages do NOT count into the banner's curated total.
    """
    if not topics:
        return []
    lines = ["## Guidance", "", f"- {vault_wikilink('guidance/index', 'All guidance topics')}"]
    for topic, count in topics:
        label = topic.replace("-", " ").replace("_", " ").title()
        noun = "page" if count == 1 else "pages"
        lines.append(f"- {vault_wikilink(f'guidance/{topic}/index', label)} — {count} {noun}")
    lines.append("")
    return lines


# ============================================================================
# Orchestrators (D-03, D-16, D-19)
# ============================================================================


def _render(
    reader: GraphReaderLike, wiki_root: Path, display_name: str | None = None
) -> tuple[str, int, int, int, int]:
    """Render the full index.

    `display_name` titles the index (the wiki's human topic). Falls back to the
    wiki directory name when not supplied.

    Returns (text, entity_count, curated_count, direct_count, repo_count).
    """
    # Phase 53 D-05: one-shot collision pre-pass, threaded through every
    # entity-link derivation so the index agrees with `write_entities`.
    collision_set = _compute_collision_set(reader, _ADMITTED_KINDS, _kind_list_fns())

    per_repo, name_to_entity = _place_entities(reader, wiki_root, collision_set)

    all_placed: list[PlacedEntity] = []
    for entities in per_repo.values():
        all_placed.extend(entities)
    entity_count = len(all_placed)

    # D-01/D-10: one global dep/suite-under-package grouping over ALL placed
    # entities, shared across all repo sections, so nesting behavior is
    # identical regardless of which repo a consumer renders in.
    sub_for_pkg = _build_sub_for_pkg(all_placed)

    workspace_root = wiki_root.parent

    curated_entries_by_lane: dict[str, list[dict]] = {}
    for stable_id, lane_dir, _label in CURATED_LANES:
        curated_entries_by_lane[stable_id] = _scan_curated_lane(wiki_root, lane_dir)
    work_entries = _scan_work(workspace_root)
    curated_count = sum(len(v) for v in curated_entries_by_lane.values()) + len(work_entries)

    today = datetime.date.today().isoformat()
    lines: list[str] = [
        f"# Index — {display_name or wiki_root.name}",
        "",
        f"_Auto-generated {today} • {entity_count} entities • {curated_count} curated pages_",
        "",
    ]

    repo_name_to_uri = {r.name: (r.attrs.get("uri") or "") for r in reader.list_repositories()}

    repo_count = 0
    direct_count = 0
    for repo_name in sorted(per_repo):
        direct = per_repo[repo_name]
        section, dir_count = _render_repository_section(
            reader,
            repo_name=repo_name,
            repo_uri=repo_name_to_uri.get(repo_name, ""),
            direct=direct,
            collision_set=collision_set,
            name_to_entity=name_to_entity,
            sub_for_pkg=sub_for_pkg,
        )
        if section:
            lines.extend(section)
            repo_count += 1
            direct_count += dir_count

    for stable_id, _lane_dir, section_label in CURATED_LANES:
        if stable_id == "concepts":
            lines.extend(_render_concepts_section(curated_entries_by_lane[stable_id]))
        else:
            lines.extend(_render_curated_section(section_label, curated_entries_by_lane[stable_id]))
    lines.extend(_render_guidance_section(_scan_guidance_topics(wiki_root)))
    lines.extend(_render_curated_section("Work", work_entries))

    text = "\n".join(lines).rstrip("\n") + "\n"  # POSIX trailing newline
    return text, entity_count, curated_count, direct_count, repo_count


def generate_index(reader: GraphReaderLike, wiki_root: Path, display_name: str | None = None) -> IndexWriteResult:
    """Render `wiki/index.md` and write-if-changed. Atomic on POSIX.

    `display_name` titles the index (the wiki's human topic); falls back to the
    wiki directory name when not supplied.

    D-16: byte-compare against the existing file; only `os.replace` when
    bytes differ. D-19: all-or-nothing — exceptions in render/place
    propagate out untouched.
    """
    text, entity_count, curated_count, direct_count, repo_count = _render(reader, wiki_root, display_name)
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
            direct_count=direct_count,
            repo_count=repo_count,
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
        direct_count=direct_count,
        repo_count=repo_count,
    )


# Re-export for tests that want to assert frozen-ness via dataclasses.FrozenInstanceError
__all__ = [
    "BY_KIND_ORDER",
    "CURATED_LANES",
    "GENERATED_FILES",
    "IndexWriteResult",
    "KIND_HEADING_LABELS",
    "PlacedEntity",
    "_PLACEABLE_KINDS",
    "_build_sub_for_pkg",
    "_consumer_pkgs",
    "_entity_bullet",
    "_infer_title",
    "_kind_major",
    "_parse_frontmatter",
    "_parse_repo_key",
    "_place_entities",
    "_read_entity_summary",
    "_render",
    "_render_concepts_section",
    "_render_curated_section",
    "_render_entity_heading",
    "_render_guidance_section",
    "_render_pkg_nested",
    "_render_repository_section",
    "_scan_curated_lane",
    "_scan_guidance_topics",
    "_scan_work",
    "generate_index",
    "dataclasses",  # exported so tests can do `from wiki_io.index_generator import dataclasses`
]
