# `gw --verbose` (`-v` / `-vv`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global `-v/-vv/--verbose` flag to the `gw` CLI that streams a live, step-by-step execution log (fan-out start/completion/summary plus existing module logs) to stderr without polluting stdout or changing `gw trace`.

**Architecture:** Logging-based and decoupled. The pool and command modules emit lifecycle and per-item lines *unconditionally* through the `logging` module; a new root Typer callback installs a stderr handler at INFO (`-v`) or DEBUG (`-vv`). The pool never learns about "verbose" — the entry point decides what surfaces. The per-record line renderer moves into `subagent_runtime/trace_io.py` so the pool (live) and `gw trace` (post-hoc) share one source of truth.

**Tech Stack:** Python 3.11, `uv` workspace, Typer (counted option), stdlib `logging`, pytest + `pytest-asyncio` (`asyncio_mode = "auto"`), Typer `CliRunner`, `caplog`.

---

## File Structure

**Modified:**
- `packages/subagent-runtime/src/subagent_runtime/trace_io.py` — gains public `render_trace_record`; `write_trace_record` returns the record it builds.
- `packages/subagent-runtime/src/subagent_runtime/pool.py` — `run_all` logs fan-out start/summary; `_run_one` logs per-item start (DEBUG); `_write_trace` logs each completion line through a dedicated trace logger.
- `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py` — `trace` command imports the shared renderer (drops local `_render_trace_record`); new root callback wires `-v/-vv/--verbose` to `configure_verbose_logging`.

**Created:**
- `packages/graph-wiki-cli/src/graph_wiki_cli/logging_config.py` — `configure_verbose_logging(verbosity: int) -> None`.

**Tests (modified):**
- `packages/subagent-runtime/tests/test_trace_io.py`
- `packages/graph-wiki-cli/tests/unit/test_trace_viewer.py`

**Tests (created):**
- `packages/subagent-runtime/tests/test_pool_logging.py`
- `packages/graph-wiki-cli/tests/unit/test_logging_config.py`
- `packages/graph-wiki-cli/tests/unit/test_cli_verbose.py`

**Test commands:**
- subagent-runtime: `uv run --package subagent-runtime pytest <path> -v`
- graph-wiki-cli: `uv run --package graph-wiki-cli pytest <path> -v`

---

## Task 1: Shared renderer + record-returning writer in `trace_io.py`

Move the per-record line renderer into `trace_io` as a public function and make `write_trace_record` return the dict it builds (backward compatible — current callers ignore the return value).

**Files:**
- Modify: `packages/subagent-runtime/src/subagent_runtime/trace_io.py`
- Test: `packages/subagent-runtime/tests/test_trace_io.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/subagent-runtime/tests/test_trace_io.py`:

```python
def test_write_trace_record_returns_record(tmp_path):
    """write_trace_record returns the dict it built AND writes the same record to disk."""
    import json
    from subagent_runtime.trace_io import write_trace_record

    path = tmp_path / "t.jsonl"
    returned = write_trace_record(
        path, "scanner", "model-x", "page-a", "success", 100, None,
    )
    assert isinstance(returned, dict)
    assert returned["role"] == "scanner"
    assert returned["status"] == "success"
    assert returned["item_id"] == "page-a"
    # Backward compat: the on-disk record matches the returned dict exactly.
    written = json.loads(path.read_text().splitlines()[0])
    assert written == returned


def test_render_trace_record_format():
    """render_trace_record renders a single human-readable line for a record."""
    from subagent_runtime.trace_io import render_trace_record

    record = {
        "timestamp": "2026-05-13T10:00:00Z",
        "role": "scanner",
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "item_id": "page-a",
        "status": "success",
        "latency_ms": 350,
        "tokens_in": 10,
        "tokens_out": 5,
    }
    out = render_trace_record(record)
    assert isinstance(out, str)
    assert "scanner" in out
    assert "page-a" in out
    assert "success" in out
    assert "350ms" in out
    assert "10->5" in out
    # Model id is rendered as its last 30 chars (matches gw trace convention).
    assert record["model_id"][-30:] in out


def test_render_trace_record_error_suffix():
    """Error records append an ERROR: <message> suffix."""
    from subagent_runtime.trace_io import render_trace_record

    record = {
        "timestamp": "2026-05-13T10:00:00Z",
        "role": "scanner",
        "model_id": "model-x",
        "item_id": "page-b",
        "status": "error",
        "latency_ms": 12,
        "tokens_in": None,
        "tokens_out": None,
        "error": "boom",
    }
    out = render_trace_record(record)
    assert "ERROR: boom" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package subagent-runtime pytest packages/subagent-runtime/tests/test_trace_io.py -v`
