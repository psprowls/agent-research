# Phase 2: Subagent Fan-Out Runtime - Pattern Map

**Mapped:** 2026-05-13
**Files analyzed:** 10 new/modified files
**Analogs found:** 10 / 10

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `cores/subagent-runtime/pyproject.toml` | config | — | `cores/model-adapter/pyproject.toml` | exact |
| `cores/subagent-runtime/src/subagent_runtime/__init__.py` | config | — | `cores/model-adapter/src/model_adapter/__init__.py` (implicit) | role-match |
| `cores/subagent-runtime/src/subagent_runtime/pool.py` | service | event-driven (asyncio fan-out) | `cores/model-adapter/src/model_adapter/loader.py` | role-match |
| `cores/subagent-runtime/tests/conftest.py` | test | — | `cores/model-adapter/tests/test_loader.py` (fixture patterns) | role-match |
| `cores/subagent-runtime/tests/test_pool.py` | test | — | `cores/model-adapter/tests/test_loader.py` | exact |
| `cores/subagent-runtime/tests/integration/test_pool_bedrock.py` | test | request-response | `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` | exact |
| `cores/model-adapter/src/model_adapter/models.toml` (extend) | config | — | itself (Phase 1 entries) | exact |
| `cores/model-adapter/src/model_adapter/loader.py` (extend) | service | request-response | itself (existing `make_llm`) | exact |
| `agents/code-wiki-agent/src/code_wiki_agent/cli.py` (extend) | controller | request-response | itself (existing `version` command) | exact |
| `agents/code-wiki-agent/tests/unit/test_trace_viewer.py` | test | — | `agents/code-wiki-agent/tests/unit/test_cli_help.py` | role-match |

---

## Pattern Assignments

### `cores/subagent-runtime/pyproject.toml` (config)

**Analog:** `cores/model-adapter/pyproject.toml`

**Full analog** (`cores/model-adapter/pyproject.toml` lines 1-20):
```toml
[project]
name = "model-adapter"
version = "0.1.0"
description = "AWS Bedrock model loader for code-wiki-agent"
requires-python = ">=3.11"
dependencies = [
    "langchain-aws>=1.4.6",
    "boto3>=1.38",
]

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.uv.build.include]
include = ["src/model_adapter/models.toml"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
```

