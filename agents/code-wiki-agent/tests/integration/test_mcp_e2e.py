from __future__ import annotations

"""End-to-end test launching code-wiki-mcp as a stdio subprocess and exercising all six MCP tools.

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
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
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


def _run_server_long(payload_objs: list[dict], expected_ids: set[int], timeout: int = 180) -> tuple[str, str]:
    """Spawn code-wiki-mcp and collect responses for all expected request IDs.

    Unlike communicate(), this helper keeps stdin open while reading stdout so that
    in-flight Bedrock calls are not cancelled when stdin EOF is detected.
    The MCP server cancels all in-flight handlers on stdin-close (mcp 1.27.1
    lowlevel/server.py:690), so stdin must stay open until all expected responses arrive.

    Args:
        payload_objs: JSON-RPC messages to send.
        expected_ids: Set of request IDs we expect responses for. Stdin closes only
                      after all IDs have a response (or timeout is hit).
        timeout: Total wall-clock seconds to wait for all responses.
    """
    payload = "\n".join(json.dumps(obj) for obj in payload_objs) + "\n"
    proc = subprocess.Popen(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Send all requests to stdin then KEEP stdin open (don't close yet).
    assert proc.stdin is not None
    proc.stdin.write(payload.encode())
    proc.stdin.flush()

    # Drain stderr in a background thread so it doesn't block.
    stderr_buf = io.BytesIO()

    def _drain_stderr() -> None:
        assert proc.stderr is not None
        for chunk in iter(lambda: proc.stderr.read(4096), b""):
            stderr_buf.write(chunk)

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    # Read stdout lines until all expected IDs are answered or timeout.
    assert proc.stdout is not None
    stdout_lines: list[str] = []
    received_ids: set[int] = set()
    deadline = time.monotonic() + timeout

    while received_ids < expected_ids:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            proc.kill()
            proc.wait()
            pytest.fail(
                f"Timed out after {timeout}s waiting for responses to ids "
                f"{expected_ids - received_ids}.\n"
                f"stdout so far: {''.join(stdout_lines)[-500:]}\n"
                f"stderr: {stderr_buf.getvalue().decode()[-500:]}"
            )

        # Non-blocking line read with a short poll interval.
        readable, _, _ = select.select([proc.stdout], [], [], min(1.0, remaining))
        if not readable:
            # Check if process died
            if proc.poll() is not None:
                break
            continue

        line = proc.stdout.readline()
        if not line:
            break  # stdout closed — process likely dead
        decoded = line.decode()
        stdout_lines.append(decoded)
        try:
            obj = json.loads(decoded)
            rid = obj.get("id")
            if rid is not None:
                received_ids.add(rid)
        except json.JSONDecodeError:
            pass

    # All expected responses received (or process died). Close stdin to signal shutdown.
    proc.stdin.close()

    # Wait for process to finish and collect any remaining stdout lines.
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    # Drain any remaining stdout after process exits.
    if proc.stdout:
        for line in proc.stdout:
            stdout_lines.append(line.decode())

    stderr_thread.join(timeout=5)
    return "".join(stdout_lines), stderr_buf.getvalue().decode()


# ---------------------------------------------------------------------------
# Per-tool payload builders (arguments nested under "input" param — Pydantic shape)
# ---------------------------------------------------------------------------


def _send_wiki_init(request_id: int, vault_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_init",
            "arguments": {"input": {
                "topic": "test repo",
                "tool": "claude-code",
                "vault_path": vault_path,
            }},
        },
    }


def _send_wiki_scan(request_id: int, vault_path: str, repo_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_scan",
            "arguments": {"input": {
                "vault_path": vault_path,
                "repo_path": repo_path,
                "max_depth": 2,
            }},
        },
    }


def _send_wiki_ingest(request_id: int, source_path: str, vault_path: str) -> dict:
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
                "vault_path": vault_path,
            }},
        },
    }


def _send_wiki_query(request_id: int, query: str, vault_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_query",
            "arguments": {"input": {
                "query": query,
                "vault_path": vault_path,
                "top_k": 3,
            }},
        },
    }


def _send_wiki_lint(request_id: int, vault_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_lint",
            "arguments": {"input": {
                "vault_path": vault_path,
            }},
        },
    }


def _send_wiki_log(request_id: int, vault_path: str) -> dict:
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
                "vault_path": vault_path,
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

    payloads = [
        _send_initialize(),
        _send_initialized_notification(),
        _send_wiki_init(2, str(vault)),
        _send_wiki_scan(3, str(vault), str(tmp_path)),         # repo_path = tmp_path (NEW FIELD)
        _send_wiki_ingest(4, str(sample), str(vault)),
        _send_wiki_query(5, "What is alpha?", str(vault)),
        _send_wiki_lint(6, str(vault)),
        _send_wiki_log(7, str(vault)),
    ]

    stdout, stderr = _run_server_long(payloads, expected_ids={1, 2, 3, 4, 5, 6, 7})

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
