from __future__ import annotations

import os
from pathlib import Path

import pytest

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "round-trip-vault"


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Return a fresh temp directory (pytest tmp_path variant)."""
    return tmp_path


def write_file(path: Path, content: str = "") -> Path:
    """Module-level helper (not a fixture): write content to path, creating parents."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def vault_path(tmp_path: Path) -> Path:
    """Return an empty vault directory under tmp_path."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    return wiki


@pytest.fixture
def round_trip_vault() -> Path:
    """Return the committed vault fixture, or the env-override path if set."""
    override = os.environ.get("GRAPH_WIKI_WORKSPACE")
    if override:
        return Path(override)
    return FIXTURE_VAULT
