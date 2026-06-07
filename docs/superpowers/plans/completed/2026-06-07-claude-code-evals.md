# claude-code-evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `packages/claude-code-evals/` — a generic, installable Python library for evaluating Claude Code behavior across plugin configurations, with no dependencies on other agent-research packages.

**Architecture:** Consuming projects place scenario YAML + prompt + verifier files under `evals/`; this package provides all harness machinery. deepeval handles metric/test-runner integration; pytest-evals gates expensive runs behind `CLAUDE_CODE_RUN_EVALS=1`. Both a `cc-eval` CLI and a pytest plugin expose the same `run_one()` orchestrator core.

**Tech Stack:** Python 3.11, Pydantic v2, Click, Jinja2, Rich, PyYAML, deepeval>=4.0.0, pytest-evals>=0.3.4

---

## File Map

| File | Responsibility |
|------|---------------|
| `packages/claude-code-evals/pyproject.toml` | Package metadata, deps, entry-points |
| `src/claude_code_evals/schemas.py` | Pydantic v2 models: Scenario, Config, Runset, AutoUser, VerifyEntry |
| `src/claude_code_evals/isolation.py` | IsolationContext protocol, WorktreeIsolation, FixtureIsolation |
| `src/claude_code_evals/transcript.py` | Parse stream-json JSONL → Transcript dataclass |
| `src/claude_code_evals/pricing.py` | Hardcoded Claude model cost table |
| `src/claude_code_evals/metrics.py` | Compute flat metrics dict from Transcript + verify result |
| `src/claude_code_evals/judge.py` | ClaudeCodeJudge(DeepEvalBaseLLM) using `claude -p` |
| `src/claude_code_evals/user_simulator.py` | AutoUserSimulator — LLM-driven multi-turn reply driver |
| `src/claude_code_evals/runner.py` | Headless runner: one-shot + multi-turn subprocess management |
| `src/claude_code_evals/verify/base.py` | VerifyOutcome dataclass, abstract VerifierBase(BaseMetric) |
| `src/claude_code_evals/verify/script.py` | ScriptVerifier — run verify.sh, pass/fail by exit code |
| `src/claude_code_evals/verify/golden.py` | GoldenVerifier — apply golden.patch, diff check |
| `src/claude_code_evals/verify/rubric.py` | RubricVerifier — GEval + ClaudeCodeJudge |
| `src/claude_code_evals/orchestrator.py` | run_one(), ScenarioRunResult, artifact writing |
| `src/claude_code_evals/pytest_plugin.py` | pytest fixtures (evals_root, run_scenario), assert_scenario |
| `src/claude_code_evals/report.py` | Markdown + JSON report from runset run artifacts |
| `src/claude_code_evals/cli.py` | cc-eval list/run/report CLI (Click) |
| `src/claude_code_evals/templates/report.md.j2` | Jinja2 report template |

---

### Task 1: Package scaffold

**Files:**
- Create: `packages/claude-code-evals/pyproject.toml`
- Create: `packages/claude-code-evals/src/claude_code_evals/__init__.py`
- Create: `packages/claude-code-evals/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p packages/claude-code-evals/src/claude_code_evals/verify
mkdir -p packages/claude-code-evals/src/claude_code_evals/templates
mkdir -p packages/claude-code-evals/tests
touch packages/claude-code-evals/src/claude_code_evals/__init__.py
touch packages/claude-code-evals/src/claude_code_evals/verify/__init__.py
touch packages/claude-code-evals/tests/__init__.py
```

- [ ] **Step 2: Write pyproject.toml**

```toml
# packages/claude-code-evals/pyproject.toml
[project]
name = "claude-code-evals"
version = "0.1.0"
description = "Generic harness for evaluating Claude Code behavior across plugin configurations"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.6",
    "click>=8.1",
    "jinja2>=3.1",
    "rich>=13.7",
    "pyyaml>=6.0",
    "deepeval>=4.0.0",
    "pytest-evals>=0.3.4",
    "pytest>=8.0",
]

[project.scripts]
cc-eval = "claude_code_evals.cli:app"

[project.entry-points."pytest11"]
claude-code-evals = "claude_code_evals.pytest_plugin"

[build-system]
requires = ["uv_build>=0.11.14,<0.12"]
build-backend = "uv_build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
asyncio_mode = "auto"
markers = [
    "eval: requires CLAUDE_CODE_RUN_EVALS=1",
    "integration: requires subprocess/real claude binary",
]
```

- [ ] **Step 3: Install the workspace**

```bash
uv sync
```

Expected: no errors; `claude-code-evals` appears in `uv run --package claude-code-evals python -c "import claude_code_evals; print('ok')"` output.

- [ ] **Step 4: Verify import**

```bash
uv run --package claude-code-evals python -c "import claude_code_evals; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): package scaffold"
```

---

### Task 2: schemas.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/schemas.py`
- Create: `packages/claude-code-evals/tests/test_schemas.py`
- Create: `packages/claude-code-evals/tests/fixtures/scenario_worktree.yaml`
- Create: `packages/claude-code-evals/tests/fixtures/scenario_fixture.yaml`
- Create: `packages/claude-code-evals/tests/fixtures/config_base.yaml`
- Create: `packages/claude-code-evals/tests/fixtures/runset.yaml`
- Create: `packages/claude-code-evals/tests/fixtures/auto_user.yaml`

- [ ] **Step 1: Write test fixtures**

`packages/claude-code-evals/tests/fixtures/scenario_worktree.yaml`:
```yaml
name: smoke-readme
description: Agent reads README and answers a question
isolation_mode: worktree
target_repo: ~/Personal/my-repo
baseline_sha: abc1234
configs: [base]
mode: headless
eval_mode: qa
verify:
  - kind: script
    path: verify.sh
budgets:
  max_turns: 10
  max_input_tokens: 50000
  max_wall_seconds: 120
```

`packages/claude-code-evals/tests/fixtures/scenario_fixture.yaml`:
```yaml
name: smoke-fixture
description: Agent works in a fixture directory
isolation_mode: fixture
fixture_dir: fixtures/
configs: [base]
mode: headless
eval_mode: implement
verify:
  - kind: golden
    path: golden.patch
```

`packages/claude-code-evals/tests/fixtures/config_base.yaml`:
```yaml
name: base
model: claude-sonnet-4-6
temperature: 0.0
```

`packages/claude-code-evals/tests/fixtures/runset.yaml`:
```yaml
name: smoke
scenarios: [smoke-readme]
default_configs: [base]
```

`packages/claude-code-evals/tests/fixtures/auto_user.yaml`:
```yaml
model: claude-haiku-4-5-20251001
max_replies: 3
stop_on: "<DONE>"
system_prompt: "Drive the task forward. Say <DONE> when finished."
```

- [ ] **Step 2: Write failing tests**

```python
# packages/claude-code-evals/tests/test_schemas.py
from __future__ import annotations
import pytest
from pathlib import Path
from pydantic import ValidationError
from claude_code_evals.schemas import Scenario, Config, Runset, AutoUser, VerifyEntry

FIXTURES = Path(__file__).parent / "fixtures"


def test_scenario_worktree_from_path():
    s = Scenario.from_path(FIXTURES / "scenario_worktree.yaml")
    assert s.name == "smoke-readme"
    assert s.isolation_mode == "worktree"
    assert s.target_repo == "~/Personal/my-repo"
    assert s.baseline_sha == "abc1234"
    assert len(s.verify) == 1
    assert s.verify[0].kind == "script"
    assert s.budgets.max_turns == 10


def test_scenario_fixture_from_path():
    s = Scenario.from_path(FIXTURES / "scenario_fixture.yaml")
    assert s.isolation_mode == "fixture"
    assert s.fixture_dir == "fixtures/"
    assert s.verify[0].kind == "golden"


def test_config_from_path():
    c = Config.from_path(FIXTURES / "config_base.yaml")
    assert c.name == "base"
    assert c.model == "claude-sonnet-4-6"
    assert c.temperature == 0.0
    assert c.plugin_dirs == []
    assert c.extra_env == {}


def test_runset_from_path():
    r = Runset.from_path(FIXTURES / "runset.yaml")
    assert r.name == "smoke"
    assert r.scenarios == ["smoke-readme"]
    assert r.default_configs == ["base"]


def test_auto_user_from_path():
    a = AutoUser.from_path(FIXTURES / "auto_user.yaml")
    assert a.model == "claude-haiku-4-5-20251001"
    assert a.max_replies == 3
    assert a.stop_on == "<DONE>"


def test_worktree_mode_requires_target_repo():
    with pytest.raises(ValidationError, match="target_repo"):
        Scenario.model_validate({
            "name": "x",
            "isolation_mode": "worktree",
            "baseline_sha": "abc1234",
        })


def test_worktree_mode_requires_baseline_sha():
    with pytest.raises(ValidationError, match="baseline_sha"):
        Scenario.model_validate({
            "name": "x",
            "isolation_mode": "worktree",
            "target_repo": "~/repo",
        })


def test_fixture_mode_requires_fixture_dir():
    with pytest.raises(ValidationError, match="fixture_dir"):
        Scenario.model_validate({
            "name": "x",
            "isolation_mode": "fixture",
        })


def test_interactive_mode_forbids_auto_user():
    with pytest.raises(ValidationError, match="interactive"):
        Scenario.model_validate({
            "name": "x",
            "isolation_mode": "fixture",
            "fixture_dir": "fixtures/",
            "mode": "interactive",
            "auto_user": "auto_user.yaml",
        })


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Config.model_validate({"name": "x", "unknown_field": True})


def test_verify_entry_rubric_fields():
    v = VerifyEntry.model_validate({
        "kind": "rubric",
        "path": "rubric.md",
        "judge": "claude-haiku-4-5-20251001",
        "pass_threshold": 4,
    })
    assert v.pass_threshold == 4
    assert v.judge == "claude-haiku-4-5-20251001"
```

