# Interactive Mode & Auto-User Triggers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring `claude-code-evals` to full parity with `lattice-evals` for interactive mode and auto_user: add trigger-based reply selection to the simulator, add a `default_reply` LLM-failure fallback, and wire interactive mode to poll for a sentinel file instead of silently doing nothing.

**Architecture:** The current code has schema fields declared (`mode`, `auto_user`) and both runners implemented (`run_one_shot`, `run_multi_turn`) but the orchestrator only ever calls `run_one_shot`. This plan wires up the dispatch logic (mode → runner), enhances `AutoUser` with trigger/default_reply fields, updates `AutoUserSimulator` to follow the priority chain (stop_on → triggers → LLM → default_reply → abort), and adds `run_interactive()` for sentinel-file polling.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, `re` (stdlib), `time` (stdlib)

---

## File Map

| File | Change |
|------|--------|
| `packages/claude-code-evals/src/claude_code_evals/schemas.py` | Add `TriggerMatch`, `Trigger`; extend `AutoUser` with `triggers`, `default_reply`, `abort_on_default_after` |
| `packages/claude-code-evals/src/claude_code_evals/user_simulator.py` | Rewrite `reply()` with full priority chain; add exception handling for LLM fallback |
| `packages/claude-code-evals/src/claude_code_evals/runner.py` | Add `run_interactive()` |
| `packages/claude-code-evals/src/claude_code_evals/orchestrator.py` | Import and wire `run_multi_turn`, `run_interactive`, `AutoUser`, `AutoUserSimulator`; dispatch by mode |
| `packages/claude-code-evals/tests/test_schemas.py` | Add tests for `TriggerMatch`, `Trigger`, extended `AutoUser` |
| `packages/claude-code-evals/tests/test_user_simulator.py` | New file — full simulator behavior |
| `packages/claude-code-evals/tests/test_runner.py` | Add `run_interactive` tests |
| `packages/claude-code-evals/tests/test_orchestrator.py` | Add mode-dispatch tests |
| `packages/claude-code-evals/tests/fixtures/auto_user.yaml` | Add `triggers`, `default_reply`, `abort_on_default_after` |
| `packages/claude-code-evals/tests/fixtures/auto_user_triggers.yaml` | New — fixture with contains/regex triggers |

---

### Task 1: Add TriggerMatch, Trigger, and extend AutoUser in schemas.py

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/schemas.py`
- Test: `packages/claude-code-evals/tests/test_schemas.py`

- [ ] **Step 1: Write failing tests for new schema types**

Add to `tests/test_schemas.py` (after existing tests):

```python
from claude_code_evals.schemas import AutoUser, Trigger, TriggerMatch


def test_trigger_match_contains():
    t = TriggerMatch.model_validate({"contains": "hello"})
    assert t.contains == "hello"
    assert t.regex is None


def test_trigger_match_regex():
    t = TriggerMatch.model_validate({"regex": r"\d+"})
    assert t.regex == r"\d+"
    assert t.contains is None


def test_trigger_match_requires_exactly_one():
    with pytest.raises(ValidationError, match="exactly one"):
        TriggerMatch.model_validate({})

    with pytest.raises(ValidationError, match="exactly one"):
        TriggerMatch.model_validate({"contains": "a", "regex": "b"})


def test_trigger_has_match_and_reply():
    t = Trigger.model_validate({"match": {"contains": "proceed"}, "reply": "yes"})
    assert t.match.contains == "proceed"
    assert t.reply == "yes"


def test_auto_user_defaults():
    a = AutoUser.model_validate({})
    assert a.triggers == []
    assert a.default_reply == "proceed"
    assert a.abort_on_default_after == 2


def test_auto_user_with_triggers():
    a = AutoUser.model_validate({
        "triggers": [
            {"match": {"contains": "clarify"}, "reply": "Please go ahead."},
            {"match": {"regex": r"question\?"}, "reply": "Yes."},
        ],
        "default_reply": "continue",
        "abort_on_default_after": 3,
    })
    assert len(a.triggers) == 2
    assert a.triggers[0].match.contains == "clarify"
    assert a.triggers[1].match.regex == r"question\?"
    assert a.default_reply == "continue"
    assert a.abort_on_default_after == 3


