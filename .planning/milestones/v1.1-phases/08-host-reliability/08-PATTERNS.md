# Phase 8: Host Reliability - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 6 (4 new, 2 modified)
**Analogs found:** 5 / 6 (docs/cancellation.md has no close analog)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py` | test | event-driven (asyncio task cancel) | `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py` | role-match (same file, different harness mode) |
| `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` | test | request-response (subprocess JSON-RPC) | `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py` | exact (same subprocess+JSON-RPC pattern, extended) |
| `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py` | test | unit/schema | `agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py` | exact (same WikiScanInput import + field assertion pattern) |
| `docs/cancellation.md` | docs | — | `README.md` (repo root) | partial (prose only; no code pattern to copy) |
| `cores/subagent-runtime/src/subagent_runtime/pool.py` | service | event-driven (asyncio fan-out) | self (existing `except Exception` branches in same file) | self-analog |
| `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` | service/config | request-response | self (existing `WikiQueryInput`/`WikiLogInput` pattern in same file) | self-analog |

---

## Pattern Assignments

### `agents/graph-wiki-agent/tests/integration/test_mcp_cancel.py` (test, direct-asyncio cancel)

**Decision:** D-10 — cancel test runs WITHOUT `GRAPH_WIKI_RUN_INTEGRATION=1`. Direct asyncio, NOT subprocess. `monkeypatch` works because the test runs in-process.

**Analog:** `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py`

**Imports pattern** (`test_mcp_stdio.py` lines 1-21):
```python
from __future__ import annotations

import json
import shutil
import subprocess

import pytest
```

For the cancel test, swap subprocess imports for asyncio + unittest.mock:
```python
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
```

**No INTEGRATION_GATE** (contrast with E2E test): The cancel test uses a monkeypatched stub model — no Bedrock, no gate. This matches the pattern of `test_mcp_stdout_is_valid_jsonrpc` in `test_mcp_stdio.py` (lines 81-107), which also runs ungated because `wiki_ping` never touches Bedrock.

**Core cancel pattern** (new — no existing analog; copy structure from RESEARCH.md Q3):
```python
async def test_cancel_mid_fan_out(tmp_path, monkeypatch):
    # 1. Patch make_llm to return a slow stub
    async def _slow_llm(*args, **kwargs):
        await asyncio.sleep(3)
        msg = AsyncMock()
        msg.usage_metadata = None
        return msg

    stub = AsyncMock(side_effect=_slow_llm)
    monkeypatch.setattr("model_adapter.loader.make_llm", lambda *a, **kw: stub)

    # 2. Set up minimal vault in tmp_path
    # 3. Create an asyncio Task wrapping run_query(...)
    task = asyncio.ensure_future(run_query(query="...", vault_path=tmp_path, top_k=3))

    # 4. Yield once to let gather start
    await asyncio.sleep(0)

    # 5. Cancel and collect
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # 6. Assert trace has cancelled records + batch_cancelled summary
    trace_files = list((tmp_path / ".code-wiki" / "traces").glob("*.jsonl"))
    assert trace_files
    lines = [json.loads(l) for l in trace_files[0].read_text().splitlines() if l.strip()]
    cancelled = [l for l in lines if l.get("status") == "cancelled"]
    batch_summary = [l for l in lines if l.get("event") == "batch_cancelled"]
    assert cancelled
    assert len(batch_summary) == 1
```

**Key pitfall to avoid:** `asyncio.CancelledError` inherits from `BaseException`, NOT `Exception` — the existing `except Exception` in `_run_one` does NOT catch it. See RESEARCH.md Pitfall 1.

---

### `agents/graph-wiki-agent/tests/integration/test_mcp_e2e.py` (test, subprocess JSON-RPC)

**Decision:** D-01, D-14 — subprocess-based, gated by `GRAPH_WIKI_RUN_INTEGRATION=1`, one sequential test function.

**Analog:** `agents/graph-wiki-agent/tests/integration/test_mcp_stdio.py` — copy the entire harness.

**Imports pattern** (copy from `test_mcp_stdio.py` lines 1-22):
```python
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest
```

**INTEGRATION_GATE pattern** (`test_mcp_stdio.py` lines 141-144 and `conftest.py` lines 19-23):
```python
# conftest.py canonical definition:
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
    reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)