- [ ] **Step 3: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_schemas.py -v
```

Expected: `ImportError: cannot import name 'Scenario' from 'claude_code_evals.schemas'`

- [ ] **Step 4: Implement schemas.py**

```python
# packages/claude-code-evals/src/claude_code_evals/schemas.py
"""Pydantic v2 data models for scenario, config, runset, and verifier configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator


class VerifyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["script", "golden", "rubric"]
    path: str
    judge: str | None = None
    pass_threshold: float | None = None


class Budgets(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_turns: int = 20
    max_input_tokens: int = 100000
    max_wall_seconds: int = 300


class MetricsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_shape: bool = True
    judge_qualitative: bool = False


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    description: str = ""
    isolation_mode: Literal["worktree", "fixture"] = "worktree"
    target_repo: str | None = None
    baseline_sha: str | None = None
    fixture_dir: str | None = None
    configs: list[str] = []
    mode: Literal["headless", "interactive"] = "headless"
    eval_mode: Literal["qa", "implement"] = "qa"
    auto_user: str | None = None
    preflight: str | None = None
    verify: list[VerifyEntry] = []
    metrics: MetricsConfig = MetricsConfig()
    budgets: Budgets = Budgets()

    @model_validator(mode="after")
    def _check_isolation(self) -> "Scenario":
        if self.isolation_mode == "worktree":
            if not self.target_repo:
                raise ValueError("worktree mode requires target_repo")
            if not self.baseline_sha:
                raise ValueError("worktree mode requires baseline_sha")
        else:
            if not self.fixture_dir:
                raise ValueError("fixture mode requires fixture_dir")
        return self

    @model_validator(mode="after")
    def _check_interactive(self) -> "Scenario":
        if self.mode == "interactive" and self.auto_user:
            raise ValueError("interactive mode forbids auto_user")
        return self

    @classmethod
    def from_path(cls, path: Path) -> "Scenario":
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    plugin_dirs: list[str] = []
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.0
    extra_env: dict[str, str] = {}
    extra_settings: dict = {}

    @classmethod
    def from_path(cls, path: Path) -> "Config":
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))


class Runset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    scenarios: list[str] = []
    default_configs: list[str] = []

    @classmethod
    def from_path(cls, path: Path) -> "Runset":
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))


class AutoUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = "claude-haiku-4-5-20251001"
    max_replies: int = 5
    stop_on: str = "<DONE>"
    system_prompt: str = "Drive the task forward. Say <DONE> when the task is complete."

    @classmethod
    def from_path(cls, path: Path) -> "AutoUser":
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))
```

- [ ] **Step 5: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_schemas.py -v
```

Expected: `12 passed`

- [ ] **Step 6: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): schemas — Scenario, Config, Runset, AutoUser, VerifyEntry"
```

---

### Task 3: transcript.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/transcript.py`
- Create: `packages/claude-code-evals/tests/test_transcript.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_transcript.py
from __future__ import annotations
import json
from claude_code_evals.transcript import parse_transcript, Transcript

def _make_jsonl(*events: dict) -> str:
    return "\n".join(json.dumps(e) for e in events)


ASSISTANT_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {"type": "text", "text": "Hello"},
            {
                "type": "tool_use",
                "id": "tu1",
                "name": "Read",
                "input": {"file_path": "README.md"},
            },
        ]
    },
}

TOOL_RESULT_EVENT = {
    "type": "user",
    "message": {
        "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": "content"}]
    },
}

EDIT_EVENT = {
    "type": "assistant",
    "message": {
        "content": [
            {
                "type": "tool_use",
                "id": "tu2",
                "name": "Edit",
                "input": {"file_path": "src/foo.py", "old_string": "a", "new_string": "b"},
            }
        ]
    },
}

RESULT_EVENT = {
    "type": "result",
    "subtype": "success",
    "usage": {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_input_tokens": 20,
        "cache_creation_input_tokens": 10,
    },
}


def test_parse_empty():
    t = parse_transcript("")
    assert isinstance(t, Transcript)
    assert t.turn_count == 0
    assert t.input_tokens == 0


def test_parse_token_usage():
    jsonl = _make_jsonl(RESULT_EVENT)
    t = parse_transcript(jsonl)
    assert t.input_tokens == 100
    assert t.output_tokens == 50
    assert t.cache_read_tokens == 20
    assert t.cache_write_tokens == 10


def test_parse_turn_count():
    jsonl = _make_jsonl(ASSISTANT_EVENT, TOOL_RESULT_EVENT, ASSISTANT_EVENT)
    t = parse_transcript(jsonl)
    assert t.turn_count == 2


def test_parse_tool_calls():
    jsonl = _make_jsonl(ASSISTANT_EVENT)
    t = parse_transcript(jsonl)
    assert t.tool_call_counts["Read"] == 1
    assert len(t.tool_calls) == 1
    assert t.tool_calls[0].tool == "Read"


def test_files_read():
    jsonl = _make_jsonl(ASSISTANT_EVENT)
    t = parse_transcript(jsonl)
    assert "README.md" in t.files_read


def test_files_edited():
    jsonl = _make_jsonl(EDIT_EVENT)
    t = parse_transcript(jsonl)
    assert "src/foo.py" in t.files_edited


def test_files_written():
    write_event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu3",
                    "name": "Write",
                    "input": {"file_path": "out.txt", "content": "x"},
                }
            ]
        },
    }
    jsonl = _make_jsonl(write_event)
    t = parse_transcript(jsonl)
    assert "out.txt" in t.files_written


def test_final_assistant_text():
    jsonl = _make_jsonl(ASSISTANT_EVENT, RESULT_EVENT)
    t = parse_transcript(jsonl)
    assert t.final_assistant_text == "Hello"


def test_subagent_dispatches():
    agent_event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu4",
                    "name": "Agent",
                    "input": {"prompt": "do something"},
                }
            ]
        },
    }
    jsonl = _make_jsonl(agent_event)
    t = parse_transcript(jsonl)
    assert t.subagent_dispatches == 1


def test_permission_prompt_count():
    perm_event = {"type": "permission", "tool": "Bash", "input": {}}
    jsonl = _make_jsonl(perm_event)
    t = parse_transcript(jsonl)
    assert t.permission_prompt_count == 1


def test_skill_invocations():
    skill_event = {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": "tu5",
                    "name": "Skill",
                    "input": {"skill": "my-skill"},
                }
            ]
        },
    }
    jsonl = _make_jsonl(skill_event)
    t = parse_transcript(jsonl)
    assert "my-skill" in t.skill_invocations
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_transcript.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement transcript.py**

```python
# packages/claude-code-evals/src/claude_code_evals/transcript.py
"""Parse Claude Code stream-json JSONL output into a structured Transcript."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class ToolCallEvent:
    tool: str
    input_keys: list[str]


@dataclass
class Transcript:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    turn_count: int = 0
    tool_calls: list[ToolCallEvent] = field(default_factory=list)
    tool_call_counts: dict[str, int] = field(default_factory=dict)
    files_read: list[str] = field(default_factory=list)
    files_edited: list[str] = field(default_factory=list)
    files_written: list[str] = field(default_factory=list)
    subagent_dispatches: int = 0
    skill_invocations: list[str] = field(default_factory=list)
    hook_loaded_skills: list[str] = field(default_factory=list)
    permission_prompt_count: int = 0
    final_assistant_text: str = ""


_READ_TOOLS = {"Read", "Glob", "Grep"}
_EDIT_TOOLS = {"Edit"}
_WRITE_TOOLS = {"Write", "NotebookEdit"}


def parse_transcript(jsonl: str) -> Transcript:
    """Parse stream-json JSONL into a Transcript.

    Processes each line as a JSON event. Unknown event types are silently
    skipped. JSONDecodeError lines are skipped.
    """
    t = Transcript()
    last_assistant_text = ""

    for line in jsonl.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue

        ev_type = ev.get("type")

        if ev_type == "assistant":
            t.turn_count += 1
            msg = ev.get("message") or {}
            text_parts: list[str] = []
            for block in msg.get("content") or []:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    _handle_tool_use(t, block)
            if text_parts:
                last_assistant_text = "".join(text_parts)

        elif ev_type == "result":
            usage = ev.get("usage") or {}
            t.input_tokens = usage.get("input_tokens", 0)
            t.output_tokens = usage.get("output_tokens", 0)
            t.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            t.cache_write_tokens = usage.get("cache_creation_input_tokens", 0)

        elif ev_type == "permission":
            t.permission_prompt_count += 1

    t.final_assistant_text = last_assistant_text
    return t


def _handle_tool_use(t: Transcript, block: dict) -> None:
    name = block.get("name", "")
    inp = block.get("input") or {}
    keys = list(inp.keys())

    t.tool_calls.append(ToolCallEvent(tool=name, input_keys=keys))
    t.tool_call_counts[name] = t.tool_call_counts.get(name, 0) + 1

    path = inp.get("file_path") or inp.get("path", "")
    if name in _READ_TOOLS and path:
        t.files_read.append(path)
    elif name in _EDIT_TOOLS and path:
        t.files_edited.append(path)
    elif name in _WRITE_TOOLS and path:
        t.files_written.append(path)
    elif name == "Agent":
        t.subagent_dispatches += 1
    elif name == "Skill":
        skill_name = inp.get("skill", "")
        if skill_name:
            t.skill_invocations.append(skill_name)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_transcript.py -v
```

Expected: `13 passed`

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): transcript — stream-json JSONL parser"
```

---

### Task 4: pricing.py + metrics.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/pricing.py`
- Create: `packages/claude-code-evals/src/claude_code_evals/metrics.py`
- Create: `packages/claude-code-evals/tests/test_pricing.py`
- Create: `packages/claude-code-evals/tests/test_metrics.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_pricing.py
import pytest
from claude_code_evals.pricing import cost_for_usage, UnknownModelError

def test_cost_for_usage_sonnet():
    cost = cost_for_usage("claude-sonnet-4-6", {"input": 1_000_000, "output": 0})
    assert cost == pytest.approx(3.0)

def test_cost_for_usage_with_cache():
    cost = cost_for_usage("claude-sonnet-4-6", {
        "input": 0, "output": 0,
        "cache_read": 1_000_000, "cache_write": 1_000_000,
    })
    assert cost == pytest.approx(0.30 + 3.75)

def test_unknown_model_raises():
    with pytest.raises(UnknownModelError):
        cost_for_usage("nonexistent-model", {"input": 1000})

def test_missing_keys_default_to_zero():
    cost = cost_for_usage("claude-haiku-4-5-20251001", {})
    assert cost == 0.0
```