def test_auto_user_abort_on_default_after_min_1():
    with pytest.raises(ValidationError):
        AutoUser.model_validate({"abort_on_default_after": 0})


def test_auto_user_backward_compat():
    # Old-style YAML (no new fields) still loads cleanly
    a = AutoUser.model_validate({
        "model": "claude-haiku-4-5-20251001",
        "max_replies": 3,
        "stop_on": "<DONE>",
        "system_prompt": "Drive the task.",
    })
    assert a.triggers == []
    assert a.default_reply == "proceed"
    assert a.abort_on_default_after == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/pat/Personal/agent-research
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_schemas.py::test_trigger_match_contains -v
```
Expected: `ImportError` or `FAILED` — `TriggerMatch` and `Trigger` don't exist yet.

- [ ] **Step 3: Add TriggerMatch, Trigger, and extend AutoUser in schemas.py**

In `packages/claude-code-evals/src/claude_code_evals/schemas.py`, after the `MetricsConfig` class and before `Scenario`, add:

```python
class TriggerMatch(BaseModel):
    """Pattern for a trigger: exactly one of contains or regex must be set."""

    model_config = ConfigDict(extra="forbid")

    contains: str | None = None
    regex: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "TriggerMatch":
        if (self.contains is None) == (self.regex is None):
            raise ValueError("trigger match must set exactly one of contains/regex")
        return self


class Trigger(BaseModel):
    """A rule-based trigger: if match fires, reply with the given text."""

    model_config = ConfigDict(extra="forbid")

    match: TriggerMatch
    reply: str
```

Then update the `AutoUser` class (at the bottom of the file) to add the three new fields:

```python
class AutoUser(BaseModel):
    """Configuration for the auto-user agent in headless mode."""

    model_config = ConfigDict(extra="forbid")

    model: str = "claude-haiku-4-5-20251001"
    max_replies: int = 5
    stop_on: str = "<DONE>"
    system_prompt: str = "Drive the task forward. Say <DONE> when the task is complete."
    triggers: list[Trigger] = Field(default_factory=list)
    default_reply: str = "proceed"
    abort_on_default_after: int = Field(default=2, ge=1)

    @classmethod
    def from_path(cls, path: Path) -> "AutoUser":
        """Load AutoUser config from YAML file."""
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))
```

Also update the import of `Trigger` in the module — it's defined locally so no import needed, but make sure `Field` is already imported (it is).

- [ ] **Step 4: Run all new schema tests**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_schemas.py -v
```
Expected: all pass, including the new trigger/auto_user tests.

- [ ] **Step 5: Update auto_user.yaml fixture with new fields**

Replace `packages/claude-code-evals/tests/fixtures/auto_user.yaml`:

```yaml
model: claude-haiku-4-5-20251001
max_replies: 3
stop_on: "<DONE>"
system_prompt: "Drive the task forward. Say <DONE> when finished."
triggers: []
default_reply: proceed
abort_on_default_after: 2
```

- [ ] **Step 6: Create auto_user_triggers.yaml fixture**

Create `packages/claude-code-evals/tests/fixtures/auto_user_triggers.yaml`:

```yaml
model: claude-haiku-4-5-20251001
max_replies: 10
stop_on: "<DONE>"
system_prompt: "Drive the task. Say <DONE> when done."
triggers:
  - match:
      contains: "clarify"
    reply: "Please proceed without clarification."
  - match:
      regex: "question\\?"
    reply: "Yes, go ahead."
default_reply: continue
abort_on_default_after: 3
```

- [ ] **Step 7: Verify fixture loads cleanly**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_schemas.py::test_auto_user_from_path -v
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/schemas.py \
        packages/claude-code-evals/tests/test_schemas.py \
        packages/claude-code-evals/tests/fixtures/auto_user.yaml \
        packages/claude-code-evals/tests/fixtures/auto_user_triggers.yaml
git commit -m "feat(cc-eval): add TriggerMatch/Trigger models and extend AutoUser schema"
```

---

### Task 2: Rewrite AutoUserSimulator with full priority chain

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/user_simulator.py`
- Create: `packages/claude-code-evals/tests/test_user_simulator.py`

Priority chain: `stop_on` → `max_replies` budget → trigger match → LLM call (with exception fallback) → `abort_on_default_after` → `default_reply`.

- [ ] **Step 1: Write failing tests for the simulator**