Expected: FAIL — `test_render_trace_record_*` fail with `ImportError: cannot import name 'render_trace_record'`; `test_write_trace_record_returns_record` fails on `assert isinstance(returned, dict)` (currently returns `None`).

- [ ] **Step 3: Add `render_trace_record` and return the record**

In `packages/subagent-runtime/src/subagent_runtime/trace_io.py`, change the `write_trace_record` signature's return annotation and append a `return record`. The function currently ends:

```python
    try:
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("Trace write failed (data loss): %s", exc)
```

Change the signature line `) -> None:` to `) -> dict[str, Any]:` and add `return record` after the `try/except`:

```python
    try:
        with path.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as exc:
        logger.warning("Trace write failed (data loss): %s", exc)

    return record
```

Then add this new public function immediately after `write_trace_record` (before `_compute_cost_usd`):

```python
def render_trace_record(record: dict) -> str:
    """Return a single-line human-readable representation of a trace record.

    Single source of truth for the per-record line format, shared by the live
    fan-out log (subagent_runtime.pool) and the post-hoc `gw trace` viewer.

    Fields: timestamp role model_id(last 30 chars) item_id(first 40 chars)
            status latency_ms tokens_in -> tokens_out
    Error records append: ERROR: <error message>
    Missing fields are substituted with '-' so .get() never raises KeyError.
    """
    timestamp = record.get("timestamp", "-")
    role = record.get("role", "-")
    model_id = record.get("model_id", "-")
    model_short = model_id[-30:] if model_id != "-" else "-"
    item_id = record.get("item_id", "-")
    item_short = item_id[:40] if item_id != "-" else "-"
    status = record.get("status", "-")
    latency_ms = record.get("latency_ms", "-")
    tokens_in = record.get("tokens_in", "-")
    tokens_out = record.get("tokens_out", "-")

    line = (
        f"[{timestamp}] {role} {model_short} {item_short} "
        f"{status} {latency_ms}ms {tokens_in}->{tokens_out}"
    )
    if record.get("status") == "error":
        line += f"  ERROR: {record.get('error', '')}"
    return line
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package subagent-runtime pytest packages/subagent-runtime/tests/test_trace_io.py -v`
Expected: PASS — all three new tests plus the pre-existing trace_io tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/subagent-runtime/src/subagent_runtime/trace_io.py packages/subagent-runtime/tests/test_trace_io.py
git commit -m "feat(trace-io): add render_trace_record; write_trace_record returns the record"
```

---

## Task 2: `gw trace` uses the shared renderer

Make the `trace` command import `render_trace_record` from `trace_io` and drop the local `_render_trace_record`. The collapsing/aggregation helpers (`_render_collapsed_group`, `_aggregate_trace`, `_is_groupable`) stay in `cli.py` — they are post-hoc-only. Add a parity test proving the live-emitted string equals what `gw trace --expand` prints.

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_trace_viewer.py`

- [ ] **Step 1: Write the failing parity test and fix the existing import test**

In `packages/graph-wiki-cli/tests/unit/test_trace_viewer.py`, change the import in `test_render_trace_record_pure_function` (currently at line 128) from:

```python
    from graph_wiki_cli.cli import _render_trace_record
```

to:

```python
    from subagent_runtime.trace_io import render_trace_record as _render_trace_record
```

Then append a new parity test:

```python
def test_live_render_matches_trace_expand(tmp_path):
    """The string the pool emits live equals what `gw trace --expand` prints
    for the same record — both go through subagent_runtime.trace_io.render_trace_record.
    """
    from typer.testing import CliRunner
    from subagent_runtime.trace_io import render_trace_record
    from graph_wiki_cli.cli import app

    record = {
        "schema_version": 1,
        "role": "scanner",
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "item_id": "page-a",
        "status": "success",
        "latency_ms": 350,
        "tokens_in": 10,
        "tokens_out": 5,
        "cost_usd": None,
        "timestamp": "2026-05-13T10:00:00Z",
    }
    trace_file = tmp_path / "one.jsonl"
    trace_file.write_text(json.dumps(record) + "\n")

    expected_line = render_trace_record(record)

    runner = CliRunner()
    result = runner.invoke(app, ["trace", str(trace_file), "--expand"])
    assert result.exit_code == 0
    assert expected_line in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_trace_viewer.py::test_render_trace_record_pure_function packages/graph-wiki-cli/tests/unit/test_trace_viewer.py::test_live_render_matches_trace_expand -v`
Expected: `test_render_trace_record_pure_function` PASSES (the function exists in `trace_io` after Task 1). `test_live_render_matches_trace_expand` PASSES too — but run it now to confirm; if `gw trace` still uses its own renderer it will still match by coincidence. The real guard is the next step's refactor not breaking it.

> Note: this test passes before and after the refactor by design (it pins the contract). Proceed to wire the refactor; it must stay green.

- [ ] **Step 3: Import the shared renderer and delete the local one**

In `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`, add the import alongside the other package imports (after the `from graph_wiki_core.commands.scan import run_scan` line, ~line 67):

```python
from subagent_runtime.trace_io import render_trace_record
```

Delete the entire local `_render_trace_record` function (the `def _render_trace_record(record: dict) -> str:` block and its docstring/body, ~lines 197-222).

Replace the three call sites that reference the deleted function (in the `trace` command body):

```python
            typer.echo(_render_trace_record(record))
```
→
```python
            typer.echo(render_trace_record(record))
```

```python
                typer.echo(_render_trace_record(current_run[0]))
```
→
```python
                typer.echo(render_trace_record(current_run[0]))
```

```python
                typer.echo(_render_trace_record(record))
```
→
```python
                typer.echo(render_trace_record(record))
```

(Three occurrences total — use the surrounding context to disambiguate; the first is in the `if expand:` branch, the other two are in the default-collapse branch.)

- [ ] **Step 4: Run the full trace-viewer suite to verify it passes**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_trace_viewer.py -v`
Expected: PASS — all trace-viewer tests (including the snapshot tests under `__snapshots__`) pass with the shared renderer, and the new parity test is green.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/cli.py packages/graph-wiki-cli/tests/unit/test_trace_viewer.py
git commit -m "refactor(cli): gw trace uses shared render_trace_record from trace_io"
```

---

## Task 3: `logging_config.py` — `configure_verbose_logging`

New module that installs stderr handlers gated by verbosity. Idempotent; a no-op at verbosity 0.

**Files:**
- Create: `packages/graph-wiki-cli/src/graph_wiki_cli/logging_config.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_logging_config.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/graph-wiki-cli/tests/unit/test_logging_config.py`:

