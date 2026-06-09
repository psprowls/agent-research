# Add Informative Stderr Instrumentation to Claude-Code-Eval

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide real-time visibility into cc-eval test execution by writing structured, timestamped logs to stderr showing fixture setup, prompts, Claude messages, tool calls, and execution flow.

**Architecture:** Create a lightweight structured logger that writes to stderr with timestamps and context tags. Instrument isolation (fixture/worktree setup), runner (prompt and Claude invocation details), and orchestrator (scenario execution flow) to emit logs at key points. Parse stream-json output to extract tool calls and assistant/user messages. Logs are always-on by default but configurable via `CLAUDE_EVAL_STDERR=0` env var to disable for tests that need clean output.

**Tech Stack:** Python stdlib `sys.stderr`, `json` for structured logs, existing stream-json parsing in transcript.py

---

## File Structure

```
packages/claude-code-evals/src/claude_code_evals/
├── stderr_logger.py                    # NEW: Structured stderr logging
├── isolation.py                        # MODIFY: Log fixture setup/teardown
├── runner.py                           # MODIFY: Log prompt details, stream events
├── orchestrator.py                     # MODIFY: Log scenario/config execution
└── transcript.py                       # MODIFY: Add tool-call extractor helper

packages/claude-code-evals/tests/
├── test_stderr_logger.py               # NEW: Test logger functionality
└── (existing tests remain, some may need CLAUDE_EVAL_STDERR=0)
```

---

## Task 1: Create stderr_logger.py Module

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/stderr_logger.py`
- Test: `packages/claude-code-evals/tests/test_stderr_logger.py`

- [ ] **Step 1: Write test for the logger module**

```python
# packages/claude-code-evals/tests/test_stderr_logger.py
import io
import sys
from pathlib import Path

from claude_code_evals.stderr_logger import EvalLogger, set_logger_enabled


def test_logger_writes_to_stderr(capsys):
    """Verify logs are written to stderr with timestamp and context."""
    logger = EvalLogger("test_context")
    logger.log("test message")
    
    captured = capsys.readouterr()
    assert "test message" in captured.err
    assert "test_context" in captured.err
    

def test_logger_disabled_by_env(monkeypatch, capsys):
    """Verify CLAUDE_EVAL_STDERR=0 disables logging."""
    monkeypatch.setenv("CLAUDE_EVAL_STDERR", "0")
    set_logger_enabled(False)
    
    logger = EvalLogger("test")
    logger.log("should not appear")
    
    captured = capsys.readouterr()
    assert "should not appear" not in captured.err


def test_logger_formats_dict_data(capsys):
    """Verify dict data is formatted as readable key=value pairs."""
    logger = EvalLogger("fixture_setup")
    logger.log_dict("Isolation created", {
        "worktree": "/tmp/wt",
        "scenario": "test-scenario",
        "config": "test-config"
    })
    
    captured = capsys.readouterr()
    assert "Isolation created" in captured.err
    assert "worktree=/tmp/wt" in captured.err or '"worktree": "/tmp/wt"' in captured.err
    assert "scenario=test-scenario" in captured.err or '"scenario": "test-scenario"' in captured.err


def test_logger_with_enabled_false_no_output(monkeypatch, capsys):
    """Verify set_logger_enabled(False) suppresses all output."""
    set_logger_enabled(False)
    
    logger = EvalLogger("test")
    logger.log("msg1")
    logger.log_dict("data", {"key": "value"})
    
    captured = capsys.readouterr()
    assert captured.err == ""
    
    # Restore for other tests
    set_logger_enabled(True)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/pat/Personal/agent-research/.claude/worktrees/cc-eval-stderr-instrumentation
uv run --package claude-code-evals pytest tests/test_stderr_logger.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'claude_code_evals.stderr_logger'"

- [ ] **Step 3: Implement stderr_logger.py**

