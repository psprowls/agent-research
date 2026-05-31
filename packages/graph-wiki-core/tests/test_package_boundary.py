from __future__ import annotations

import tomllib
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src" / "graph_wiki_core"
TEST_ROOT = PACKAGE_ROOT / "tests"


def test_core_package_has_no_console_scripts() -> None:
    metadata = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text())

    assert "scripts" not in metadata.get("project", {})


def test_core_source_and_tests_do_not_contain_copied_bytecode_files() -> None:
    stale_artifacts = []
    for root in (SOURCE_ROOT, TEST_ROOT):
        # Pytest may create normal __pycache__ directories while this suite is
        # running. The package-split boundary only forbids copied/checked-in
        # bytecode artifacts that sit outside Python's runtime cache dirs.
        stale_artifacts.extend(
            path.relative_to(PACKAGE_ROOT)
            for path in root.rglob("*.pyc")
            if "__pycache__" not in path.parts
        )

    assert sorted(stale_artifacts) == []


def test_migrated_core_python_source_uses_core_namespace() -> None:
    stale_references = []
    for path in SOURCE_ROOT.rglob("*.py"):
        text = path.read_text()
        old_import_namespace = "graph_wiki" + "_agent"
        old_distribution_name = "graph-wiki" + "-agent"
        if old_import_namespace in text or old_distribution_name in text:
            stale_references.append(path.relative_to(PACKAGE_ROOT))

    assert stale_references == []


def test_core_consumers_do_not_import_old_command_namespace() -> None:
    search_roots = [
        PACKAGE_ROOT,
        REPO_ROOT / "packages" / "eval-harness",
    ]
    stale_imports = []
    for root in search_roots:
        for path in root.rglob("*.py"):
            text = path.read_text()
            needle = "graph_wiki" + "_agent" + ".commands"
            if needle in text:
                stale_imports.append(path.relative_to(REPO_ROOT))

    assert stale_imports == []


def test_query_command_imports_from_core_namespace() -> None:
    import graph_wiki_core.commands.query as query

    assert query.__name__ == "graph_wiki_core.commands.query"
