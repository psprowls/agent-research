"""Verify MCP server stdout contains only valid JSON-RPC lines.

This test is the end-to-end gate for MCP-05: it spawns the real
``graph-wiki-mcp`` entry point as a subprocess, drives an ``initialize``
+ ``notifications/initialized`` + ``tools/call wiki_ping`` exchange over
stdin, and asserts that every non-empty line on stdout parses as JSON-RPC.
If any library accidentally writes to stdout (boto3, anyio, a stray
``print``), this test fails with the offending line plus the first 500
chars of stderr for fast diagnosis.

Intentionally NOT marked as an integration-only test (D-16): runs in CI by
default because wiki_ping never calls Bedrock.
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest


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
    # MCP spec: client MUST send ``notifications/initialized`` after the
    # initialize response. Without it, FastMCP refuses tools/call and
    # responds with -32602 "Received request before initialization".
    return {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}


def _send_tools_call() -> dict:
    # FastMCP names the tool argument after the Python parameter name. Our
    # signature is ``wiki_ping(input: PingInput)`` so the wire shape is
    # ``arguments={"input": {"message": "hello"}}`` (Pydantic schema nested
    # under the parameter name). The flat shorthand in RESEARCH Pattern 7
    # (``arguments={"message": "hello"}``) does NOT match a Pydantic-typed
    # parameter and yields a validation error — verified empirically
    # against mcp 1.27.1.
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "wiki_ping",
            "arguments": {"input": {"message": "hello"}},
        },
    }


def _run_server(payload_objs: list[dict]) -> tuple[str, str]:
    """Spawn ``graph-wiki-mcp``, feed payload, return (stdout, stderr)."""
    payload = "\n".join(json.dumps(obj) for obj in payload_objs) + "\n"
    proc = subprocess.Popen(
        ["uv", "run", "--package", "graph-wiki-agent", "graph-wiki-mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = proc.communicate(input=payload.encode(), timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout_bytes, stderr_bytes = proc.communicate()  # reap zombie, collect output
        pytest.fail(f"MCP server did not respond within 15s.\nstderr: {stderr_bytes.decode()[:500]}")
    return stdout_bytes.decode(), stderr_bytes.decode()


def test_mcp_stdout_is_valid_jsonrpc():
    """Every non-empty stdout line must be valid JSON-RPC (MCP-05)."""
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH; required to spawn graph-wiki-mcp")

    stdout, stderr = _run_server(
        [
            _send_initialize(),
            _send_initialized_notification(),
            _send_tools_call(),
        ]
    )

    lines = [line for line in stdout.splitlines() if line.strip()]
    assert lines, "MCP server produced no stdout output"

    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            pytest.fail(f"Non-JSON stdout line from MCP server: {line!r}\nJSON error: {e}\nFull stderr: {stderr[:500]}")
        assert "jsonrpc" in obj or "id" in obj, f"Line is JSON but not JSON-RPC: {line!r}"

    # At least one response must carry a `result` (the tools/call reply).
    assert any("result" in json.loads(line) for line in lines), (
        f"No JSON-RPC response with 'result' key.\nstderr: {stderr[:500]}"
    )


def test_mcp_wiki_ping_returns_pong():
    """tools/call wiki_ping must round-trip pong+echo end-to-end."""
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH; required to spawn graph-wiki-mcp")

    stdout, stderr = _run_server(
        [
            _send_initialize(),
            _send_initialized_notification(),
            _send_tools_call(),
        ]
    )

    responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    # Find the response to id=2 (the tools/call). Notifications have no id.
    tool_resp = next((r for r in responses if r.get("id") == 2), None)
    assert tool_resp is not None, (
        f"No response with id=2 (tools/call).\nResponses: {responses!r}\nstderr: {stderr[:500]}"
    )
    assert "result" in tool_resp, f"tools/call had no result: {tool_resp!r}"
    # FastMCP returns the typed BaseModel under `structuredContent` and a
    # text rendering under `content[0].text`. Both must mention pong+hello.
    blob = json.dumps(tool_resp["result"])
    assert "pong" in blob, f"'pong' missing from result: {blob}"
    assert "hello" in blob, f"'hello' (echoed input) missing from result: {blob}"
    assert tool_resp["result"].get("isError") is False, f"tools/call result flagged as error: {tool_resp!r}"


import os


INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run integration tests",
)


def _send_tools_list() -> dict:
    """Build a tools/list request."""
    return {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/list",
        "params": {},
    }


@pytest.mark.integration
@INTEGRATION_GATE
def test_wiki_query_in_tools_list() -> None:
    """tools/list response from graph-wiki-mcp includes wiki_query with hybrid description (MCP-07).

    Gated by GRAPH_WIKI_RUN_INTEGRATION=1 because the subprocess launch
    triggers import of graph_wiki_agent.commands.query, which imports bm25s,
    langchain-aws, and other heavy deps that might fail without AWS config.
    The test is intentionally lightweight (no Bedrock calls) but requires
    a working install of all deps.
    """
    if shutil.which("uv") is None:
        pytest.skip("uv not on PATH; required to spawn graph-wiki-mcp")

    stdout, stderr = _run_server(
        [
            _send_initialize(),
            _send_initialized_notification(),
            _send_tools_list(),
        ]
    )

    responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    # Find the response to id=3 (the tools/list).
    list_resp = next((r for r in responses if r.get("id") == 3), None)
    assert list_resp is not None, (
        f"No response with id=3 (tools/list).\nResponses: {responses!r}\nstderr: {stderr[:500]}"
    )
    assert "result" in list_resp, f"tools/list had no result: {list_resp!r}"

    tools = list_resp["result"].get("tools", [])
    tool_names = [t.get("name") for t in tools]
    assert "wiki_query" in tool_names, (
        f"wiki_query not found in tools/list response.\nTool names: {tool_names!r}\nstderr: {stderr[:500]}"
    )

    # Verify description contains the expected signal strings (MCP-02)
    wiki_query_tool = next(t for t in tools if t.get("name") == "wiki_query")
    description = wiki_query_tool.get("description", "")
    assert "hybrid" in description or "BM25" in description, (
        f"wiki_query description missing 'hybrid'/'BM25' signal.\ndescription: {description!r}"
    )
