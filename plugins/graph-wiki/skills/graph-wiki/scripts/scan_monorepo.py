#!/usr/bin/env python3
"""Plugin shim for scan — graph-driven entities/ scan in-process (claude) or gw (bedrock).

Claude branch: imports run_scan from graph_wiki_core and runs it with
narrate=False (structural-only — writes entity pages + indexes deterministically,
no Bedrock fan-out, no model_adapter/subagent_runtime needed). Bedrock branch:
shells out to `gw scan` (narrated), preserving the user's trailing argv.
"""

import argparse
import asyncio
import dataclasses
import json
import subprocess
import sys
from pathlib import Path

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scan the monorepo into wiki/entities/.")
    p.add_argument("--workspace", default="", help="Workspace path (default: GRAPH_WIKI_WORKSPACE)")
    p.add_argument("--no-file-map", action="store_true", help="Skip per-package file maps")
    p.add_argument("--max-depth", type=int, default=3, help="Max file-map directory depth")
    p.add_argument("--json", action="store_true", dest="json_output", help="Emit ScanResult as JSON")
    return p.parse_args(argv)


def main() -> None:
    try:
        from _config import backend_for
    except ImportError:

        def backend_for(cmd: str, repo: object = None) -> str:  # type: ignore[misc]
            return "claude"

    backend = backend_for("scan")

    if backend == "bedrock":
        result = subprocess.run(
            ["gw", "scan"] + sys.argv[1:],
            check=True,
        )
        sys.exit(result.returncode)

    # Claude branch — in-process, structural-only (no Bedrock).
    from graph_wiki_core.commands.scan import ScanAbortedError, run_scan

    args = _parse_args(sys.argv[1:])
    workspace_path = Path(args.workspace) if args.workspace else None
    try:
        result = asyncio.run(
            run_scan(
                workspace_path=workspace_path,
                no_file_map=args.no_file_map,
                max_depth=args.max_depth,
                narrate=False,
            )
        )
    except ScanAbortedError as e:
        print(f"[error] scan aborted: {e}", file=sys.stderr)
        sys.exit(2)
    except (RuntimeError, FileNotFoundError) as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    if args.json_output:
        print(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        c = len(result.entities_created)
        u = len(result.entities_updated)
        d = len(result.entities_deleted)
        print(f"Scan complete: entities +{c} ~{u} -{d}")
        for uri in result.entities_deleted:
            print(f"  - deleted: {uri}")
        for err in result.entity_errors:
            print(f"  error: {err}", file=sys.stderr)

    if result.entity_errors:
        sys.exit(3)


if __name__ == "__main__":
    main()