Create `packages/claude-code-evals/tests/test_user_simulator.py`:

```python
"""Tests for AutoUserSimulator priority chain."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from claude_code_evals.schemas import AutoUser, Trigger, TriggerMatch
from claude_code_evals.user_simulator import AutoUserSimulator


def _make_auto_user(**kwargs) -> AutoUser:
    defaults = {
        "model": "claude-haiku-4-5-20251001",
        "max_replies": 10,
        "stop_on": "<DONE>",
        "system_prompt": "Drive task.",
        "default_reply": "proceed",
        "abort_on_default_after": 2,
        "triggers": [],
    }
    defaults.update(kwargs)
    return AutoUser.model_validate(defaults)


def _make_judge_result(text: str) -> MagicMock:
    r = MagicMock()
    r.stdout = text
    r.input_tokens = 5
    r.output_tokens = 3
    return r


def test_stop_on_returns_none():
    sim = AutoUserSimulator(_make_auto_user())
    assert sim.reply("task complete <DONE>") is None


def test_max_replies_exhausted_returns_none():
    sim = AutoUserSimulator(_make_auto_user(max_replies=1))
    with patch("claude_code_evals.user_simulator._run_claude_judge", return_value=_make_judge_result("ok")):
        sim.reply("first")
    # Second call exceeds max_replies
    assert sim.reply("second") is None


def test_trigger_contains_matches_and_returns_reply():
    triggers = [Trigger(match=TriggerMatch(contains="clarify"), reply="No clarification needed.")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers))
    result = sim.reply("Can you clarify this for me?")
    assert result == "No clarification needed."


def test_trigger_regex_matches_and_returns_reply():
    triggers = [Trigger(match=TriggerMatch(regex=r"question\?"), reply="Yes.")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers))
    assert sim.reply("Is this a question?") == "Yes."


def test_trigger_no_match_falls_through_to_llm():
    triggers = [Trigger(match=TriggerMatch(contains="never_matches"), reply="nope")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers))
    judge_result = _make_judge_result("LLM reply")
    with patch("claude_code_evals.user_simulator._run_claude_judge", return_value=judge_result) as mock_judge:
        result = sim.reply("some text")
    assert result == "LLM reply"
    mock_judge.assert_called_once()


def test_trigger_match_resets_consecutive_defaults():
    triggers = [Trigger(match=TriggerMatch(contains="trigger"), reply="matched")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers, abort_on_default_after=1))
    # Exhaust consecutive defaults (LLM fails)
    with patch("claude_code_evals.user_simulator._run_claude_judge", side_effect=RuntimeError("fail")):
        sim.reply("no match here")  # → default_reply, consecutive_defaults=1
    # Now trigger fires → resets consecutive_defaults
    result = sim.reply("trigger word here")
    assert result == "matched"
    # Next LLM failure should not abort yet (consecutive_defaults was reset to 0)
    with patch("claude_code_evals.user_simulator._run_claude_judge", side_effect=RuntimeError("fail")):
        result = sim.reply("no match")
    assert result == "proceed"  # default_reply, not None


def test_llm_failure_falls_back_to_default_reply():
    sim = AutoUserSimulator(_make_auto_user(default_reply="fallback", abort_on_default_after=3))
    with patch("claude_code_evals.user_simulator._run_claude_judge", side_effect=RuntimeError("LLM error")):
        result = sim.reply("something")
    assert result == "fallback"


def test_abort_on_default_after_consecutive_failures():
    sim = AutoUserSimulator(_make_auto_user(abort_on_default_after=2))
    with patch("claude_code_evals.user_simulator._run_claude_judge", side_effect=RuntimeError("fail")):
        r1 = sim.reply("turn 1")  # consecutive_defaults=1
        r2 = sim.reply("turn 2")  # consecutive_defaults=2, abort
    assert r1 == "proceed"
    assert r2 is None


def test_token_accumulation_across_turns():
    sim = AutoUserSimulator(_make_auto_user())
    with patch("claude_code_evals.user_simulator._run_claude_judge", return_value=_make_judge_result("ok")):
        sim.reply("turn 1")
        sim.reply("turn 2")
    assert sim.input_tokens == 10
    assert sim.output_tokens == 6


def test_stop_on_checked_before_triggers():
    triggers = [Trigger(match=TriggerMatch(contains="<DONE>"), reply="matched")]
    sim = AutoUserSimulator(_make_auto_user(triggers=triggers))
    # stop_on should fire before the trigger check
    assert sim.reply("all done <DONE>") is None
```

