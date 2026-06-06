"""Static contracts for Typer-created graph CLI command namespaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class WorkspaceArgs(Protocol):
    workspace: Path


class FormatArgs(WorkspaceArgs, Protocol):
    fmt: str


class RepoWorkspaceArgs(WorkspaceArgs, Protocol):
    repo: Path


class UpdateArgs(RepoWorkspaceArgs, Protocol):
    full: bool


class NameArgs(FormatArgs, Protocol):
    name: str


class DepthNameArgs(NameArgs, Protocol):
    depth: int


class OptionalNameArgs(FormatArgs, Protocol):
    name: str | None


class FindArgs(FormatArgs, Protocol):
    name: str | None
    kind: str | None
    in_package: str | None


class DescribeArgs(FormatArgs, Protocol):
    selector: str | None
    kind: str | None
    ecosystem: str | None


class MutableDescribeArgs(DescribeArgs, Protocol):
    name: str
    uri: str
    path: str


class DependencyDescribeArgs(NameArgs, Protocol):
    ecosystem: str | None


class BuiltinDescribeArgs(FormatArgs, Protocol):
    uri: str


class PathDescribeArgs(FormatArgs, Protocol):
    path: str


class ListArgs(FormatArgs, Protocol):
    kind: str | None


class ListScriptsArgs(FormatArgs, Protocol):
    kind: str | None
    owner: str | None


class WhatTestsArgs(FormatArgs, Protocol):
    name: str
    kind: str | None


class DomainArgs(FormatArgs, Protocol):
    name: str


class AnyRunModule(Protocol):
    def run(self, args: Any) -> int:
        ...
