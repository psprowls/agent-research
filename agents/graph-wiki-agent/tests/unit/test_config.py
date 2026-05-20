from __future__ import annotations

"""Unit tests for graph_wiki_agent.config module — exercises load_config TOML parsing and the _active_config singleton. (CLI-05 / --config plumbing was removed in Phase 20 / WMC-03.)"""

import tomllib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write_toml(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# load_config() tests
# ---------------------------------------------------------------------------


def test_load_config_parses_remaining_fields(tmp_path: Path) -> None:
    """load_config() parses vault_path and state_gate_enabled from TOML."""
    cfg_file = _write_toml(
        tmp_path / "wiki.toml",
        'vault_path = "/my/vault"\nstate_gate_enabled = false\n',
    )

    from graph_wiki_agent.config import load_config

    cfg = load_config(cfg_file)
    assert cfg.vault_path == "/my/vault"
    assert cfg.state_gate_enabled is False


def test_load_config_drops_unknown_keys(tmp_path: Path) -> None:
    """load_config() silently ignores unknown TOML keys (no TypeError)."""
    cfg_file = _write_toml(
        tmp_path / "wiki.toml",
        'vault_path = "/vault"\nfuture_key = "ignored"\n',
    )

    from graph_wiki_agent.config import load_config

    cfg = load_config(cfg_file)
    assert cfg.vault_path == "/vault"
    # If unknown keys weren't dropped, this would raise TypeError
    assert not hasattr(cfg, "future_key")


def test_load_config_defaults_for_missing_fields(tmp_path: Path) -> None:
    """load_config() returns defaults when TOML doesn't specify all fields."""
    cfg_file = _write_toml(tmp_path / "wiki.toml", "state_gate_enabled = true\n")

    from graph_wiki_agent.config import load_config

    cfg = load_config(cfg_file)
    assert cfg.vault_path is None
    assert cfg.state_gate_enabled is True
