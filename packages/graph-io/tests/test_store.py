"""Store: connect, read-only, transaction context manager."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from graph_io import exit_codes, store


def test_exit_codes_constants() -> None:
    assert exit_codes.SUCCESS == 0
    assert exit_codes.GENERIC == 1
    assert exit_codes.STALE == 2
    assert exit_codes.NOT_INITIALIZED == 3
    assert exit_codes.SCHEMA_MISMATCH == 4
    assert exit_codes.NOT_IN_GIT_REPO == 5
    assert exit_codes.UPDATE_IN_PROGRESS == 6


def test_connect_create_true_creates_file_and_schema(tmp_path: Path) -> None:
    db = tmp_path / "graph" / "code.db"
    conn = store.connect(db, create=True)
    try:
        names = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        assert names == {"nodes", "edges", "metadata"}
    finally:
        conn.close()
    assert db.exists()


def test_connect_create_false_missing_raises(tmp_path: Path) -> None:
    db = tmp_path / "code.db"
    with pytest.raises(store.GraphNotInitializedError):
        store.connect(db, create=False)


def test_read_only_connect_blocks_writes(tmp_path: Path) -> None:
    db = tmp_path / "code.db"
    rw = store.connect(db, create=True)
    rw.close()
    ro = store.read_only_connect(db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            ro.execute("INSERT INTO metadata(key, value) VALUES ('x', 'y')")
    finally:
        ro.close()


def test_transaction_commits_on_success(tmp_path: Path) -> None:
    db = tmp_path / "code.db"
    conn = store.connect(db, create=True)
    try:
        with store.transaction(conn):
            conn.execute(
                "INSERT INTO metadata(key, value) VALUES ('k', 'v')"
            )
        row = conn.execute(
            "SELECT value FROM metadata WHERE key='k'"
        ).fetchone()
        assert row == ("v",)
    finally:
        conn.close()


def test_transaction_rolls_back_on_exception(tmp_path: Path) -> None:
    db = tmp_path / "code.db"
    conn = store.connect(db, create=True)
    try:
        with pytest.raises(RuntimeError):
            with store.transaction(conn):
                conn.execute(
                    "INSERT INTO metadata(key, value) VALUES ('k', 'v')"
                )
                raise RuntimeError("boom")
        row = conn.execute(
            "SELECT value FROM metadata WHERE key='k'"
        ).fetchone()
        assert row is None
    finally:
        conn.close()
