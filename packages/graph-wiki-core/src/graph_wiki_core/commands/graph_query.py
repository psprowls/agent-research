"""Shared graph-query plumbing for the `gw graph` CLI surface.

The ~30 `graph_cli/q_*.py` / `ops_*.py` command modules in graph-wiki-cli
previously imported graph_io / wiki_io directly — a layering violation
(graph-wiki-cli is declared to depend only on graph-wiki-core; see work item
2026-07-05-thin-the-delivery-surfaces-route-graph-wiki-cli-and-subagent-cli-through-graph-wiki-core).
This module is the sole crosser of that boundary for the CLI query surface:
it re-exports the primitives those files need, plus `connect_or_error`, a
shared reader-opening helper that collapses the identical open -> translate
error -> close boilerplate that was duplicated file by file.
"""

from __future__ import annotations

from pathlib import Path

from graph_io import (
    SCHEMA_VERSION,  # noqa: F401
    VALID_KINDS,  # noqa: F401
    DriftReport,  # noqa: F401
    GraphNotInitializedError,
    GraphReader,
    NodeRecord,  # noqa: F401
    SchemaMismatchError,
    exit_codes,
    open_reader,
    render,
    run_sync_wiki,  # noqa: F401
    update,  # noqa: F401
)
from wiki_io.package_pages import resolve_overview_path  # noqa: F401

# graph_io.render module attrs re-exported for graph_cli/_format.py's shim
# (that file predates this module and re-exports these under its own name —
# see its docstring for why it is kept rather than deleted).
_importer_human = render._importer_human
_importer_json = render._importer_json
_is_importer_batch = render._is_importer_batch
_to_dict = render._to_dict


def connect_or_error(workspace: Path) -> tuple[GraphReader | None, int, str]:
    """Open a read-only GraphReader, returning (reader, exit_code, stderr).

    No printing. On success returns (reader, SUCCESS, ""); caller is
    responsible for `reader.close()` (try/finally). On a store error returns
    (None, NOT_INITIALIZED|SCHEMA_MISMATCH, "error: ..."); caller prints
    `stderr` to stderr and returns `exit_code` immediately.

    Mirrors graph_wiki_core.commands.graph._connect_or_error's shape (kept
    separate rather than consolidated: that module's callers raise
    typer.Exit, these are plain int-returning functions).
    """
    try:
        return open_reader(workspace), exit_codes.SUCCESS, ""
    except GraphNotInitializedError as exc:
        return None, exit_codes.NOT_INITIALIZED, f"error: {exc}"
    except SchemaMismatchError as exc:
        return None, exit_codes.SCHEMA_MISMATCH, f"error: {exc}"
