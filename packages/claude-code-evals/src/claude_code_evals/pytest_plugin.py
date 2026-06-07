"""Pytest plugin for claude-code-evals."""

from __future__ import annotations


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "eval: mark test as requiring CLAUDE_CODE_RUN_EVALS=1")
    config.addinivalue_line("markers", "integration: mark test as requiring subprocess/real claude binary")
