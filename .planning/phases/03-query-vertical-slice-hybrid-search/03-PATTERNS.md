# Phase 3: Query Vertical Slice + Hybrid Search - Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 11 new/modified files
**Analogs found:** 10 / 11

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `agents/code-wiki-agent/src/code_wiki_agent/commands/__init__.py` | utility | — | `agents/code-wiki-agent/src/code_wiki_mcp/__init__.py` | role-match (empty init) |
| `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` | service | CRUD + batch | `cores/subagent-runtime/src/subagent_runtime/pool.py` | role-match |
| `agents/code-wiki-agent/tests/commands/__init__.py` | utility | — | `agents/code-wiki-agent/tests/unit/__init__.py` | role-match (empty init) |
| `agents/code-wiki-agent/tests/unit/test_query_search.py` | test | batch | `cores/subagent-runtime/tests/test_pool.py` | role-match |
| `agents/code-wiki-agent/tests/unit/test_query_result.py` | test | CRUD | `agents/code-wiki-agent/tests/unit/test_trace_viewer.py` | role-match |
| `agents/code-wiki-agent/tests/unit/test_cli_query.py` | test | request-response | `agents/code-wiki-agent/tests/unit/test_cli_help.py` | role-match |
| `agents/code-wiki-agent/tests/unit/test_mcp_query_schema.py` | test | request-response | `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py` | role-match |
| `agents/code-wiki-agent/tests/integration/test_query_e2e.py` | test | batch | `cores/subagent-runtime/tests/integration/test_pool_bedrock.py` | exact |
| `agents/code-wiki-agent/src/code_wiki_mcp/server.py` (modify) | middleware | request-response | existing `wiki_ping` in same file | exact |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` (modify) | controller | request-response | existing `trace` command in same file | exact |
| `agents/code-wiki-agent/pyproject.toml` (modify) | config | — | `cores/subagent-runtime/pyproject.toml` | role-match |

---

## Pattern Assignments

### `commands/__init__.py` and `tests/commands/__init__.py` (empty init files)

These are empty `__init__.py` files to declare subpackages. Follow the pattern of every other `__init__.py` in the project — the file is empty (zero bytes). No docstring required.

---

### `agents/code-wiki-agent/src/code_wiki_agent/commands/query.py` (service, CRUD + batch)

**Analog:** `cores/subagent-runtime/src/subagent_runtime/pool.py`

**Imports pattern** (lines 1-39 of pool.py):

```python
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
import sqlite3
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import bm25s
from bm25s.tokenization import Tokenizer
from langchain_aws import BedrockEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage

from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import FanOutResult, SubagentPool
from vault_io._workspace import resolve_wiki_and_repo

logger = logging.getLogger(__name__)
```

**Core dataclass pattern** — match `FanOutResult`/`PerItemError` style (pool.py lines 43-59):

```python
@dataclass
class QueryResult:
    """Returned by run_query(). Consistent with FanOutResult/PerItemError pattern."""
    answer: str
    citations: list[str]        # [[wikilink]] strings found in answer
    pages_drilled: int
    search_scores: dict         # {page_path: {"bm25": float, "embed": float, "rrf": float}}
```

**SubagentPool construction and fan-out pattern** (pool.py lines 79-98, integration test lines 43-63):

```python
# Construction — trace_dir established by Phase 2 convention
pool = SubagentPool(trace_dir=vault_path / ".code-wiki" / "traces")

# Fan-out call with keyword-only args after *
fan_result: FanOutResult = await pool.run_all(
    items=top_pages,           # list[str] page paths
    task=drill_page,           # async def drill_page(page_path: str) -> AIMessage
    role="librarian",
    model_id=lib_cfg["model_id"],
    max_concurrency=lib_cfg["max_concurrency"],
)
# fan_result.successes -> [(page_path, AIMessage), ...]  (completion order, not input order)
# fan_result.errors   -> [PerItemError(item=..., exception=...), ...]
```

**Partial-failure handling** — synthesizer proceeds with whatever successes landed (pool.py design doc lines 1-25):

```python
# Do NOT assume len(fan_result.successes) == len(top_pages)
excerpts = {page: resp.content for page, resp in fan_result.successes}
# Proceed to synthesizer even if some librarians failed
```

**load_role_config pattern** (loader.py lines 98-108):

```python
from model_adapter.loader import load_role_config, make_llm

