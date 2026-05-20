"""Unit tests for the _StdoutGuard sentinel and basic server module wiring.

These tests must NOT permanently break pytest's stdout capture. Each test
that touches sys.stdout uses monkeypatch so the original interpreter stdout
is restored on teardown.
"""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(autouse=True)
def _restore_stdout(monkeypatch):
    """Snapshot sys.stdout before each test; monkeypatch restores it after."""
    monkeypatch.setattr(sys, "stdout", sys.stdout)
    yield


def test_stdout_guard_raises_on_nonempty_write():
    from graph_wiki_mcp.server import _StdoutGuard

    guard = _StdoutGuard()
    with pytest.raises(RuntimeError) as exc_info:
        guard.write("oops")
    msg = str(exc_info.value)
    assert "Illegal stdout write" in msg
    assert "oops" in msg


def test_stdout_guard_tolerates_empty_and_whitespace():
    from graph_wiki_mcp.server import _StdoutGuard

    guard = _StdoutGuard()
    # All three are whitespace-only; none must raise. Each returns len(data).
    assert guard.write("") == 0
    assert guard.write("\n") == 1
    assert guard.write("   ") == 3


def test_stdout_guard_flush_is_noop():
    from graph_wiki_mcp.server import _StdoutGuard

    guard = _StdoutGuard()
    # Must not raise; return value is None (no-op).
    assert guard.flush() is None


def test_server_module_exposes_mcp_and_main():
    from graph_wiki_mcp import server

    assert hasattr(server, "mcp")
    assert hasattr(server, "main")
    assert callable(server.main)
    # FastMCP 1.27.1 exposes the name via the `.name` attribute.
    assert server.mcp.name == "graph-wiki-mcp"


def test_wiki_ping_returns_pong():
    from graph_wiki_mcp import server

    result = server.wiki_ping(server.PingInput(message="hello"))
    assert result.status == "pong"
    assert result.echo == "hello"
