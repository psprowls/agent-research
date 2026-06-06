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
    # work/ lives UNDER the wiki so [[work/foo]] resolves against the wiki
    # root identically to [[concepts/foo]] (single vault-relative base).
    return wiki_dir(workspace) / "work"


def knowledge_dir(workspace: Path) -> Path:
    return Path(workspace) / "knowledge"


def graph_dir(workspace: Path) -> Path:
    """The consolidated local-artifacts directory at the workspace root.

    Holds all uncommitted graph-wiki machine state: the code graph DB
    (`code.db` + `cache/`), subagent `traces/`, and the search index
    (`bm25/`, `search.db`). Gitignored wholesale. Distinct from the
    committed `.graph-wiki.yaml` manifest (see `manifest_path`).
    """
    return Path(workspace) / ".graph-wiki"
