"""Repair stale spec_doc/plan_doc pointers in work items after source archival.

A work item's design phase stamps ``spec_doc: raw/specs/<slug>.md`` (or
``plan_doc: raw/plans/<slug>.md``). When that source is later ingested, the raw
file moves to ``raw/_archive/<...>`` (mirroring
``wiki_io.ingest_source.archive_destination``) but the frontmatter pointer is not
rewritten, leaving it stale.

``sweep`` rewrites such a pointer only when BOTH the current target is missing
AND its ``raw/_archive/`` counterpart exists, so active items are never touched
and the operation is idempotent and safe to call from any site (mid-ingest, or
as a ``gw work archive`` backstop). The rewrite is a surgical in-place splice on
the frontmatter block — it never reserializes YAML, so key order, formatting,
and comments are preserved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Frontmatter-level keys sit at column 0. Body mentions such as "- `spec_doc: …`"
# never match this anchored pattern; matching is further restricted to the
# frontmatter span by slicing it out before substitution.
_POINTER_LINE = re.compile(r"^(?P<key>spec_doc|plan_doc):[ \t]*(?P<val>\S+)[ \t]*$", re.MULTILINE)


@dataclass
class SweepReport:
    """Disposition of a sweep: which pointers were rewritten, already-ok, or unfixable."""

    rewrote: list[str] = field(default_factory=list)
    ok: list[str] = field(default_factory=list)
    unfixable: list[str] = field(default_factory=list)


def _frontmatter_span(text: str) -> tuple[int, int] | None:
    """Return (start, end) char offsets of the frontmatter block body, or None.

    The block is the region between the opening ``---\\n`` fence and the closing
    ``\\n---`` fence. Files without a leading fence have no frontmatter.
    """
    if not text.startswith("---\n"):
        return None
    close = text.find("\n---", 4)
    if close == -1:
        return None
    return 4, close + 1


def archived_counterpart(ws_root: Path, pointer: str) -> str | None:
    """Return the corrected pointer if a rewrite applies, else None.

    Rewrite iff the current target is missing AND the archive counterpart exists.
    The counterpart mirrors ``wiki_io.ingest_source.archive_destination``: insert
    ``_archive`` after the leading ``raw/`` segment. Pointers that still resolve,
    are not under ``raw/``, or are already under ``raw/_archive/`` return None.
    """
    if (ws_root / pointer).exists():
        return None
    parts = Path(pointer).parts
    if len(parts) < 2 or parts[0] != "raw" or parts[1] == "_archive":
        return None
    candidate = Path("raw", "_archive", *parts[1:]).as_posix()
    return candidate if (ws_root / candidate).exists() else None


def sweep(ws_root: Path, *, dry_run: bool) -> SweepReport:
    """Walk wiki/work/**/*.md and repoint stale spec_doc/plan_doc pointers.

    Guarded (only missing-with-counterpart), idempotent, and formatting-preserving.
    Returns a :class:`SweepReport`. ``index.md`` and body text are never touched.
    """
    report = SweepReport()
    work_dir = ws_root / "wiki" / "work"
    if not work_dir.is_dir():
        return report

    for md in sorted(work_dir.rglob("*.md")):
        if md.name == "index.md":
            continue
        text = md.read_text(encoding="utf-8")
        span = _frontmatter_span(text)
        if span is None:
            continue
        fm_start, fm_end = span
        rel = md.relative_to(ws_root).as_posix()
        frontmatter = text[fm_start:fm_end]

        def _replace(m: re.Match[str]) -> str:
            key, pointer = m.group("key"), m.group("val")
            if (ws_root / pointer).exists():
                report.ok.append(f"{rel} ({key})")
                return m.group(0)
            target = archived_counterpart(ws_root, pointer)
            if target is None:
                report.unfixable.append(f"{rel} ({key}={pointer})")
                return m.group(0)
            report.rewrote.append(f"{rel} ({key}) -> {target}")
            return f"{key}: {target}"

        new_frontmatter = _POINTER_LINE.sub(_replace, frontmatter)
        if new_frontmatter != frontmatter and not dry_run:
            md.write_text(text[:fm_start] + new_frontmatter + text[fm_end:], encoding="utf-8")

    return report
