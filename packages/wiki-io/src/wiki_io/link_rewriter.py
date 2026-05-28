"""Markdown-aware wikilink rewriter for the v1.8 vault migration (Phase 46).

Pure-function core (``rewrite_text``), plus mapping derivation
(``build_rewrite_table``) and the vault walker (``rewrite_vault``).
Plan 03 wires this into the ``cg migrate-vault`` CLI subcommand.

CONTEXT.md decisions (see .planning/phases/46-inbound-link-migration-cutover/46-CONTEXT.md):
    D-01 regex with position-aware code-region masking (no markdown-it-py)
    D-02 explicit fixture suite for edge cases
    D-03 three-source rewrite mapping pipeline (convention + scan + grep)
    D-04 (Phase 46) family-grouping deferred — Phase 51 retired the kind
         outright; strict-deletion of the former deferral branches per
         Phase 51 RESEARCH.md Pitfall 4. Any live-vault leftovers are
         handled atomically by Phase 53's migrate-vault cutover.
    D-13 5 curated lanes (concepts, adrs, architecture, sources, work) — applied by rewrite_vault
    D-14 wiki/ root files NOT rewritten — enforced by rewrite_vault's lane scope
    D-16 JSONL migration.log helper private to this module
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from graph_io import queries as _queries

from wiki_io.entity_writer import encode_slug as _encode_slug
from wiki_io.lint.common import (
    FENCED_CODE_RE,
    INLINE_CODE_RE,
    WIKILINK_RE,
    indented_code_spans,
)


# ----------------------------------------------------------------------------
# Module-level constants (CONTEXT D-03, D-13)
# ----------------------------------------------------------------------------


CONVENTION_TEMPLATES: dict[str, str] = {
    "package":    "packages/{name}/index",
    "dependency": "dependencies/{ecosystem}/{name}/overview",
    "domain":     "domain/{name}/index",
    "plugin":     "plugin/{name}/overview",
    "test_suite": "test-suites/{name}/index",
}

OLD_LAYOUT_ROOTS: tuple[str, ...] = (
    "packages", "dependencies", "domain", "plugin",
)

# All target prefixes the rewriter recognizes as "old layout" candidates.
# Includes bare and ``wiki/``-prefixed forms per CONTEXT §deferred
# "Wikilink target normalization." Note ``test-suites`` is included as a valid
# old-layout kind even though no ``wiki/test-suites/`` directory removal is in
# scope (the dir may or may not exist in a given vault).
_PREFIX_ROOTS: tuple[str, ...] = OLD_LAYOUT_ROOTS + ("test-suites",)
OLD_LAYOUT_PREFIXES: tuple[str, ...] = tuple(
    f"{p}/" for p in _PREFIX_ROOTS
) + tuple(
    f"wiki/{p}/" for p in _PREFIX_ROOTS
)

# Curated lane suffixes (relative to wiki_root.parent — the workspace root).
# work/ is workspace-rooted (sibling of wiki/) per CONTEXT D-13.
CURATED_LANES_REL: tuple[str, ...] = (
    "wiki/concepts",
    "wiki/adrs",
    "wiki/architecture",
    "wiki/sources",
    "work",
)


# ----------------------------------------------------------------------------
# Result dataclass (CONTEXT D-13)
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class RewriteResult:
    """Per-vault rewrite outcome from :func:`rewrite_vault`."""

    files_scanned: int
    files_modified: int
    rewrites_total: int
    unresolved_total: int
    per_file: dict[str, int] = field(default_factory=dict)


# ----------------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------------


def _code_region_spans(text: str) -> list[tuple[int, int]]:
    """Return sorted, merged spans covering fenced + inline + indented code regions.

    The union covers every position whose surrounding context is code.
    Wikilinks whose start position falls inside any returned span are SKIPPED
    by :func:`rewrite_text`.
    """
    spans: list[tuple[int, int]] = []
    # Fenced
    for m in FENCED_CODE_RE.finditer(text):
        spans.append((m.start(), m.end()))
    # Inline — find on whole text; if an inline match falls inside a fenced
    # span, it's harmless (already covered by the merge below).
    for m in INLINE_CODE_RE.finditer(text):
        spans.append((m.start(), m.end()))
    # Indented
    spans.extend(indented_code_spans(text))
    if not spans:
        return []
    spans.sort()
    # Merge overlapping/adjacent.
    merged: list[tuple[int, int]] = [spans[0]]
    for s, e in spans[1:]:
        ms, me = merged[-1]
        if s <= me:
            merged[-1] = (ms, max(me, e))
        else:
            merged.append((s, e))
    return merged


def _is_inside_any_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    """O(N) scan — N is tiny for typical markdown docs.

    Spans are sorted ascending, so we can short-circuit once we pass the
    candidate position.
    """
    for s, e in spans:
        if s <= pos < e:
            return True
        if pos < s:
            return False
    return False


def _rebuild_wikilink(original: str, old_target: str, new_slug: str) -> str:
    """Replace ``old_target`` with ``new_slug`` in the wikilink, preserving anchor + alias.

    ``WIKILINK_RE`` guarantees the captured target appears at the start of the
    bracketed content. ``original.replace(old_target, new_slug, 1)`` is
    sufficient because:

    - the target appears exactly once at the lead position
    - the ``, 1`` limits replacement to the first occurrence (defensive
      against an alias whose text happens to equal the target).
    """
    return original.replace(old_target, new_slug, 1)


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


def rewrite_text(text: str, table: dict[str, str | None]) -> tuple[str, int]:
    """Rewrite old-layout wikilinks to new-layout slugs in ``text``.

    Args:
        text: The markdown content of one file.
        table: Mapping from old-layout target string to new-layout slug.
            A ``None`` value means "discovered as inbound but unresolvable" —
            the wikilink is SKIPPED. A missing key also means SKIP.

    Returns:
        ``(new_text, rewrite_count)``. ``rewrite_count`` is the number of
        wikilinks actually rewritten (NOT the number of wikilink matches).

    Behavior:
        - Wikilinks inside fenced code blocks, inline code spans, or indented
          code blocks are SKIPPED (their bytes are preserved byte-identical).
        - Alias (``|alias``) and anchor (``#anchor``) suffixes are preserved.
        - Idempotent: a second call on already-rewritten text yields count == 0.

    See CONTEXT.md D-01 / D-02 for the decisions backing this design.
    """
    code_spans = _code_region_spans(text)
    parts: list[str] = []
    cursor = 0
    count = 0
    for m in WIKILINK_RE.finditer(text):
        if _is_inside_any_span(m.start(), code_spans):
            continue
        target = m.group(1).strip()
        new_slug = table.get(target)
        if new_slug is None:
            # Missing key OR explicit None — skip silently.
            continue
        # Splice text up to match start, then the rebuilt link.
        parts.append(text[cursor:m.start()])
        parts.append(_rebuild_wikilink(m.group(0), target, new_slug))
        cursor = m.end()
        count += 1
    parts.append(text[cursor:])
    return ("".join(parts), count)


# ----------------------------------------------------------------------------
# Migration log helpers (CONTEXT D-16)
# ----------------------------------------------------------------------------


def _append_migration(log_path: Path, record: dict) -> None:
    """Append one JSONL record to ``.graph-wiki/migration.log`` (CONTEXT D-16).

    Mirrors ``entity_writer._append_deletion`` shape but without rotation
    (migration.log is one-shot per Research §8). Caller supplies the
    ``timestamp`` field; the helper does not stamp.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":"), sort_keys=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _utc_iso_z() -> str:
    """ISO-Z UTC timestamp string for migration.log records."""
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------
# Three-source rewrite table (CONTEXT D-03)
# ----------------------------------------------------------------------------