- [ ] **Step 2: Run tests to see them fail**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_user_simulator.py -v
```
Expected: most FAIL — simulator doesn't have trigger/default_reply logic yet.

- [ ] **Step 3: Rewrite user_simulator.py**

Replace `packages/claude-code-evals/src/claude_code_evals/user_simulator.py` entirely:

```python
"""AutoUserSimulator: LLM-driven reply driver for multi-turn eval runs."""

from __future__ import annotations

import re

from claude_code_evals.judge import _run_claude_judge
from claude_code_evals.schemas import AutoUser


class AutoUserSimulator:
    """Drive multi-turn conversations using a priority chain for each reply.

    Priority per turn:
    1. stop_on found in assistant text → end conversation (return None)
    2. max_replies budget exhausted → end conversation (return None)
    3. Trigger match (contains/regex) → return trigger.reply, reset consecutive defaults
    4. LLM call → return LLM reply, reset consecutive defaults
    5. LLM exception → fall back to default_reply:
       - if consecutive defaults >= abort_on_default_after → end conversation (return None)
       - else increment consecutive defaults and return default_reply
    """

    def __init__(self, config: AutoUser) -> None:
        self._config = config
        self._reply_count = 0
        self._consecutive_defaults = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def reply(self, assistant_text: str) -> str | None:
        """Return next user message, or None to end the conversation."""
        if self._config.stop_on in assistant_text:
            return None

        if self._reply_count >= self._config.max_replies:
            return None

        for trigger in self._config.triggers:
            if trigger.match.contains is not None:
                if trigger.match.contains in assistant_text:
                    self._reply_count += 1
                    self._consecutive_defaults = 0
                    return trigger.reply
            elif trigger.match.regex is not None:
                if re.search(trigger.match.regex, assistant_text):
                    self._reply_count += 1
                    self._consecutive_defaults = 0
                    return trigger.reply

        try:
            prompt = f"{self._config.system_prompt}\n\nAgent said:\n{assistant_text}"
            result = _run_claude_judge(prompt, model=self._config.model)
            self.input_tokens += result.input_tokens
            self.output_tokens += result.output_tokens
            self._reply_count += 1
            self._consecutive_defaults = 0
            return result.stdout
        except Exception:
            if self._consecutive_defaults >= self._config.abort_on_default_after:
                return None
            self._consecutive_defaults += 1
            self._reply_count += 1
            return self._config.default_reply
```

- [ ] **Step 4: Run all simulator tests**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_user_simulator.py -v
```
Expected: all pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/ -v
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/user_simulator.py \
        packages/claude-code-evals/tests/test_user_simulator.py
git commit -m "feat(cc-eval): rewrite AutoUserSimulator with trigger/default_reply priority chain"
```

---

### Task 3: Add run_interactive() to runner.py

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/runner.py`
- Test: `packages/claude-code-evals/tests/test_runner.py`

`run_interactive()` sets up the worktree, prints instructions for the user, then polls for a `.eval-done` sentinel file until it appears or the wall-clock limit is hit.

- [ ] **Step 1: Write failing tests for run_interactive**

Add to `packages/claude-code-evals/tests/test_runner.py`:

```python
import threading
from claude_code_evals.runner import run_interactive


def test_run_interactive_returns_completed_when_done_file_appears(tmp_path: Path):
    done_file = tmp_path / ".eval-done"

    def _touch_after_short_delay():
        import time
        time.sleep(0.05)
        done_file.touch()

    t = threading.Thread(target=_touch_after_short_delay, daemon=True)
    t.start()

    result, jsonl = run_interactive(worktree_path=tmp_path, poll_interval=0.01)
    t.join(timeout=1)

    assert result.final_status == "completed_interactive"
    assert result.budget_exceeded is False
    assert jsonl == ""


def test_run_interactive_budget_exceeded_when_timeout(tmp_path: Path):
    result, jsonl = run_interactive(
        worktree_path=tmp_path,
        poll_interval=0.01,
        max_wait_seconds=0.05,
    )
    assert result.final_status == "budget_exceeded"
    assert result.budget_exceeded is True
    assert jsonl == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_runner.py::test_run_interactive_returns_completed_when_done_file_appears -v
```
Expected: `ImportError` — `run_interactive` doesn't exist yet.

