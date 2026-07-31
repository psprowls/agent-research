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
    p.add_argument("--json", action="store_true", dest="json_output", help="Emit ScanResult/ApplyResult as JSON")
    p.add_argument("--emit-worklist", default="", help="Emit the commit-gated worklist JSON to this path and exit")
    p.add_argument("--apply-worklist", default="", help="Apply a results JSON from this path")
    p.add_argument(
        "--results-dir",
        default="",
        help="Apply per-entity result JSON files from this directory (merges with --apply-worklist)",
    )
    p.add_argument(
        "--worklist-path",
        default="",
        help="Worklist JSON for apply (defaults to worklist.json beside the results source)",
    )
    p.add_argument("--short-head", default="", help="Stamp value for --apply-worklist (short HEAD sha)")
    p.add_argument("--propagate-drift", action="store_true", help="Include opt-in M4 cross-page drift")
    return p.parse_args(argv)


def main() -> None:
    try:
        from _config import backend_for
    except ImportError:

        def backend_for(command: str, repo_root: str | None = None) -> str:
            return "claude"

    backend = backend_for("scan")

    if backend == "bedrock":
        result = subprocess.run(
            ["gw", "scan"] + sys.argv[1:],
            check=True,
        )
        sys.exit(result.returncode)

    # Claude branch — in-process, structural-only (no Bedrock).
    args = _parse_args(sys.argv[1:])
    workspace_path = Path(args.workspace) if args.workspace else None

    if args.emit_worklist:
        from graph_wiki_core.commands.scan import (
            ScanAbortedError,
            briefs_dir_for,
            emit_scan_worklist,
            results_dir_for,
        )

        out_path = Path(args.emit_worklist)
        try:
            result = asyncio.run(
                emit_scan_worklist(
                    workspace_path=workspace_path,
                    repo_path=None,
                    no_file_map=args.no_file_map,
                    max_depth=args.max_depth,
                    propagate=args.propagate_drift,
                    out_path=out_path,
                )
            )
        except ScanAbortedError as e:
            print(f"[error] scan aborted: {e}", file=sys.stderr)
            sys.exit(2)
        payload = {
            "worklist_path": args.emit_worklist,
            "briefs_dir": str(briefs_dir_for(out_path)),
            "results_dir": str(results_dir_for(out_path)),
            "scan_result": dataclasses.asdict(result),
        }
        print(json.dumps(payload, indent=2))
        if result.entity_errors:
            sys.exit(3)
        return

    if args.apply_worklist or args.results_dir:
        from graph_wiki_core.commands.scan import apply_scan_worklist

        results_path = Path(args.apply_worklist) if args.apply_worklist else None
        results_dir = Path(args.results_dir) if args.results_dir else None
        # worklist.json sits beside whichever results source was given:
        #   <ws>/.graph-wiki/results.json -> <ws>/.graph-wiki/worklist.json
        #   <ws>/.graph-wiki/results/     -> <ws>/.graph-wiki/worklist.json
        source_dir = results_path.parent if results_path is not None else results_dir.parent  # type: ignore[union-attr]
        worklist_path = Path(args.worklist_path) if args.worklist_path else source_dir / "worklist.json"
        applied = asyncio.run(
            apply_scan_worklist(
                workspace_path=workspace_path,
                repo_path=None,
                results_path=results_path,
                results_dir=results_dir,
                worklist_path=worklist_path,
                short_head=(args.short_head or None),
                propagate=args.propagate_drift,
            )
        )
        print(json.dumps(applied.to_dict(), indent=2))
        if applied.entity_errors:
            sys.exit(3)
        return

    # Bare invocation — structural-only fast path (unchanged).
    from graph_wiki_core.commands.scan import ScanAbortedError, run_scan

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