_LIST_FNS: dict[str, Callable[[sqlite3.Connection], Iterable]] = {
    "package":    _queries.list_packages,
    "dependency": _queries.list_dependencies,
    "domain":     _queries.list_domains,
    "plugin":     _queries.list_plugins,
    "test_suite": _queries.list_test_suites,
}


def _new_slug(uri: str) -> str:
    return f"entities/{_encode_slug(uri)}"


def _build_source1_and_index(
    conn: sqlite3.Connection,
) -> tuple[dict[str, str | None], dict[str, dict[str, str]]]:
    """Source 1 + (kind, name[, ecosystem]) index for Source 2/3 lookups.

    Returns ``(table_partial, index)`` where:
      ``table_partial``: bare + ``wiki/``-prefixed entries from convention templates
      ``index``: ``{kind: {key: new_slug}}`` where ``key`` is ``name`` (or
        ``f"{ecosystem}/{name}"`` for dependency).
    """
    table: dict[str, str | None] = {}
    index: dict[str, dict[str, str]] = {k: {} for k in CONVENTION_TEMPLATES}
    for kind, template in CONVENTION_TEMPLATES.items():
        list_fn = _LIST_FNS[kind]
        for node in list_fn(conn):
            attrs = node.attrs if isinstance(node.attrs, dict) else {}
            uri = attrs.get("uri")
            if not uri:
                continue
            new_slug = _new_slug(uri)
            name = node.name
            if kind == "dependency":
                ecosystem = attrs.get("ecosystem", "")
                if not ecosystem:
                    continue  # defensive — deps always have ecosystem in v1.7+
                bare = template.format(name=name, ecosystem=ecosystem)
                index[kind][f"{ecosystem}/{name}"] = new_slug
            else:
                bare = template.format(name=name)
                index[kind][name] = new_slug
            table[bare] = new_slug
            table[f"wiki/{bare}"] = new_slug
    return table, index


