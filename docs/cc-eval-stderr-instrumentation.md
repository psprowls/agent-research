# Claude-Code-Eval Stderr Instrumentation

## Overview

cc-eval now logs detailed execution information to stderr, allowing real-time visibility into test runs.

## Log Format

All logs are written as JSON-lines to stderr:

```json
{"timestamp": "2025-06-08T12:34:56.789Z", "context": "fixture_worktree_setup", "message": "Worktree isolation created", "scenario": "test-scenario"}
{"timestamp": "2025-06-08T12:34:57.123Z", "context": "runner_cmd_build", "title": "Claude invocation command built", "data": {"model": "claude-sonnet-4-6", "multi_turn": false}}
```

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

```bash
CLAUDE_EVAL_STDERR=1 uv run --package eval-harness pytest ...
```

To disable in eval runs:

```bash
CLAUDE_EVAL_STDERR=0 uv run --package eval-harness pytest ...
```

### Parsing Logs

The JSON format makes logs easy to parse and filter:

```bash
# Find all orchestrator completions
uv run ... 2>&1 | grep '"context": "orchestrator_scenario_complete'

# Count tool calls
uv run ... 2>&1 | grep -c '"tool_name"'

# Extract final statuses
uv run ... 2>&1 | jq -r 'select(.context=="orchestrator_scenario_complete") | .data.final_status'
```

## Implementation Details

- **stderr_logger.py**: Core logging module with global enable/disable
- **isolation.py**: Logs fixture/worktree setup and teardown
- **runner.py**: Logs Claude invocation details and stream events
- **orchestrator.py**: Logs high-level scenario execution flow
- **conftest.py**: Disables logging in tests by default (CLAUDE_EVAL_STDERR=0)

All logs respect the CLAUDE_EVAL_STDERR env var and global enable/disable state.
