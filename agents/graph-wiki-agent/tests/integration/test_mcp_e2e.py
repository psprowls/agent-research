from __future__ import annotations

"""End-to-end test launching graph-wiki-mcp as a stdio subprocess and exercising all six MCP tools.

Requirements covered: DACLI-01, DACLI-02, DACLI-03.
"""

import io
import json
import os
import select
import subprocess
import threading
import time
from pathlib import Path

import pytest


INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)


# ---------------------------------------------------------------------------
# Subprocess JSON-RPC harness (copied verbatim from test_mcp_stdio.py pattern)
# ---------------------------------------------------------------------------


def _send_initialize() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.0.1"},
        },
    }


def _send_initialized_notification() -> dict:
    return {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}


def _run_server_serial(
    handshake_objs: list[dict],
    tool_call_objs: list[dict],
    timeout: int = 180,
) -> tuple[str, str]:
    r"""Spawn graph-wiki-mcp and exercise tool calls one at a time.

    Unlike a write-all-then-read approach (which lets FastMCP's TaskGroup
    schedule every tool call concurrently and race the vault into
    existence), this helper:
      1. Sends the initialize request + initialized notification together
         (the handshake — order-independent for our assertions).
      2. Sends each subsequent tool call SERIALLY: write one request,
         await the matching id in stdout, then send the next.

    This guarantees `wiki_bootstrap` (id=2) completes before `wiki_scan`
    (id=3) starts, so scan does not race against vault creation (WR-04).
    Stdin stays open until all responses arrive — the MCP server cancels
    all in-flight handlers on stdin-close (mcp 1.27.1
    lowlevel/server.py:690).

    Args:
        handshake_objs: JSON-RPC handshake messages (initialize + initialized).
        tool_call_objs: Tool-call requests, sent and awaited one at a time
                        in list order.
        timeout: Total wall-clock seconds to wait for all responses.
    """
    proc = subprocess.Popen(
        ["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    # Drain stderr in a background thread so it doesn't block.
    stderr_buf = io.BytesIO()

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in iter(lambda: proc.stderr.read(4096), b""):
            stderr_buf.write(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    stdout_lines: list[str] = []
    received_ids: set[int] = set()
    deadline = time.monotonic() + timeout

    def _write(obj: dict) -> None:
        proc.stdin.write((json.dumps(obj) + "\n").encode())
        proc.stdin.flush()

    def _await_id(target_id: int) -> None:
        """Read stdout until a response with id=target_id arrives or we time out."""
        while target_id not in received_ids:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                proc.kill()
                proc.wait()
                pytest.fail(
                    f"Timed out after {timeout}s waiting for id={target_id}.\n"
                    f"stdout so far: {''.join(stdout_lines)[-500:]}\n"
                    f"stderr: {stderr_buf.getvalue().decode()[-500:]}"
                )
            readable, _, _ = select.select([proc.stdout], [], [], min(1.0, remaining))
            if not readable:
                if proc.poll() is not None:
                    return
                continue
            line = proc.stdout.readline()
            if not line:
                return
            decoded = line.decode()
            stdout_lines.append(decoded)
            try:
                obj = json.loads(decoded)
                rid = obj.get("id")
                if rid is not None:
                    received_ids.add(rid)
            except json.JSONDecodeError:
                pass

    # Send handshake: initialize (has id) + initialized notification (no id).
    for obj in handshake_objs:
        _write(obj)
    # Await response to the initialize request specifically (id=1).
    _await_id(1)

    # Send each tool call serially, awaiting its response before the next.
    for obj in tool_call_objs:
        _write(obj)
        _await_id(obj["id"])

    # All expected responses received. Close stdin to signal shutdown.
    proc.stdin.close()

    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    if proc.stdout:
        for line in proc.stdout:
            stdout_lines.append(line.decode())

    stderr_thread.join(timeout=5)
    return "".join(stdout_lines), stderr_buf.getvalue().decode()


# ---------------------------------------------------------------------------
# Per-tool payload builders (arguments nested under "input" param — Pydantic shape)
# ---------------------------------------------------------------------------


def _send_wiki_bootstrap(request_id: int, workspace_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_bootstrap",
            "arguments": {"input": {
                "topic": "test repo",
                "tool": "claude-code",
                "workspace_path": workspace_path,
            }},
        },
    }


def _send_wiki_scan(request_id: int, workspace_path: str, repo_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_scan",
            "arguments": {"input": {
                "workspace_path": workspace_path,
                "repo_path": repo_path,
                "max_depth": 2,
            }},
        },
    }


def _send_wiki_ingest(request_id: int, source_path: str, workspace_path: str) -> dict:
    # WikiIngestInput uses type="source" and source_path (not op/path)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_ingest",
            "arguments": {"input": {
                "type": "source",
                "source_path": source_path,
                "workspace_path": workspace_path,
            }},
        },
    }


