"""Living Wiki M2b: commit-gated File-map row re-description + shared anchor."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import frontmatter as _fm
import graph_wiki_core.commands.scan as scan_mod
import pytest
from graph_io import exit_codes
from graph_wiki_core.commands.scan import _changed_rel_paths
from wiki_io.entity_writer import EntityWriteResult


# ---------------------------------------------------------------------------
# §3.3 path-namespace transform (unit)
# ---------------------------------------------------------------------------


def test_changed_rel_paths_relativizes_under_root() -> None:
    assert _changed_rel_paths(
        ["packages/pkg-a/mod.py", "packages/pkg-a/src/util.py"],
        "packages/pkg-a",
    ) == {"mod.py", "src/util.py"}


def test_changed_rel_paths_drops_paths_outside_root() -> None:
    assert _changed_rel_paths(
        ["packages/pkg-a/mod.py", "packages/pkg-b/other.py", "README.md"],
        "packages/pkg-a",
    ) == {"mod.py"}


def test_changed_rel_paths_empty() -> None:
    assert _changed_rel_paths([], "packages/pkg-a") == set()