```python
from __future__ import annotations

"""Unit tests for graph_wiki_cli.logging_config.configure_verbose_logging."""

import logging
import sys

import pytest


@pytest.fixture(autouse=True)
def _restore_logging():
    """Snapshot and restore global logging state — these tests mutate the root logger."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    trace = logging.getLogger("subagent_runtime.pool.trace")
    saved_trace_handlers = trace.handlers[:]
    saved_trace_level = trace.level
    saved_trace_propagate = trace.propagate
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    trace.handlers[:] = saved_trace_handlers
    trace.setLevel(saved_trace_level)
    trace.propagate = saved_trace_propagate


def _gw_handlers(logger):
    return [h for h in logger.handlers if getattr(h, "_gw_verbose_handler", False)]


def test_verbosity_zero_is_noop():
    from graph_wiki_cli.logging_config import configure_verbose_logging

    root = logging.getLogger()
    before = root.handlers[:]
    configure_verbose_logging(0)
    assert root.handlers == before
    assert _gw_handlers(root) == []


def test_verbosity_one_installs_info_stderr_handler():
    from graph_wiki_cli.logging_config import configure_verbose_logging

    configure_verbose_logging(1)
    root = logging.getLogger()
    assert root.level == logging.INFO
    handlers = _gw_handlers(root)
    assert len(handlers) == 1
    # stdout stays clean — verbose output goes to stderr only.
    assert handlers[0].stream is sys.stderr


def test_verbosity_two_installs_debug_handler():
    from graph_wiki_cli.logging_config import configure_verbose_logging

    configure_verbose_logging(2)
    assert logging.getLogger().level == logging.DEBUG


def test_trace_logger_has_bare_formatter_and_no_propagate():
    from graph_wiki_cli.logging_config import configure_verbose_logging

    configure_verbose_logging(1)
    trace = logging.getLogger("subagent_runtime.pool.trace")
    handlers = _gw_handlers(trace)
    assert len(handlers) == 1
    assert handlers[0].formatter._fmt == "%(message)s"
    assert trace.propagate is False


def test_boto_loggers_pinned_to_warning():
    from graph_wiki_cli.logging_config import configure_verbose_logging

    configure_verbose_logging(2)
    for name in ("boto3", "botocore", "urllib3"):
        assert logging.getLogger(name).level == logging.WARNING


def test_idempotent_no_duplicate_handlers():
    from graph_wiki_cli.logging_config import configure_verbose_logging

    configure_verbose_logging(1)
    configure_verbose_logging(1)
    assert len(_gw_handlers(logging.getLogger())) == 1
    assert len(_gw_handlers(logging.getLogger("subagent_runtime.pool.trace"))) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_logging_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'graph_wiki_cli.logging_config'`.

- [ ] **Step 3: Write the module**

Create `packages/graph-wiki-cli/src/graph_wiki_cli/logging_config.py`:

```python
from __future__ import annotations

"""Verbose-logging configuration for the `gw` CLI.

Installs stderr logging handlers gated by the root `-v/-vv` flag. Absent the
flag (verbosity == 0) this is a no-op: no handler is installed and the CLI
produces no new stderr output (today's behavior preserved exactly).

The fan-out trace logger (``subagent_runtime.pool.trace``) gets a DEDICATED
handler with a bare ``%(message)s`` formatter and ``propagate=False``, so live
per-item completion lines stay byte-identical to ``gw trace`` output.
"""

import logging
import sys

# Logger carrying per-item completion lines already rendered via
# render_trace_record. MUST match the trace logger name in
# subagent_runtime.pool (``<pool-module>.trace``).
_FANOUT_TRACE_LOGGER = "subagent_runtime.pool.trace"

# Marks handlers this module installed, so repeated calls are idempotent.
_HANDLER_FLAG = "_gw_verbose_handler"


def configure_verbose_logging(verbosity: int) -> None:
    """Install stderr logging handlers for the given verbosity.

    verbosity == 0 -> no-op (no handler installed).
    verbosity == 1 -> INFO  on the root logger.
    verbosity >= 2 -> DEBUG on the root logger.

    All output goes to stderr; stdout stays clean. Idempotent: safe to call
    once per process; never duplicates handlers.
    """
    if verbosity <= 0:
        return

    level = logging.INFO if verbosity == 1 else logging.DEBUG

    root = logging.getLogger()
    if not _has_gw_handler(root):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        setattr(handler, _HANDLER_FLAG, True)
        root.addHandler(handler)
    root.setLevel(level)

    # Dedicated handler for per-item trace lines: bare message, no propagation,
    # so the LEVEL/name prefix never leaks into trace-format output.
    trace_logger = logging.getLogger(_FANOUT_TRACE_LOGGER)
    if not _has_gw_handler(trace_logger):
        trace_handler = logging.StreamHandler(sys.stderr)
        trace_handler.setFormatter(logging.Formatter("%(message)s"))
        setattr(trace_handler, _HANDLER_FLAG, True)
        trace_logger.addHandler(trace_handler)
    trace_logger.setLevel(logging.INFO)
    trace_logger.propagate = False

    # Mirror graph_wiki_mcp/server.py:74-75 — keep AWS SDK chatter out of -vv.
    for noisy in ("boto3", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _has_gw_handler(logger: logging.Logger) -> bool:
    """True if this module already installed a handler on ``logger``."""
    return any(getattr(h, _HANDLER_FLAG, False) for h in logger.handlers)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_logging_config.py -v`