def _send_wiki_query(request_id: int, query: str, workspace_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_query",
            "arguments": {"input": {
                "query": query,
                "workspace_path": workspace_path,
                "top_k": 3,
            }},
        },
    }


def _send_wiki_lint(request_id: int, workspace_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_lint",
            "arguments": {"input": {
                "workspace_path": workspace_path,
            }},
        },
    }


def _send_wiki_log(request_id: int, workspace_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_log",
            "arguments": {"input": {
                "op": "note",
                "title": "e2e test entry",
                "detail": "smoke",
                "workspace_path": workspace_path,
            }},
        },
    }


# ---------------------------------------------------------------------------
# Seed helper: create a minimal uv workspace under tmp_path
# ---------------------------------------------------------------------------


def _seed_minimal_workspace(tmp_path: Path) -> Path:
    """Seed tmp_path with a minimal uv workspace + one source file so wiki_scan/wiki_ingest have material."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "e2e-test-root"\nversion = "0.0.1"\n'
        '[tool.uv.workspace]\nmembers = ["packages/alpha"]\n'
    )
    pkg = tmp_path / "packages" / "alpha"
    (pkg / "src" / "alpha").mkdir(parents=True)
    (pkg / "pyproject.toml").write_text('[project]\nname = "alpha"\nversion = "0.0.1"\n')
    sample = pkg / "src" / "alpha" / "sample.py"
    sample.write_text('"""Alpha sample module."""\n\ndef hello() -> str:\n    return "alpha"\n')
    return sample


# ---------------------------------------------------------------------------
# End-to-end test
# ---------------------------------------------------------------------------


@INTEGRATION_GATE
def test_all_six_tools_end_to_end(tmp_path: Path) -> None:
    """All six MCP tools round-trip through the real stdio subprocess against a seeded tmp_path vault.

    Covers DACLI-01 (subprocess launch), DACLI-02 (all 6 tools, non-error), DACLI-03 (gated).
    """
    sample = _seed_minimal_workspace(tmp_path)
    vault = tmp_path / "wiki"

    handshake = [
        _send_initialize(),
        _send_initialized_notification(),
    ]
    # WR-04: send each tool call serially. FastMCP runs tool handlers in a
    # TaskGroup; queueing them all at once lets wiki_scan/wiki_ingest race
    # wiki_bootstrap's vault creation. Sending one-at-a-time and awaiting each
    # response guarantees ordering.
    tool_calls = [
        _send_wiki_bootstrap(2, str(vault)),
        _send_wiki_scan(3, str(vault), str(tmp_path)),         # repo_path = tmp_path (NEW FIELD)
        _send_wiki_ingest(4, str(sample), str(vault)),
        _send_wiki_query(5, "What is alpha?", str(vault)),
        _send_wiki_lint(6, str(vault)),
        _send_wiki_log(7, str(vault)),
    ]

    stdout, stderr = _run_server_serial(handshake, tool_calls)

    # Parse response lines only (filter out notifications which have no "id")
    responses = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if parsed.get("id") is not None:
            responses.append(parsed)

    for req_id in (2, 3, 4, 5, 6, 7):
        resp = next((r for r in responses if r.get("id") == req_id), None)
        assert resp is not None, f"No response for id={req_id}.\nstderr tail: {stderr[-500:]}"
        assert "result" in resp, f"id={req_id}: missing result: {resp!r}"
        assert resp["result"].get("isError") is False, (
            f"id={req_id} flagged isError=True. result={resp['result']!r}\nstderr tail: {stderr[-500:]}"
        )
