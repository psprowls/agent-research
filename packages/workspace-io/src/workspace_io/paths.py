"""Pure path accessors over a resolved workspace path.

Callers obtain the workspace from `workspace_io.config.resolve()`
and pass `.workspace` here. These functions do no I/O — they only
compose paths.
"""
from __future__ import annotations
from pathlib import Path


def manifest_path(workspace: Path) -> Path:
    return Path(workspace) / ".graph-wiki.yaml"


def wiki_dir(workspace: Path) -> Path:
    return Path(workspace) / "wiki"


def raw_dir(workspace: Path) -> Path:
    return Path(workspace) / "raw"


def work_dir(workspace: Path) -> Path:
    return Path(workspace) / "work"


def knowledge_dir(workspace: Path) -> Path:
    return Path(workspace) / "knowledge"


def graph_dir(workspace: Path) -> Path:
    return Path(workspace) / ".graph"
