"""Pydantic v2 data models for scenario, config, runset, and verifier configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Discriminator(BaseModel):
    """Per-scenario verdict type for three-arm eval.

    Attributes:
        type: One of 'correctness-gated', 'efficiency-gated', 'impossible-without-wiki'.
        metric: For efficiency-gated only; metric to compare (e.g. 'files_read_count').
        min_improvement_pct: For efficiency-gated only; wiki arm must beat base by this %.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["correctness-gated", "efficiency-gated", "impossible-without-wiki"]
    metric: str | None = None
    min_improvement_pct: float | None = None


class VerifyEntry(BaseModel):
    """A single verification step: script, golden patch, or LLM-judged rubric."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["script", "golden", "rubric"]
    path: str
    judge: str | None = None
    pass_threshold: float | None = None


class Budgets(BaseModel):
    """Token and time budgets for a scenario run."""

    model_config = ConfigDict(extra="forbid")

    max_turns: int = 20
    max_input_tokens: int = 100000
    max_wall_seconds: int = 300


class MetricsConfig(BaseModel):
    """Metrics collection flags."""

    model_config = ConfigDict(extra="forbid")

    tool_shape: bool = True
    judge_qualitative: bool = False


class Scenario(BaseModel):
    """A single evaluation scenario: environment, task, verification."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    isolation_mode: Literal["worktree", "fixture"] = "worktree"
    target_repo: str | None = None
    baseline_sha: str | None = None
    fixture_dir: str | None = None
    configs: list[str] = []
    mode: Literal["headless", "interactive"] = "headless"
    eval_mode: Literal["qa", "implement"] = "qa"
    auto_user: str | None = None
    preflight: str | None = None
    verify: list[VerifyEntry] = []
    metrics: MetricsConfig = MetricsConfig()
    budgets: Budgets = Budgets()
    discriminator: Discriminator | None = None
    inject: list[str] = Field(default_factory=list)

    @field_validator("discriminator", mode="before")
    @classmethod
    def validate_discriminator(cls, v: Any) -> Discriminator | None:
        """Convert dict to Discriminator using Pydantic validation."""
        if v is None:
            return None
        if isinstance(v, Discriminator):
            return v
        return Discriminator.model_validate(v)

    @model_validator(mode="after")
    def _check_isolation(self) -> "Scenario":
        """Enforce mode-specific requirements."""
        if self.isolation_mode == "worktree":
            if not self.target_repo:
                raise ValueError("worktree mode requires target_repo")
            if not self.baseline_sha:
                raise ValueError("worktree mode requires baseline_sha")
        else:
            if not self.fixture_dir:
                raise ValueError("fixture mode requires fixture_dir")
        return self

    @model_validator(mode="after")
    def _check_interactive(self) -> "Scenario":
        """Forbid auto_user in interactive mode."""
        if self.mode == "interactive" and self.auto_user:
            raise ValueError("interactive mode forbids auto_user")
        return self

    @classmethod
    def from_path(cls, path: Path) -> "Scenario":
        """Load scenario from YAML file."""
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))


class Config(BaseModel):
    """Configuration for a Claude Code agent: model, environment, plugins."""

    model_config = ConfigDict(extra="forbid")

    name: str
    plugin_dirs: list[str] = []
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.0
    extra_env: dict[str, str] = Field(default_factory=dict)
    extra_settings: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_path(cls, path: Path) -> "Config":
        """Load config from YAML file."""
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))


class Runset(BaseModel):
    """A set of scenarios to run together, with shared defaults."""

    model_config = ConfigDict(extra="forbid")

    name: str
    scenarios: list[str] = []
    default_configs: list[str] = []

    @classmethod
    def from_path(cls, path: Path) -> "Runset":
        """Load runset from YAML file."""
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))


class AutoUser(BaseModel):
    """Configuration for the auto-user agent in headless mode."""

    model_config = ConfigDict(extra="forbid")

    model: str = "claude-haiku-4-5-20251001"
    max_replies: int = 5
    stop_on: str = "<DONE>"
    system_prompt: str = "Drive the task forward. Say <DONE> when the task is complete."

    @classmethod
    def from_path(cls, path: Path) -> "AutoUser":
        """Load AutoUser config from YAML file."""
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))