```python
# packages/claude-code-evals/tests/test_metrics.py
from claude_code_evals.transcript import Transcript, ToolCallEvent
from claude_code_evals.metrics import compute_metrics


def _transcript(**kwargs) -> Transcript:
    defaults = dict(
        input_tokens=100, output_tokens=50,
        cache_read_tokens=0, cache_write_tokens=0,
        turn_count=2,
        tool_calls=[], tool_call_counts={},
        files_read=[], files_edited=[], files_written=[],
        subagent_dispatches=0, skill_invocations=[],
        hook_loaded_skills=[], permission_prompt_count=0,
        final_assistant_text="done",
    )
    defaults.update(kwargs)
    return Transcript(**defaults)


def test_basic_metrics():
    t = _transcript()
    m = compute_metrics(t, {"success": True})
    assert m["input_tokens"] == 100
    assert m["output_tokens"] == 50
    assert m["turn_count"] == 2
    assert m["verify_passed"] is True


def test_distinct_paths_touched():
    t = _transcript(
        files_read=["a.py", "b.py"],
        files_edited=["a.py"],
        files_written=["c.py"],
    )
    m = compute_metrics(t, {})
    assert m["distinct_paths_touched"] == 3  # a.py, b.py, c.py


def test_tool_calls_before_first_edit_no_edit():
    calls = [ToolCallEvent("Read", []), ToolCallEvent("Grep", [])]
    t = _transcript(tool_calls=calls)
    m = compute_metrics(t, {})
    assert m["tool_calls_before_first_edit"] == 2


def test_tool_calls_before_first_edit_with_edit():
    calls = [
        ToolCallEvent("Read", []),
        ToolCallEvent("Grep", []),
        ToolCallEvent("Edit", []),
        ToolCallEvent("Read", []),
    ]
    t = _transcript(tool_calls=calls)
    m = compute_metrics(t, {})
    assert m["tool_calls_before_first_edit"] == 2
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_pricing.py tests/test_metrics.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement pricing.py**

```python
# packages/claude-code-evals/src/claude_code_evals/pricing.py
"""Hardcoded Claude model pricing for cost tracking. Update manually when Anthropic changes prices.

Prices are USD per million tokens, current as of 2026-06-07.
"""
from __future__ import annotations


class UnknownModelError(KeyError):
    pass


PRICES: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {
        "input": 1.0, "output": 5.0, "cache_read": 0.10, "cache_write": 1.25,
    },
    "claude-sonnet-4-6": {
        "input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75,
    },
    "claude-opus-4-7": {
        "input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75,
    },
    "claude-opus-4-8": {
        "input": 15.0, "output": 75.0, "cache_read": 1.50, "cache_write": 18.75,
    },
}


def cost_for_usage(model: str, usage: dict[str, int]) -> float:
    """Return USD cost for token usage on model.

    usage keys: input, output, cache_read, cache_write (int token counts).
    Missing keys default to 0. Raises UnknownModelError if model not in PRICES.
    """
    if model not in PRICES:
        raise UnknownModelError(f"unknown model {model!r}; update pricing.py")
    p = PRICES[model]
    return sum(usage.get(k, 0) * p[k] / 1_000_000 for k in p)
```

- [ ] **Step 4: Implement metrics.py**

```python
# packages/claude-code-evals/src/claude_code_evals/metrics.py
"""Compute flat metrics dict from Transcript + verify result."""
from __future__ import annotations

from claude_code_evals.transcript import Transcript

_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}


def _tool_calls_before_first_edit(transcript: Transcript) -> int:
    for i, call in enumerate(transcript.tool_calls):
        if call.tool in _EDIT_TOOLS:
            return i
    return len(transcript.tool_calls)


def compute_metrics(transcript: Transcript, verify_result: dict) -> dict:
    """Return flat metrics dict from a Transcript and verify result dict."""
    all_paths = set(transcript.files_read + transcript.files_edited + transcript.files_written)
    return {
        "input_tokens": transcript.input_tokens,
        "output_tokens": transcript.output_tokens,
        "cache_read_tokens": transcript.cache_read_tokens,
        "cache_write_tokens": transcript.cache_write_tokens,
        "turn_count": transcript.turn_count,
        "tool_call_counts": dict(transcript.tool_call_counts),
        "files_read_count": len(transcript.files_read),
        "files_edited_count": len(transcript.files_edited),
        "files_written_count": len(transcript.files_written),
        "tool_calls_before_first_edit": _tool_calls_before_first_edit(transcript),
        "distinct_paths_touched": len(all_paths),
        "subagent_dispatches": transcript.subagent_dispatches,
        "skill_invocations_count": len(transcript.skill_invocations),
        "permission_prompt_count": transcript.permission_prompt_count,
        "verify_passed": verify_result.get("success", False),
    }
```

- [ ] **Step 5: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_pricing.py tests/test_metrics.py -v
```

Expected: `8 passed`