def _source2_scan_old_layout(
    wiki_root: Path,
    table: dict[str, str | None],
    index: dict[str, dict[str, str]],
) -> None:
    """Source 2: scan-and-match over old layout dirs. Mutates ``table`` in place."""
    kind_for_root = {
        "packages": "package",
        "dependencies": "dependency",
        "domain": "domain",
        "plugin": "plugin",
    }
    for root_name in OLD_LAYOUT_ROOTS:
        root = wiki_root / root_name
        if not root.is_dir():
            continue
        kind = kind_for_root.get(root_name)
        if kind is None:
            continue  # defensive — unknown root in OLD_LAYOUT_ROOTS
        for md in root.rglob("*.md"):
            try:
                old_target = str(
                    md.relative_to(wiki_root).with_suffix("")
                ).replace(os.sep, "/")
            except ValueError:
                continue
            # Skip if Source 1 already covered it (in either bare or wiki/ form).
            if old_target in table or f"wiki/{old_target}" in table:
                continue
            parts = md.relative_to(root).parts
            if kind == "dependency":
                # path shape: <ecosystem>/<name>/overview.md
                if len(parts) < 2:
                    continue
                key = f"{parts[0]}/{parts[1]}"
            else:
                # path shape: <name>/index.md (or similar)
                if len(parts) < 1:
                    continue
                key = parts[0]
            new_slug = index.get(kind, {}).get(key)
            if new_slug is None:
                continue  # not in graph; leave uncovered (Source 3 may catch it)
            table[old_target] = new_slug
            table[f"wiki/{old_target}"] = new_slug


_KIND_FOR_PREFIX: dict[str, str | None] = {
    "packages/": "package",
    "wiki/packages/": "package",
    "dependencies/": "dependency",
    "wiki/dependencies/": "dependency",
    "domain/": "domain",
    "wiki/domain/": "domain",
    "plugin/": "plugin",
    "wiki/plugin/": "plugin",
    "test-suites/": "test_suite",
    "wiki/test-suites/": "test_suite",
}


def _record_unresolvable(
    table: dict[str, str | None],
    log_path: Path | None,
    md: Path,
    workspace_root: Path,
    target: str,
) -> None:
    """Mark ``target`` as unresolvable in the table and (optionally) log it."""
    table[target] = None
    if log_path is not None:
        try:
            rel_file = str(md.relative_to(workspace_root))
        except ValueError:
            rel_file = str(md)
        _append_migration(log_path, {
            "timestamp": _utc_iso_z(),
            "phase": "unresolved",
            "file": rel_file,
            "target": target,
        })


def _source3_grep_curated_lanes(
    wiki_root: Path,
    table: dict[str, str | None],
    index: dict[str, dict[str, str]],
    log_path: Path | None,
) -> None:
    """Source 3: grep curated lanes for inbound links to old-layout prefixes.

    Adds resolvable inbound targets to ``table`` (mapping to the new slug).
    Unresolvable targets are added with value ``None`` and logged.
    """
    workspace_root = wiki_root.parent
    lanes = [
        wiki_root / "concepts",
        wiki_root / "adrs",
        wiki_root / "architecture",
        wiki_root / "sources",
        workspace_root / "work",
    ]
    for lane in lanes:
        if not lane.is_dir():
            continue
        for md in lane.rglob("*.md"):
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            spans = _code_region_spans(text)
            for m in WIKILINK_RE.finditer(text):
                if _is_inside_any_span(m.start(), spans):
                    continue
                target = m.group(1).strip()
                matched_prefix = next(
                    (p for p in OLD_LAYOUT_PREFIXES if target.startswith(p)),
                    None,
                )
                if matched_prefix is None:
                    continue
                if target in table:
                    continue  # already covered (possibly with None)
                kind = _KIND_FOR_PREFIX.get(matched_prefix)
                if kind is None:
                    # Defensive: prefix matched OLD_LAYOUT_PREFIXES but is
                    # missing from _KIND_FOR_PREFIX — treat as unresolvable.
                    _record_unresolvable(table, log_path, md, workspace_root, target)
                    continue
                tail = target[len(matched_prefix):]
                tail_parts = tail.split("/")
                if kind == "dependency":
                    if len(tail_parts) < 2:
                        _record_unresolvable(table, log_path, md, workspace_root, target)
                        continue
                    key = f"{tail_parts[0]}/{tail_parts[1]}"
                else:
                    if not tail_parts:
                        _record_unresolvable(table, log_path, md, workspace_root, target)
                        continue
                    key = tail_parts[0]
                new_slug = index.get(kind, {}).get(key)
                if new_slug is None:
                    _record_unresolvable(table, log_path, md, workspace_root, target)
                    continue
                table[target] = new_slug


