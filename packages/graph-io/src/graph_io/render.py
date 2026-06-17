"""Render lists of dataclass records as JSON or aligned-column human output.

Public formatter module for graph_io. Shared by graph-wiki-cli's gw graph
modules and other graph-wiki surfaces without pulling CLI code back into graph-io.

Per-kind formatters (format_package, format_path, format_repo, format_domain,
format_entry_point, format_suite) extracted from the corresponding q_describe_*.py
inline printers to form a single source of truth (D-02).
"""

from __future__ import annotations

import dataclasses
import json as _json
from collections.abc import Mapping
from typing import Any, Callable, Iterable, NamedTuple


def _to_dict(record: Any) -> dict[str, Any]:
    if dataclasses.is_dataclass(record) and not isinstance(record, type):
        out: dict[str, Any] = dataclasses.asdict(record)
        return out
    if isinstance(record, Mapping):
        return {str(key): value for key, value in record.items()}
    raise TypeError(f"record is not renderable as a mapping: {type(record).__name__}")


def _is_importer_batch(rows: list[Any]) -> bool:
    # Avoid an explicit import cycle (render must not import queries at module load).
    return bool(rows) and type(rows[0]).__name__ == "ImporterRecord"


def _importer_human(rows: list[Any]) -> str:
    if not rows:
        return ""
    formatted = [
        {
            "path": r.path,
            "symbols": "(" + ", ".join(r.symbols) + ")" if r.symbols else "",
            "depth": str(r.depth),
        }
        for r in rows
    ]
    keys = ["path", "symbols", "depth"]
    widths = {k: max(len(row[k]) for row in formatted) for k in keys}
    return "\n".join("  ".join(row[k].ljust(widths[k]) for k in keys) for row in formatted)


def _importer_json(rows: list[Any]) -> str:
    flat: list[dict[str, Any]] = []
    for r in rows:
        if r.symbols:
            for sym in r.symbols:
                flat.append({"path": r.path, "symbol": sym, "depth": r.depth})
        else:
            flat.append({"path": r.path, "symbol": None, "depth": r.depth})
    return _json.dumps(flat, default=str)


class Attr(NamedTuple):
    """One attributes-block entry. `human` is the pre-rendered human value;
    `json` is the raw value placed under `key` in JSON output."""

    label: str
    key: str
    human: str
    json: object

    @classmethod
    def scalar(cls, label: str, key: str, value: object) -> "Attr":
        human = "(none)" if value is None or value == "" else str(value)
        return cls(label, key, human, value)

    @classmethod
    def joined(cls, label: str, key: str, values: list[str]) -> "Attr":
        return cls(label, key, ", ".join(values) or "(none)", list(values))


class Rel(NamedTuple):
    """One relationships-block entry. Human renders as a comma-joined list;
    JSON places `values` under `key`."""

    label: str
    key: str
    values: list[str]


def _pluralize(word: str, n: int) -> str:
    if n == 1:
        return word
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def _counts_human(counts: dict[str, int]) -> str:
    if not counts:
        return "(none)"
    return " · ".join(f"{n} {_pluralize(k, n)}" for k, n in counts.items())


def _aligned_block(title: str, pairs: list[tuple[str, str]]) -> list[str]:
    """Render a titled block: title line then `  label: value` lines aligned to
    the widest label. Returns [] when pairs is empty (caller omits the section)."""
    if not pairs:
        return []
    width = max(len(label) for label, _ in pairs)
    lines = [title]
    for label, value in pairs:
        lines.append(f"  {(label + ':').ljust(width + 1)} {value}")
    return lines


def describe_block(
    *,
    kind: str,
    name: str,
    identity_label: str,
    identity_value: str,
    attributes: list[Attr],
    relationships: list[Rel],
    nav: list[str],
    fmt: str,
) -> str:
    """Single sectioned-spine builder shared by every format_<kind>.

    Human: `<kind> <name>` header, indented identity line, then the present
    `attributes`/`relationships`/nav sections (empty sections omitted), each
    separated by a blank line, labels aligned within their block.
    JSON: {kind, name, <identity_label>, attributes, relationships, nav} —
    empty sections kept as {}/[] for a stable machine shape.
    """
    if fmt == "json":
        payload: dict[str, object] = {
            "kind": kind,
            "name": name,
            identity_label: identity_value,
            "attributes": {a.key: a.json for a in attributes},
            "relationships": {r.key: r.values for r in relationships},
            "nav": list(nav),
        }
        return _json.dumps(payload, default=str)
    if fmt != "human":
        raise ValueError(f"unknown format: {fmt!r}")

    lines = [f"{kind} {name}", f"  {identity_label}: {identity_value}"]
    attr_lines = _aligned_block("attributes", [(a.label, a.human) for a in attributes])
    if attr_lines:
        lines.append("")
        lines.extend(attr_lines)
    rel_lines = _aligned_block("relationships", [(r.label, ", ".join(r.values)) for r in relationships])
    if rel_lines:
        lines.append("")
        lines.extend(rel_lines)
    if nav:
        lines.append("")
        lines.extend(f"→ {cmd}" for cmd in nav)
    return "\n".join(lines)


