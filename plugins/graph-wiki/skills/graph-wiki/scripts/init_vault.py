#!/usr/bin/env python3
"""Plugin script for initializing a Graph Wiki vault."""

from __future__ import annotations

import argparse
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
    result = subprocess.run(["gw", "bootstrap"] + sys.argv[1:], check=True)
    sys.exit(result.returncode)


def main() -> None:
    if _backend_for("init") == "bedrock":
        _run_bedrock()

    from graph_wiki_core.page_kind_templates import kind_template_dirs
    from wiki_io._workspace import resolve_wiki_and_repo
    from wiki_io.init_vault import TOOL_FILES, init_wiki

    parser = argparse.ArgumentParser(description="Initialize a Code Wiki in the resolved graph-wiki workspace.")
    parser.add_argument("--topic", required=True, help="Short description of the repo")
    parser.add_argument(
        "--tool",
        default="all",
        choices=sorted(TOOL_FILES.keys()),
        help="Which schema file(s) to install (default: all)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite non-empty target directory")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Emit result as JSON")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Accepted for compatibility; has no effect (container detection removed).",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace path (bypasses .graph-wiki.yaml discovery; required on first bootstrap).",
    )
    parser.add_argument("--repo", default=None, help="Override repo root when used with --workspace.")
    args = parser.parse_args()

    workspace_arg = Path(args.workspace).expanduser().resolve() if args.workspace else None
    repo_arg = Path(args.repo).expanduser().resolve() if args.repo else None
    if workspace_arg is not None and repo_arg is not None:
        wiki = workspace_arg / "wiki"
        repo_path = repo_arg
    else:
        wiki, resolved_repo = resolve_wiki_and_repo(workspace_path=workspace_arg, repo_path=repo_arg)
        repo_path = resolved_repo or Path.cwd()

    init_wiki(
        wiki,
        repo_path,
        topic=args.topic,
        tool=args.tool,
        force=args.force,
        as_json=args.json_output,
        non_interactive=args.non_interactive,
        extra_template_dirs=kind_template_dirs(),
    )


if __name__ == "__main__":
    main()