lib_cfg = load_role_config("librarian")
# lib_cfg = {"model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
#             "region": "us-east-1", "max_tokens": 2048, "max_concurrency": 5}
syn_cfg = load_role_config("synthesizer")
# syn_cfg = {"model_id": "us.anthropic.claude-sonnet-4-6",
#             "region": "us-east-1", "max_tokens": 4096, "max_concurrency": 3}

# make_llm for direct ainvoke (synthesizer is a single call, not a fan-out)
synthesizer_llm = make_llm("synthesizer")
```

**Error handling pattern** — never raise from trace writes; use module logger (pool.py lines 162-210):

```python
# Log to stderr via module-level logger — never print() or write to stdout
logger.warning("BM25 index missing; triggering first-time build (this may take a moment).")
logger.error("Synthesizer call failed: %s", exc)
```

---

### `agents/code-wiki-agent/src/code_wiki_mcp/server.py` — add `wiki_query` tool

**Analog:** `wiki_ping` in same file (server.py lines 80-94)

**Import addition** — add AFTER the guard, alongside existing imports (server.py lines 55-58):

```python
# Existing imports (already in file)
from mcp.server.fastmcp import FastMCP  # noqa: E402
from pydantic import BaseModel          # noqa: E402

# Add for wiki_query:
from mcp.server.fastmcp import Context  # noqa: E402
from code_wiki_agent.commands.query import QueryResult, run_query  # noqa: E402
```

**Pydantic schema pattern** — follow PingInput/PingOutput structure (server.py lines 80-87):

```python
# Copy the BaseModel field style from PingInput/PingOutput
class WikiQueryInput(BaseModel):
    query: str
    vault_path: str = ""   # empty -> resolve from CODE_WIKI_REAL_VAULT_PATH
    top_k: int = 5         # 3-10 range

class WikiQueryOutput(BaseModel):
    answer: str
    citations: list[str]
    pages_drilled: int
    search_scores: dict    # {page_path: {"bm25": float, "embed": float, "rrf": float}}
```

**Tool registration pattern** — follow `@mcp.tool` decorator on `wiki_ping` (server.py lines 89-94):

```python
# wiki_ping is sync; wiki_query MUST be async def (awaits run_query)
@mcp.tool(
    name="wiki_query",
    description=(
        "Query the code wiki using hybrid BM25+embedding search with parallel librarian "
        "analysis. Returns an answer with [[wikilink]] citations. "
        "vault_path defaults to CODE_WIKI_REAL_VAULT_PATH env var."
    ),
)
async def wiki_query(input: WikiQueryInput, ctx: Context) -> WikiQueryOutput:
    ...
```

**Wire format note** (confirmed in test_mcp_stdio.py lines 44-60):

The FastMCP wire shape nests the Pydantic model under the parameter name. For `wiki_query(input: WikiQueryInput, ctx: Context)`, the client sends `arguments={"input": {"query": "...", "top_k": 5}}` — NOT flat `arguments={"query": "..."}`.

---

### `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — add `query` subcommand

**Analog:** `trace` subcommand in same file (cli.py lines 86-121)

**Import additions** — add to existing import block at top (cli.py lines 1-9):

```python
# Existing imports (already in file — do not duplicate)
from __future__ import annotations
import json
from pathlib import Path
import typer

# Add for query subcommand:
import asyncio
import dataclasses
import sys
from code_wiki_agent.commands.query import run_query
```

**Subcommand registration pattern** — follow `@app.command()` + `typer.Option` style of `trace` (cli.py lines 86-88):

```python
@app.command()
def query(
    query_text: str = typer.Argument(..., help="Natural language query"),
    top_k: int = typer.Option(5, "--top-k", help="Pages to drill (3-10)"),
    vault: str = typer.Option("", "--vault", help="Vault path (default: resolve from workspace)"),
    json_output: bool = typer.Option(False, "--json", help="Emit QueryResult as JSON"),
    _no_state_gate: bool = typer.Option(False, "--no-state-gate", help="No-op; query is read-only"),
) -> None:
    ...
```

**Error and exit code pattern** — follow `trace` error exit (cli.py lines 89-92):

```python
# trace does:
if not file.exists():
    typer.echo(f"trace file not found: {file}", err=True)
    raise typer.Exit(code=1)

# query follows same pattern:
try:
    result = asyncio.run(run_query(query_text, vault_path, top_k=top_k))
except RuntimeError as e:
    typer.echo(f"Error: {e}", err=True)
    raise typer.Exit(code=1)
```