def render(
    records: Iterable[Any],
    fmt: str,
    *,
    cap: int | None = None,
    on_truncate: Callable[[int, int], None] | None = None,
) -> str:
    """Render `records` as `fmt` ('human' or 'json'), optionally capping rows.

    When `cap` is set and `len(rows) > cap`, only the first `cap` rows are
    rendered. For `fmt='human'`, a trailing line `... showing {cap} of {total}
    (truncated)` is appended. For `fmt='json'`, the truncation is silent (no
    envelope wrap — flat array of the first `cap` rows). When truncation
    fires and `on_truncate` is provided, it is invoked with `(cap, total)` so
    the caller can emit a side-channel notice (e.g. stderr). `render` itself
    never writes outside its return value.

    `cap=None` (the default) preserves the pre-Phase-36 pass-through behavior
    for every caller that does not opt in.
    """
    rows = list(records)
    total = len(rows)
    truncated = cap is not None and total > cap
    if truncated:
        row_cap = cap
        if row_cap is None:
            raise RuntimeError("truncated render requires a row cap")
        rows = rows[:row_cap]
        if on_truncate is not None:
            on_truncate(row_cap, total)

    if _is_importer_batch(rows):
        if fmt == "json":
            return _importer_json(rows)
        if fmt == "human":
            out = _importer_human(rows)
            if truncated:
                trailer = f"... showing {cap} of {total} (truncated)"
                return f"{out}\n{trailer}" if out else trailer
            return out
        raise ValueError(f"unknown format: {fmt!r}")

    dicts = [_to_dict(r) for r in rows]
    if fmt == "json":
        return _json.dumps(dicts, default=str)
    if fmt == "human":
        if not dicts:
            return ""
        keys = list(dicts[0].keys())
        widths = {k: max(len(str(r.get(k, ""))) for r in dicts + [dict.fromkeys(keys, k)]) for k in keys}
        lines = []
        for r in dicts:
            lines.append("  ".join(str(r.get(k, "")).ljust(widths[k]) for k in keys))
        if truncated:
            if cap is None:
                raise RuntimeError("truncated render requires a row cap")
            lines.append(f"... showing {cap} of {total} (truncated)")
        return "\n".join(lines)
    raise ValueError(f"unknown format: {fmt!r}")


# ── Per-kind formatters (extracted from q_describe_*.py inline printers) ──────


def format_package(desc: Any, fmt: str) -> str:
    """Format a PackageDescription as human text or JSON.

    Extracted from q_describe_package.py lines 36-47.
    """
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    lines = [
        f"package: {desc.name}",
        f"language: {desc.language}",
        f"version:  {desc.version}",
        f"files:    {len(desc.files)}",
        f"counts:   {desc.counts}",
        f"internal deps:       {', '.join(desc.internal_dependencies) or '-'}",
        f"internal dependents: {', '.join(desc.internal_dependents) or '-'}",
    ]
    return "\n".join(lines)


def format_path(desc: Any, fmt: str) -> str:
    """Format a PathDescription as human text or JSON.

    Extracted from q_describe_path.py lines 39-46.
    """
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    lines = [f"path: {desc.path}"]
    if desc.token_count is not None:
        lines.append(f"tokens: {desc.token_count}")
    lines.append("children:")
    for c in desc.children:
        tc = c.attrs.get("token_count")
        suffix = f"  ({tc} tokens)" if tc is not None else ""
        lines.append(f"  {c.kind}  {c.name}  line {c.line}{suffix}")
    lines.append("imports:")
    for i in desc.imports:
        lines.append(f"  {i.name}  {i.path}")
    lines.append("exports:")
    for e in desc.exports:
        lines.append(f"  {e.kind}  {e.name}  line {e.line}")
    return "\n".join(lines)


