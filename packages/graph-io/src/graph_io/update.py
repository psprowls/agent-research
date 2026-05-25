"""Update orchestrator: git diff → parse + project + upsert → resolve → metadata."""

from __future__ import annotations

import datetime as _dt
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Iterable

from source_parser.parse import parse_bytes
from source_parser.projections.graph import to_graph_records

from workspace_io.config import resolve as resolve_workspace
from workspace_io.paths import graph_dir

from graph_io import _ignore, packages, resolve, store, upsert

_GITIGNORE_BODY = "code.db\ncode.db-wal\ncode.db-shm\n"


class NotInGitRepoError(Exception):
    pass


class UpdateInProgressError(Exception):
    """Raised when another writer holds the SQLite write lock past the timeout."""


def _git(args: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise NotInGitRepoError(result.stderr.strip() or "git command failed")
    return result.stdout


def _head(cwd: Path) -> str:
    return _git(["rev-parse", "HEAD"], cwd=cwd).strip()


def _all_tracked(cwd: Path) -> list[tuple[str, str]]:
    out = _git(["ls-files"], cwd=cwd)
    return [("A", line) for line in out.splitlines() if line]


def _diff(cwd: Path, prev: str) -> list[tuple[str, str]]:
    out = _git(["diff", "--name-status", f"{prev}..HEAD"], cwd=cwd)
    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0][0]
        if status == "R":
            if len(parts) < 3:
                continue
            old_path, new_path = parts[1], parts[2]
            rows.append(("D", old_path))
            rows.append(("M", new_path))
        elif status in {"A", "M", "D"}:
            rows.append((status, parts[-1]))
    return rows


def _is_parseable(path: str) -> bool:
    from source_parser.parsers import EXTENSIONS
    return Path(path).suffix in EXTENSIONS


def _delete_file_nodes(conn, path: str) -> None:
    conn.execute("DELETE FROM nodes WHERE path = ?", (path,))


def _set_metadata(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def _get_metadata(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _ensure_gitignore(workspace: Path) -> None:
    target = graph_dir(workspace) / ".gitignore"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_GITIGNORE_BODY)


def _changed_files(repo_root: Path, full: bool, prev: str | None) -> list[tuple[str, str]]:
    if full or prev is None:
        return _all_tracked(repo_root)
    return _diff(repo_root, prev)


def _process_files(
    conn,
    repo_root: Path,
    changed: Iterable[tuple[str, str]],
    skip_dirs: frozenset[str],
) -> None:
    for status, rel in changed:
        if _ignore.should_skip(rel, skip_dirs):
            continue
        if not _is_parseable(rel):
            continue
        if status == "D":
            _delete_file_nodes(conn, rel)
            continue
        full = repo_root / rel
        if not full.exists():
            continue
        source = full.read_bytes()
        tree = parse_bytes(source, path=Path(rel), package=None)
        records = to_graph_records(tree)
        for node in records.nodes:
            if node.path is not None:
                node.attrs.setdefault("language", tree.language)
        upsert.upsert_records(conn, records)


def _default_lock_timeout() -> int:
    raw = os.environ.get("LATTICE_GRAPH_LOCK_TIMEOUT_MS")
    if raw is None:
        return 30_000
    try:
        return max(0, int(raw))
    except ValueError:
        return 30_000


def run(repo_root: Path, *, workspace: Path | None = None, full: bool = False, lock_timeout_ms: int | None = None) -> None:
    """Run an update against `repo_root`. Single SQLite transaction.

    If `workspace` is provided (e.g. already resolved at the CLI layer), it is
    used as-is. Otherwise, the workspace is resolved from `repo_root` with
    `require_manifest=False` — `update` is the bootstrap path that creates
    the graph DB before any manifest may exist.
    """
    repo_root = Path(repo_root).resolve()
    if workspace is None:
        workspace = resolve_workspace(repo_root, require_manifest=False).workspace
    else:
        workspace = Path(workspace).resolve()
    head = _head(repo_root)
    skip_dirs = _ignore.load_skip_dirs(repo_root)

    db_path = graph_dir(workspace) / "code.db"
    if lock_timeout_ms is None:
        lock_timeout_ms = _default_lock_timeout()
    conn = None
    try:
        try:
            conn = store.connect(db_path, create=True, busy_timeout_ms=lock_timeout_ms)
            _ensure_gitignore(workspace)
            prev = _get_metadata(conn, "last_indexed_commit")
            changed = _changed_files(repo_root, full=full, prev=prev)
            if not changed and prev == head and not full:
                return

            with store.transaction(conn):
                _process_files(conn, repo_root, changed, skip_dirs)
                packages.refresh(conn, repo_root=repo_root)
                if full:
                    tracked_paths = [
                        rel for _, rel in changed
                        if _is_parseable(rel) and not _ignore.should_skip(rel, skip_dirs)
                    ]
                    if tracked_paths:
                        placeholders = ",".join("?" for _ in tracked_paths)
                        conn.execute(
                            f"DELETE FROM nodes WHERE kind != 'package' AND path IS NOT NULL AND path NOT IN ({placeholders})",
                            tracked_paths,
                        )
                    else:
                        conn.execute(
                            "DELETE FROM nodes WHERE kind != 'package' AND path IS NOT NULL"
                        )
                resolve.sweep(conn)
                _set_metadata(conn, "last_indexed_commit", head)
                _set_metadata(conn, "last_indexed_at", _dt.datetime.now(_dt.UTC).isoformat())
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower():
                raise UpdateInProgressError(
                    "another `cg update` appears to be in progress "
                    f"(SQLite write lock held longer than {lock_timeout_ms}ms)"
                ) from exc
            raise
    finally:
        if conn is not None:
            conn.close()