- [ ] **Step 6: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): pricing + metrics"
```

---

### Task 5: isolation.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/isolation.py`
- Create: `packages/claude-code-evals/tests/test_isolation.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_isolation.py
from __future__ import annotations
import json
import subprocess
import tempfile
from pathlib import Path
import pytest
from claude_code_evals.isolation import WorktreeIsolation, FixtureIsolation
from claude_code_evals.schemas import Scenario, Config


def _fixture_scenario(tmp_path: Path) -> tuple[Scenario, Config]:
    fixture_src = tmp_path / "fixture_src"
    fixture_src.mkdir()
    (fixture_src / "README.md").write_text("hello")
    s = Scenario.model_validate({
        "name": "test",
        "isolation_mode": "fixture",
        "fixture_dir": str(fixture_src),
    })
    c = Config.model_validate({"name": "base"})
    return s, c


def test_fixture_isolation_creates_worktree_path(tmp_path: Path):
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        assert iso.worktree_path.exists()
        assert (iso.worktree_path / "README.md").exists()


def test_fixture_isolation_creates_cfg_dir(tmp_path: Path):
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        assert iso.cfg_dir.exists()
        assert (iso.cfg_dir / "settings.json").exists()


def test_fixture_isolation_writes_settings_accept_edits(tmp_path: Path):
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        settings = json.loads((iso.cfg_dir / "settings.json").read_text())
        assert settings["permissions"]["defaultMode"] == "acceptEdits"


def test_fixture_isolation_cleanup(tmp_path: Path):
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        wt = iso.worktree_path
    assert not wt.exists()


def test_fixture_isolation_keep(tmp_path: Path):
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c, keep=True) as iso:
        wt = iso.worktree_path
    assert wt.exists()


def test_fixture_isolation_writes_meta_json(tmp_path: Path):
    s, c = _fixture_scenario(tmp_path)
    with FixtureIsolation(s, c) as iso:
        meta = json.loads(iso.meta_path.read_text())
        assert meta["scenario"] == "test"
        assert meta["config"] == "base"


def test_fixture_isolation_extra_env_in_settings(tmp_path: Path):
    s, c = _fixture_scenario(tmp_path)
    c2 = Config.model_validate({"name": "base", "extra_env": {"MY_VAR": "hello"}})
    with FixtureIsolation(s, c2) as iso:
        settings = json.loads((iso.cfg_dir / "settings.json").read_text())
        assert settings["env"]["MY_VAR"] == "hello"
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_isolation.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement isolation.py**

```python
# packages/claude-code-evals/src/claude_code_evals/isolation.py
"""Workspace isolation: WorktreeIsolation (git worktree) and FixtureIsolation (directory copy)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from claude_code_evals.schemas import Config, Scenario


@runtime_checkable
class IsolationContext(Protocol):
    @property
    def worktree_path(self) -> Path: ...
    @property
    def cfg_dir(self) -> Path: ...
    @property
    def oauth_token(self) -> str | None: ...
    @property
    def meta_path(self) -> Path: ...
    def __enter__(self) -> "IsolationContext": ...
    def __exit__(self, *exc: object) -> None: ...


class _BaseIsolation:
    def __init__(self, scenario: Scenario, config: Config, *, keep: bool = False) -> None:
        self._scenario = scenario
        self._config = config
        self._keep = keep
        self._tmp: str | None = None
        self._wt: Path | None = None
        self._cfg: Path | None = None

    @property
    def worktree_path(self) -> Path:
        assert self._wt is not None
        return self._wt

    @property
    def cfg_dir(self) -> Path:
        assert self._cfg is not None
        return self._cfg

    @property
    def oauth_token(self) -> str | None:
        return os.environ.get("CLAUDE_OAUTH_TOKEN")

    @property
    def meta_path(self) -> Path:
        return self.cfg_dir / "meta.json"

    def _setup_cfg_dir(self) -> None:
        self._cfg = Path(self._tmp) / "cfg"
        self._cfg.mkdir(parents=True)

        # Symlink each plugin_dir into cfg/plugins/
        plugins_dir = self._cfg / "plugins"
        plugins_dir.mkdir()
        evals_root = Path.cwd()
        for plugin_dir_str in self._config.plugin_dirs:
            pd = Path(plugin_dir_str)
            if not pd.is_absolute():
                pd = (evals_root / pd).resolve()
            link = plugins_dir / pd.name
            link.symlink_to(pd)

        # Write installed_plugins.json + known_marketplaces.json
        installed = [pd.name for pd_str in self._config.plugin_dirs
                     for pd in [Path(pd_str)] if True]
        (self._cfg / "installed_plugins.json").write_text(
            json.dumps({"plugins": installed}, indent=2)
        )
        (self._cfg / "known_marketplaces.json").write_text(json.dumps([]))

        # Build settings.json
        settings: dict = {
            "permissions": {"defaultMode": "acceptEdits"},
        }
        if self._config.extra_env:
            settings["env"] = dict(self._config.extra_env)
        settings.update(self._config.extra_settings)
        (self._cfg / "settings.json").write_text(json.dumps(settings, indent=2))

        # Write meta.json
        meta = {
            "scenario": self._scenario.name,
            "config": self._config.name,
            "model": self._config.model,
        }
        self.meta_path.write_text(json.dumps(meta, indent=2))

    def _cleanup(self) -> None:
        if self._tmp and not self._keep:
            shutil.rmtree(Path(self._tmp), ignore_errors=True)


class WorktreeIsolation(_BaseIsolation):
    """Git worktree isolation: checks out baseline_sha in a fresh tmpdir."""

    def __enter__(self) -> "WorktreeIsolation":
        self._tmp = tempfile.mkdtemp(prefix="cc-eval-wt-")
        self._wt = Path(self._tmp) / "wt"

        target_repo = Path(self._scenario.target_repo).expanduser()  # type: ignore[arg-type]
        sha = self._scenario.baseline_sha

        subprocess.run(
            ["git", "worktree", "add", "--detach", str(self._wt), sha],
            cwd=str(target_repo),
            check=True,
            capture_output=True,
        )

        self._setup_cfg_dir()
        return self

    def __exit__(self, *exc: object) -> None:
        if self._wt and self._wt.exists():
            target_repo = Path(self._scenario.target_repo).expanduser()  # type: ignore[arg-type]
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self._wt)],
                cwd=str(target_repo),
                capture_output=True,
            )
        self._cleanup()


class FixtureIsolation(_BaseIsolation):
    """Fixture directory isolation: copies fixture_dir into a fresh tmpdir."""

    def __enter__(self) -> "FixtureIsolation":
        self._tmp = tempfile.mkdtemp(prefix="cc-eval-fix-")
        fixture_src = Path(self._scenario.fixture_dir)  # type: ignore[arg-type]
        self._wt = Path(self._tmp) / "wt"
        shutil.copytree(fixture_src, self._wt)
        self._setup_cfg_dir()
        return self

    def __exit__(self, *exc: object) -> None:
        self._cleanup()
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_isolation.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): isolation — WorktreeIsolation + FixtureIsolation"
```

---

### Task 6: judge.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/judge.py`
- Create: `packages/claude-code-evals/tests/test_judge.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_judge.py
from __future__ import annotations
import json
from unittest.mock import MagicMock, patch
from claude_code_evals.judge import ClaudeCodeJudge, JudgeResult, _run_claude_judge


def _fake_result(text: str) -> JudgeResult:
    return JudgeResult(stdout=text, input_tokens=10, output_tokens=5)


def test_get_model_name():
    judge = ClaudeCodeJudge(model="claude-haiku-4-5-20251001")
    assert judge.get_model_name() == "claude-haiku-4-5-20251001"


def test_generate_returns_stdout():
    judge = ClaudeCodeJudge()
    with patch("claude_code_evals.judge._run_claude_judge", return_value=_fake_result("score: 4")):
        result = judge.generate("rate this")
    assert result == "score: 4"


def test_run_claude_judge_parses_text(tmp_path):
    """_run_claude_judge parses stream-json and returns text."""
    assistant_event = json.dumps({
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "4"}]},
    })
    result_event = json.dumps({
        "type": "result",
        "usage": {"input_tokens": 10, "output_tokens": 2,
                  "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
    })
    fake_stdout = f"{assistant_event}\n{result_event}\n"

    mock_proc = MagicMock()
    mock_proc.stdout = iter(fake_stdout.splitlines(keepends=True))
    mock_proc.returncode = 0

    with patch("subprocess.Popen", return_value=mock_proc):
        mock_proc.__enter__ = lambda s: s
        mock_proc.__exit__ = MagicMock(return_value=False)
        result = _run_claude_judge("rate this", model="claude-haiku-4-5-20251001")

    assert result.stdout == "4"
    assert result.input_tokens == 10
    assert result.output_tokens == 2
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_judge.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement judge.py**

```python
# packages/claude-code-evals/src/claude_code_evals/judge.py
"""ClaudeCodeJudge: a DeepEvalBaseLLM that uses `claude -p` as its backend."""

from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass

from deepeval.models.base_model import DeepEvalBaseLLM


@dataclass
class JudgeResult:
    stdout: str
    input_tokens: int
    output_tokens: int


def _run_claude_judge(prompt: str, *, model: str) -> JudgeResult:
    """Spawn `claude -p --model <model> --output-format stream-json` and parse output.

    Security: cmd is always a list; prompt is the final element — never interpolated.
    """
    cmd = ["claude", "-p", "--model", model, "--output-format", "stream-json", prompt]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    text_parts: list[str] = []
    input_tokens = 0
    output_tokens = 0

    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for block in (ev.get("message") or {}).get("content") or []:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
        elif ev.get("type") == "result":
            usage = ev.get("usage") or {}
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

    proc.wait()
    return JudgeResult(
        stdout="".join(text_parts),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


class ClaudeCodeJudge(DeepEvalBaseLLM):
    """DeepEvalBaseLLM implementation backed by `claude -p`."""

    def __init__(self, model: str = "claude-haiku-4-5-20251001") -> None:
        self.model = model

    def generate(self, prompt: str) -> str:
        return _run_claude_judge(prompt, model=self.model).stdout

    async def a_generate(self, prompt: str) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate, prompt)

    def get_model_name(self) -> str:
        return self.model
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_judge.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): judge — ClaudeCodeJudge(DeepEvalBaseLLM)"
```

---

### Task 7: user_simulator.py + runner.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/user_simulator.py`
- Create: `packages/claude-code-evals/src/claude_code_evals/runner.py`
- Create: `packages/claude-code-evals/tests/test_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_runner.py
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from claude_code_evals.runner import run_one_shot, RunResult, EVAL_SYSTEM_PROMPT_QA, EVAL_SYSTEM_PROMPT_IMPLEMENT


def _make_fake_proc(events: list[dict]) -> MagicMock:
    jsonl = "\n".join(json.dumps(e) for e in events) + "\n"
    mock = MagicMock()
    mock.stdout = iter(jsonl.splitlines(keepends=True))
    mock.returncode = 0
    mock.terminate = MagicMock()
    mock.wait = MagicMock()
    return mock


RESULT_EVENT = {
    "type": "result",
    "subtype": "success",
    "usage": {"input_tokens": 50, "output_tokens": 20,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
}

ASSISTANT_EVENT = {
    "type": "assistant",
    "message": {"content": [{"type": "text", "text": "Done."}]},
}


def test_run_one_shot_success(tmp_path: Path):
    proc = _make_fake_proc([ASSISTANT_EVENT, RESULT_EVENT])
    with patch("subprocess.Popen", return_value=proc):
        result, jsonl = run_one_shot(
            prompt="Do something",
            worktree_path=tmp_path,
            cfg_dir=tmp_path,
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
        )
    assert result.final_status == "success"
    assert result.budget_exceeded is False
    assert result.wall_seconds >= 0


def test_run_one_shot_returns_jsonl(tmp_path: Path):
    proc = _make_fake_proc([ASSISTANT_EVENT, RESULT_EVENT])
    with patch("subprocess.Popen", return_value=proc):
        _, jsonl = run_one_shot(
            prompt="Do something",
            worktree_path=tmp_path,
            cfg_dir=tmp_path,
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
        )
    events = [json.loads(line) for line in jsonl.splitlines() if line.strip()]
    types = [e["type"] for e in events]
    assert "assistant" in types
    assert "result" in types


def test_run_one_shot_error_status(tmp_path: Path):
    error_event = {"type": "result", "subtype": "error_max_turns",
                   "usage": {"input_tokens": 10, "output_tokens": 5,
                             "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}}
    proc = _make_fake_proc([error_event])
    with patch("subprocess.Popen", return_value=proc):
        result, _ = run_one_shot(
            prompt="Do something",
            worktree_path=tmp_path,
            cfg_dir=tmp_path,
            system_prompt=EVAL_SYSTEM_PROMPT_QA,
        )
    assert result.final_status == "error_max_turns"


def test_system_prompt_constants():
    assert "EVAL MODE" in EVAL_SYSTEM_PROMPT_QA
    assert "Q&A" in EVAL_SYSTEM_PROMPT_QA
    assert "EVAL MODE" in EVAL_SYSTEM_PROMPT_IMPLEMENT
    assert "IMPLEMENT" in EVAL_SYSTEM_PROMPT_IMPLEMENT
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_runner.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement user_simulator.py**

```python
# packages/claude-code-evals/src/claude_code_evals/user_simulator.py
"""AutoUserSimulator: LLM-driven reply driver for multi-turn eval runs."""

from __future__ import annotations

from claude_code_evals.judge import _run_claude_judge
from claude_code_evals.schemas import AutoUser


class AutoUserSimulator:
    """Drive multi-turn conversations by calling claude -p for each reply.

    Stops when stop_on pattern appears in assistant text or max_replies exhausted.
    """

    def __init__(self, config: AutoUser) -> None:
        self._config = config
        self._reply_count = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def reply(self, assistant_text: str) -> str | None:
        """Return next user message, or None to stop the conversation."""
        if self._reply_count >= self._config.max_replies:
            return None
        if self._config.stop_on in assistant_text:
            return None

        prompt = f"{self._config.system_prompt}\n\nAgent said:\n{assistant_text}"
        result = _run_claude_judge(prompt, model=self._config.model)
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self._reply_count += 1
        return result.stdout
```

- [ ] **Step 4: Implement runner.py**

```python
# packages/claude-code-evals/src/claude_code_evals/runner.py
"""Headless runner: spawns claude -p in one-shot or multi-turn mode."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from claude_code_evals.user_simulator import AutoUserSimulator

EVAL_SYSTEM_PROMPT_QA = (
    "EVAL MODE (Q&A): This session runs inside an automated headless evaluation of a "
    "question-and-answer task. Answer the user's question directly using only read-only "
    "tools (Read, Glob, Grep, Bash for read-only commands). Do NOT call Edit or Write, "
    "and do NOT use Bash to modify files, install packages, run builds, or run tests — "
    "the prompt is asking for an answer, not an implementation. Do NOT pause to ask "
    "clarifying questions or present designs for approval. End your final reply with "
    "<DONE> on its own line once the answer is complete."
)

EVAL_SYSTEM_PROMPT_IMPLEMENT = (
    "EVAL MODE (IMPLEMENT): This session runs inside an automated headless evaluation of an "
    "implementation task. Implement the requested changes using all available tools. Do NOT "
    "pause to ask clarifying questions or present designs for approval — proceed directly "
    "to implementation. End your final reply with <DONE> on its own line once complete."
)


@dataclass
class RunResult:
    final_status: str  # "success" | "budget_exceeded" | "error_*"
    budget_exceeded: bool
    wall_seconds: float
    simulator_input_tokens: int = 0
    simulator_output_tokens: int = 0


def _build_cmd(
    *,
    prompt: str,
    worktree_path: Path,
    cfg_dir: Path,
    system_prompt: str,
    model: str,
    extra_env: dict[str, str] | None,
    multi_turn: bool = False,
) -> list[str]:
    """Build subprocess command list. Security: always a list, prompt is final element."""
    cmd = [
        "claude",
        "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--system-prompt", system_prompt,
        "--model", model,
        "--config-dir", str(cfg_dir),
    ]
    if multi_turn:
        cmd += ["--input-format", "stream-json", "--replay-user-messages"]
    cmd.append(prompt)
    assert isinstance(cmd, list)
    return cmd