def format_repo(desc: Any, fmt: str) -> str:
    """Format a RepoDescription as human text or JSON.

    Extracted from q_describe_repo.py lines 39-46.
    """
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    url = desc.url if desc.url else "(none)"
    default_branch = desc.default_branch if desc.default_branch else "(none)"
    lines = [
        f"repository:     {desc.name}",
        f"uri:            {desc.uri}",
        f"url:            {url}",
        f"default_branch: {default_branch}",
        f"package_count:  {desc.package_count}",
    ]
    return "\n".join(lines)


def format_domain(
    desc: Any,
    packages: list[str],
    subdomains: list[str],
    fmt: str,
) -> str:
    """Format a DomainDescription as human text or JSON.

    Extracted from q_describe_domain.py lines 55-80.
    NOTE: packages and subdomains are NOT in DomainDescription; callers pass them explicitly.
    """
    if fmt == "json":
        payload = {**dataclasses.asdict(desc), "packages": packages, "subdomains": subdomains}
        return _json.dumps(payload, default=str)
    parent = desc.parent if desc.parent else "(none)"
    description = desc.description if desc.description else "(none)"
    lines = [
        f"domain:        {desc.name}",
        f"uri:           {desc.uri}",
        f"parent:        {parent}",
        f"description:   {description}",
        "packages:",
    ]
    if packages:
        for name in packages:
            lines.append(f"  - {name}")
    else:
        lines.append("  (none)")
    lines.append("subdomains:")
    if subdomains:
        for name in subdomains:
            lines.append(f"  - {name}")
    else:
        lines.append("  (none)")
    return "\n".join(lines)


def format_entry_point(desc: Any, fmt: str) -> str:
    """Format an EntryPointDescription as human text or JSON.

    Extracted from q_describe_entry_point.py lines 83-92.
    """
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    callable_value = desc.callable if desc.callable else "(none)"
    impl_path = desc.implemented_by_path if desc.implemented_by_path else "(none)"
    source = desc.source if desc.source else "(none)"
    lines = [
        f"entry-point: {desc.name}",
        f"uri:         {desc.uri}",
        f"kind:        {desc.kind}",
        f"callable:    {callable_value}",
        f"path:        {impl_path}",
        f"source:      {source}",
    ]
    return "\n".join(lines)


def format_suite(desc: Any, fmt: str) -> str:
    """Format a SuiteDescription as human text or JSON.

    Extracted from q_describe_suite.py lines 43-46.
    NOTE: label is 'suite:', not 'test_suite:' (D-03 byte-identical).
    """
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    lines = [
        f"suite:  {desc.name}",
        f"uri:    {desc.uri}",
        f"kind:   {desc.kind}",
        f"files:  {desc.file_count}",
    ]
    return "\n".join(lines)


def format_symbol(desc: Any, fmt: str) -> str:
    """Format a SymbolDescription (graph_io.queries) as human text or JSON."""
    if fmt == "json":
        return _json.dumps(dataclasses.asdict(desc), default=str)
    if fmt != "human":
        raise ValueError(f"unknown format: {fmt!r}")
    loc = f"{desc.path}:{desc.line}" if desc.line is not None else (desc.path or "(unknown)")
    lines = [f"{desc.kind} {desc.name}", f"  path: {loc}"]
    if desc.token_count is not None:
        lines.append(f"  tokens: {desc.token_count}")
    if desc.package:
        pkg_line = f"  package: {desc.package}"
        if desc.domain:
            pkg_line += f"   domain: {desc.domain}"
        lines.append(pkg_line)
    if desc.exported_from:
        lines.append(f"  exported: yes (from {desc.exported_from})")
    else:
        lines.append("  exported: no")
    if desc.callers:
        lines.append(f"  callers (depth 1): {', '.join(c.name for c in desc.callers)}")
    if desc.callees:
        lines.append(f"  callees (depth 1): {', '.join(c.name for c in desc.callees)}")
    lines.append(f"  → deeper: gw graph callers {desc.name} --depth 3")
    return "\n".join(lines)


def format_matches(records: Iterable[Any], fmt: str) -> str:
    """Format MatchRecord disambiguation entries as human text or JSON."""
    rows = list(records)
    if fmt == "json":
        return _json.dumps([dataclasses.asdict(r) for r in rows], default=str)
    if fmt == "human":
        lines = []
        for r in rows:
            mid = f"  {r.address}" if r.address else ""
            lines.append(f"{r.kind}{mid}  → {r.command}")
        return "\n".join(lines)
    raise ValueError(f"unknown format: {fmt!r}")
