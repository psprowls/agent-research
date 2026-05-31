"""Package split boundary checks for the graph-wiki workspace."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def test_root_workspace_is_packages_only() -> None:
    root_pyproject = _load_toml(ROOT / "pyproject.toml")

    assert root_pyproject["tool"]["uv"]["workspace"]["members"] == ["packages/*"]


def test_obsolete_agents_workspace_tree_is_absent() -> None:
    assert not (ROOT / "agents").exists()


def test_lockfile_does_not_reference_obsolete_agent_package() -> None:
    lock_text = (ROOT / "uv.lock").read_text(encoding="utf-8")

    assert 'name = "graph-wiki-agent"' not in lock_text
    assert "agents/graph-wiki-agent" not in lock_text


def test_obsolete_graph_wiki_agent_namespace_is_not_importable() -> None:
    assert importlib.util.find_spec("graph_wiki_agent") is None


def test_package_metadata_and_entrypoints_are_owned_by_split_packages() -> None:
    cli_pyproject = _load_toml(ROOT / "packages" / "graph-wiki-cli" / "pyproject.toml")
    mcp_pyproject = _load_toml(ROOT / "packages" / "graph-wiki-mcp" / "pyproject.toml")

    assert cli_pyproject["project"]["name"] == "graph-wiki-cli"
    assert cli_pyproject["project"]["scripts"] == {"gw": "graph_wiki_cli.cli:app"}

    assert mcp_pyproject["project"]["name"] == "graph-wiki-mcp"
    assert mcp_pyproject["project"]["scripts"] == {"graph-wiki-mcp": "graph_wiki_mcp.server:main"}
