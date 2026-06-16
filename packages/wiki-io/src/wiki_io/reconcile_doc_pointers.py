"""Repoint stale work-item spec_doc/plan_doc pointers after a source archive.

Thin wrapper over ``work_io.doc_pointers.sweep`` for the Claude-hosted ingest
path, which moves a source into ``raw/_archive/`` but (unlike ``gw ingest``)
does not otherwise reconcile work-item pointers. Idempotent and best-effort;
safe to run after any ingest.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from work_io.doc_pointers import sweep

from wiki_io._workspace import resolve_wiki_and_repo


def main() -> None:
    parser = argparse.ArgumentParser(description="Repoint stale work-item doc pointers.")
    parser.add_argument("--workspace", default="", help="Workspace path (default: env / git heuristic)")
    args = parser.parse_args()

    workspace_path = Path(args.workspace).expanduser().resolve() if args.workspace else None
    wiki, _repo = resolve_wiki_and_repo(workspace_path)
    report = sweep(wiki.parent, dry_run=False)

    for entry in report.rewrote:
        print(f"repointed: {entry}")
    print(f"reconcile: {len(report.rewrote)} repointed, {len(report.ok)} ok, {len(report.unfixable)} unfixable")


if __name__ == "__main__":
    main()
