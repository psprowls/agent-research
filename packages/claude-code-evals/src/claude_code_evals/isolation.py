"""Workspace isolation: WorktreeIsolation (git worktree) and FixtureIsolation (directory copy)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from claude_code_evals.schemas import Config, Scenario


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
        """OAuth token from environment, or None."""
        return os.environ.get("CLAUDE_OAUTH_TOKEN")

    @property
    def meta_path(self) -> Path:
        """Path to meta.json."""
        return self.cfg_dir / "meta.json"

    def _setup_cfg_dir(self) -> None:
        """Create and populate .claude/ config directory."""
        assert self._tmp is not None
        self._cfg = Path(self._tmp) / "cfg"
        self._cfg.mkdir(parents=True)

        # Symlink each plugin_dir into cfg/plugins/
        plugins_dir = self._cfg / "plugins"
        plugins_dir.mkdir()
        evals_root = Path.cwd()
        for plugin_dir_str in self._config.plugin_dirs:
            pd = Path(plugin_dir_str)
            if not pd.is_absolute():
                pd = (evals_root / pd).resolve()
            link = plugins_dir / pd.name
            link.symlink_to(pd)

        # Write installed_plugins.json + known_marketplaces.json
        installed = [Path(pd_str).name for pd_str in self._config.plugin_dirs]
        (self._cfg / "installed_plugins.json").write_text(json.dumps({"plugins": installed}, indent=2))
        (self._cfg / "known_marketplaces.json").write_text(json.dumps([]))

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
        return self

    def __exit__(self, *_: object) -> None:
        """Remove git worktree and clean up tmpdir."""
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
        return self

    def __exit__(self, *_: object) -> None:
        """Clean up tmpdir (unless keep=True)."""
        self._cleanup()
