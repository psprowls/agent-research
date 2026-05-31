"""Smoke tests: package imports."""

from __future__ import annotations


def test_package_imports() -> None:
    import graph_io
    assert graph_io.__version__ == "0.1.0"
