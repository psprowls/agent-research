#!/usr/bin/env python3
"""
append_log.py — Append a standardized entry to wiki/log.md.

The log is append-only and uses a consistent header so unix tools can parse it:
    ## [YYYY-MM-DD] <op> | <title>

Discovers wiki location via vault_io._workspace.resolve_wiki_and_repo.
Requires GRAPH_WIKI_WORKSPACE env var (or a git repo containing a wiki/ directory).

Usage:
    python append_log.py --op ingest --title "Auth Migration Spec"
    python append_log.py --op scan --title "detected 3 new packages" --detail "..."
    python append_log.py --op lint --title "weekly health check" --json

Valid ops:
    scan     — a /lattice-wiki:scan pass ran
    ingest   — a source was read and integrated
    query    — a question was answered (filed back as a page)
    lint     — a health-check pass ran
    create   — a new page was created outside of an ingest
    update   — an existing page was updated outside of an ingest
    delete   — a page was removed
    note     — freeform note (contradictions flagged, thesis revisions, etc.)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from vault_io._workspace import resolve_wiki_and_repo

VALID_OPS = {"scan", "ingest", "query", "lint", "create", "update", "delete", "note"}


def _error(message, as_json=False, raise_exception=False):
    """Report an error.

    When called from a library context (e.g. an MCP tool handler) pass
    ``raise_exception=True`` so the failure surfaces as a normal
    ``ValueError`` that the MCP boundary can catch — never ``sys.exit``,
    which would kill the stdio server process (WR-01).

    JSON-formatted error output is written to stderr, not stdout, so that
    a future caller accidentally enabling ``as_json=True`` from inside the
    MCP server cannot trip ``_StdoutGuard`` (WR-02).
    """
    if raise_exception:
        raise ValueError(message)
    if as_json:
        print(json.dumps({"status": "error", "message": message}), file=sys.stderr)
    else:
        print(f"[error] {message}", file=sys.stderr)
    sys.exit(1)


def validate_wiki(wiki):
    if not wiki.exists():
        raise FileNotFoundError(f"wiki does not exist: {wiki}")
    log_path = wiki / "log.md"
    if not log_path.exists():
        raise FileNotFoundError(f"{log_path} does not exist — is this a wiki?")
    return log_path


def format_entry(op, title, detail):
    today = dt.date.today().isoformat()
    header = f"## [{today}] {op} | {title}"
    body = f"\n{detail}\n" if detail else "\n"
    return today, header, f"\n{header}\n{body}"


def append_log(wiki, op, title, detail, as_json=False, silent=False, raise_exception=False):
    """Append a log entry to wiki/log.md.

    Args:
        silent: When True, suppress all stdout output. Use from MCP tool handlers
                to avoid tripping _StdoutGuard. Overrides as_json for output only.
        raise_exception: When True, error paths raise ``ValueError`` instead of
                calling ``sys.exit(1)``. Library callers (MCP tool handlers,
                file_work_item) MUST set this — a ``SystemExit`` from inside the
                MCP server's tool boundary would terminate the stdio server.
    """
    if op not in VALID_OPS:
        _error(
            f"unknown op '{op}'. Valid: {sorted(VALID_OPS)}",
            as_json,
            raise_exception=raise_exception,
        )

    try:
        log_path = validate_wiki(wiki)
    except FileNotFoundError as e:
        _error(str(e), as_json, raise_exception=raise_exception)

    today, header, entry_text = format_entry(op, title, detail)

    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(entry_text)
    except OSError as e:
        _error(
            f"failed to write {log_path}: {e}",
            as_json,
            raise_exception=raise_exception,
        )

    result = {
        "status": "ok",
        "log_path": str(log_path),
        "date": today,
        "op": op,
        "title": title,
        "header": header,
        "detail": detail,
    }

    if not silent:
        if as_json:
            print(json.dumps(result, indent=2))
        else:
            print(f"[ok] appended to {log_path}")
            print(f"     {header}")
            if detail:
                print(f"     detail: {detail}")
    return result


def main():
    p = argparse.ArgumentParser(description="Append a standardized entry to wiki/log.md")
    p.add_argument("--op", required=True, choices=sorted(VALID_OPS))
    p.add_argument("--title", required=True)
    p.add_argument("--detail", default=None)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    wiki, _ = resolve_wiki_and_repo()
    append_log(
        wiki,
        args.op,
        args.title,
        args.detail,
        as_json=args.json,
    )


if __name__ == "__main__":
    main()