# In test_mcp_e2e.py — import from conftest or redefine locally (either is fine per conftest comment):
from agents.graph_wiki_agent.tests.conftest import INTEGRATION_GATE
# OR redefine at top of file same as test_mcp_stdio.py line 141-144
```

**`_run_server` helper** (copy verbatim from `test_mcp_stdio.py` lines 63-78):
```python
def _run_server(payload_objs: list[dict]) -> tuple[str, str]:
    """Spawn graph-wiki-mcp, feed payload, return (stdout, stderr)."""
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
        stdout_bytes, stderr_bytes = proc.communicate()
        pytest.fail(f"MCP server did not respond within 15s.\nstderr: {stderr_bytes.decode()[:500]}")
    return stdout_bytes.decode(), stderr_bytes.decode()
```

**`_send_initialize` + `_send_initialized_notification`** (copy from `test_mcp_stdio.py` lines 24-41):
```python
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
```

**`_send_tools_call` shape** (copy structure from `test_mcp_stdio.py` lines 44-60 — note the Pydantic nested-under-param-name shape):
```python
# IMPORTANT: arguments must be nested under the Python parameter name ("input")
# Flat shorthand does NOT work with Pydantic-typed params (verified against mcp 1.27.1)
def _send_wiki_init(request_id: int, tmp_path: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "wiki_init",
            "arguments": {"input": {
                "topic": "test repo",
                "tool": "claude-code",
                "vault_path": tmp_path,
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
                "repo_path": repo_path,  # NEW FIELD — must be added to WikiScanInput first
                "max_depth": 2,
            }},
        },
    }
```

**Response extraction pattern** (from `test_mcp_stdio.py` lines 123-135):
```python
responses = [json.loads(line) for line in stdout.splitlines() if line.strip()]
tool_resp = next((r for r in responses if r.get("id") == request_id), None)
assert tool_resp is not None, f"No response with id={request_id}.\nstderr: {stderr[:500]}"
assert "result" in tool_resp, f"tools/call had no result: {tool_resp!r}"
assert tool_resp["result"].get("isError") is False, f"tools/call flagged as error: {tool_resp!r}"
```

**Non-error outcome assertion** (adapted from `test_mcp_stdio.py` line 135):
```python
# For each tool response, assert non-error:
assert tool_resp["result"].get("isError") is False
# Then assert result content (planner picks field per tool):
blob = json.dumps(tool_resp["result"])
assert "status" in blob  # or tool-specific field
```

**`notifications/cancelled` wire shape** (new — no existing analog in codebase; from RESEARCH.md Q1):
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/cancelled",
  "params": {
    "requestId": "123",
    "reason": "User requested cancellation"
  }
}
```
Note: `notifications/cancelled` is a notification — it has no `id` field and receives no response.

---

### `agents/graph-wiki-agent/tests/unit/test_wiki_scan_input.py` (test, unit/schema)

**Analog:** `agents/graph-wiki-agent/tests/unit/test_mcp_new_tools.py` — exact pattern.

**Imports pattern** (`test_mcp_new_tools.py` lines 1-8):
```python
from __future__ import annotations

"""<docstring: what this tests>

Requirements covered: <req IDs>.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
```

**Schema default assertion pattern** (`test_mcp_new_tools.py` lines 31-37, 39-44, 46-50):
```python
def test_wiki_scan_input_default_vault_path_is_empty() -> None:
    """WikiScanInput defaults to vault_path='' (resolves from env)."""
    from graph_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.vault_path == ""

def test_wiki_scan_input_default_no_file_map_is_false() -> None:
    """WikiScanInput defaults to no_file_map=False."""
    from graph_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.no_file_map is False
```

**New field assertion pattern** (for `repo_path` — copy shape from lines 55-60):
```python
def test_wiki_scan_input_default_repo_path_is_empty() -> None:
    """WikiScanInput defaults to repo_path='' (no override — resolves from vault_path)."""
    from graph_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput()
    assert inp.repo_path == ""

def test_wiki_scan_input_accepts_repo_path() -> None:
    """WikiScanInput accepts an explicit repo_path string."""
    from graph_wiki_mcp.server import WikiScanInput

    inp = WikiScanInput(repo_path="/tmp/test-repo")
    assert inp.repo_path == "/tmp/test-repo"
```

**Function-level docstring style** (from `test_mcp_query_schema.py` line 14):
```python
def test_wiki_query_tool_registered() -> None:
    """wiki_query tool is importable and callable (MCP-02)."""
```
All test function docstrings cite the requirement ID in parentheses.

---

### `docs/cancellation.md` (docs)

