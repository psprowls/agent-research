"""Pydantic v2 data models for scenario, config, runset, and verifier configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


@dataclass
class Discriminator:
    """Discriminator to filter scenarios based on correctness, efficiency, or wiki availability."""

    type: Literal["correctness-gated", "efficiency-gated", "impossible-without-wiki"]
    metric: str | None = None
    min_improvement_pct: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Discriminator":
        """Create Discriminator from a dictionary (e.g., from YAML)."""
        return cls(
            type=data["type"],
            metric=data.get("metric"),
            min_improvement_pct=data.get("min_improvement_pct"),
        )


class OrderStep(BaseModel):
    """One step of an ordering assertion: a tool plus param regexes."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    params: dict[str, str] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def _compile_regexes(cls, v: dict[str, str]) -> dict[str, str]:
        for name, pattern in v.items():
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex for param {name!r}: {exc}") from exc
        return v


class ToolAssertion(BaseModel):
    """One tool-call assertion: presence/count/absence on a tool, or an ordering constraint."""

    model_config = ConfigDict(extra="forbid")

    tool: str | None = None
    params: dict[str, str] = Field(default_factory=dict)
    min_count: int | None = Field(default=None, ge=0)
    max_count: int | None = Field(default=None, ge=0)
    absent: bool = False
    include_subagents: bool = False
    order: list[OrderStep] | None = None

    @field_validator("params")
    @classmethod
    def _compile_regexes(cls, v: dict[str, str]) -> dict[str, str]:
        for name, pattern in v.items():
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex for param {name!r}: {exc}") from exc
        return v

    @model_validator(mode="after")
    def _check_shape(self) -> "ToolAssertion":
        if self.order is not None:
            if (
                self.tool is not None
                or self.params
                or self.min_count is not None
                or self.max_count is not None
                or self.absent
            ):
                raise ValueError("order assertions cannot combine with tool/params/counts/absent")
            if not self.order:
                raise ValueError("order must contain at least one step")
        else:
            if self.tool is None:
                raise ValueError("assertion requires either tool or order")
            if self.absent and (self.min_count is not None or self.max_count is not None):
                raise ValueError("absent: true cannot combine with min_count/max_count")
            if self.min_count is not None and self.max_count is not None and self.min_count > self.max_count:
                raise ValueError("min_count cannot exceed max_count")
        return self


class VerifyEntry(BaseModel):
    """A single verification step: script, golden patch, LLM-judged rubric, or tool-call assertions."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["script", "golden", "rubric", "tools"]
    path: str | None = None
    judge: str | None = None
    pass_threshold: float | None = None
    assertions: list[ToolAssertion] | None = None

    @model_validator(mode="after")
    def _check_kind_fields(self) -> "VerifyEntry":
        if self.kind == "tools":
            if not self.assertions:
                raise ValueError("kind: tools requires assertions")
            if self.path is not None:
                raise ValueError("kind: tools does not use path")
        else:
            if self.path is None:
                raise ValueError(f"kind: {self.kind} requires path")
            if self.assertions is not None:
                raise ValueError("assertions are only valid for kind: tools")
        return self


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


class TriggerMatch(BaseModel):
    """Pattern for a trigger: exactly one of contains or regex must be set."""

    model_config = ConfigDict(extra="forbid")

    contains: str | None = None
    regex: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "TriggerMatch":
        if (self.contains is None) == (self.regex is None):
            raise ValueError("trigger match must set exactly one of contains/regex")
        return self


class Trigger(BaseModel):
    """A rule-based trigger: if match fires, reply with the given text."""

    model_config = ConfigDict(extra="forbid")

    match: TriggerMatch
    reply: str


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
        """Convert discriminator dict to Discriminator object."""
        if v is None:
            return None
        if isinstance(v, dict):
            return Discriminator.from_dict(v)
        return v

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

    model: str | None = Field(
        default=None,
        description=(
            "Bedrock model id override for the user_simulator role; None uses the role default from models.toml."
        ),
    )
    max_replies: int = 5
    stop_on: str = "<DONE>"
    system_prompt: str = "Drive the task forward. Say <DONE> when the task is complete."
    triggers: list[Trigger] = Field(default_factory=list)
    default_reply: str = "proceed"
    abort_on_default_after: int = Field(default=2, ge=1)

    @classmethod
    def from_path(cls, path: Path) -> "AutoUser":
        """Load AutoUser config from YAML file."""
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))
