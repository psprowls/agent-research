"""Workspace isolation: WorktreeIsolation (git worktree) and FixtureIsolation (directory copy)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

from claude_code_evals.schemas import Config, Scenario
from claude_code_evals.stderr_logger import EvalLogger


@runtime_checkable
class IsolationContext(Protocol):
    """Protocol for isolation context managers (WorktreeIsolation, FixtureIsolation)."""

    @property
    def worktree_path(self) -> Path:
        """Path to the isolated working directory (copy or git worktree)."""
        ...

    @property
    def cfg_dir(self) -> Path:
        """Path to the Claude Code config directory (.claude/)."""
        ...

    @property
    def oauth_token(self) -> str | None:
        """OAuth token from CLAUDE_OAUTH_TOKEN env var, or None."""
        ...

    @property
    def meta_path(self) -> Path:
        """Path to meta.json (scenario/config metadata)."""
        ...

    def __enter__(self) -> IsolationContext: ...

    def __exit__(self, *_: object) -> None: ...


class _BaseIsolation:
    """Base class for isolation contexts."""

    def __init__(self, scenario: Scenario, config: Config, *, keep: bool = False) -> None:
        self._scenario = scenario
        self._config = config
        self._keep = keep
        self._tmp: str | None = None
        self._wt: Path | None = None
        self._cfg: Path | None = None

    @property
    def worktree_path(self) -> Path:
        """Path to the isolated working directory."""
        assert self._wt is not None
        return self._wt

    @property
    def cfg_dir(self) -> Path:
        """Path to the Claude Code config directory."""
        assert self._cfg is not None
        return self._cfg

    @property
    def oauth_token(self) -> str | None:
        """Subscription OAuth token from environment, or None.

        ``CLAUDE_CODE_OAUTH_TOKEN`` (minted via ``claude setup-token``) is what the claude CLI
        reads and what bills the subscription rather than API credits.
        """
        return os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")

    @property
    def meta_path(self) -> Path:
        """Path to meta.json."""
        return self.cfg_dir / "meta.json"

    def _setup_cfg_dir(self) -> None:
        """Create and populate .claude/ config directory."""
        assert self._tmp is not None
        self._cfg = Path(self._tmp) / "cfg"
        self._cfg.mkdir(parents=True)

        # Register each plugin_dir under cfg/plugins/ (CLAUDE_CONFIG_DIR fully replaces ~/.claude,
        # so any marketplace/registry that lives there is invisible — recreate the minimal one).
        plugins_dir = self._cfg / "plugins"
        plugins_dir.mkdir()
        evals_root = Path.cwd()
        resolved_dirs: list[Path] = []
        for plugin_dir_str in self._config.plugin_dirs:
            pd = Path(plugin_dir_str)
            if not pd.is_absolute():
                pd = (evals_root / pd).resolve()
            resolved_dirs.append(pd)
            link = plugins_dir / pd.name
            link.symlink_to(pd)
        self._write_plugin_registry(plugins_dir, resolved_dirs)

        # Build settings.json
        settings: dict = {
            "permissions": {"defaultMode": "acceptEdits"},
        }
        if self._config.extra_env:
            settings["env"] = dict(self._config.extra_env)
        settings.update(self._config.extra_settings)
        (self._cfg / "settings.json").write_text(json.dumps(settings, indent=2))

        # Write meta.json
        meta = {
            "scenario": self._scenario.name,
            "config": self._config.name,
            "model": self._config.model,
        }
        self.meta_path.write_text(json.dumps(meta, indent=2))

    def _write_plugin_registry(self, plugins_dir: Path, resolved_dirs: list[Path]) -> None:
        """Write v2 installed_plugins.json + known_marketplaces.json pointing at the live plugin trees.

        Each plugin is registered under a synthetic ``local`` marketplace; ``installPath`` points at
        the resolved source dir so Claude Code loads it directly (no marketplace fetch needed).
        """
        now = datetime.now(timezone.utc).isoformat()
        installed: dict = {"version": 2, "plugins": {}}
        for pd in resolved_dirs:
            plugin_json = pd / ".claude-plugin" / "plugin.json"
            try:
                version = json.loads(plugin_json.read_text()).get("version", "local")
            except Exception:
                version = "local"
            installed["plugins"][f"{pd.name}@local"] = [
                {
                    "scope": "user",
                    "installPath": str(pd),
                    "version": version,
                    "installedAt": now,
                    "lastUpdated": now,
                }
            ]
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(installed, indent=2))

        known_marketplaces = {
            "local": {
                "source": {"source": "directory", "path": str(Path.cwd())},
                "installLocation": str(Path.cwd()),
                "lastUpdated": now,
            }
        }
        (plugins_dir / "known_marketplaces.json").write_text(json.dumps(known_marketplaces, indent=2))

    def _cleanup(self) -> None:
        """Clean up temporary directory (unless keep=True)."""
        if self._tmp and not self._keep:
            shutil.rmtree(Path(self._tmp), ignore_errors=True)


class WorktreeIsolation(_BaseIsolation):
    """Git worktree isolation: checks out baseline_sha in a fresh tmpdir."""

    def __enter__(self) -> WorktreeIsolation:
        """Create git worktree at baseline_sha."""
        self._tmp = tempfile.mkdtemp(prefix="cc-eval-wt-")
        self._wt = Path(self._tmp) / "wt"

        target_repo = Path(self._scenario.target_repo).expanduser()  # type: ignore[arg-type]
        sha = self._scenario.baseline_sha
        if sha is None:
            raise ValueError("WorktreeIsolation requires baseline_sha to be set")

        subprocess.run(
            ["git", "worktree", "add", "--detach", str(self._wt), sha],
            cwd=str(target_repo),
            check=True,
            capture_output=True,
        )

        self._setup_cfg_dir()
        logger = EvalLogger("fixture_worktree_setup")
        logger.log_dict(
            "Worktree isolation created",
            {
                "scenario": self._scenario.name,
                "config": self._config.name,
                "worktree_path": str(self.worktree_path),
                "baseline_sha": self._scenario.baseline_sha,
                "isolation_mode": "worktree",
            },
        )
        return self

    def __exit__(self, *_: object) -> None:
        """Remove git worktree and clean up tmpdir."""
        logger = EvalLogger("fixture_worktree_teardown")
        logger.log("Worktree isolation cleaning up", scenario=self._scenario.name)
        if self._wt and self._wt.exists():
            target_repo = Path(self._scenario.target_repo).expanduser()  # type: ignore[arg-type]
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self._wt)],
                cwd=str(target_repo),
                capture_output=True,
            )
        self._cleanup()


class FixtureIsolation(_BaseIsolation):
    """Fixture directory isolation: copies fixture_dir into a fresh tmpdir."""

    def __enter__(self) -> FixtureIsolation:
        """Copy fixture_dir into a fresh tmpdir."""
        self._tmp = tempfile.mkdtemp(prefix="cc-eval-fix-")
        fixture_src = Path(self._scenario.fixture_dir)  # type: ignore[arg-type]
        self._wt = Path(self._tmp) / "wt"
        shutil.copytree(fixture_src, self._wt)
        self._setup_cfg_dir()
        logger = EvalLogger("fixture_copy_setup")
        logger.log_dict(
            "Fixture isolation created",
            {
                "scenario": self._scenario.name,
                "config": self._config.name,
                "fixture_path": str(self.worktree_path),
                "isolation_mode": "fixture",
            },
        )
        return self

    def __exit__(self, *_: object) -> None:
        """Clean up tmpdir (unless keep=True)."""
        logger = EvalLogger("fixture_copy_teardown")
        logger.log("Fixture isolation cleaning up", scenario=self._scenario.name)
        self._cleanup()