- [ ] **Step 3: Add run_interactive() to runner.py**

Add the following function to `packages/claude-code-evals/src/claude_code_evals/runner.py`, after the `run_multi_turn` function and before `_build_env`:

```python
def run_interactive(
    *,
    worktree_path: Path,
    poll_interval: float = 1.0,
    max_wait_seconds: float = 3600.0,
) -> tuple[RunResult, str]:
    """Wait for a manual interactive session to complete.

    Prints the worktree path and polls for a .eval-done sentinel file.
    Returns a RunResult with final_status="completed_interactive" on success
    or final_status="budget_exceeded" if max_wait_seconds is exceeded.
    """
    done_file = worktree_path / ".eval-done"
    start = time.monotonic()

    print(
        f"\n[INTERACTIVE MODE]\n"
        f"  Worktree: {worktree_path}\n"
        f"  Run claude in the worktree, then signal completion with:\n"
        f"    touch {done_file}\n"
    )

    logger = EvalLogger("runner_interactive")
    logger.log("Waiting for interactive session", done_file=str(done_file))

    while not done_file.exists():
        elapsed = time.monotonic() - start
        if elapsed > max_wait_seconds:
            logger.log("Interactive wait timed out", elapsed=elapsed)
            return (
                RunResult(
                    final_status="budget_exceeded",
                    budget_exceeded=True,
                    wall_seconds=elapsed,
                ),
                "",
            )
        time.sleep(poll_interval)

    wall_seconds = time.monotonic() - start
    logger.log("Interactive session complete", wall_seconds=wall_seconds)
    return (
        RunResult(
            final_status="completed_interactive",
            budget_exceeded=False,
            wall_seconds=wall_seconds,
        ),
        "",
    )
```

- [ ] **Step 4: Run runner tests**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_runner.py -v
```
Expected: all pass, including the two new interactive tests.

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/runner.py \
        packages/claude-code-evals/tests/test_runner.py
git commit -m "feat(cc-eval): add run_interactive() with sentinel-file polling"
```

---

### Task 4: Wire orchestrator to dispatch by mode and auto_user

**Files:**
- Modify: `packages/claude-code-evals/src/claude_code_evals/orchestrator.py`
- Test: `packages/claude-code-evals/tests/test_orchestrator.py`

This is the integration step. The orchestrator currently always calls `run_one_shot()`. After this task it will:
- Load `auto_user` YAML if `scenario.auto_user` is set
- Route `mode="interactive"` → `run_interactive()`
- Route headless + `auto_user` → `run_multi_turn()` with simulator
- Fall through to `run_one_shot()` (existing behavior)

- [ ] **Step 1: Read current orchestrator tests to understand what's being tested**

Check `packages/claude-code-evals/tests/test_orchestrator.py` — understand existing mock patterns before writing new ones.

- [ ] **Step 2: Write failing tests for orchestrator dispatch**

Find the first appropriate place in `test_orchestrator.py` and add (or append to the file if tests exist):

