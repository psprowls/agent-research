#!/usr/bin/env python3
"""Plugin shim for reconciling stale work-item spec_doc/plan_doc pointers after a
source archive.

Inlined from the former ``wiki_io.reconcile_doc_pointers`` (thin wrapper over
``work_io.doc_pointers.sweep``) for the Claude-hosted ingest path, which moves
a source into ``raw/_archive/`` but (unlike ``gw ingest``) does not otherwise
reconcile work-item pointers. Idempotent and best-effort; safe to run after
any ingest. Pure local IO — no Bedrock backend branch.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def main() -> None:
    from wiki_io._workspace import resolve_wiki_and_repo
    from work_io.doc_pointers import sweep

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