**Output pattern** — `typer.echo()` for user-facing output (cli.py lines 103-121):

```python
# trace uses typer.echo() for all output:
typer.echo(...)

# query uses same; json_output flag controls format:
if json_output:
    typer.echo(json.dumps(dataclasses.asdict(result), indent=2))
else:
    typer.echo(result.answer)
    if result.citations:
        typer.echo(f"\nCitations: {', '.join(result.citations)}")
```

**Critical: `asyncio.run()` only in the sync Typer command** — never inside the async MCP handler. The MCP handler uses `await run_query(...)`.

---

### `agents/code-wiki-agent/pyproject.toml` — add bm25s + asyncio_mode

**Analog:** `cores/subagent-runtime/pyproject.toml` `[tool.pytest.ini_options]`

**Existing `[tool.pytest.ini_options]` block** (pyproject.toml lines 27-31):

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
markers = ["integration: requires real Bedrock or subprocess (skipped in CI by default)"]
```

**Required change** — add `asyncio_mode = "auto"` (copy from subagent-runtime):

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
asyncio_mode = "auto"
markers = ["integration: requires real Bedrock or subprocess (skipped in CI by default)"]
```

**Add bm25s to `[project]` dependencies** (pyproject.toml lines 6-13):

```toml
dependencies = [
    "vault-io",
    "model-adapter",
    "subagent-runtime",     # add — Phase 3 calls SubagentPool directly
    "mcp>=1.27.1",
    "langchain-aws>=1.4.6",
    "typer>=0.25.1",
    "pydantic>=2.0",
    "bm25s==0.3.8",         # add — new dep for Phase 3 BM25 index
]
```

---

### `agents/code-wiki-agent/tests/unit/test_query_search.py` (test, batch)

**Analog:** `cores/subagent-runtime/tests/test_pool.py`

**File-level structure** (test_pool.py lines 1-21):

```python
from __future__ import annotations

"""Unit tests for code_wiki_agent.commands.query — BM25, SQLite, cosine, RRF.

No real Bedrock calls — all embedding paths are mocked via unittest.mock.
"""

import json
import math
import sqlite3
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
```

**Test function style** — no class, no `self`, inline imports from the module under test (test_pool.py lines 26-42):

```python
# test_pool.py pattern:
async def test_fanout_returns_fanout_result_dataclass(tmp_path, make_task):
    from subagent_runtime.pool import SubagentPool, FanOutResult, PerItemError
    pool = SubagentPool(trace_dir=tmp_path / "traces")
    ...

# test_query_search.py follows same pattern:
def test_bm25_index_build_and_query(tmp_path: Path) -> None:
    from code_wiki_agent.commands.query import build_index, bm25_query
    # create minimal vault pages in tmp_path
    # call build_index(tmp_path, ...)
    # assert results ranked correctly
    ...
```

**tmp_path fixture** — use pytest's built-in `tmp_path` for all filesystem operations (test_pool.py lines 27, 114, 130, etc.). No custom temp dir logic.

**Monkeypatch for isolation** — use `monkeypatch.setattr` to replace `BedrockEmbeddings.embed_query` so BM25 tests never hit the network (test_pool.py lines 298-306):

```python
def test_incremental_skip_avoids_reembedding(tmp_path, monkeypatch):
    # Monkeypatch BedrockEmbeddings to return a fixed 1024-dim vector
    call_count = 0
    def fake_embed(self, text):
        nonlocal call_count
        call_count += 1
        return [0.1] * 1024
    monkeypatch.setattr("langchain_aws.BedrockEmbeddings.embed_query", fake_embed)
    ...
```

---

### `agents/code-wiki-agent/tests/unit/test_query_result.py` (test, CRUD)

**Analog:** `agents/code-wiki-agent/tests/unit/test_trace_viewer.py`

**File-level structure** (test_trace_viewer.py lines 1-12):

```python
from __future__ import annotations

import json
import subprocess
import pytest
from pathlib import Path
```

**Pure function test pattern** — import from module, call function directly, assert on return value (test_trace_viewer.py lines 115-130):