def build_rewrite_table(
    conn: sqlite3.Connection,
    wiki_root: Path,
    *,
    log_path: Path | None = None,
) -> dict[str, str | None]:
    """Build the old-target -> new-slug rewrite table from three sources (CONTEXT D-03).

    Source 1: convention templates per kind (5 kinds).
    Source 2: scan-and-match over ``wiki/{packages,dependencies,domain,plugin}/``.
    Source 3: grep the 5 curated lanes for inbound old-layout wikilinks; log unresolvables.

    Args:
        conn: read-only graph connection.
        wiki_root: absolute path to the vault ``wiki/`` directory.
        log_path: where to write unresolvable-target JSONL records (typically
            ``.graph-wiki/migration.log``). If None, unresolvables are still
            added to the table as None but not logged.

    Returns:
        ``dict`` mapping old-target string to new-slug string OR ``None``
        (unresolvable).
    """
    table, index = _build_source1_and_index(conn)
    _source2_scan_old_layout(wiki_root, table, index)
    _source3_grep_curated_lanes(wiki_root, table, index, log_path)
    return table


# ----------------------------------------------------------------------------
# Vault walker (CONTEXT D-13, D-14)
# ----------------------------------------------------------------------------


def _atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically (temp file + ``os.replace``)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _default_lanes(wiki_root: Path) -> list[Path]:
    workspace_root = wiki_root.parent
    return [
        wiki_root / "concepts",
        wiki_root / "adrs",
        wiki_root / "architecture",
        wiki_root / "sources",
        workspace_root / "work",
    ]


def _count_unresolved_in_text(text: str, table: dict[str, str | None]) -> int:
    """Count wikilinks in non-code regions whose target maps to ``None`` in ``table``."""
    spans = _code_region_spans(text)
    count = 0
    for m in WIKILINK_RE.finditer(text):
        if _is_inside_any_span(m.start(), spans):
            continue
        target = m.group(1).strip()
        # Sentinel string distinguishes "missing key" from "explicit None".
        value = table.get(target, "<missing>")
        if value is None:
            count += 1
    return count


def _log_rewrites(
    text_before: str,
    text_after: str,
    table: dict[str, str | None],
    log_path: Path,
    file_rel: str,
) -> None:
    """For each rewritten wikilink in ``text_before``, append one JSONL line to ``log_path``."""
    spans = _code_region_spans(text_before)
    ts = _utc_iso_z()
    for m in WIKILINK_RE.finditer(text_before):
        if _is_inside_any_span(m.start(), spans):
            continue
        target = m.group(1).strip()
        new_slug = table.get(target)
        if new_slug is None:
            continue
        _append_migration(log_path, {
            "timestamp": ts,
            "phase": "rewrite",
            "file": file_rel,
            "from": target,
            "to": new_slug,
        })


def rewrite_vault(
    wiki_root: Path,
    table: dict[str, str | None],
    *,
    log_path: Path | None = None,
    lanes: list[Path] | None = None,
) -> RewriteResult:
    """Walk the 5 curated lanes and rewrite wikilinks per the table.

    Per CONTEXT D-13: defaults walk ``wiki/concepts``, ``wiki/adrs``,
    ``wiki/architecture``, ``wiki/sources``, and workspace-rooted ``work/``
    (sibling of ``wiki/``). Per D-14: ``wiki/`` root files are never visited.

    For each ``.md`` file in scope, call :func:`rewrite_text`; if ``count > 0``,
    write back atomically (temp-file + ``os.replace``) and append one JSONL
    line per rewrite to ``log_path`` (if not None).

    Returns :class:`RewriteResult` with totals and per-file counts.
    """
    workspace_root = wiki_root.parent
    lanes_resolved = lanes if lanes is not None else _default_lanes(wiki_root)
    files_scanned = 0
    files_modified = 0
    rewrites_total = 0
    unresolved_total = 0
    per_file: dict[str, int] = {}
    for lane in lanes_resolved:
        if not lane.is_dir():
            continue
        for md in sorted(lane.rglob("*.md")):
            files_scanned += 1
            try:
                text = md.read_text(encoding="utf-8")
            except OSError:
                continue
            unresolved_total += _count_unresolved_in_text(text, table)
            new_text, count = rewrite_text(text, table)
            if count > 0:
                _atomic_write_text(md, new_text)
                files_modified += 1
                rewrites_total += count
                try:
                    rel = str(md.relative_to(workspace_root))
                except ValueError:
                    rel = str(md)
                per_file[rel] = count
                if log_path is not None:
                    _log_rewrites(text, new_text, table, log_path, rel)
    return RewriteResult(
        files_scanned=files_scanned,
        files_modified=files_modified,
        rewrites_total=rewrites_total,
        unresolved_total=unresolved_total,
        per_file=per_file,
    )
