from __future__ import annotations

from importlib.metadata import entry_points


def test_graph_wiki_mcp_distribution_owns_console_script() -> None:
    console_scripts = entry_points(group="console_scripts")
    matching = [script for script in console_scripts if script.name == "graph-wiki-mcp"]

    assert matching, "graph-wiki-mcp console script is not installed"
    assert {script.value for script in matching} == {"graph_wiki_mcp.server:main"}
