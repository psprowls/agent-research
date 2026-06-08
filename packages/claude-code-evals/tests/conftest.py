import pytest


@pytest.fixture(autouse=True)
def _disable_stderr_logging_by_default(monkeypatch):
    """Disable stderr logging for tests by default to keep output clean."""
    monkeypatch.setenv("CLAUDE_EVAL_STDERR", "0")
