#!/usr/bin/env python3
"""Plugin script for wiki lint checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from _uv_reexec import ensure as _ensure_uv

_ensure_uv()


def _backend_for(command: str) -> str:
    try:
        from _config import backend_for
    except ImportError:
        return "claude"
    return backend_for(command)


def _run_bedrock() -> None:
    result = subprocess.run(["gw", "wiki", "lint"] + sys.argv[1:], check=True)
    sys.exit(result.returncode)


def main() -> None:
    if _backend_for("lint") == "bedrock":
        _run_bedrock()

    from graph_wiki_core.commands.lint_mechanical import OPTIONAL_GROUPS, print_report, scan
    from wiki_io._workspace import resolve_wiki_and_repo

    parser = argparse.ArgumentParser(description="Lint a Code Wiki (with code-drift detection)")
    parser.add_argument("--stale-days", type=int, default=90)
    parser.add_argument("--log-gap-days", type=int, default=14)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--check",
        default="",
        help=(
            "Comma-separated optional check groups to enable in addition to the "
            "default set. Available: " + ",".join(sorted(OPTIONAL_GROUPS))
        ),
    )
    args = parser.parse_args()

    optional_checks: set[str] = set()
    if args.check:
        for name in args.check.split(","):
            name = name.strip()
            if not name:
                continue
            if name not in OPTIONAL_GROUPS:
                print(
                    f"[error] unknown --check group '{name}' (known: {','.join(sorted(OPTIONAL_GROUPS))})",
                    file=sys.stderr,
                )
                sys.exit(2)
            optional_checks.add(name)

    wiki, repo_path = resolve_wiki_and_repo()
    report = scan(
        wiki,
        stale_days=args.stale_days,
        log_gap_days=args.log_gap_days,
        repo_path=repo_path,
        optional_checks=optional_checks,
    )
    if args.json:
        print(json.dumps(report, indent=2, default=list))
    else:
        print_report(report)


if __name__ == "__main__":
    main()