Expected: PASS — all six tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/logging_config.py packages/graph-wiki-cli/tests/unit/test_logging_config.py
git commit -m "feat(cli): add configure_verbose_logging (stderr handlers, idempotent)"
```

---

## Task 4: Root callback wires `-v/-vv/--verbose`

Add a root Typer callback on `app` that parses the global counted flag before the subcommand and calls `configure_verbose_logging`.

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`
- Test: `packages/graph-wiki-cli/tests/unit/test_cli_verbose.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/graph-wiki-cli/tests/unit/test_cli_verbose.py`:

```python
from __future__ import annotations

"""Tests for the gw root --verbose/-v/-vv callback."""

import os
import subprocess

import pytest

_PLAIN_ENV = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"}


@pytest.mark.parametrize(
    "argv,expected",
    [
        (["version"], 0),
        (["-v", "version"], 1),
        (["-vv", "version"], 2),
        (["--verbose", "version"], 1),
    ],
)
def test_callback_passes_verbosity_count(monkeypatch, argv, expected):
    """The root callback calls configure_verbose_logging with the counted -v value."""
    from typer.testing import CliRunner
    import graph_wiki_cli.cli as cli

    calls: list[int] = []
    monkeypatch.setattr(cli, "configure_verbose_logging", lambda v: calls.append(v))

    runner = CliRunner()
    result = runner.invoke(cli.app, argv)
    assert result.exit_code == 0, result.output
    assert calls == [expected]


def test_verbose_keeps_stdout_clean_for_version():
    """`gw -v version` writes only the version banner to stdout (logs go to stderr)."""
    result = subprocess.run(
        ["uv", "run", "--package", "graph-wiki-cli", "gw", "-v", "version"],
        capture_output=True,
        text=True,
        env=_PLAIN_ENV,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert result.stdout.startswith("gw ")
    # Exactly one line on stdout — no verbose noise leaked from stderr.
    assert "\n" not in result.stdout.strip()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_cli_verbose.py -v`
Expected: FAIL — `test_callback_passes_verbosity_count[...-v...]` fails because `gw` rejects the unknown `-v` option (no callback exists yet); `monkeypatch.setattr(cli, "configure_verbose_logging", ...)` also fails with `AttributeError` because the name is not yet imported into `cli`.

- [ ] **Step 3: Import the config function and add the callback**

In `packages/graph-wiki-cli/src/graph_wiki_cli/cli.py`, add the import alongside the other package imports (near the `from subagent_runtime.trace_io import render_trace_record` line added in Task 2):

```python
from graph_wiki_cli.logging_config import configure_verbose_logging
```

Then add a root callback immediately after the `app = typer.Typer(...)` block (after the closing `)` at ~line 73, before the `KNOWN_SCHEMA_VERSION` comment):

