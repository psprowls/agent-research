"""cg update [--full] — refresh the code graph from git."""

from __future__ import annotations

import argparse
import sys

from graph_io import exit_codes, store, update


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--full", action="store_true", help="full rebuild from scratch")


def run(args: argparse.Namespace) -> int:
    try:
        update.run(args.repo, workspace=args.workspace, full=args.full)
    except update.NotInGitRepoError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.NOT_IN_GIT_REPO
    except update.UpdateInProgressError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.UPDATE_IN_PROGRESS
    except store.SchemaMismatchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.SCHEMA_MISMATCH
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exit_codes.GENERIC
    return exit_codes.SUCCESS
