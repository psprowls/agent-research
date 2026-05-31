from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def test_graph_wiki_mcp_distribution_owns_console_script() -> None:
    console_scripts = entry_points(group="console_scripts")
    matching = [script for script in console_scripts if script.name == "graph-wiki-mcp"]

    assert matching, "graph-wiki-mcp console script is not installed"
    assert {script.value for script in matching} == {"graph_wiki_mcp.server:main"}


def test_mcp_package_has_no_stale_agent_mcp_references() -> None:
    stale_import = "_".join(("graph", "wiki", "agent")) + "." + "mcp"
    stale_subprocess = " ".join(("uv", "run", "--package", "graph-wiki-agent", "graph-wiki-mcp"))
    forbidden_strings = (stale_import, stale_subprocess)
    scanned_suffixes = {".py", ".toml"}

    offenders: list[str] = []
    for path in sorted(PACKAGE_ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in scanned_suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        for forbidden in forbidden_strings:
            if forbidden in text:
                offenders.append(f"{path.relative_to(PACKAGE_ROOT)} contains {forbidden!r}")

    assert offenders == []