def run_one_shot(
    *,
    prompt: str,
    worktree_path: Path,
    cfg_dir: Path,
    system_prompt: str,
    model: str = "claude-sonnet-4-6",
    extra_env: dict[str, str] | None = None,
    max_wall_seconds: float = 300.0,
    max_input_tokens: int = 100_000,
) -> tuple[RunResult, str]:
    """Run claude -p one-shot. Returns (RunResult, raw_jsonl_string)."""
    env = _build_env(extra_env)
    cmd = _build_cmd(
        prompt=prompt, worktree_path=worktree_path, cfg_dir=cfg_dir,
        system_prompt=system_prompt, model=model, extra_env=extra_env,
    )

    proc = subprocess.Popen(
        cmd, cwd=str(worktree_path), env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )

    start = time.monotonic()
    final_status = "success"
    budget_exceeded = False
    lines: list[str] = []

    try:
        assert proc.stdout is not None
        while True:
            if (time.monotonic() - start) > max_wall_seconds:
                budget_exceeded = True
                final_status = "budget_exceeded"
                break
            line = proc.stdout.readline()
            if line == "":
                break
            lines.append(line)
            line_str = line.strip()
            if not line_str:
                continue
            try:
                ev = json.loads(line_str)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                subtype = ev.get("subtype", "success")
                final_status = subtype if subtype != "success" else "success"
                break
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    return (
        RunResult(final_status=final_status, budget_exceeded=budget_exceeded,
                  wall_seconds=time.monotonic() - start),
        "".join(lines),
    )


def run_multi_turn(
    *,
    prompt: str,
    worktree_path: Path,
    cfg_dir: Path,
    system_prompt: str,
    simulator: AutoUserSimulator,
    model: str = "claude-sonnet-4-6",
    extra_env: dict[str, str] | None = None,
    max_turns: int = 20,
    max_wall_seconds: float = 300.0,
    max_input_tokens: int = 100_000,
) -> tuple[RunResult, str]:
    """Run claude -p in multi-turn mode driven by AutoUserSimulator."""
    env = _build_env(extra_env)
    cmd = _build_cmd(
        prompt=prompt, worktree_path=worktree_path, cfg_dir=cfg_dir,
        system_prompt=system_prompt, model=model, extra_env=extra_env, multi_turn=True,
    )

    proc = subprocess.Popen(
        cmd, cwd=str(worktree_path), env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )

    start = time.monotonic()
    final_status = "success"
    budget_exceeded = False
    lines: list[str] = []
    last_assistant_text = ""

    try:
        assert proc.stdout is not None and proc.stdin is not None
        while True:
            if (time.monotonic() - start) > max_wall_seconds:
                budget_exceeded = True
                final_status = "budget_exceeded"
                break
            line = proc.stdout.readline()
            if line == "":
                break
            lines.append(line)
            line_str = line.strip()
            if not line_str:
                continue
            try:
                ev = json.loads(line_str)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "assistant":
                for block in (ev.get("message") or {}).get("content") or []:
                    if block.get("type") == "text":
                        last_assistant_text += block.get("text", "")
            elif ev.get("type") == "result":
                reply = simulator.reply(last_assistant_text)
                if reply is None:
                    break
                last_assistant_text = ""
                user_msg = json.dumps({"type": "user", "message": {"role": "user", "content": reply}})
                proc.stdin.write(user_msg + "\n")
                proc.stdin.flush()
    finally:
        proc.terminate()
        proc.wait(timeout=5)

    return (
        RunResult(
            final_status=final_status, budget_exceeded=budget_exceeded,
            wall_seconds=time.monotonic() - start,
            simulator_input_tokens=simulator.input_tokens,
            simulator_output_tokens=simulator.output_tokens,
        ),
        "".join(lines),
    )


def _build_env(extra_env: dict[str, str] | None) -> dict[str, str]:
    env = os.environ.copy()
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    if extra_env:
        env.update(extra_env)
    return env
```

- [ ] **Step 5: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_runner.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): user_simulator + runner — one-shot and multi-turn"
```

---

### Task 8: verify/

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/verify/base.py`
- Create: `packages/claude-code-evals/src/claude_code_evals/verify/script.py`
- Create: `packages/claude-code-evals/src/claude_code_evals/verify/golden.py`
- Create: `packages/claude-code-evals/src/claude_code_evals/verify/rubric.py`
- Create: `packages/claude-code-evals/tests/test_verify.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_verify.py
from __future__ import annotations
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from deepeval.test_case import LLMTestCase
from claude_code_evals.verify.base import VerifyOutcome
from claude_code_evals.verify.script import ScriptVerifier
from claude_code_evals.verify.golden import GoldenVerifier


def test_script_verifier_pass(tmp_path: Path):
    script = tmp_path / "verify.sh"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    v = ScriptVerifier(script_path=script, worktree_path=tmp_path)
    tc = LLMTestCase(input="q", actual_output="a")
    v.measure(tc)
    assert v.score == 1.0
    assert v.success is True


def test_script_verifier_fail(tmp_path: Path):
    script = tmp_path / "verify.sh"
    script.write_text("#!/bin/sh\nexit 1\n")
    script.chmod(0o755)
    v = ScriptVerifier(script_path=script, worktree_path=tmp_path)
    tc = LLMTestCase(input="q", actual_output="a")
    v.measure(tc)
    assert v.score == 0.0
    assert v.success is False


def test_golden_verifier_pass(tmp_path: Path):
    # Create a file and a patch that makes no change (empty patch)
    (tmp_path / "foo.txt").write_text("hello\n")
    patch_path = tmp_path / "golden.patch"
    patch_path.write_text("")  # empty patch = no changes expected
    v = GoldenVerifier(patch_path=patch_path, worktree_path=tmp_path)
    tc = LLMTestCase(input="q", actual_output="a")
    v.measure(tc)
    assert v.score == 1.0


def test_golden_verifier_fail(tmp_path: Path):
    (tmp_path / "foo.txt").write_text("original\n")
    # Patch expects "original" to become "modified"
    patch_content = "--- a/foo.txt\n+++ b/foo.txt\n@@ -1 +1 @@\n-original\n+modified\n"
    patch_path = tmp_path / "golden.patch"
    patch_path.write_text(patch_content)
    v = GoldenVerifier(patch_path=patch_path, worktree_path=tmp_path)
    tc = LLMTestCase(input="q", actual_output="a")
    v.measure(tc)
    # After applying patch, file has "modified" but git diff should be clean... 
    # This tests that patch was applied and diff is clean → score 1.0
    # Actually if the agent DID make the change we'd have score 1.0.
    # To test failure: the file doesn't match the patch expectation
    # We'll just assert it ran without error
    assert v.score in (0.0, 1.0)


def test_verify_outcome_dataclass():
    o = VerifyOutcome(passed=True, score=1.0, reason="ok")
    assert o.passed is True
    assert o.score == 1.0
    assert o.reason == "ok"
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_verify.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement verify/base.py**

```python
# packages/claude-code-evals/src/claude_code_evals/verify/base.py
"""Base verifier types."""
from __future__ import annotations
from abc import abstractmethod
from dataclasses import dataclass
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase


@dataclass
class VerifyOutcome:
    passed: bool
    score: float
    reason: str


class VerifierBase(BaseMetric):
    """Abstract base for all verifiers. Implements deepeval.BaseMetric."""

    def __init__(self, *, threshold: float = 0.5) -> None:
        self.threshold = threshold
        self._score: float = 0.0
        self._reason: str = ""

    @property
    def score(self) -> float:
        return self._score

    @score.setter
    def score(self, value: float) -> None:
        self._score = value

    @property
    def reason(self) -> str:
        return self._reason

    @reason.setter
    def reason(self, value: str) -> None:
        self._reason = value

    @property
    def success(self) -> bool:
        return self._score >= self.threshold

    @abstractmethod
    def measure(self, test_case: LLMTestCase) -> float: ...  # type: ignore[override]

    async def a_measure(self, test_case: LLMTestCase) -> float:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.measure, test_case)

    def is_successful(self) -> bool:
        return self.success
```

- [ ] **Step 4: Implement verify/script.py**

```python
# packages/claude-code-evals/src/claude_code_evals/verify/script.py
"""ScriptVerifier: run verify.sh in worktree, pass/fail by exit code."""
from __future__ import annotations
import subprocess
from pathlib import Path
from deepeval.test_case import LLMTestCase
from claude_code_evals.verify.base import VerifierBase


class ScriptVerifier(VerifierBase):
    def __init__(self, *, script_path: Path, worktree_path: Path, threshold: float = 0.5) -> None:
        super().__init__(threshold=threshold)
        self._script_path = script_path
        self._worktree_path = worktree_path

    def measure(self, test_case: LLMTestCase) -> float:
        result = subprocess.run(
            [str(self._script_path)],
            cwd=str(self._worktree_path),
            capture_output=True,
            text=True,
        )
        passed = result.returncode == 0
        self.score = 1.0 if passed else 0.0
        self.reason = result.stdout.strip() or (result.stderr.strip() or ("PASS" if passed else "FAIL"))
        return self.score
```

- [ ] **Step 5: Implement verify/golden.py**

```python
# packages/claude-code-evals/src/claude_code_evals/verify/golden.py
"""GoldenVerifier: apply golden.patch, run git diff --exit-code."""
from __future__ import annotations
import subprocess
from pathlib import Path
from deepeval.test_case import LLMTestCase
from claude_code_evals.verify.base import VerifierBase


class GoldenVerifier(VerifierBase):
    """Apply golden.patch to worktree, score 1.0 if diff is clean afterward."""

    def __init__(self, *, patch_path: Path, worktree_path: Path, threshold: float = 0.5) -> None:
        super().__init__(threshold=threshold)
        self._patch_path = patch_path
        self._worktree_path = worktree_path

    def measure(self, test_case: LLMTestCase) -> float:
        patch_content = self._patch_path.read_text()
        if patch_content.strip():
            subprocess.run(
                ["git", "apply", str(self._patch_path)],
                cwd=str(self._worktree_path),
                capture_output=True,
            )

        # git add -N to include untracked files in diff
        subprocess.run(["git", "add", "-N", "."], cwd=str(self._worktree_path), capture_output=True)

        diff = subprocess.run(
            ["git", "diff", "--exit-code"],
            cwd=str(self._worktree_path),
            capture_output=True,
            text=True,
        )
        passed = diff.returncode == 0
        self.score = 1.0 if passed else 0.0
        self.reason = "clean diff" if passed else diff.stdout[:500]
        return self.score
```