**Key differences for subagent-runtime:**
- `name = "subagent-runtime"`, `description` updated
- Add `langchain-core>=1.4.0` and `model-adapter` to `dependencies`
- Add `[tool.uv.sources]` block: `model-adapter = { workspace = true }`
- Add `asyncio_mode = "auto"` to `[tool.pytest.ini_options]` (required for async tests — NOT present in model-adapter's pyproject because it has no async tests)
- Add `markers = ["integration: requires real Bedrock (skipped by default)"]`
- No `[tool.uv.build.include]` block needed (no bundled data files)

---

### `cores/subagent-runtime/src/subagent_runtime/pool.py` (service, event-driven)

**Analog:** `cores/model-adapter/src/model_adapter/loader.py`

**Imports pattern** (`loader.py` lines 1-26):
```python
from __future__ import annotations

import tomllib
from importlib import resources
from typing import Any

import botocore.exceptions
from langchain_aws import ChatBedrockConverse

from model_adapter.exceptions import BedrockAccessDenied
```

For `pool.py`, the import pattern becomes:
```python
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from langchain_core.runnables import RunnableConfig
```

**Core asyncio gather pattern** (from RESEARCH.md — no existing analog in codebase; use verbatim):
```python
async def run_all(self, items, task, role, *, model_id, max_concurrency, recursion_limit=None):
    rlimit = recursion_limit if recursion_limit is not None else self._default_recursion_limit
    semaphore = asyncio.Semaphore(max_concurrency)   # MUST be created here, not in __init__
    trace_file = self._trace_dir / f"{int(time.time())}.jsonl"

    async def _run_one(item):
        async with semaphore:
            t0 = time.monotonic()
            try:
                result = await task(item)
                latency_ms = int((time.monotonic() - t0) * 1000)
                self._write_trace(trace_file, role, model_id, item, "success", latency_ms, result)
                return (item, result)
            except Exception as exc:
                latency_ms = int((time.monotonic() - t0) * 1000)
                self._write_trace(trace_file, role, model_id, item, "error", latency_ms, None, error=str(exc))
                return PerItemError(item=item, exception=exc)

    raw = await asyncio.gather(*(_run_one(i) for i in items), return_exceptions=True)
    result = FanOutResult()
    for r in raw:
        if isinstance(r, PerItemError):
            result.errors.append(r)
        elif isinstance(r, BaseException):
            logger.error("Unexpected gather exception: %s", r)
        else:
            result.successes.append(r)
    return result
```

**Error handling pattern — `_write_trace` OSError guard** (from RESEARCH.md anti-patterns):
```python
def _write_trace(self, path, role, model_id, item, status, latency_ms, response, *, error=None):
    tokens_in = tokens_out = None
    if response is not None and hasattr(response, "usage_metadata"):
        meta = response.usage_metadata  # None on ThrottlingException / content filter
        if meta is not None:
            tokens_in = meta.get("input_tokens")
            tokens_out = meta.get("output_tokens")
    # ... build record dict ...
    try:
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("Trace write failed (data loss): %s", exc)
        # Never raise — trace failure must not mask task success
```

**Exception class pattern** (matches `loader.py` `_GuardedChatBedrockConverse` subclass strategy — use same `object.__setattr__` bypass if needed; for dataclasses, use `@dataclass` with `field(default_factory=list)`):
```python
# loader.py lines 47-67 — subclass override without Pydantic interference
class _GuardedChatBedrockConverse(ChatBedrockConverse):
    _model_id_for_errors: str = ""
    def _original_invoke(self, *args, **kwargs):
        return ChatBedrockConverse.invoke(self, *args, **kwargs)
    def invoke(self, *args, **kwargs):
        try:
            return self._original_invoke(*args, **kwargs)
        except botocore.exceptions.ClientError as e:
            if e.response.get("Error", {}).get("Code") == "AccessDeniedException":
                raise BedrockAccessDenied(...) from e
            raise
```

For pool.py, the dataclass pattern (no Pydantic — plain stdlib `@dataclass`):
```python
@dataclass
class PerItemError:
    item: Any
    exception: Exception

@dataclass
class FanOutResult:
    successes: list[tuple[Any, Any]] = field(default_factory=list)
    errors: list[PerItemError] = field(default_factory=list)
```

**Logging pattern** (`loader.py` — no module-level logger; `server.py` lines 55-65 show stderr-only pattern):
```python
# From server.py lines 55-65
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)
# pool.py: use module-level logger (not basicConfig — that's for entrypoints)
logger = logging.getLogger(__name__)
```

---

### `cores/subagent-runtime/tests/conftest.py` (test fixture file)

**Analog:** `cores/model-adapter/tests/test_loader.py` (no conftest.py exists in model-adapter; borrow fixture style from test_loader.py's monkeypatch usage and from agents integration test patterns)

**Fixture pattern from `test_loader.py` lines 44-65**:
```python
def _build_client_error(code: str) -> botocore.exceptions.ClientError:
    return botocore.exceptions.ClientError(
        {"Error": {"Code": code, "Message": "denied"}},
        "InvokeModel",
    )

def test_invoke_wraps_access_denied_with_arn_and_iam_action(monkeypatch):
    from model_adapter.loader import make_llm
    def raise_access_denied(*a, **kw):
        raise _build_client_error("AccessDeniedException")
    llm = make_llm("haiku")
    monkeypatch.setattr(llm, "_original_invoke", raise_access_denied)
```

**For conftest.py** — use `unittest.mock.AsyncMock` + `MagicMock` (stdlib, no pytest-mock needed per CLAUDE.md):
```python
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def fake_llm_response():
    resp = MagicMock()
    resp.content = "mocked response"
    resp.usage_metadata = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    return resp

@pytest.fixture
def fake_llm_response_error():
    resp = MagicMock()
    resp.content = ""
    resp.usage_metadata = None
    return resp

@pytest.fixture
def make_task(fake_llm_response):
    def _make(*, raise_for=frozenset()):
        async def task(item):
            if item in raise_for:
                raise ValueError(f"Intentional failure for item: {item}")
            return fake_llm_response
        return task
    return _make
```

---

### `cores/subagent-runtime/tests/test_pool.py` (unit test, 12 cases)

**Analog:** `cores/model-adapter/tests/test_loader.py` (lines 1-99)

**Test file header pattern** (`test_loader.py` lines 1-12):
```python
"""Unit tests for model_adapter.loader.

Covers models.toml parsing and the BedrockAccessDenied error-wrapping path.
No real Bedrock calls — all network paths are mocked via a stub `_original_invoke`.
"""

from __future__ import annotations

import botocore.exceptions
import pytest

HAIKU_ARN = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
```

**Test function structure** (`test_loader.py` lines 16-26 — inline imports, one assert per concern):
```python
def test_make_llm_haiku_returns_chatbedrockconverse_with_haiku_arn():
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import make_llm

    llm = make_llm("haiku")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == HAIKU_ARN
```

**Key deviation for pool tests:** All pool test functions must be `async def` (pytest-asyncio `asyncio_mode="auto"` handles the loop). Pattern:
```python
async def test_partial_failure_isolation(make_task, tmp_path):
    from subagent_runtime.pool import SubagentPool, FanOutResult

    task = make_task(raise_for={"bad"})
    pool = SubagentPool(trace_dir=tmp_path / "traces")
    result = await pool.run_all(
        items=["a", "b", "bad", "c"],
        task=task,
        role="scanner",
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        max_concurrency=4,
    )
    assert len(result.successes) == 3
    assert len(result.errors) == 1
```

---

### `cores/subagent-runtime/tests/integration/test_pool_bedrock.py` (integration test)

**Analog:** `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` (lines 1-63) — exact match for integration skip pattern

**Integration skip pattern** (`test_bedrock_iam.py` lines 31-39):
```python
@pytest.mark.integration
def test_make_llm_haiku_invoke():
    """Calls real Bedrock when CODE_WIKI_RUN_INTEGRATION=1; otherwise skips."""
    if not os.environ.get("CODE_WIKI_RUN_INTEGRATION"):
        pytest.skip("Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations")
    from model_adapter.loader import make_llm

    llm = make_llm("haiku")
    result = llm.invoke("Reply with exactly: pong")
    assert result.content  # non-empty
```

**File header pattern** (`test_bedrock_iam.py` lines 1-19):
```python
"""Bedrock IAM gate tests for code-wiki-agent.

...docstring explaining what runs in CI vs integration...
"""

from __future__ import annotations

import os

import botocore.exceptions
import pytest
```

**For integration pool tests:** All functions are `async def` + `@pytest.mark.integration`:
```python
@pytest.mark.integration
async def test_partial_failure_real_bedrock(tmp_path):
    if not os.environ.get("CODE_WIKI_RUN_INTEGRATION"):
        pytest.skip("Set CODE_WIKI_RUN_INTEGRATION=1")
    from model_adapter.loader import make_llm, load_role_config
    ...
```

---

### `cores/model-adapter/src/model_adapter/models.toml` (config, extend)

**Analog:** itself — lines 1-5 (current Phase 1 state)

**Existing pattern** (`models.toml` lines 1-5):
```toml
[roles.haiku]
model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
region   = "us-east-1"

[roles.sonnet]
model_id = "us.anthropic.claude-sonnet-4-6"
region   = "us-east-1"
```

**Extension pattern** — add `max_tokens` and `max_concurrency` to existing entries, add 7 named roles after them. Keep the same 3-field alignment (`model_id`, `region`, aligned with spaces). Never modify existing `[roles.haiku]` or `[roles.sonnet]` structure — only append fields.

---

### `cores/model-adapter/src/model_adapter/loader.py` (service, extend — additions only)

**Analog:** itself — lines 28-32 (`_load_models_config`)

**Function to add** — copy the `_load_models_config()` call pattern from `make_llm()` (lines 81-84):
```python
# loader.py lines 81-86 — existing make_llm reads config the same way
def make_llm(role: str) -> ChatBedrockConverse:
    config = _load_models_config()
    role_cfg = config["roles"][role]
    model_id = role_cfg["model_id"]
    region = role_cfg.get("region", "us-east-1")
```

**New function to add** (additions only — no existing code touched):
```python
def load_role_config(role: str) -> dict:
    """Return the raw config dict for a role from models.toml.

    Raises KeyError if role is not present.
    Returns all keys present in models.toml for the role:
    {model_id, region, max_tokens (optional), max_concurrency (optional)}
    """
    config = _load_models_config()
    return config["roles"][role]  # KeyError if role absent — intentional
```

**Also extend `make_llm`** to pass `max_tokens` if present in config. Pattern using `.get()` to stay backward-compatible with old `haiku`/`sonnet` entries that may not have `max_tokens`:
```python
# Extend make_llm() at line 86 — pass max_tokens if present:
max_tokens = role_cfg.get("max_tokens")
kwargs = dict(model=model_id, region_name=region)
if max_tokens is not None:
    kwargs["max_tokens"] = max_tokens
llm = _GuardedChatBedrockConverse(**kwargs)
```

**Surgical change rule:** Only touch the `make_llm` function body at the point of `_GuardedChatBedrockConverse` construction (line 86). Add `load_role_config` as a new top-level function after `make_llm`. Touch no other lines.

---

### `agents/code-wiki-agent/src/code_wiki_agent/cli.py` (controller, extend)

**Analog:** itself — lines 1-22 (current Phase 1 state)

**Full existing file** (`cli.py` lines 1-22):
```python
from __future__ import annotations

import importlib.metadata

import typer

app = typer.Typer(
    name="code-wiki-agent",
    help="code-wiki-agent: AWS Bedrock-powered wiki maintenance CLI.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print version and exit."""
    v = importlib.metadata.version("code-wiki-agent")
    typer.echo(f"code-wiki-agent {v}")


if __name__ == "__main__":
    app()
```

**New command pattern** — copy the `@app.command()` + `typer.echo()` pattern from the `version` command. The `trace` command accepts a `file` argument (Typer `Path` type) and writes to stdout via `typer.echo()`:
```python
@app.command()
def trace(file: Path) -> None:
    """Render a JSONL trace file as a human-readable timeline."""
    import json
    for line in file.read_text().splitlines():
        record = json.loads(line)
        typer.echo(...)  # planner designs the exact format (OBS-02)
```

**Surgical change rule:** Add `from pathlib import Path` import only if not already present. Add the `trace` command function before the `if __name__ == "__main__"` block. Touch no other lines.

---

### `agents/code-wiki-agent/tests/unit/test_trace_viewer.py` (unit test)

**Analog:** `agents/code-wiki-agent/tests/unit/test_cli_help.py` (lines 1-13)

**Full analog** (`test_cli_help.py` lines 1-13):
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

**For trace viewer tests:** Use the same `subprocess.run` pattern to invoke `code-wiki-agent trace <file>` against a tmp JSONL file, asserting stdout content. Also test the trace rendering function directly if it is extracted as a pure function (preferred for faster unit tests):
```python
from __future__ import annotations
import json
import pytest
from pathlib import Path


def test_trace_command_renders_jsonl(tmp_path):
    record = {"role": "scanner", "model_id": "...", "status": "success", "latency_ms": 100, ...}
    trace_file = tmp_path / "trace.jsonl"
    trace_file.write_text(json.dumps(record) + "\n")

    result = subprocess.run(
        ["uv", "run", "--package", "code-wiki-agent", "code-wiki-agent", "trace", str(trace_file)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "scanner" in result.stdout
```

---

## Shared Patterns

### `from __future__ import annotations` header
**Source:** Every existing source file (`loader.py` line 1, `server.py` line 15, `test_loader.py` line 3, `test_bedrock_iam.py` line 3)
**Apply to:** All new `.py` files — first line in every file

### Stderr-only logging
**Source:** `agents/code-wiki-agent/src/code_wiki_mcp/server.py` lines 55-65
```python
logging.basicConfig(
    stream=sys.stderr,
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)
logging.getLogger("boto3").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
```
**Apply to:** `pool.py` uses `logging.getLogger(__name__)` (module logger, not `basicConfig`). `basicConfig` is for entrypoints only. Pool must never write to stdout.

### KeyError on unknown role (intentional)
**Source:** `loader.py` lines 81-83
```python
config = _load_models_config()
role_cfg = config["roles"][role]  # KeyError if role absent — intentional
```
**Apply to:** `load_role_config()` in `loader.py` — same pattern, same intentional KeyError.

### Integration test skip gate
**Source:** `agents/code-wiki-agent/tests/integration/test_bedrock_iam.py` lines 31-37
```python
@pytest.mark.integration
def test_make_llm_haiku_invoke():
    if not os.environ.get("CODE_WIKI_RUN_INTEGRATION"):
        pytest.skip("Set CODE_WIKI_RUN_INTEGRATION=1 to run real Bedrock invocations")
```
**Apply to:** All functions in `tests/integration/test_pool_bedrock.py` — same env var name `CODE_WIKI_RUN_INTEGRATION`.

### uv workspace build system block
**Source:** `cores/model-adapter/pyproject.toml` lines 11-13
```toml
[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"
```
**Apply to:** `cores/subagent-runtime/pyproject.toml` — identical block.

### workspace dep declaration
**Source:** `agents/code-wiki-agent/pyproject.toml` lines 23-26
```toml
[tool.uv.sources]
vault-io      = { workspace = true }
model-adapter = { workspace = true }
```
**Apply to:** `cores/subagent-runtime/pyproject.toml` — add `[tool.uv.sources]` block with `model-adapter = { workspace = true }`.

### Typer command pattern
**Source:** `agents/code-wiki-agent/src/code_wiki_agent/cli.py` lines 14-18
```python
@app.command()
def version() -> None:
    """Print version and exit."""
    v = importlib.metadata.version("code-wiki-agent")
    typer.echo(f"code-wiki-agent {v}")
```
**Apply to:** `trace` command in `cli.py` — same decorator, same `typer.echo()` for output.

---

## No Analog Found

No files are without analog. All 10 files have at least a role-match analog in the existing codebase.

---

## Metadata

**Analog search scope:** `cores/model-adapter/`, `cores/vault-io/`, `agents/code-wiki-agent/`, workspace root `pyproject.toml`
**Files scanned:** 12 source files read (loader.py, models.toml, test_loader.py, cli.py, server.py, test_bedrock_iam.py, test_cli_help.py, test_stdout_guard.py, model-adapter/pyproject.toml, code-wiki-agent/pyproject.toml, root pyproject.toml, test_bedrock_iam.py)
**Pattern extraction date:** 2026-05-13
