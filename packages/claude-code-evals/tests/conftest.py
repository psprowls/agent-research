"""Pytest configuration for claude-code-evals tests."""

import pytest
from claude_code_evals.stderr_logger import set_logger_enabled


@pytest.fixture(autouse=True)
def reset_logger_state():
    """Reset logger global state before each test."""
    set_logger_enabled(True)
    yield
    # Cleanup after test
    set_logger_enabled(True)