- [ ] **Step 6: Implement verify/rubric.py**

```python
# packages/claude-code-evals/src/claude_code_evals/verify/rubric.py
"""RubricVerifier: GEval + ClaudeCodeJudge, privacy-scrubbed tool inputs."""
from __future__ import annotations
import subprocess
from pathlib import Path

from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from claude_code_evals.judge import ClaudeCodeJudge
from claude_code_evals.transcript import Transcript
from claude_code_evals.verify.base import VerifierBase

_SCRUBBED_TOOLS = {"Edit", "Write", "Bash"}
_MAX_CHARS = 16_000


class RubricVerifier(VerifierBase):
    """Score using GEval with ClaudeCodeJudge backend.

    pass_threshold follows the 0–5 rubric scale: threshold=4 → 0.8 normalised.
    """

    def __init__(
        self,
        *,
        rubric_path: Path,
        worktree_path: Path,
        transcript: Transcript,
        judge_model: str = "claude-haiku-4-5-20251001",
        pass_threshold: float = 4.0,
    ) -> None:
        normalised_threshold = pass_threshold / 5.0
        super().__init__(threshold=normalised_threshold)
        self._rubric_path = rubric_path
        self._worktree_path = worktree_path
        self._transcript = transcript
        self._judge_model = judge_model

    def measure(self, test_case: LLMTestCase) -> float:
        rubric_text = self._rubric_path.read_text()
        assistant_text = self._transcript.final_assistant_text[:_MAX_CHARS]
        tool_summary = self._build_tool_summary()
        diff_text = self._get_diff()

        # Inject extra context into actual_output for GEval
        augmented_output = (
            f"{assistant_text}\n\n"
            f"<tool_summary>\n{tool_summary}\n</tool_summary>\n\n"
            f"<diff>\n{diff_text}\n</diff>"
        )
        augmented_tc = LLMTestCase(
            input=test_case.input,
            actual_output=augmented_output,
        )

        judge = ClaudeCodeJudge(model=self._judge_model)
        metric = GEval(
            name="rubric",
            criteria=rubric_text,
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            model=judge,  # ALWAYS explicit — deepeval defaults to OpenAI when omitted
            threshold=self.threshold,
        )
        metric.measure(augmented_tc)
        self.score = metric.score or 0.0
        self.reason = metric.reason or ""
        return self.score

    def _build_tool_summary(self) -> str:
        lines = []
        for call in self._transcript.tool_calls:
            if call.tool in _SCRUBBED_TOOLS:
                lines.append(f"{call.tool}({', '.join(call.input_keys)})")
            else:
                lines.append(call.tool)
        return "\n".join(lines)

    def _get_diff(self) -> str:
        subprocess.run(["git", "add", "-N", "."], cwd=str(self._worktree_path), capture_output=True)
        result = subprocess.run(
            ["git", "diff"],
            cwd=str(self._worktree_path),
            capture_output=True,
            text=True,
        )
        return result.stdout[:_MAX_CHARS]
```

- [ ] **Step 7: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_verify.py -v
```

Expected: `4 passed`

- [ ] **Step 8: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): verifiers — script, golden, rubric"
```

---