```python
# test_trace_viewer.py pattern:
def test_render_trace_record_pure_function() -> None:
    from code_wiki_agent.cli import _render_trace_record
    record = {...}
    output = _render_trace_record(record)
    assert isinstance(output, str)
    assert "scanner" in output

# test_query_result.py follows same pattern for QueryResult:
def test_query_result_is_dataclass() -> None:
    from code_wiki_agent.commands.query import QueryResult
    result = QueryResult(
        answer="test answer",
        citations=["[[SomePage]]"],
        pages_drilled=3,
        search_scores={"page.md": {"bm25": 0.9, "embed": 0.8, "rrf": 0.016}},
    )
    assert result.answer == "test answer"
    assert len(result.citations) == 1
```

**`dataclasses.asdict` round-trip test** — validates `--json` output shape:

```python
import dataclasses
def test_query_result_asdict_has_required_keys() -> None:
    from code_wiki_agent.commands.query import QueryResult
    result = QueryResult(answer="a", citations=[], pages_drilled=1, search_scores={})
    d = dataclasses.asdict(result)
    assert set(d.keys()) == {"answer", "citations", "pages_drilled", "search_scores"}
```

---

### `agents/code-wiki-agent/tests/unit/test_cli_query.py` (test, request-response)

**Analog:** `agents/code-wiki-agent/tests/unit/test_cli_help.py`

**Subprocess invocation pattern** (test_cli_help.py lines 1-13):

```python
from __future__ import annotations
import subprocess

def test_cli_help_exits_zero() -> None:
    result = subprocess.run(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-agent", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"--help exited {result.returncode}\n{result.stderr}"
    assert "code-wiki-agent" in result.stdout.lower()
```

**Project root resolution** — use `_PROJECT_ROOT` pattern from test_trace_viewer.py (line 50):

```python
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

def _run_query_cmd(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-agent", "query"] + args,
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
    )
```

**`--help` test** — follows test_cli_help.py pattern:

```python
def test_query_help_exits_zero() -> None:
    result = subprocess.run(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-agent", "query", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "--top-k" in result.stdout
    assert "--vault" in result.stdout
    assert "--no-state-gate" in result.stdout
```

**Unit test for shared impl** — import-only check, no subprocess needed:

```python
def test_shared_impl_is_imported_from_commands() -> None:
    from code_wiki_agent.cli import query as query_cmd
    import inspect
    src = inspect.getsource(query_cmd)
    assert "run_query" in src
    assert "commands.query" in src or "from code_wiki_agent.commands" in src
```

---

### `agents/code-wiki-agent/tests/unit/test_mcp_query_schema.py` (test, request-response)

**Analog:** `agents/code-wiki-agent/tests/integration/test_mcp_stdio.py`

**Wire format from test_mcp_stdio.py** (lines 44-60) — the Pydantic model is nested under the parameter name:

```python
# For wiki_ping(input: PingInput) -> arguments={"input": {"message": "hello"}}
# For wiki_query(input: WikiQueryInput, ctx: Context) -> arguments={"input": {"query": "...", "top_k": 5}}
```

**Tool schema validation test** — use `_run_server` + JSON parse pattern from test_mcp_stdio.py (lines 63-78):

```python
def _send_wiki_query_call(query: str, top_k: int = 5) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "wiki_query",
            "arguments": {"input": {"query": query, "top_k": top_k}},
        },
    }
```

**Progress mock for unit test** — mock the `Context` object:

```python
async def test_progress_calls_made(monkeypatch) -> None:
    from unittest.mock import AsyncMock, MagicMock
    mock_ctx = MagicMock()
    mock_ctx.report_progress = AsyncMock()
    # monkeypatch run_query to return a fixed QueryResult
    monkeypatch.setattr(
        "code_wiki_mcp.server.run_query",
        AsyncMock(return_value=QueryResult(answer="ok", citations=[], pages_drilled=2, search_scores={}))
    )
    from code_wiki_mcp.server import wiki_query, WikiQueryInput
    await wiki_query(WikiQueryInput(query="test"), mock_ctx)
    assert mock_ctx.report_progress.call_count >= 2
```

---

### `agents/code-wiki-agent/tests/integration/test_query_e2e.py` (test, batch)

**Analog:** `cores/subagent-runtime/tests/integration/test_pool_bedrock.py`

**Integration gate pattern** (test_pool_bedrock.py lines 28-31):

```python
import os
import pytest

INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)
```

**Test function structure** (test_pool_bedrock.py lines 34-78):