```python
# packages/claude-code-evals/src/claude_code_evals/stderr_logger.py
"""Structured stderr logging for eval execution visibility."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

_ENABLED = True


def set_logger_enabled(enabled: bool) -> None:
    """Enable or disable all logging globally (for test isolation)."""
    global _ENABLED
    _ENABLED = enabled


class EvalLogger:
    """Structured logger that writes timestamped, contextual logs to stderr."""

    def __init__(self, context: str) -> None:
        """Initialize logger with a context tag (e.g., 'fixture_setup', 'runner', 'tool_call').

        Args:
            context: A short string identifying the logging context
        """
        self.context = context

    def log(self, message: str, **kwargs: object) -> None:
        """Write a message to stderr with timestamp and context.

        Args:
            message: The log message
            **kwargs: Additional key-value pairs to include in the log
        """
        if not _ENABLED and os.environ.get("CLAUDE_EVAL_STDERR") != "1":
            return

        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        log_entry = {
            "timestamp": timestamp,
            "context": self.context,
            "message": message,
        }
        log_entry.update(kwargs)

        sys.stderr.write(json.dumps(log_entry) + "\n")
        sys.stderr.flush()

    def log_dict(self, title: str, data: dict[str, object]) -> None:
        """Write a titled dict to stderr as a pretty-printed log entry.

        Args:
            title: The title/label for this log entry
            data: Dictionary of key-value pairs to log
        """
        if not _ENABLED and os.environ.get("CLAUDE_EVAL_STDERR") != "1":
            return

        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        log_entry = {
            "timestamp": timestamp,
            "context": self.context,
            "title": title,
            "data": data,
        }

        sys.stderr.write(json.dumps(log_entry) + "\n")
        sys.stderr.flush()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run --package claude-code-evals pytest tests/test_stderr_logger.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/stderr_logger.py packages/claude-code-evals/tests/test_stderr_logger.py
git commit -m "feat: add structured stderr logging module for eval instrumentation"
```

---

## Task 2: Instrument isolation.py (Fixture/Worktree Setup)

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/isolation.py`
- Test: `packages/claude-code-evals/tests/test_isolation.py`

- [ ] **Step 1: Add stderr_logger import and logging to isolation.py**

Add import:
```python
from claude_code_evals.stderr_logger import EvalLogger
```

In `WorktreeIsolation.__enter__`, after `self._setup_cfg_dir()` and before return:
```python
        logger = EvalLogger("fixture_worktree_setup")
        logger.log_dict("Worktree isolation created", {
            "scenario": self._scenario.name,
            "config": self._config.name,
            "worktree_path": str(self.worktree_path),
            "git_shallow": self._scenario.git_shallow,
            "isolation_mode": "worktree",
        })
```

In `WorktreeIsolation.__exit__`, at start:
```python
        logger = EvalLogger("fixture_worktree_teardown")
        logger.log("Worktree isolation cleaning up", scenario=self._scenario.name)
```

In `FixtureIsolation.__enter__`, after `self._setup_cfg_dir()` and before return:
```python
        logger = EvalLogger("fixture_copy_setup")
        logger.log_dict("Fixture isolation created", {
            "scenario": self._scenario.name,
            "config": self._config.name,
            "fixture_path": str(self.worktree_path),
            "isolation_mode": "fixture",
        })
```

In `FixtureIsolation.__exit__`, at start:
```python
        logger = EvalLogger("fixture_copy_teardown")
        logger.log("Fixture isolation cleaning up", scenario=self._scenario.name)
```

- [ ] **Step 2: Run isolation tests to verify no regression**

```bash
uv run --package claude-code-evals pytest tests/test_isolation.py -v
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/isolation.py
git commit -m "feat: add stderr logging to fixture isolation setup/teardown"
```

---

## Task 3: Instrument runner.py (Prompt & Stream Events)

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/runner.py`
- Test: `packages/claude-code-evals/tests/test_runner.py`

- [ ] **Step 1: Add import and logging to runner.py**

Add import after existing imports:
```python
from claude_code_evals.stderr_logger import EvalLogger
```

In `_build_cmd`, at end before returning:
```python
    logger = EvalLogger("runner_cmd_build")
    logger.log_dict("Claude invocation command built", {
        "model": model,
        "multi_turn": multi_turn,
        "plugin_dirs_count": len(plugin_dirs or []),
        "system_prompt_length": len(system_prompt),
        "user_prompt_length": len(prompt),
    })
    
    return cmd
```

In `run_one_shot`, after building cmd but before `subprocess.Popen`:
```python
    logger = EvalLogger("runner_one_shot")
    logger.log("Starting one-shot run", model=model, max_wall_seconds=max_wall_seconds)
    logger.log_dict("System prompt injected", {
        "system_prompt_length": len(system_prompt),
        "system_prompt_prefix": system_prompt[:100] + "..." if len(system_prompt) > 100 else system_prompt,
    })
    logger.log_dict("User prompt", {
        "prompt_length": len(prompt),
        "prompt_prefix": prompt[:100] + "..." if len(prompt) > 100 else prompt,
    })
```

In `run_one_shot`, inside the main loop after `json.loads(line_str)`:
```python
            ev = json.loads(line_str)
            
            # Log notable events
            if ev.get("type") == "message":
                if ev.get("role") == "assistant":
                    logger.log("Assistant message received", token_count=len(ev.get("content", "")))
                elif ev.get("role") == "user":
                    logger.log("User message received", token_count=len(ev.get("content", "")))
            elif ev.get("type") == "tool_call":
                logger.log("Tool called", tool_name=ev.get("tool_name"), tool_id=ev.get("id"))
            elif ev.get("type") == "tool_result":
                logger.log("Tool result received", tool_id=ev.get("id"), result_length=len(str(ev.get("result", ""))))
```