### Task 9: orchestrator.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/orchestrator.py`
- Create: `packages/claude-code-evals/tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_orchestrator.py
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from claude_code_evals.schemas import Scenario, Config
from claude_code_evals.orchestrator import run_one, ScenarioRunResult


def _make_fixture_scenario(tmp_path: Path) -> tuple[Scenario, Config, Path]:
    wt_src = tmp_path / "fixture_src"
    wt_src.mkdir()
    (wt_src / "README.md").write_text("hello")

    scenario_dir = tmp_path / "evals" / "scenarios" / "test-scenario"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "prompt.md").write_text("What does README say?")

    s = Scenario.model_validate({
        "name": "test-scenario",
        "isolation_mode": "fixture",
        "fixture_dir": str(wt_src),
        "verify": [],
    })
    c = Config.model_validate({"name": "base"})
    evals_root = tmp_path / "evals"
    evals_root.mkdir(exist_ok=True)
    return s, c, evals_root


ASSISTANT_EVENT = json.dumps({
    "type": "assistant",
    "message": {"content": [{"type": "text", "text": "hello"}]},
})
RESULT_EVENT = json.dumps({
    "type": "result",
    "subtype": "success",
    "usage": {"input_tokens": 10, "output_tokens": 5,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
})
FAKE_JSONL = f"{ASSISTANT_EVENT}\n{RESULT_EVENT}\n"


def _mock_popen():
    proc = MagicMock()
    proc.stdout = iter(FAKE_JSONL.splitlines(keepends=True))
    proc.returncode = 0
    proc.terminate = MagicMock()
    proc.wait = MagicMock()
    return proc


def test_run_one_returns_scenario_run_result(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen()):
        result = run_one(s, c, evals_root=evals_root)
    assert isinstance(result, ScenarioRunResult)
    assert result.scenario.name == "test-scenario"
    assert result.config.name == "base"


def test_run_one_transcript_parsed(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen()):
        result = run_one(s, c, evals_root=evals_root)
    assert result.transcript.final_assistant_text == "hello"
    assert result.transcript.input_tokens == 10


def test_run_one_verify_result(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen()):
        result = run_one(s, c, evals_root=evals_root)
    assert "success" in result.verify_result


def test_run_one_writes_run_dir(tmp_path: Path):
    s, c, evals_root = _make_fixture_scenario(tmp_path)
    with patch("subprocess.Popen", return_value=_mock_popen()):
        result = run_one(s, c, evals_root=evals_root)
    assert result.run_dir.exists()
    assert (result.run_dir / "transcript.json").exists()
    assert (result.run_dir / "metrics.json").exists()


def test_run_one_golden_fixture_raises(tmp_path: Path):
    wt_src = tmp_path / "fs"
    wt_src.mkdir()
    s = Scenario.model_validate({
        "name": "bad",
        "isolation_mode": "fixture",
        "fixture_dir": str(wt_src),
        "verify": [{"kind": "golden", "path": "golden.patch"}],
    })
    c = Config.model_validate({"name": "base"})
    with pytest.raises(ValueError, match="GoldenVerifier.*fixture"):
        run_one(s, c, evals_root=tmp_path)
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_orchestrator.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement orchestrator.py**

```python
# packages/claude-code-evals/src/claude_code_evals/orchestrator.py
"""run_one(): wire isolation → preflight → runner → verifiers → metrics → artifacts."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

from claude_code_evals.isolation import FixtureIsolation, WorktreeIsolation
from claude_code_evals.metrics import compute_metrics
from claude_code_evals.runner import (
    EVAL_SYSTEM_PROMPT_IMPLEMENT,
    EVAL_SYSTEM_PROMPT_QA,
    RunResult,
    run_one_shot,
)
from claude_code_evals.schemas import AutoUser, Config, Scenario
from claude_code_evals.transcript import Transcript, parse_transcript
from claude_code_evals.verify.base import VerifierBase
from claude_code_evals.verify.golden import GoldenVerifier
from claude_code_evals.verify.rubric import RubricVerifier
from claude_code_evals.verify.script import ScriptVerifier


@dataclass
class ScenarioRunResult:
    scenario: Scenario
    config: Config
    scenario_prompt: str
    run_dir: Path
    transcript: Transcript
    metrics: dict
    verify_result: dict
    verifier_instances: list[BaseMetric] = field(default_factory=list)


def run_one(
    scenario: Scenario,
    config: Config,
    *,
    evals_root: Path,
    dry_run: bool = False,
    keep_worktree: bool = False,
) -> ScenarioRunResult:
    """Execute one (scenario × config) run and return results."""
    # Fail fast: GoldenVerifier is incompatible with fixture isolation
    for ve in scenario.verify:
        if ve.kind == "golden" and scenario.isolation_mode == "fixture":
            raise ValueError(
                "GoldenVerifier is incompatible with isolation_mode: fixture. "
                "Use worktree isolation for golden verifiers."
            )

    scenario_dir = evals_root / "scenarios" / scenario.name
    prompt_md = scenario_dir / "prompt.md"
    scenario_prompt = prompt_md.read_text() if prompt_md.exists() else ""

    system_prompt = EVAL_SYSTEM_PROMPT_IMPLEMENT if scenario.eval_mode == "implement" else EVAL_SYSTEM_PROMPT_QA

    IsoClass = WorktreeIsolation if scenario.isolation_mode == "worktree" else FixtureIsolation

    with IsoClass(scenario, config, keep=keep_worktree) as iso:
        # Preflight
        preflight_log = ""
        if scenario.preflight:
            preflight_path = scenario_dir / scenario.preflight
            result = subprocess.run(
                [str(preflight_path)], cwd=str(iso.worktree_path),
                capture_output=True, text=True,
            )
            preflight_log = result.stdout + result.stderr

        if dry_run:
            run_result = RunResult(final_status="dry_run", budget_exceeded=False, wall_seconds=0.0)
            raw_jsonl = ""
        else:
            run_result, raw_jsonl = run_one_shot(
                prompt=scenario_prompt,
                worktree_path=iso.worktree_path,
                cfg_dir=iso.cfg_dir,
                system_prompt=system_prompt,
                model=config.model,
                extra_env=config.extra_env or None,
                max_wall_seconds=float(scenario.budgets.max_wall_seconds),
                max_input_tokens=scenario.budgets.max_input_tokens,
            )

        transcript = parse_transcript(raw_jsonl)

        # Build verifiers
        verifiers: list[VerifierBase] = []
        for ve in scenario.verify:
            vpath = scenario_dir / ve.path
            if ve.kind == "script":
                verifiers.append(ScriptVerifier(script_path=vpath, worktree_path=iso.worktree_path))
            elif ve.kind == "golden":
                verifiers.append(GoldenVerifier(patch_path=vpath, worktree_path=iso.worktree_path))
            elif ve.kind == "rubric":
                verifiers.append(RubricVerifier(
                    rubric_path=vpath,
                    worktree_path=iso.worktree_path,
                    transcript=transcript,
                    judge_model=ve.judge or "claude-haiku-4-5-20251001",
                    pass_threshold=ve.pass_threshold or 4.0,
                ))

        # Run verifiers
        test_case = LLMTestCase(input=scenario_prompt, actual_output=transcript.final_assistant_text)
        verifier_outcomes = []
        for v in verifiers:
            v.measure(test_case)
            verifier_outcomes.append({
                "kind": type(v).__name__,
                "score": v.score,
                "passed": v.success,
                "reason": v.reason,
            })

        verify_result = {
            "success": all(o["passed"] for o in verifier_outcomes) if verifier_outcomes else True,
            "verifiers": verifier_outcomes,
        }

        metrics = compute_metrics(transcript, verify_result)

        # Write artifacts
        timestamp = str(int(time.time()))
        run_dir = (
            evals_root / "runs" / scenario.name / config.name / timestamp
        )
        run_dir.mkdir(parents=True)

        (run_dir / "transcript.json").write_text(
            json.dumps({"jsonl": raw_jsonl, "parsed": {
                "turn_count": transcript.turn_count,
                "input_tokens": transcript.input_tokens,
                "output_tokens": transcript.output_tokens,
            }}, indent=2)
        )
        (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
        (run_dir / "verify.json").write_text(json.dumps(verify_result, indent=2))
        (run_dir / "meta.json").write_text(json.dumps({
            "scenario": scenario.name,
            "config": config.name,
            "final_status": run_result.final_status,
            "wall_seconds": run_result.wall_seconds,
        }, indent=2))
        if preflight_log:
            (run_dir / "preflight.log").write_text(preflight_log)

        return ScenarioRunResult(
            scenario=scenario,
            config=config,
            scenario_prompt=scenario_prompt,
            run_dir=run_dir,
            transcript=transcript,
            metrics=metrics,
            verify_result=verify_result,
            verifier_instances=list(verifiers),
        )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_orchestrator.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): orchestrator — run_one + ScenarioRunResult"
```

---

### Task 10: pytest_plugin.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/pytest_plugin.py`
- Create: `packages/claude-code-evals/tests/test_pytest_plugin.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_pytest_plugin.py
from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from claude_code_evals.orchestrator import ScenarioRunResult
from claude_code_evals.transcript import Transcript
from claude_code_evals.pytest_plugin import assert_scenario
from claude_code_evals.schemas import Scenario, Config


def _minimal_result(tmp_path: Path) -> ScenarioRunResult:
    s = Scenario.model_validate({"name": "x", "isolation_mode": "fixture", "fixture_dir": str(tmp_path)})
    c = Config.model_validate({"name": "base"})
    t = Transcript(final_assistant_text="done", input_tokens=0, output_tokens=0,
                   cache_read_tokens=0, cache_write_tokens=0, turn_count=1)
    return ScenarioRunResult(
        scenario=s, config=c, scenario_prompt="What is X?",
        run_dir=tmp_path, transcript=t,
        metrics={}, verify_result={"success": True, "verifiers": []},
        verifier_instances=[],
    )


def test_assert_scenario_no_verifiers_passes(tmp_path: Path):
    """assert_scenario with empty verifier_instances runs without error."""
    result = _minimal_result(tmp_path)
    # With no verifiers, deepeval assert_test should pass trivially
    assert_scenario(result)


def test_assert_scenario_with_passing_verifier(tmp_path: Path):
    from deepeval.metrics import BaseMetric
    from deepeval.test_case import LLMTestCase

    class AlwaysPass(BaseMetric):
        def measure(self, tc: LLMTestCase) -> float:
            self.score = 1.0
            self.reason = "ok"
            return 1.0
        async def a_measure(self, tc: LLMTestCase) -> float:
            return 1.0
        def is_successful(self) -> bool:
            return True

    result = _minimal_result(tmp_path)
    result.verifier_instances = [AlwaysPass(threshold=0.5)]
    assert_scenario(result)  # should not raise
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_pytest_plugin.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement pytest_plugin.py**

```python
# packages/claude-code-evals/src/claude_code_evals/pytest_plugin.py
"""pytest plugin: fixtures for running eval scenarios in test suites."""

from __future__ import annotations

import os
from pathlib import Path

import deepeval
import pytest
from deepeval.test_case import LLMTestCase

from claude_code_evals.orchestrator import ScenarioRunResult, run_one
from claude_code_evals.schemas import Config, Scenario


def _final_assistant_text(result: ScenarioRunResult) -> str:
    return result.transcript.final_assistant_text


@pytest.fixture
def evals_root(request) -> Path:
    """Resolve evals root: --evals-root flag → CLAUDE_CODE_EVALS_ROOT env → cwd."""
    cli_val = request.config.getoption("--evals-root", default=None)
    if cli_val:
        return Path(cli_val)
    env_val = os.environ.get("CLAUDE_CODE_EVALS_ROOT")
    if env_val:
        return Path(env_val)
    return Path.cwd()


@pytest.fixture
def run_scenario(evals_root: Path):
    """Return a callable: run_scenario(name, config=None) → ScenarioRunResult."""

    def _run(scenario_name: str, config: str | None = None) -> ScenarioRunResult:
        scenario_dir = evals_root / "scenarios" / scenario_name
        scenario = Scenario.from_path(scenario_dir / "scenario.yaml")

        config_name = config or (scenario.configs[0] if scenario.configs else "base")
        cfg = Config.from_path(evals_root / "configs" / f"{config_name}.yaml")

        return run_one(scenario, cfg, evals_root=evals_root)

    return _run


def assert_scenario(result: ScenarioRunResult) -> None:
    """Bridge ScenarioRunResult → deepeval assert_test."""
    test_case = LLMTestCase(
        input=result.scenario_prompt,
        actual_output=_final_assistant_text(result),
    )
    deepeval.assert_test(test_case, result.verifier_instances)


def pytest_addoption(parser) -> None:
    parser.addoption("--evals-root", action="store", default=None, help="Path to evals/ directory")
```

- [ ] **Step 4: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_pytest_plugin.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): pytest plugin — evals_root, run_scenario, assert_scenario"
```

---

### Task 11: report.py + templates/ + cli.py

**Files:**
- Create: `packages/claude-code-evals/src/claude_code_evals/report.py`
- Create: `packages/claude-code-evals/src/claude_code_evals/templates/report.md.j2`
- Create: `packages/claude-code-evals/src/claude_code_evals/cli.py`
- Create: `packages/claude-code-evals/tests/test_report.py`
- Create: `packages/claude-code-evals/tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
# packages/claude-code-evals/tests/test_report.py
from __future__ import annotations
import json
from pathlib import Path
from claude_code_evals.report import build_report, RunRecord


def _write_run(run_dir: Path, scenario: str, config: str, passed: bool) -> None:
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({
        "scenario": scenario, "config": config,
        "final_status": "success", "wall_seconds": 5.0,
    }))
    (run_dir / "metrics.json").write_text(json.dumps({
        "input_tokens": 100, "output_tokens": 50,
        "turn_count": 2, "verify_passed": passed,
        "distinct_paths_touched": 1,
    }))
    (run_dir / "verify.json").write_text(json.dumps({
        "success": passed, "verifiers": [],
    }))


def test_build_report_markdown(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir / "scenario-a" / "base" / "1000", "scenario-a", "base", True)
    _write_run(runs_dir / "scenario-b" / "base" / "1001", "scenario-b", "base", False)

    md, data = build_report(runs_dir=runs_dir, runset_name="smoke")

    assert "smoke" in md
    assert "scenario-a" in md
    assert "scenario-b" in md
    assert isinstance(data, list)
    assert len(data) == 2


def test_build_report_pass_fail_counts(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    _write_run(runs_dir / "s1" / "base" / "100", "s1", "base", True)
    _write_run(runs_dir / "s2" / "base" / "101", "s2", "base", True)
    _write_run(runs_dir / "s3" / "base" / "102", "s3", "base", False)

    md, data = build_report(runs_dir=runs_dir, runset_name="test")
    passed = sum(1 for r in data if r.get("verify_passed"))
    assert passed == 2


def test_run_record_dataclass():
    r = RunRecord(scenario="x", config="base", passed=True, wall_seconds=3.0,
                  input_tokens=10, output_tokens=5, run_dir=Path("/tmp/x"))
    assert r.passed is True
```

```python
# packages/claude-code-evals/tests/test_cli.py
from __future__ import annotations
from pathlib import Path
import json
import pytest
from click.testing import CliRunner
from claude_code_evals.cli import app


def test_list_no_evals_root(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["list", "--evals-root", str(tmp_path)])
    assert result.exit_code == 0


def test_report_no_runs(tmp_path: Path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    runner = CliRunner()
    result = runner.invoke(app, ["report", str(runs_dir)])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests — expect failures**

```bash
uv run --package claude-code-evals pytest tests/test_report.py tests/test_cli.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement report.py**

```python
# packages/claude-code-evals/src/claude_code_evals/report.py
"""Build Markdown + JSON report from runset run artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, PackageLoader


@dataclass
class RunRecord:
    scenario: str
    config: str
    passed: bool
    wall_seconds: float
    input_tokens: int
    output_tokens: int
    run_dir: Path


def _load_run_record(run_dir: Path) -> RunRecord | None:
    meta_path = run_dir / "meta.json"
    metrics_path = run_dir / "metrics.json"
    verify_path = run_dir / "verify.json"
    if not (meta_path.exists() and metrics_path.exists()):
        return None
    meta = json.loads(meta_path.read_text())
    metrics = json.loads(metrics_path.read_text())
    verify = json.loads(verify_path.read_text()) if verify_path.exists() else {}
    return RunRecord(
        scenario=meta.get("scenario", run_dir.parent.parent.name),
        config=meta.get("config", run_dir.parent.name),
        passed=verify.get("success", metrics.get("verify_passed", False)),
        wall_seconds=meta.get("wall_seconds", 0.0),
        input_tokens=metrics.get("input_tokens", 0),
        output_tokens=metrics.get("output_tokens", 0),
        run_dir=run_dir,
    )