```python
@pytest.mark.integration
@INTEGRATION_GATE
async def test_query_fixture_vault(tmp_path: Path) -> None:
    """End-to-end query against the round-trip-vault fixture; asserts at least one [[wikilink]] citation."""
    from pathlib import Path
    from code_wiki_agent.commands.query import run_query

    # Cross-package fixture vault path resolution (RESEARCH Pitfall 6)
    FIXTURE_VAULT = (
        Path(__file__).parent.parent.parent.parent.parent  # project root
        / "cores" / "vault-io" / "tests" / "fixtures" / "round-trip-vault"
    )
    assert FIXTURE_VAULT.exists(), f"Fixture vault not found at {FIXTURE_VAULT}"
    ...
```

**Assertion style** — descriptive f-string messages (test_pool_bedrock.py lines 64-66):

```python
assert len(result.successes) == 3, f"Expected 3 successes; got {len(result.successes)}"

# query e2e follows same pattern:
assert result.pages_drilled >= 1, f"Expected at least 1 page drilled; got {result.pages_drilled}"
assert len(result.citations) >= 1, f"Expected at least one [[wikilink]] citation; got {result.citations}"
assert "[[" in result.answer, f"Expected [[wikilink]] in answer; got: {result.answer}"
```

**Run command** (test_pool_bedrock.py docstring line 13):

```
CODE_WIKI_RUN_INTEGRATION=1 uv run --package code-wiki-agent pytest \
    agents/code-wiki-agent/tests/integration/test_query_e2e.py -v
```

---

## Shared Patterns

### `from __future__ import annotations`
**Source:** Every source file in the codebase (pool.py line 1, cli.py line 1, server.py line 15)
**Apply to:** All new `.py` files
```python
from __future__ import annotations
```

### Logging — stderr only, never stdout
**Source:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py` lines 60-71
**Apply to:** `commands/query.py` — the only new non-test file with logging needs
```python
# At module level — do NOT configure basicConfig here (server.py already does it)
logger = logging.getLogger(__name__)

# Use only logger methods — never print() or sys.stdout.write()
logger.warning("First-time index build; this may take a moment.")
logger.error("Librarian fan-out error on page %s: %s", page, exc)
```

### Integration test gate
**Source:** `cores/subagent-runtime/tests/integration/test_pool_bedrock.py` lines 28-31
**Apply to:** `tests/integration/test_query_e2e.py`
```python
INTEGRATION_GATE = pytest.mark.skipif(
    not os.environ.get("CODE_WIKI_RUN_INTEGRATION"),
    reason="Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations",
)
```

### `tmp_path` for filesystem tests
**Source:** `cores/subagent-runtime/tests/test_pool.py` (every test function signature)
**Apply to:** All test functions in `test_query_search.py` that create BM25 dirs or SQLite files
```python
def test_bm25_index_build_and_query(tmp_path: Path) -> None:
    bm25_dir = tmp_path / "bm25"
    db_path = tmp_path / "search.db"
    ...
```

### `_PROJECT_ROOT` path anchor
**Source:** `agents/code-wiki-agent/tests/unit/test_trace_viewer.py` line 50
**Apply to:** `tests/unit/test_cli_query.py`, `tests/integration/test_query_e2e.py`
```python
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
```

### SubagentPool construction — trace_dir inside vault
**Source:** Integration tests in `test_pool_bedrock.py` lines 55-56; pool.py `__init__` lines 79-87
**Apply to:** `commands/query.py` `run_query()` function
```python
# Mirrors Phase 2 convention: trace_dir is .code-wiki/traces/ under the vault
pool = SubagentPool(trace_dir=vault_path / ".code-wiki" / "traces")
```

### FastMCP tool placement — after `_StdoutGuard`
**Source:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py` lines 15-57
**Apply to:** New `wiki_query` addition in `server.py`

All new imports and tool definitions go AFTER line 77 (`mcp = FastMCP(name="code-wiki-mcp")`). The `_StdoutGuard` is installed at lines 28-51 and must remain the very first code that executes. Never move imports above it.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/fixtures/eval-cases/phase-03/` (TOML eval cases) | config | — | No eval case TOML files exist yet in this project; planner uses RESEARCH.md's test-requirement map to author the 10 cases |

Note: The RESEARCH.md "Validation Architecture" section (lines 880-901) provides the full requirement-to-test mapping that serves as the template for the eval TOML files.

---

## Metadata

**Analog search scope:** `agents/code-wiki-agent/`, `cores/subagent-runtime/`, `cores/model-adapter/`
**Files read:** 11 source files + 2 context/research docs
**Pattern extraction date:** 2026-05-13