**No close analog** — the `docs/` directory does not exist yet. `README.md` is the only existing markdown doc at repo root.

**Prose style from `README.md`** (lines 1-30): terse, code-block-heavy, no emojis. Headings use `##` for sections. Code examples are fenced with language identifiers. No bullet lists for technical prose — use tables where structured.

**Structure from CONTEXT.md D-15 and RESEARCH.md Q10:**
1. `## Protocol Behavior` — what `notifications/cancelled` triggers; wire format; no response sent
2. `## Internal Cancellation Chain` — FastMCP → anyio CancelScope → asyncio task → `run_all` → `_run_one`
3. `## Trace Shapes` — per-item `status: cancelled` record + `event: batch_cancelled` summary, with JSON examples
4. `## Known Limitations (v1.1)` — boto3 worker thread continues; "clean cancel" definition; wasted Bedrock call
5. `## Future Work (v1.2+)` — aioboto3 / socket-close; SIGINT paths

**JSON trace record examples** (from CONTEXT.md D-06):
```json
{"role":"librarian","model_id":"...","item_id":"...","status":"cancelled",
 "latency_ms":1240,"tokens_in":null,"tokens_out":null,"cost_usd":null,"timestamp":"..."}

{"role":"librarian","model_id":"...","event":"batch_cancelled",
 "items_total":5,"items_completed":0,"items_cancelled":5,"wall_clock_ms":1243,"timestamp":"..."}
```

---

### `cores/subagent-runtime/src/subagent_runtime/pool.py` (modify — service, event-driven)

**Self-analog:** The existing `except Exception` branch in `_run_one` (lines 141-146) and the `asyncio.gather` call (line 149) are the precise insertion points.

**Existing `_run_one` error branch** (lines 141-146) — new `CancelledError` branch goes BEFORE this:
```python
# EXISTING (lines 141-146):
except Exception as exc:
    latency_ms = int((time.monotonic() - t0) * 1000)
    self._write_trace(
        trace_file, role, model_id, item, "error", latency_ms, None, error=str(exc)
    )
    return PerItemError(item=item, exception=exc)

# NEW — add BEFORE the existing except Exception block:
except asyncio.CancelledError:
    latency_ms = int((time.monotonic() - t0) * 1000)
    self._write_trace(
        trace_file, role, model_id, item, "cancelled", latency_ms, None
    )
    raise  # MUST re-raise — outer cancel must propagate
```

**Existing `asyncio.gather` call** (line 149) — wrap in try/except:
```python
# EXISTING (line 149):
raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)

# REPLACE WITH:
batch_t0 = time.monotonic()
try:
    raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)
except asyncio.CancelledError:
    wall_ms = int((time.monotonic() - batch_t0) * 1000)
    self._write_batch_terminal(
        trace_file, role, model_id,
        items_total=len(items),
        items_completed=0,           # conservative: gather result unavailable on cancel
        items_cancelled=len(items),  # conservative upper bound
        wall_clock_ms=wall_ms,
    )
    raise  # MUST re-raise — FastMCP anyio CancelScope expects this
```

**`_write_trace` — no changes required** (lines 162-210): the existing `None` guard on lines 185-189 already handles `response=None` for the cancelled case. `_compute_cost_usd` with `tokens_in=None` already returns `None` (lines 224-225). Only the caller changes.

**New `_write_batch_terminal` helper** — copy `_write_trace`'s error-handling skeleton (lines 206-210):
```python
def _write_batch_terminal(
    self,
    path: Path,
    role: str,
    model_id: str,
    *,
    items_total: int,
    items_completed: int,
    items_cancelled: int,
    wall_clock_ms: int,
) -> None:
    """Write the batch_cancelled summary record. Never raises."""
    record = {
        "role": role,
        "model_id": model_id,
        "event": "batch_cancelled",
        "items_total": items_total,
        "items_completed": items_completed,
        "items_cancelled": items_cancelled,
        "wall_clock_ms": wall_clock_ms,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("Batch terminal trace write failed: %s", exc)
```

The "never raises — OSError logged at WARNING" contract is copied verbatim from `_write_trace` (lines 206-210).

---

### `agents/graph-wiki-agent/src/graph_wiki_mcp/server.py` (modify — service)

**Self-analog: `WikiQueryInput`** (lines 103-107) — existing field-with-default pattern:
```python
class WikiQueryInput(BaseModel):
    query: str
    vault_path: str = ""  # empty -> resolve from GRAPH_WIKI_REAL_VAULT_PATH env var
    top_k: int = Field(default=5, ge=3, le=10)
```