In `run_one_shot`, after try/finally and before return:
```python
    logger = EvalLogger("runner_one_shot_complete")
    logger.log_dict("One-shot run completed", {
        "final_status": final_status,
        "budget_exceeded": budget_exceeded,
        "wall_seconds": time.monotonic() - start,
        "exit_code": exit_code,
        "error_reason": error_reason,
    })
```

- [ ] **Step 2: Run runner tests to verify no regression**

```bash
uv run --package claude-code-evals pytest tests/test_runner.py -v -k "not integration"
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/runner.py
git commit -m "feat: add stderr logging to runner for prompt and stream events"
```

---

## Task 4: Instrument orchestrator.py (Scenario Execution Flow)

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/orchestrator.py`
- Test: `packages/claude-code-evals/tests/test_orchestrator.py`

- [ ] **Step 1: Add import and logging to orchestrator.py**

Add import after existing imports:
```python
from claude_code_evals.stderr_logger import EvalLogger
```

In `run_one`, at very start:
```python
    logger = EvalLogger("orchestrator_scenario_start")
    logger.log_dict("Scenario execution starting", {
        "scenario": scenario.name,
        "config": config.name,
        "model": config.model,
        "eval_mode": scenario.eval_mode,
        "isolation_mode": scenario.isolation_mode,
    })
```

After `with IsoClass(...) as iso:`:
```python
        logger = EvalLogger("orchestrator_isolation_entered")
        logger.log("Isolation context entered", scenario=scenario.name)
```

After preflight script runs (replace existing code):
```python
        if scenario.preflight:
            logger = EvalLogger("orchestrator_preflight")
            if result.returncode == 0:
                logger.log("Preflight script passed", preflight=scenario.preflight)
            else:
                logger.log("Preflight script failed", preflight=scenario.preflight, return_code=result.returncode)
```

Before calling `run_one_shot`:
```python
        logger = EvalLogger("orchestrator_runner_start")
        logger.log("Invoking runner", model=config.model)
```

Before returning `ScenarioRunResult`:
```python
    logger = EvalLogger("orchestrator_scenario_complete")
    logger.log_dict("Scenario execution complete", {
        "scenario": scenario.name,
        "config": config.name,
        "final_status": result.final_status,
        "error_reason": result.error_reason,
        "wall_seconds": result.wall_seconds,
    })
```

- [ ] **Step 2: Run orchestrator tests to verify no regression**

```bash
uv run --package claude-code-evals pytest tests/test_orchestrator.py -v
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/orchestrator.py
git commit -m "feat: add stderr logging to orchestrator for scenario execution flow"
```

---

## Task 5: Add Tool Call Extraction Helper to transcript.py

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/transcript.py`
- Test: `packages/claude-code-evals/tests/test_transcript.py`

- [ ] **Step 1: Add helper function to transcript.py**

At end of `transcript.py`:
```python
def extract_tool_calls_from_jsonl(raw_jsonl: str) -> list[dict[str, object]]:
    """Extract tool call details from raw stream-json output.
    
    Args:
        raw_jsonl: Raw output from claude -p in stream-json format (one JSON per line)
    
    Returns:
        List of dicts with keys: tool_name, tool_id, input_length (approx)
    """
    tool_calls: list[dict[str, object]] = []
    
    for line in raw_jsonl.splitlines():
        s = line.strip()
        if not s:
            continue
        try:
            ev = json.loads(s)
        except json.JSONDecodeError:
            continue
        
        if ev.get("type") == "tool_call":
            tool_calls.append({
                "tool_name": ev.get("tool_name"),
                "tool_id": ev.get("id"),
                "input_length": len(json.dumps(ev.get("input", {}))),
            })
    
    return tool_calls
```

- [ ] **Step 2: Run transcript tests to verify no regression**

```bash
uv run --package claude-code-evals pytest tests/test_transcript.py -v
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/transcript.py
git commit -m "feat: add helper to extract tool call details from stream-json"
```

---

## Task 6: Update Existing Tests to Handle Stderr Output

**Files:**
- Modify: `packages/claude-code-evals/tests/conftest.py`

- [ ] **Step 1: Create or update conftest.py**

Create `packages/claude-code-evals/tests/conftest.py` with:
```python
import os
import pytest


@pytest.fixture(autouse=True)
def _disable_stderr_logging_by_default(monkeypatch):
    """Disable stderr logging for tests by default to keep output clean."""
    monkeypatch.setenv("CLAUDE_EVAL_STDERR", "0")
```

- [ ] **Step 2: Run all tests to verify no regressions**

