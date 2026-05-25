"""cg sync-wiki — link package nodes to wiki overview pages."""

from __future__ import annotations

import argparse
import sys

from workspace_io.paths import graph_dir

from graph_io import exit_codes, store, sync_wiki


def add_arguments(parser: argparse.ArgumentParser) -> None:
    pass


def _format_report(report: sync_wiki.DriftReport) -> str:
    lines: list[str] = []

    lines.append("newly linked:")
    if report.newly_linked:
        for pkg, wiki_rel in report.newly_linked:
            lines.append(f"  {pkg} -> {wiki_rel}")
    else:
        lines.append("  (none)")

    lines.append("undocumented:")
    if report.undocumented:
        for pkg in report.undocumented:
            lines.append(f"  {pkg}")
    else:
        lines.append("  (none)")

    lines.append("stale (file gone):")
    if report.stale:
        for wiki_rel in report.stale:
            lines.append(f"  {wiki_rel}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def run(args: argparse.Namespace) -> int:
    db = graph_dir(args.workspace) / "code.db"
    try:
        conn = store.connect(db, create=False)
    except store.GraphNotInitializedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_INITIALIZED
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    try:
        report = sync_wiki.run(workspace=args.workspace, conn=conn)
    finally:
        conn.close()
    print(_format_report(report))
    return exit_codes.SUCCESS