```python
@app.callback()
def _root(
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help=(
            "Stream a live execution log to stderr (-v = INFO, -vv = DEBUG). "
            "stderr only — stdout stays clean, so `gw -v query ... --json | jq` "
            "still works. Independent of a command's own --quiet."
        ),
    ),
) -> None:
    """gw: AWS Bedrock-powered wiki maintenance CLI."""
    configure_verbose_logging(verbose)
```

> The callback docstring is intentionally identical to the existing `app` help string so `gw --help`'s banner is unchanged. `count=True` makes `-v`→1, `-vv`→2, and `--verbose`→1 (alias for a single `-v`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_cli_verbose.py -v`
Expected: PASS — all four parametrized callback cases and the stdout-clean subprocess test pass.

- [ ] **Step 5: Confirm existing help tests still pass**

Run: `uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_cli_help.py -v`
Expected: PASS — `--help` still exits 0 and lists the same subcommands (the callback added a `-v` option but did not change the command list or banner).

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/cli.py packages/graph-wiki-cli/tests/unit/test_cli_verbose.py
git commit -m "feat(cli): add global -v/-vv/--verbose root callback"
```

---

## Task 5: Pool emits fan-out lifecycle + per-item logs

Make `SubagentPool.run_all` log a fan-out start (INFO) and summary (INFO); `_run_one` log a per-item start (DEBUG) after acquiring the semaphore; and `_write_trace` log each completion line at INFO through a dedicated trace logger. The pool stays ignorant of verbosity — it always logs; the installed handler (or its absence) decides what surfaces.

**Files:**
- Modify: `packages/subagent-runtime/src/subagent_runtime/pool.py`
- Test: `packages/subagent-runtime/tests/test_pool_logging.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/subagent-runtime/tests/test_pool_logging.py`:

```python
from __future__ import annotations

"""Fan-out lifecycle logging tests for SubagentPool (gw --verbose).

The pool logs unconditionally; these tests use caplog (which captures via the
root logger by propagation) to assert what is emitted at INFO vs DEBUG.
"""

import logging


async def test_fanout_emits_start_completions_and_summary(tmp_path, make_task, caplog):
    from subagent_runtime.pool import SubagentPool

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    task = make_task()

    with caplog.at_level(logging.INFO):
        result = await pool.run_all(
            items=["a", "b"],
            task=task,
            role="librarian",
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            max_concurrency=5,
        )

    assert len(result.successes) == 2

    starts = [
        r for r in caplog.records
        if r.name == "subagent_runtime.pool" and r.getMessage().startswith("-> fan-out start:")
    ]
    summaries = [
        r for r in caplog.records
        if r.name == "subagent_runtime.pool" and r.getMessage().startswith("ok fan-out done:")
    ]
    completions = [r for r in caplog.records if r.name == "subagent_runtime.pool.trace"]

    assert len(starts) == 1
    assert "role=librarian" in starts[0].getMessage()
    assert "items=2" in starts[0].getMessage()
    assert "concurrency=5" in starts[0].getMessage()

    assert len(completions) == 2
    assert all("success" in r.getMessage() for r in completions)

    assert len(summaries) == 1
    assert "2 ok / 0 err" in summaries[0].getMessage()


async def test_per_item_start_only_at_debug(tmp_path, make_task, caplog):
    from subagent_runtime.pool import SubagentPool

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    task = make_task()

    # At INFO: per-item start lines (DEBUG) are NOT emitted.
    with caplog.at_level(logging.INFO):
        await pool.run_all(
            items=["a"], task=task, role="librarian", model_id="m", max_concurrency=1
        )
    info_item_starts = [
        r for r in caplog.records if r.getMessage().startswith("-> item start:")
    ]
    assert info_item_starts == []

    caplog.clear()

    # At DEBUG: one per-item start line per item.
    with caplog.at_level(logging.DEBUG):
        await pool.run_all(
            items=["a", "b"], task=task, role="librarian", model_id="m", max_concurrency=1
        )
    debug_item_starts = [
        r for r in caplog.records if r.getMessage().startswith("-> item start:")
    ]
    assert len(debug_item_starts) == 2


