"""Executable-boundary tests for wiki_io library modules."""

from __future__ import annotations

import importlib
import inspect

LIBRARY_ONLY_MODULES = [
    "wiki_io.update_index",
    "wiki_io.update_tokens",
    "wiki_io.append_log",
    "wiki_io.init_vault",
    "wiki_io.ingest_source",
    "wiki_io.wiki_search",
    "wiki_io.lint_wiki",
    "wiki_io.graph_analyzer",
]


def test_wiki_io_boundary_modules_do_not_export_main() -> None:
    for module_name in LIBRARY_ONLY_MODULES:
        module = importlib.import_module(module_name)
        assert not hasattr(module, "main"), f"{module_name} must not expose an executable main()"


def test_wiki_io_boundary_modules_have_no_main_guard() -> None:
    for module_name in LIBRARY_ONLY_MODULES:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        assert 'if __name__ == "__main__"' not in source
        assert "if __name__ == '__main__'" not in source


def test_wiki_io_boundary_modules_do_not_import_argparse() -> None:
    for module_name in LIBRARY_ONLY_MODULES:
        module = importlib.import_module(module_name)
        source = inspect.getsource(module)
        assert "import argparse" not in source, f"{module_name} should not own CLI parsing"
