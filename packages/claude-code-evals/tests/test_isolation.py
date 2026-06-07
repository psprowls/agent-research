"""Tests for workspace isolation (FixtureIsolation)."""

from __future__ import annotations

import json
from pathlib import Path

from claude_code_evals.isolation import FixtureIsolation
from claude_code_evals.schemas import Config, Scenario


def _fixture_scenario(tmp_path: Path) -> tuple[Scenario, Config]:
    """Create a minimal fixture-based scenario."""
    fixture_src = tmp_path / "fixture_src"
    fixture_src.mkdir()
    (fixture_src / "README.md").write_text("hello")
    s = Scenario.model_validate(
        {
            "name": "test",
            "isolation_mode": "fixture",
            "fixture_dir": str(fixture_src),
        }
    )
    c = Config.model_validate({"name": "base"})
    return s, c


def test_fixture_isolation_creates_worktree_path(tmp_path: Path):
    """FixtureIsolation creates and populates worktree_path."""
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        assert iso.worktree_path.exists()
        assert (iso.worktree_path / "README.md").exists()


def test_fixture_isolation_creates_cfg_dir(tmp_path: Path):
    """FixtureIsolation creates and populates cfg_dir."""
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        assert iso.cfg_dir.exists()
        assert (iso.cfg_dir / "settings.json").exists()


def test_fixture_isolation_writes_settings_accept_edits(tmp_path: Path):
    """FixtureIsolation writes settings.json with acceptEdits permission."""
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        settings = json.loads((iso.cfg_dir / "settings.json").read_text())
        assert settings["permissions"]["defaultMode"] == "acceptEdits"


def test_fixture_isolation_cleanup(tmp_path: Path):
    """FixtureIsolation cleans up tmpdir on exit."""
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        wt = iso.worktree_path
    assert not wt.exists()


def test_fixture_isolation_keep(tmp_path: Path):
    """FixtureIsolation preserves tmpdir when keep=True."""
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c, keep=True) as iso:
        wt = iso.worktree_path
    assert wt.exists()


def test_fixture_isolation_writes_meta_json(tmp_path: Path):
    """FixtureIsolation writes meta.json with scenario/config/model."""
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        meta = json.loads(iso.meta_path.read_text())
        assert meta["scenario"] == "test"
        assert meta["config"] == "base"


def test_fixture_isolation_extra_env_in_settings(tmp_path: Path):
    """FixtureIsolation includes extra_env in settings.json."""
    s, _ = _fixture_scenario(tmp_path)
    c2 = Config.model_validate({"name": "base", "extra_env": {"MY_VAR": "hello"}})
    with FixtureIsolation(s, c2) as iso:
        settings = json.loads((iso.cfg_dir / "settings.json").read_text())
        assert settings["env"]["MY_VAR"] == "hello"


def test_isolation_oauth_token_reads_claude_code_oauth_token(tmp_path: Path, monkeypatch):
    """The subscription token env var is CLAUDE_CODE_OAUTH_TOKEN (what the claude CLI reads)."""
    monkeypatch.delenv("CLAUDE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-resolved")
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        assert iso.oauth_token == "sk-ant-oat01-resolved"


def test_isolation_writes_v2_plugin_registry(tmp_path: Path):
    """Plugins are registered in CLAUDE_CONFIG_DIR via the v2 installed_plugins.json + a marketplace."""
    plugin_src = tmp_path / "myplugin"
    (plugin_src / ".claude-plugin").mkdir(parents=True)
    (plugin_src / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "myplugin", "version": "9.9.9"}))
    s, _ = _fixture_scenario(tmp_path)
    c = Config.model_validate({"name": "base", "plugin_dirs": [str(plugin_src)]})
    with FixtureIsolation(s, c) as iso:
        reg = json.loads((iso.cfg_dir / "plugins" / "installed_plugins.json").read_text())
        assert reg["version"] == 2
        key = next(k for k in reg["plugins"] if k.startswith("myplugin@"))
        entry = reg["plugins"][key][0]
        assert entry["installPath"] == str(plugin_src)
        assert entry["version"] == "9.9.9"
        markets = json.loads((iso.cfg_dir / "plugins" / "known_marketplaces.json").read_text())
        assert markets  # non-empty mapping
