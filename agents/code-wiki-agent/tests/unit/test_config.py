from __future__ import annotations

"""Unit tests for code_wiki_agent.config module (Plan 05-01).

Requirements covered: CLI-05 (--config global flag), D-11, D-12, D-13.
"""

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


def test_load_config_parses_all_three_fields(tmp_path: Path) -> None:
    """load_config() parses models_path, vault_path, and state_gate_enabled from TOML."""
    cfg_file = _write_toml(
        tmp_path / "wiki.toml",
        'models_path = "/some/models"\nvault_path = "/my/vault"\nstate_gate_enabled = false\n',
    )

    from code_wiki_agent.config import load_config

    cfg = load_config(cfg_file)
    assert cfg.models_path == "/some/models"
    assert cfg.vault_path == "/my/vault"
    assert cfg.state_gate_enabled is False


def test_load_config_drops_unknown_keys(tmp_path: Path) -> None:
    """load_config() silently ignores unknown TOML keys (no TypeError)."""
    cfg_file = _write_toml(
        tmp_path / "wiki.toml",
        'vault_path = "/vault"\nfuture_key = "ignored"\n',
    )

    from code_wiki_agent.config import load_config

    cfg = load_config(cfg_file)
    assert cfg.vault_path == "/vault"
    # If unknown keys weren't dropped, this would raise TypeError
    assert not hasattr(cfg, "future_key")


def test_load_config_defaults_for_missing_fields(tmp_path: Path) -> None:
    """load_config() returns defaults when TOML doesn't specify all fields."""
    cfg_file = _write_toml(tmp_path / "wiki.toml", "state_gate_enabled = true\n")

    from code_wiki_agent.config import load_config

    cfg = load_config(cfg_file)
    assert cfg.models_path is None
    assert cfg.vault_path is None
    assert cfg.state_gate_enabled is True


# ---------------------------------------------------------------------------
# Typer callback test
# ---------------------------------------------------------------------------


def test_typer_callback_sets_active_config(tmp_path: Path) -> None:
    """@app.callback() sets _active_config when --config is passed."""
    cfg_file = _write_toml(tmp_path / "wiki.toml", 'vault_path = "/cb-vault"\n')

    from typer.testing import CliRunner

    from code_wiki_agent.cli import app
    import code_wiki_agent.config as _cfg_module

    runner = CliRunner()
    # Invoke a no-op subcommand (version) with --config
    result = runner.invoke(app, ["--config", str(cfg_file), "version"])
    assert result.exit_code == 0, f"Unexpected exit: {result.output}"
    assert _cfg_module._active_config.vault_path == "/cb-vault"
