from __future__ import annotations

import tomllib
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src" / "graph_wiki_core"


def test_core_package_has_no_console_scripts() -> None:
    metadata = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text())

    assert "scripts" not in metadata.get("project", {})


def test_core_source_does_not_contain_copied_bytecode_files() -> None:
    stale_artifacts = [
        path.relative_to(PACKAGE_ROOT)
        for path in SOURCE_ROOT.rglob("*.pyc")
        if "__pycache__" not in path.parts
    ]

    assert stale_artifacts == []


def test_migrated_python_source_uses_core_namespace() -> None:
    stale_references = []
    for path in SOURCE_ROOT.rglob("*.py"):
        text = path.read_text()
        if "graph_wiki_agent" in text or "graph-wiki-agent" in text:
            stale_references.append(path.relative_to(PACKAGE_ROOT))

    assert stale_references == []


def test_query_command_imports_from_core_namespace() -> None:
    import graph_wiki_core.commands.query as query

    assert query.__name__ == "graph_wiki_core.commands.query"