```python
from unittest.mock import MagicMock, patch
from claude_code_evals.runner import RunResult
from claude_code_evals.orchestrator import run_one
from claude_code_evals.schemas import AutoUser, Config, Scenario


def _base_scenario(**overrides) -> Scenario:
    base = {
        "name": "test-scenario",
        "isolation_mode": "fixture",
        "fixture_dir": "fixtures/",
        "verify": [],
    }
    base.update(overrides)
    return Scenario.model_validate(base)


def _base_config() -> Config:
    return Config.model_validate({"name": "base", "model": "claude-sonnet-4-6"})


def _empty_run_result(status: str = "success") -> RunResult:
    return RunResult(final_status=status, budget_exceeded=False, wall_seconds=0.1)


def test_orchestrator_calls_run_one_shot_for_headless_no_auto_user(tmp_path):
    scenario = _base_scenario()
    config = _base_config()
    (tmp_path / "scenarios" / "test-scenario").mkdir(parents=True)
    (tmp_path / "scenarios" / "test-scenario" / "prompt.md").write_text("Do X")

    with patch("claude_code_evals.orchestrator.FixtureIsolation") as MockIso, \
         patch("claude_code_evals.orchestrator.run_one_shot", return_value=(_empty_run_result(), "")) as mock_shot, \
         patch("claude_code_evals.orchestrator.run_multi_turn") as mock_multi, \
         patch("claude_code_evals.orchestrator.run_interactive") as mock_interactive:
        iso_instance = MagicMock()
        iso_instance.__enter__ = MagicMock(return_value=iso_instance)
        iso_instance.__exit__ = MagicMock(return_value=False)
        iso_instance.worktree_path = tmp_path
        iso_instance.cfg_dir = tmp_path
        iso_instance.oauth_token = "tok"
        MockIso.return_value = iso_instance

        run_one(scenario, config, evals_root=tmp_path)

    mock_shot.assert_called_once()
    mock_multi.assert_not_called()
    mock_interactive.assert_not_called()


def test_orchestrator_calls_run_interactive_for_interactive_mode(tmp_path):
    scenario = _base_scenario(mode="interactive")
    config = _base_config()
    (tmp_path / "scenarios" / "test-scenario").mkdir(parents=True)
    (tmp_path / "scenarios" / "test-scenario" / "prompt.md").write_text("Do X")

    with patch("claude_code_evals.orchestrator.FixtureIsolation") as MockIso, \
         patch("claude_code_evals.orchestrator.run_one_shot") as mock_shot, \
         patch("claude_code_evals.orchestrator.run_interactive",
               return_value=(_empty_run_result("completed_interactive"), "")) as mock_interactive:
        iso_instance = MagicMock()
        iso_instance.__enter__ = MagicMock(return_value=iso_instance)
        iso_instance.__exit__ = MagicMock(return_value=False)
        iso_instance.worktree_path = tmp_path
        iso_instance.cfg_dir = tmp_path
        iso_instance.oauth_token = "tok"
        MockIso.return_value = iso_instance

        result = run_one(scenario, config, evals_root=tmp_path)

    mock_interactive.assert_called_once()
    mock_shot.assert_not_called()
    assert result.final_status == "completed_interactive"


def test_orchestrator_calls_run_multi_turn_when_auto_user_set(tmp_path):
    auto_user_yaml = tmp_path / "auto_user.yaml"
    auto_user_yaml.write_text(
        "model: claude-haiku-4-5-20251001\n"
        "max_replies: 3\n"
        "stop_on: '<DONE>'\n"
        "system_prompt: Drive.\n"
    )
    scenario = _base_scenario(auto_user=str(auto_user_yaml))
    config = _base_config()
    (tmp_path / "scenarios" / "test-scenario").mkdir(parents=True)
    (tmp_path / "scenarios" / "test-scenario" / "prompt.md").write_text("Do X")

    with patch("claude_code_evals.orchestrator.FixtureIsolation") as MockIso, \
         patch("claude_code_evals.orchestrator.run_one_shot") as mock_shot, \
         patch("claude_code_evals.orchestrator.run_multi_turn",
               return_value=(_empty_run_result(), "")) as mock_multi:
        iso_instance = MagicMock()
        iso_instance.__enter__ = MagicMock(return_value=iso_instance)
        iso_instance.__exit__ = MagicMock(return_value=False)
        iso_instance.worktree_path = tmp_path
        iso_instance.cfg_dir = tmp_path
        iso_instance.oauth_token = "tok"
        MockIso.return_value = iso_instance

        run_one(scenario, config, evals_root=tmp_path)

    mock_multi.assert_called_once()
    mock_shot.assert_not_called()
```