**Self-analog: `WikiLogInput`** (lines 150-154) — Field() with description pattern:
```python
class WikiLogInput(BaseModel):
    op: str = Field(..., description="Log operation type (...)")
    title: str = Field(..., description="Short title for the log entry")
    detail: str | None = Field(None, description="Optional extended detail")
    vault_path: str = Field("", description="Vault path (default: GRAPH_WIKI_REAL_VAULT_PATH env var)")
```

**New field to add to `WikiScanInput`** (lines 242-245) — copy `vault_path` Field style:
```python
class WikiScanInput(BaseModel):
    vault_path: str = Field("", description="Vault path (default: GRAPH_WIKI_REAL_VAULT_PATH env var)")
    no_file_map: bool = Field(False, description="Skip per-package file-map generation")
    max_depth: int = Field(3, description="Max directory depth for file map headers")
    # NEW:
    repo_path: str = Field(
        "",
        description="Override repo root for scanner (default: resolved from vault_path). Use for testing.",
    )
```

**Existing `wiki_scan` handler wiring** (lines 261-284) — add `repo_path` passthrough:
```python
# EXISTING line 264:
result: ScanResult = await run_scan(
    vault_path=vault,
    no_file_map=input.no_file_map,
    max_depth=input.max_depth,
)

# REPLACE WITH (copy path-or-None pattern from wiki_query line 125):
result: ScanResult = await run_scan(
    vault_path=vault,
    no_file_map=input.no_file_map,
    max_depth=input.max_depth,
    repo_path=Path(input.repo_path).resolve() if input.repo_path else None,
)
```

The `Path(input.X) if input.X else None` pattern is used consistently throughout `server.py` at lines 125, 169, 215.

---

## Shared Patterns

### `from __future__ import annotations` header
**Source:** All existing Python files in the codebase (e.g., `pool.py` line 1, `test_mcp_stdio.py` line 1).
**Apply to:** All new `.py` files.
```python
from __future__ import annotations
```

### Module-level docstring
**Source:** `test_mcp_stdio.py` lines 2-12 — brief paragraph explaining what the file tests and which requirement it covers.
**Apply to:** All new test files.
```python
"""<Brief description of what this test file covers>.

Requirements covered: <req IDs e.g. MCP-10, MCP-11>.
"""
```

### `_write_trace` / `_write_batch_terminal` never-raises contract
**Source:** `pool.py` lines 206-210.
**Apply to:** `_write_batch_terminal` in `pool.py`.
```python
try:
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")
except OSError as exc:
    logger.warning("...: %s", exc)
```

### Logging to stderr only (no stdout)
**Source:** `server.py` lines 65-75 — `logging.basicConfig(stream=sys.stderr, ...)`.
**Apply to:** Any cancel-path logging in `pool.py`. Use `logger.warning(...)`, never `print()`. The `_StdoutGuard` raises `RuntimeError` on any non-FastMCP stdout write.

### Pydantic `BaseModel` with `Field()` defaults
**Source:** `server.py` lines 103-107, 150-154, 242-245.
**Apply to:** `WikiScanInput.repo_path` addition.
```python
field_name: str = Field("", description="...")
```

### pytest asyncio test functions (no `@pytest.mark.asyncio` decorator)
**Source:** `test_mcp_new_tools.py` lines 70, 96, 151, 180 — async test functions declared without explicit `@pytest.mark.asyncio` because `asyncio_mode = "auto"` is set in `agents/graph-wiki-agent/pyproject.toml`.
**Apply to:** All `async def test_*` functions in `test_mcp_cancel.py` and `test_wiki_scan_input.py`.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `docs/cancellation.md` | docs | — | No `docs/` directory exists; no existing technical-reference docs at repo root beyond README. Structure comes from CONTEXT.md D-15 and RESEARCH.md Q10 exclusively. |

---

## Metadata

**Analog search scope:** `agents/graph-wiki-agent/tests/`, `cores/subagent-runtime/src/`, `agents/graph-wiki-agent/src/graph_wiki_mcp/`, repo root `*.md`
**Files read:** 9 source files (`pool.py`, `server.py`, `test_mcp_stdio.py`, `conftest.py`, `test_mcp_new_tools.py`, `test_mcp_query_schema.py`, `test_commands_scan.py`, `README.md`, `CLAUDE.md` context headers)
**Pattern extraction date:** 2026-05-17