```bash
uv run --package claude-code-evals pytest -m "not integration" -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add packages/claude-code-evals/tests/conftest.py
git commit -m "test: disable stderr logging by default in tests via conftest"
```

---

## Task 7: Manual Integration Test & Validation

**Files:**
- None (manual testing)

- [ ] **Step 1: Verify basic CLI still works**

```bash
cd /Users/pat/Personal/agent-research/.claude/worktrees/cc-eval-stderr-instrumentation
uv run --package eval-harness gw --help
```

Expected: Help output with no unexpected stderr

- [ ] **Step 2: Run a dry-run eval with stderr visible**

```bash
CLAUDE_EVAL_STDERR=1 uv run --package eval-harness pytest eval/test_sweep_dry_run.py::test_dry_run -v -s 2>&1 | head -150
```

Verify logs appear showing fixture setup, scenario execution, etc.

- [ ] **Step 3: Verify stderr suppression works**

```bash
CLAUDE_EVAL_STDERR=0 uv run --package eval-harness pytest eval/test_sweep_dry_run.py::test_dry_run -v -s 2>&1 | grep -c "fixture_setup"
```

Expected: 0 (no logs)

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: complete stderr instrumentation for cc-eval with configurable output"
```

---

## Task 8: Documentation

**Files:**
- Create: `docs/cc-eval-stderr-instrumentation.md`

- [ ] **Step 1: Write documentation**

Create file with:
```markdown
# Claude-Code-Eval Stderr Instrumentation

## Overview

cc-eval now logs detailed execution information to stderr, allowing real-time visibility into test runs.

## Log Format

All logs are written as JSON-lines to stderr:

\`\`\`json
{"timestamp": "2025-06-08T12:34:56.789Z", "context": "fixture_worktree_setup", "message": "Worktree isolation created", "scenario": "test-scenario"}
{"timestamp": "2025-06-08T12:34:57.123Z", "context": "runner_cmd_build", "title": "Claude invocation command built", "data": {"model": "claude-sonnet-4-6", "multi_turn": false}}
\`\`\`

## What's Logged

### Fixture Setup (isolation.py)
- Worktree isolation created: scenario, config, path, isolation_mode
- Fixture isolation created: scenario, config, path, isolation_mode
- Cleanup events

### Runner (runner.py)
- Command being built: model, multi_turn, plugin_dirs_count
- One-shot run starting: model, max_wall_seconds
- System prompt injected: length, prefix
- User prompt: length, prefix
- Stream events: assistant messages, user messages, tool calls, tool results
- Run completion: final_status, budget_exceeded, wall_seconds, exit_code, error_reason

### Orchestrator (orchestrator.py)
- Scenario execution starting: scenario, config, model, eval_mode, isolation_mode
- Isolation context entered
- Preflight script results
- Runner invocation
- Scenario execution complete: final_status, error_reason, wall_seconds

## Configuration

### Enable/Disable

By default, stderr logging is **disabled in tests** (via conftest.py). To enable for manual testing:

\`\`\`bash
CLAUDE_EVAL_STDERR=1 uv run --package eval-harness pytest ...
\`\`\`

To disable in eval runs:

\`\`\`bash
CLAUDE_EVAL_STDERR=0 uv run --package eval-harness pytest ...
\`\`\`

### Parsing Logs

The JSON format makes logs easy to parse and filter:

\`\`\`bash
# Find all orchestrator completions
uv run ... 2>&1 | grep '"context": "orchestrator_scenario_complete'

# Count tool calls
uv run ... 2>&1 | grep -c '"type": "tool_call"'

# Extract final statuses
uv run ... 2>&1 | jq -r 'select(.context=="orchestrator_scenario_complete") | .data.final_status'
\`\`\`

## Implementation Details

- **stderr_logger.py**: Core logging module with global enable/disable
- **isolation.py**: Logs fixture/worktree setup and teardown
- **runner.py**: Logs Claude invocation details and stream events
- **orchestrator.py**: Logs high-level scenario execution flow
- **conftest.py**: Disables logging in tests by default (CLAUDE_EVAL_STDERR=0)

All logs respect the CLAUDE_EVAL_STDERR env var and global enable/disable state.
\`\`\`

- [ ] **Step 2: Commit documentation**

```bash
git add docs/cc-eval-stderr-instrumentation.md
git commit -m "docs: add stderr instrumentation guide for cc-eval"
```

---

## Verification Checklist

- [ ] All tests pass: `uv run --package claude-code-evals pytest -m "not integration" -v`
- [ ] Stderr logs appear when enabled with CLAUDE_EVAL_STDERR=1
- [ ] Logs are JSON-formatted and parseable
- [ ] CLAUDE_EVAL_STDERR=0 successfully suppresses logs
- [ ] No regressions in existing functionality
- [ ] Documentation is clear and includes examples