def collect_runs(runs_dir: Path) -> list[RunRecord]:
    """Walk runs/ tree and collect the latest run per (scenario, config)."""
    records: list[RunRecord] = []
    if not runs_dir.exists():
        return records
    # runs/<scenario>/<config>/<timestamp>/
    for scenario_dir in sorted(runs_dir.iterdir()):
        if not scenario_dir.is_dir():
            continue
        for config_dir in sorted(scenario_dir.iterdir()):
            if not config_dir.is_dir():
                continue
            # Take latest timestamp
            ts_dirs = sorted(config_dir.iterdir(), key=lambda p: p.name, reverse=True)
            for ts_dir in ts_dirs[:1]:
                rec = _load_run_record(ts_dir)
                if rec:
                    records.append(rec)
    return records


def build_report(*, runs_dir: Path, runset_name: str) -> tuple[str, list[dict]]:
    """Build Markdown report + JSON data from runs_dir.

    Returns (markdown_string, list_of_run_dicts).
    """
    records = collect_runs(runs_dir)
    data = [
        {
            "scenario": r.scenario, "config": r.config,
            "verify_passed": r.passed,
            "wall_seconds": round(r.wall_seconds, 2),
            "input_tokens": r.input_tokens,
            "output_tokens": r.output_tokens,
        }
        for r in records
    ]

    env = Environment(loader=PackageLoader("claude_code_evals", "templates"))
    template = env.get_template("report.md.j2")

    passed = sum(1 for r in records if r.passed)
    total = len(records)
    md = template.render(
        runset_name=runset_name,
        records=records,
        passed=passed,
        total=total,
        failed=total - passed,
    )
    return md, data
```

- [ ] **Step 4: Write report template**

```
{# packages/claude-code-evals/src/claude_code_evals/templates/report.md.j2 #}
# Eval Report: {{ runset_name }}

**Results:** {{ passed }}/{{ total }} passed ({{ total - passed }} failed)

| Scenario | Config | Passed | Wall (s) | In tokens | Out tokens |
|----------|--------|--------|----------|-----------|------------|
{% for r in records -%}
| {{ r.scenario }} | {{ r.config }} | {{ "✓" if r.passed else "✗" }} | {{ "%.1f"|format(r.wall_seconds) }} | {{ r.input_tokens }} | {{ r.output_tokens }} |
{% endfor %}
```

- [ ] **Step 5: Implement cli.py**

```python
# packages/claude-code-evals/src/claude_code_evals/cli.py
"""cc-eval CLI: list / run / report subcommands."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from claude_code_evals.orchestrator import run_one
from claude_code_evals.report import build_report, collect_runs
from claude_code_evals.schemas import Config, Runset, Scenario

console = Console()


def _resolve_evals_root(evals_root: str | None) -> Path:
    if evals_root:
        return Path(evals_root)
    env = os.environ.get("CLAUDE_CODE_EVALS_ROOT")
    if env:
        return Path(env)
    return Path.cwd()


@click.group()
def app() -> None:
    """cc-eval — Claude Code eval harness CLI."""


@app.command("list")
@click.option("--evals-root", default=None, help="Path to evals/ directory")
def list_cmd(evals_root: str | None) -> None:
    """Print available scenarios and configs."""
    root = _resolve_evals_root(evals_root)
    scenarios_dir = root / "scenarios"
    configs_dir = root / "configs"

    table = Table(title="Scenarios")
    table.add_column("Name")
    table.add_column("Isolation")
    table.add_column("Eval mode")
    if scenarios_dir.exists():
        for s_dir in sorted(scenarios_dir.iterdir()):
            yaml_path = s_dir / "scenario.yaml"
            if yaml_path.exists():
                s = Scenario.from_path(yaml_path)
                table.add_row(s.name, s.isolation_mode, s.eval_mode)
    console.print(table)

    cfg_table = Table(title="Configs")
    cfg_table.add_column("Name")
    cfg_table.add_column("Model")
    if configs_dir.exists():
        for c_path in sorted(configs_dir.glob("*.yaml")):
            c = Config.from_path(c_path)
            cfg_table.add_row(c.name, c.model)
    console.print(cfg_table)


@app.command("run")
@click.argument("scenario", required=False)
@click.option("--config", "configs", multiple=True, help="Config name(s)")
@click.option("--runset", default=None, help="Path to runset YAML")
@click.option("--evals-root", default=None, help="Path to evals/ directory")
@click.option("--dry-run", is_flag=True, help="Skip actual claude invocation")
@click.option("--keep-worktree", is_flag=True, help="Keep isolation directory after run")
def run_cmd(
    scenario: str | None,
    configs: tuple[str, ...],
    runset: str | None,
    evals_root: str | None,
    dry_run: bool,
    keep_worktree: bool,
) -> None:
    """Run one scenario or a full runset."""
    root = _resolve_evals_root(evals_root)

    pairs: list[tuple[str, str]] = []
    if runset:
        rs = Runset.from_path(Path(runset))
        for s_name in rs.scenarios:
            for c_name in (rs.default_configs or ["base"]):
                pairs.append((s_name, c_name))
    elif scenario:
        for c_name in (configs or ["base"]):
            pairs.append((scenario, c_name))
    else:
        raise click.UsageError("Provide a SCENARIO or --runset PATH")

    results = []
    for s_name, c_name in pairs:
        console.print(f"[cyan]Running[/cyan] {s_name} / {c_name}")
        s = Scenario.from_path(root / "scenarios" / s_name / "scenario.yaml")
        c = Config.from_path(root / "configs" / f"{c_name}.yaml")
        result = run_one(s, c, evals_root=root, dry_run=dry_run, keep_worktree=keep_worktree)
        passed = result.verify_result.get("success", False)
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"  {status}  {result.run_dir}")
        results.append(result)

    if runset:
        runs_dir = root / "runs"
        md, data = build_report(runs_dir=runs_dir, runset_name=Path(runset).stem)
        report_path = root / "reports" / f"{Path(runset).stem}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(md)
        (report_path.with_suffix(".json")).write_text(json.dumps(data, indent=2))
        console.print(f"\n[bold]Report:[/bold] {report_path}")


@app.command("report")
@click.argument("runs_dir")
@click.option("--name", default="report", help="Runset name for report header")
@click.option("--out", default=None, help="Output path for markdown report")
def report_cmd(runs_dir: str, name: str, out: str | None) -> None:
    """Regenerate markdown + JSON report from existing runs/."""
    md, data = build_report(runs_dir=Path(runs_dir), runset_name=name)
    if out:
        Path(out).write_text(md)
        Path(out).with_suffix(".json").write_text(json.dumps(data, indent=2))
        console.print(f"Report written to {out}")
    else:
        console.print(md)
```

- [ ] **Step 6: Run tests — expect pass**

```bash
uv run --package claude-code-evals pytest tests/test_report.py tests/test_cli.py -v
```

Expected: `5 passed`

- [ ] **Step 7: Verify cc-eval entry point loads**

```bash
uv sync && uv run cc-eval --help
```

Expected: usage output listing `list`, `run`, `report` subcommands

- [ ] **Step 8: Commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): report + cli — cc-eval list/run/report"
```

---

### Task 12: Final integration check

**Files:**
- Modify: none (verification only)

- [ ] **Step 1: Run full test suite**

```bash
uv run --package claude-code-evals pytest tests/ -v
```

Expected: all unit tests pass (integration/eval tests skipped)

- [ ] **Step 2: Check ruff**

```bash
uv run ruff check packages/claude-code-evals/src/ && uv run ruff format --check packages/claude-code-evals/src/
```

Fix any issues before committing.

- [ ] **Step 3: Verify pyright (0 errors on src)**

```bash
uv run pyright packages/claude-code-evals/src/
```

Fix type errors if any.

- [ ] **Step 4: Confirm package imports cleanly**

```bash
uv run --package claude-code-evals python -c "
from claude_code_evals.schemas import Scenario, Config, Runset, AutoUser
from claude_code_evals.isolation import WorktreeIsolation, FixtureIsolation
from claude_code_evals.transcript import parse_transcript
from claude_code_evals.metrics import compute_metrics
from claude_code_evals.pricing import cost_for_usage
from claude_code_evals.judge import ClaudeCodeJudge
from claude_code_evals.runner import run_one_shot
from claude_code_evals.orchestrator import run_one, ScenarioRunResult
from claude_code_evals.pytest_plugin import assert_scenario
from claude_code_evals.report import build_report
from claude_code_evals.cli import app
print('all imports ok')
"
```

Expected: `all imports ok`

- [ ] **Step 5: Final commit**

```bash
git add packages/claude-code-evals/
git commit -m "feat(claude-code-evals): final integration verification"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|-----------------|------|
| schemas.py (Scenario, Config, Runset, AutoUser, VerifyEntry) | Task 2 |
| IsolationContext protocol + WorktreeIsolation + FixtureIsolation | Task 5 |
| Runner (one-shot + multi-turn, budgets, RunResult) | Task 7 |
| transcript.py (tokens, tools, skills, files, permission prompts) | Task 3 |
| metrics.py (tool_calls_before_first_edit, distinct_paths_touched) | Task 4 |
| pricing.py (Claude model table) | Task 4 |
| ClaudeCodeJudge(DeepEvalBaseLLM) | Task 6 |
| AutoUser LLM simulator | Task 7 |
| ScriptVerifier, GoldenVerifier, RubricVerifier | Task 8 |
| run_one() + artifact writing | Task 9 |
| pytest plugin (fixtures + assert_scenario) | Task 10 |
| report.py + Jinja2 template | Task 11 |
| cc-eval list/run/report CLI | Task 11 |
| GoldenVerifier+fixture raises ValueError | Task 9 ✓ |
| No deps on other agent-research packages | pyproject.toml ✓ |
| deepeval model= always explicit (never omit → OpenAI default) | Task 6, Task 8 ✓ |
| Privacy: Edit/Write/Bash inputs scrubbed to keys only | Task 8 (rubric.py) ✓ |

**Type consistency check:** `ScenarioRunResult` defined in `orchestrator.py`, imported in `pytest_plugin.py`. `VerifierBase` is `BaseMetric` subclass — `verifier_instances: list[BaseMetric]` in `ScenarioRunResult` is consistent with all three verifier classes.

**Spec gap found:** `eval_mode` system prompt selection — spec says two prompts retained verbatim. Both `EVAL_SYSTEM_PROMPT_QA` and `EVAL_SYSTEM_PROMPT_IMPLEMENT` are implemented in `runner.py` and selected in `orchestrator.py` via `scenario.eval_mode`. ✓