async def test_error_completion_line_is_logged(tmp_path, make_task, caplog):
    from subagent_runtime.pool import SubagentPool

    pool = SubagentPool(trace_dir=tmp_path / "traces")
    task = make_task(raise_for={"b"})

    with caplog.at_level(logging.INFO):
        result = await pool.run_all(
            items=["a", "b"], task=task, role="librarian", model_id="m", max_concurrency=2
        )

    assert len(result.successes) == 1
    assert len(result.errors) == 1

    completions = [r for r in caplog.records if r.name == "subagent_runtime.pool.trace"]
    assert len(completions) == 2
    assert any("error" in r.getMessage() for r in completions)

    summaries = [
        r for r in caplog.records
        if r.name == "subagent_runtime.pool" and r.getMessage().startswith("ok fan-out done:")
    ]
    assert "1 ok / 1 err" in summaries[0].getMessage()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package subagent-runtime pytest packages/subagent-runtime/tests/test_pool_logging.py -v`
Expected: FAIL — `starts`, `summaries`, and `completions` lists are empty because the pool emits no lifecycle/trace logging yet.

- [ ] **Step 3: Add the dedicated trace logger and the render import**

In `packages/subagent-runtime/src/subagent_runtime/pool.py`, change the import:

```python
from subagent_runtime.trace_io import write_trace_record
```
→
```python
from subagent_runtime.trace_io import render_trace_record, write_trace_record
```

Add a dedicated trace logger right after the existing module logger (`logger = logging.getLogger(__name__)`, ~line 41):

```python
logger = logging.getLogger(__name__)
# Dedicated logger for per-item completion lines (trace format). The CLI's
# configure_verbose_logging attaches a bare-message handler with propagate=False
# so these lines stay byte-identical to `gw trace`.
_trace_logger = logging.getLogger(__name__ + ".trace")
```

- [ ] **Step 4: Log fan-out start and summary in `run_all`**

In `run_all`, add the start log immediately before `batch_t0 = time.monotonic()` (right after the `_task_arity_2` introspection block and the `_run_one` definition — i.e. just before the dispatch):

```python
        logger.info(
            "-> fan-out start: role=%s model=%s items=%d concurrency=%d",
            role,
            model_id,
            len(items),
            max_concurrency,
        )

        # return_exceptions=True: one failure does NOT cancel siblings (deepagents #694).
        batch_t0 = time.monotonic()
```

Then add the summary log just before `return fan_result` at the end of `run_all`:

```python
        logger.info(
            "ok fan-out done: %d ok / %d err in %.2fs",
            len(fan_result.successes),
            len(fan_result.errors),
            time.monotonic() - batch_t0,
        )
        return fan_result
```

- [ ] **Step 5: Log per-item start in `_run_one`**

In `_run_one`, add a DEBUG log immediately after acquiring the semaphore and before `t0 = time.monotonic()`:

```python
        async with semaphore:
            logger.debug("-> item start: %s", getattr(item, "id", None) or str(item))
            t0 = time.monotonic()
