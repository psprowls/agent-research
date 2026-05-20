from __future__ import annotations

"""init command — bootstrap a wiki vault structure.

Public API:
    InitResult    -- Dataclass mirroring the dict keys returned by init_wiki()
    run_init()    -- Async wrapper: resolves workspace, calls init_wiki, returns InitResult

Creates <workspace>/wiki/ vault structure plus <workspace>/raw/ and <workspace>/work/
sibling directories (Phase 5 workspace init, formerly pending).
"""

import importlib.metadata
import logging
from dataclasses import dataclass, field
from pathlib import Path

from vault_io._workspace import resolve_wiki_and_repo
from vault_io.init_vault import init_wiki
from workspace_io import init as _ws_init

logger = logging.getLogger(__name__)


@dataclass
class InitResult:
    """Result returned by run_init(), mirroring the dict keys from init_wiki()."""

    status: str
    wiki_path: str
    repo_path: str
    topic: str
    tool: str
    date: str
    installed_files: list
    page_templates_copied: int
    layers: dict
    raw_path: str
    work_path: str


async def run_init(
    topic: str,
    tool: str,
    force: bool,
    vault_path: Path | None = None,
) -> InitResult:
    """Bootstrap a wiki vault structure.

    Args:
        topic: Short description of the repository (e.g. "my-project").
        tool: Which schema file(s) to install (claude-code, codex, cursor, all, ...).
        force: If True, overwrite non-empty wiki directory.
        vault_path: Explicit vault path; if None, reads GRAPH_WIKI_WORKSPACE env var.

    Returns:
        InitResult with fields populated from init_wiki's return dict.

    Raises:
        RuntimeError: If wiki creation fails.
    """
    # Phase 1 (D-07): bootstrap the workspace shell — creates the workspace
    # directory, writes `.graph-wiki.yaml`, ensures `.graph-wiki.local.yaml`
    # is gitignored, and registers `graph-wiki-agent` as a plugin entry
    # (D-12: installed_version == applied_version, sourced from
    # importlib.metadata per D-13).
    repo_root = vault_path.parent if vault_path is not None else Path.cwd()
    _ws_init(
        repo_root,
        plugin="graph-wiki-agent",
        version=importlib.metadata.version("graph-wiki-agent"),
    )

    # Phase 2: existing vault-io resolution + wiki tree population.
    wiki, repo = resolve_wiki_and_repo(vault_path)
    if repo is None:
        repo = Path.cwd()
    logger.debug("run_init: wiki=%s repo=%s topic=%r tool=%r force=%r", wiki, repo, topic, tool, force)
    result = init_wiki(
        wiki_path=wiki,
        repo_path=repo,
        topic=topic,
        tool=tool,
        force=force,
        non_interactive=True,
        as_json=False,  # MCP safety: as_json=True emits print(json.dumps(...)) which trips _StdoutGuard
    )
    return InitResult(
        status=result["status"],
        wiki_path=result["wiki_path"],
        repo_path=result["repo_path"],
        topic=result["topic"],
        tool=result["tool"],
        date=result["date"],
        installed_files=result["installed_files"],
        page_templates_copied=result["page_templates_copied"],
        layers=result["layers"],
        raw_path=result["raw_path"],
        work_path=result["work_path"],
    )
