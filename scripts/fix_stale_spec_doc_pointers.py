#!/usr/bin/env python3
"""Sweep stale ``spec_doc`` pointers in work items to their archived spec home.

When a work item resolves and its spec is ingested, the spec file moves from
``raw/specs/<name>.md`` to ``raw/_archive/specs/<name>.md`` but the item's
``spec_doc:`` frontmatter pointer is not rewritten, leaving every archived item
pointing at a path that no longer exists.

This guarded, idempotent sweep rewrites a frontmatter ``spec_doc:`` pointer only
when BOTH:
  1. the current target is missing, and
  2. ``raw/_archive/specs/<basename-of-target>`` exists.
The pointer is then set to that archive path. ``plan_doc`` keys, body text, other
frontmatter keys, and pointers that still resolve (active items) are left
untouched, so the sweep is safe to re-run and converges to zero edits.

Exit status:
  0 — no stale pointers remain (clean, or every fixable one was fixed)
  1 — at least one ``spec_doc`` is missing with no archive counterpart (unfixable)

Usage:
  python scripts/fix_stale_spec_doc_pointers.py --workspace <ws-root> [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# A frontmatter-level key sits at column 0. Body mentions such as
# "- `spec_doc: ...`" begin with "- " and never match this anchored pattern;
# the sweep additionally restricts matching to the frontmatter block.
_SPEC_DOC_LINE = re.compile(r"^spec_doc:[ \t]*(?P<val>\S+)[ \t]*$", re.MULTILINE)


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


def archived_target(ws_root: Path, pointer: str) -> str | None:
    """Return the corrected pointer if a rewrite applies, else None.

    Rewrite iff the current target is missing AND the archive counterpart exists.
    A pointer that still resolves, or one missing with no counterpart, returns None.
    """
    if (ws_root / pointer).exists():
        return None
    candidate = f"raw/_archive/specs/{Path(pointer).name}"
    return candidate if (ws_root / candidate).exists() else None


def sweep(ws_root: Path, *, dry_run: bool) -> dict[str, list[str]]:
    """Walk wiki/work/**/*.md and rewrite stale frontmatter spec_doc pointers.

    Returns a disposition report with three lists: ``rewrote`` (paths rewritten,
    "<rel> -> <new>"), ``ok`` (pointer already resolves), and ``unfixable``
    (missing target, no archive counterpart, "<rel> (spec_doc=<ptr>)").
    """
    report: dict[str, list[str]] = {"rewrote": [], "ok": [], "unfixable": []}
    work_dir = ws_root / "wiki" / "work"
    for md in sorted(work_dir.rglob("*.md")):
        if md.name == "index.md":
            continue
        text = md.read_text(encoding="utf-8")
        span = _frontmatter_span(text)
        if span is None:
            continue
        fm_start, fm_end = span
        m = _SPEC_DOC_LINE.search(text, fm_start, fm_end)
        if m is None:
            continue
        pointer = m.group("val")
        rel = md.relative_to(ws_root).as_posix()
        if (ws_root / pointer).exists():
            report["ok"].append(rel)
            continue
        target = archived_target(ws_root, pointer)
        if target is None:
            report["unfixable"].append(f"{rel} (spec_doc={pointer})")
            continue
        new_text = text[: m.start()] + f"spec_doc: {target}" + text[m.end() :]
        if not dry_run:
            md.write_text(new_text, encoding="utf-8")
        report["rewrote"].append(f"{rel} -> {target}")
    return report


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True, type=Path, help="Workspace root (has wiki/ and raw/)")
    ap.add_argument("--dry-run", action="store_true", help="Report planned edits without writing")
    args = ap.parse_args(argv)
    ws_root = args.workspace.expanduser().resolve()

    report = sweep(ws_root, dry_run=args.dry_run)
    verb = "WOULD REWRITE" if args.dry_run else "REWROTE"
    for line in report["rewrote"]:
        print(f"{verb}: {line}")
    for line in report["unfixable"]:
        print(f"UNFIXABLE (missing, no archive counterpart): {line}", file=sys.stderr)
    print(
        f"\n{len(report['rewrote'])} {'would be ' if args.dry_run else ''}rewritten, "
        f"{len(report['ok'])} already resolve, "
        f"{len(report['unfixable'])} unfixable."
    )
    return 1 if report["unfixable"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