```

- [ ] **Step 6: Log each completion line from `_write_trace`**

Change `_write_trace` to capture the returned record and log it through the dedicated trace logger:

```python
    def _write_trace(
        self,
        path: Path,
        role: str,
        model_id: str,
        item: Any,
        status: str,
        latency_ms: int,
        response: Any,
        *,
        error: str | None = None,
    ) -> None:
        """Thin delegate to subagent_runtime.trace_io.write_trace_record (Phase 16 D-04).

        Also emits the per-item completion line at INFO through the dedicated
        fan-out trace logger so `gw -v` can surface live progress. The pool stays
        ignorant of verbosity — it always logs; the installed handler decides
        what shows.
        """
        record = write_trace_record(
            path, role, model_id, item, status, latency_ms, response, error=error
        )
        _trace_logger.info(render_trace_record(record))
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run --package subagent-runtime pytest packages/subagent-runtime/tests/test_pool_logging.py -v`
Expected: PASS — all three logging tests pass.

- [ ] **Step 8: Run the full pool suite to confirm no regressions**

Run: `uv run --package subagent-runtime pytest packages/subagent-runtime/tests/test_pool.py packages/subagent-runtime/tests/test_trace_io.py -v`
Expected: PASS — existing pool/trace tests still pass (the new logging is additive; `_write_trace`'s observable I/O behavior is unchanged).

- [ ] **Step 9: Commit**

```bash
git add packages/subagent-runtime/src/subagent_runtime/pool.py packages/subagent-runtime/tests/test_pool_logging.py
git commit -m "feat(pool): emit fan-out start/summary/per-item logs for gw --verbose"
```

---

## Task 6: Full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run both affected package suites**

Run:
```bash
uv run --package subagent-runtime pytest packages/subagent-runtime/tests -q
uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests -q
```
Expected: PASS for both — no regressions across the pool, trace-io, trace-viewer, CLI help, query, and new verbose/logging tests.

- [ ] **Step 2: Manual smoke (optional, no Bedrock required)**

Run:
```bash
uv run --package graph-wiki-cli gw -v trace packages/graph-wiki-cli/tests/unit/__snapshots__/* 2>/dev/null || true
uv run --package graph-wiki-cli gw --help
```
Expected: `gw --help` shows the `-v/--verbose` option under Options and exits 0; the banner text is unchanged.

---

## Self-Review

**Spec coverage:**
- §"Components and changes" #1 (move renderer to `trace_io`, `write_trace_record` returns record) → Task 1.
- §"Components and changes" #2 (`trace` imports shared renderer, drops local; keep collapsing helpers; add root callback) → Task 2 (renderer) + Task 4 (callback).
- §"Components and changes" #3 (new `logging_config.py`, no-op at 0, stderr handler at INFO/DEBUG, dedicated bare-formatter handler with `propagate=False`, boto3/botocore/urllib3 pinned, idempotent) → Task 3.
- §"Components and changes" #4 (pool start/summary INFO, per-item start DEBUG, completion via `render_trace_record` on a dedicated logger, pool stays verbosity-ignorant) → Task 5.
- §"CLI surface" (counted `-v`, `--verbose` alias, stderr-only, `--quiet` independence in help text, absent flag = no handler) → Task 4 (callback + help text) + Task 3 (no-op at 0).
- §"Testing" — pool caplog tests → Task 5; renderer parity test → Task 2; CLI handler-level/no-noise/json-clean → Task 3 (handler stream/level + idempotency) and Task 4 (callback count + stdout-clean smoke); backward-compat writer test → Task 1.
- §"Out of scope" — MCP logging untouched, no `GW_VERBOSE`, no JSONL schema change, no per-command verbose flags: honored (no tasks touch those).

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to Task N". Every code step contains complete code; every test step contains full assertions.

**Type/name consistency:** `render_trace_record` (public, in `trace_io`) is defined in Task 1 and imported in Tasks 2 and 5. `configure_verbose_logging(verbosity: int) -> None` defined in Task 3, imported/called in Task 4. The fan-out trace logger name `subagent_runtime.pool.trace` is consistent between `logging_config._FANOUT_TRACE_LOGGER` (Task 3) and `pool._trace_logger = logging.getLogger(__name__ + ".trace")` (Task 5, where `__name__ == "subagent_runtime.pool"`). The handler sentinel `_gw_verbose_handler` matches between `logging_config._HANDLER_FLAG` and the test helper `_gw_handlers`. `write_trace_record` return type `dict[str, Any]` (Task 1) is consumed by `_write_trace` (Task 5).

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-01-gw-verbose-flag.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
