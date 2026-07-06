#!/usr/bin/env python3
"""Plugin script for preparing a source ingestion brief."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _backend_for(command: str) -> str:
    try:
        from _config import backend_for
    except ImportError:
        return "claude"
    return backend_for(command)


def _run_bedrock() -> None:
    result = subprocess.run(["gw", "ingest"] + sys.argv[1:], check=True)
    sys.exit(result.returncode)


def _source_for_branch(source_path: Path, repo: Path) -> Path:
    if source_path.is_absolute():
        return source_path
    candidate = repo / source_path
    return candidate if candidate.exists() else source_path.resolve()


def main() -> None:
    if _backend_for("ingest") == "bedrock":
        _run_bedrock()

    import graph_io
    from wiki_io._workspace import resolve_wiki_and_repo
    from wiki_io.ingest_source import (
        build_batch_ingest_brief,
        build_folder_ingest_brief,
        build_ingest_brief,
        build_skill_ingest_brief,
        resolve_skill_anchor,
    )

    parser = argparse.ArgumentParser(description="Prepare a source for ingestion.")
    parser.add_argument("source", nargs="?", default=None, help="Path to the source file/folder")
    parser.add_argument("--source", dest="source_opt", default=None, help="Path to the source (alt form)")
    parser.add_argument("--workspace", default="", help="Workspace path (default: env / git heuristic)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit JSON brief")
    parser.add_argument("--limit", type=int, default=10, help="Batch: max units to ingest (default 10)")
    parser.add_argument(
        "--all", action="store_true", dest="all_units", help="Batch: ingest all units (overrides --limit)"
    )
    args = parser.parse_args()

    source_arg = args.source_opt or args.source
    if not source_arg:
        print("[error] no source path given", file=sys.stderr)
        sys.exit(1)

    workspace_path = Path(args.workspace).expanduser().resolve() if args.workspace else None
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    if repo is None:
        repo = Path.cwd()
    workspace_root = workspace_path if workspace_path is not None else wiki.parent
    source_path = Path(source_arg).expanduser()

    try:
        reader = graph_io.open_reader(workspace_root)
    except graph_io.GraphNotInitializedError:
        reader = None

    try:
        resolved = _source_for_branch(source_path, repo)
        limit = None if args.all_units else args.limit
        brief = build_batch_ingest_brief(
            source_path=resolved,
            wiki=wiki,
            repo=repo,
            workspace_root=workspace_root,
            limit=limit,
        )
        if brief is None:
            anchor = resolve_skill_anchor(resolved)
            if anchor is not None:
                brief = build_skill_ingest_brief(
                    anchor=anchor,
                    wiki=wiki,
                    repo=repo,
                    workspace_root=workspace_root,
                    reader=reader,
                )
            elif resolved.is_dir():
                brief = build_folder_ingest_brief(source_path=source_path, wiki=wiki, repo=repo)
                if "_error" in brief:
                    print(f"[error] {brief['_error']}", file=sys.stderr)
                    sys.exit(1)
            else:
                brief = build_ingest_brief(
                    source_path=source_path,
                    wiki=wiki,
                    repo=repo,
                    workspace_root=workspace_root,
                    reader=reader,
                )
    finally:
        if reader is not None:
            reader.close()

    if args.json_output:
        print(json.dumps(brief, indent=2))
        return

    if brief.get("is_batch"):
        total = brief.get("total_count", brief["unit_count"])
        if brief.get("limited"):
            print(f"Batch: raw/{brief['kind_folder']} ({brief['unit_count']} of {total} units, --all for everything)")
        else:
            print(f"Batch: raw/{brief['kind_folder']} ({brief['unit_count']} units)")
        for unit in brief["units"]:
            print(f"  - {unit['rel']} ({unit['unit_type']})")
        return

    if brief.get("is_skill"):
        print(f"Title: {brief['title']}")
        print(f"Source type: {brief['source_type']}")
        print(f"{len(brief['included_files'])} included / {len(brief['excluded_files'])} excluded files")
        if brief.get("scripts_dominant"):
            print("Warning: scripts_dominant — mostly non-markdown scripts; weak guidance candidate")
        print(f"Suggested summary: {brief['suggested_summary_path']}")
        print(f"Target guidance dir: {brief['guidance_dir']}")
        entity_match = brief["entity_match"]
        if entity_match["uri"]:
            print(f"Entity match: {entity_match['uri']} -> [[entities/{entity_match['entity_filename']}]]")
        return

    if brief.get("is_folder"):
        print(f"Folder: {source_path}")
        print(f"Files: {brief['file_count']}")
        print(f"Representative: {brief.get('representative_file')}")
        warnings = brief.get("warnings") or []
        if warnings:
            print(f"Warnings: {', '.join(warnings)}")
        return

    print(f"Title: {brief['title']}")
    print(f"Source type: {brief['source_type']}")
    print(f"Suggested summary: {brief['suggested_summary_path']}")
    entity_match = brief["entity_match"]
    if entity_match["uri"]:
        print(f"Entity match: {entity_match['uri']} -> [[entities/{entity_match['entity_filename']}]]")


if __name__ == "__main__":
    main()