- [ ] **Step 3: Run new orchestrator tests to confirm they fail**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_orchestrator.py::test_orchestrator_calls_run_interactive_for_interactive_mode -v
```
Expected: FAIL — orchestrator still always calls `run_one_shot`.

- [ ] **Step 4: Update orchestrator.py imports**

At the top of `packages/claude-code-evals/src/claude_code_evals/orchestrator.py`, update the runner import block from:

```python
from claude_code_evals.runner import (
    EVAL_SYSTEM_PROMPT_IMPLEMENT,
    EVAL_SYSTEM_PROMPT_QA,
    RunResult,
    run_one_shot,
)
from claude_code_evals.schemas import Config, Scenario
```

to:

```python
from claude_code_evals.runner import (
    EVAL_SYSTEM_PROMPT_IMPLEMENT,
    EVAL_SYSTEM_PROMPT_QA,
    RunResult,
    run_interactive,
    run_multi_turn,
    run_one_shot,
)
from claude_code_evals.schemas import AutoUser, Config, Scenario
from claude_code_evals.user_simulator import AutoUserSimulator
```

- [ ] **Step 5: Add dispatch logic to run_one() in orchestrator.py**

In `run_one()`, replace the block that calls `run_one_shot` (currently lines ~117–136):

```python
            run_result, raw_jsonl = run_one_shot(
                prompt=scenario_prompt,
                ...
            )
```

with the three-way dispatch:

```python
            # Load auto_user config if specified (headless multi-turn)
            auto_user: AutoUser | None = None
            if scenario.auto_user:
                auto_user = AutoUser.from_path(Path(scenario.auto_user))

            if scenario.mode == "interactive":
                run_result, raw_jsonl = run_interactive(
                    worktree_path=iso.worktree_path,
                )
            elif auto_user is not None:
                simulator = AutoUserSimulator(auto_user)
                run_result, raw_jsonl = run_multi_turn(
                    prompt=scenario_prompt,
                    worktree_path=iso.worktree_path,
                    cfg_dir=iso.cfg_dir,
                    system_prompt=system_prompt,
                    simulator=simulator,
                    model=config.model,
                    oauth_token=iso.oauth_token,
                    plugin_dirs=_resolve_plugin_dirs(config.plugin_dirs),
                    extra_env=config.extra_env or None,
                    max_wall_seconds=float(scenario.budgets.max_wall_seconds),
                )
            else:
                run_result, raw_jsonl = run_one_shot(
                    prompt=scenario_prompt,
                    worktree_path=iso.worktree_path,
                    cfg_dir=iso.cfg_dir,
                    system_prompt=system_prompt,
                    model=config.model,
                    oauth_token=iso.oauth_token,
                    plugin_dirs=_resolve_plugin_dirs(config.plugin_dirs),
                    extra_env=config.extra_env or None,
                    max_wall_seconds=float(scenario.budgets.max_wall_seconds),
                )
```

Also add `from pathlib import Path` if not already there (it is — it's already imported at the top).

- [ ] **Step 6: Run all orchestrator tests**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_orchestrator.py -v
```
Expected: all pass.

- [ ] **Step 7: Run full test suite**

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/ -v
```
Expected: all pass with no regressions.

- [ ] **Step 8: Commit**

```bash
git add packages/claude-code-evals/src/claude_code_evals/orchestrator.py \
        packages/claude-code-evals/tests/test_orchestrator.py
git commit -m "feat(cc-eval): wire orchestrator to dispatch by mode and auto_user"
```

---

## Self-Review

### Spec coverage

| Feature | Task |
|---------|------|
| `Trigger` / `TriggerMatch` schema models | Task 1 |
| `AutoUser.triggers`, `default_reply`, `abort_on_default_after` | Task 1 |
| Backward compat for old auto_user.yaml | Task 1 (default values) |
| Simulator: stop_on priority | Task 2 |
| Simulator: trigger match (contains/regex) | Task 2 |
| Simulator: LLM call with exception fallback | Task 2 |
| Simulator: abort_on_default_after | Task 2 |
| Simulator: consecutive defaults reset on trigger/LLM | Task 2 |
| `run_interactive()` sentinel-file polling | Task 3 |
| Orchestrator: headless → run_one_shot | Task 4 |
| Orchestrator: interactive → run_interactive | Task 4 |
| Orchestrator: headless + auto_user → run_multi_turn | Task 4 |

### Placeholder scan
No TBDs, TODOs, or deferred steps found — every step includes exact code.

### Type consistency
- `TriggerMatch`, `Trigger` defined in Task 1 schemas.py — used by name in Task 2 test imports ✓
- `AutoUserSimulator` takes `AutoUser` (extended in Task 1) — types consistent ✓
- `run_interactive` defined in Task 3, imported in Task 4 ✓
- `RunResult` used uniformly across runner and orchestrator ✓
- `AutoUser.from_path(Path(...))` — `from_path` exists on the updated model ✓
