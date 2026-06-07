# claude-code-evals — Design Spec

**Date:** 2026-06-05  
**Status:** Draft  
**Location:** `packages/claude-code-evals/`

---

## Overview

A generic, installable Python library for evaluating Claude Code behavior across different plugin configurations. Consuming projects define scenario data in their own `evals/` directory; the package provides all harness machinery. deepeval is the metric and test-runner integration layer; pytest-evals gates expensive runs behind an env var.

Primary use cases: skill loading verification, tool execution pattern observation, plugin behavior comparison (wiki use, wiki ingestion, future plugins), and any scenario that can be expressed as "run Claude Code headless, observe what happened, verify correctness."

---

## Package Layout

```
packages/claude-code-evals/
  src/claude_code_evals/
    schemas.py          # Pydantic models: Scenario, Config, Runset, AutoUser, VerifyEntry
    isolation.py        # IsolationContext protocol + WorktreeIsolation + FixtureIsolation
    runner.py           # Headless runner — spawns claude -p stream-json, one-shot + multi-turn
    transcript.py       # Parse stream-json JSONL → Transcript (tokens, tools, skills, files)
    metrics.py          # Compute flat metrics dict from Transcript + verify result
    pricing.py          # Token cost lookup by model name
    judge.py            # ClaudeCodeJudge(DeepEvalBaseLLM) — claude -p as LLM backend
    user_simulator.py   # AutoUser LLM-driven reply simulator
    orchestrator.py     # run_one(): wire isolation → preflight → runner → verifiers → metrics
    verify/
      base.py           # VerifyOutcome dataclass; abstract VerifierBase
      script.py         # ScriptVerifier(BaseMetric)
      golden.py         # GoldenVerifier(BaseMetric)
      rubric.py         # RubricVerifier(BaseMetric) wrapping GEval + ClaudeCodeJudge
    pytest_plugin.py    # pytest fixtures + assert_scenario helper
    report.py           # Markdown + JSON report from runset results
    cli.py              # cc-eval list/run/report — thin wrapper over pytest + report
    templates/
      report.md.j2
  tests/
  pyproject.toml
```

---

## Schemas

All schemas are Pydantic v2 models with `extra="forbid"`, loaded from YAML via `Model.from_path()`.

### Scenario

```yaml
name: smoke-readme
description: "Agent reads README and answers a question"
isolation_mode: worktree         # "worktree" | "fixture"
target_repo: ~/Personal/my-repo  # required for worktree mode
baseline_sha: abc1234            # required for worktree mode; min 7 chars
fixture_dir: fixtures/           # required for fixture mode; relative to scenario dir
configs: [base, with-wiki]
mode: headless                   # "headless" | "interactive"
eval_mode: qa                    # "qa" | "implement"
auto_user: auto_user.yaml        # optional; headless multi-turn only
preflight: preflight.sh          # optional; runs before agent
verify:
  - kind: script
    path: verify.sh
  - kind: rubric
    path: rubric.md
    judge: claude-haiku-4-5-20251001
    pass_threshold: 4
metrics:
  tool_shape: true
  judge_qualitative: false
budgets:
  max_turns: 20
  max_input_tokens: 100000
  max_wall_seconds: 300
```

Pydantic model validators enforce:
- `isolation_mode: worktree` requires `target_repo` + `baseline_sha`
- `isolation_mode: fixture` requires `fixture_dir`
- `mode: interactive` forbids `auto_user`

### Config

```yaml
name: with-wiki
plugin_dirs:
  - /absolute/path/to/lattice-wiki          # absolute
  - ../../plugins/lattice-workflows          # relative to evals_root
model: claude-sonnet-4-6
temperature: 0.0
extra_env:
  LATTICE_WIKI_ROOT: /absolute/path/to/plugin  # project-specific env injection
extra_settings:
  hooks: {}
```

`plugin_dirs` replaces `lattice-evals`'s `plugins: list[str]` (plugin names resolved against a hardcoded parent). Relative paths are resolved against `evals_root` at load time.

### Runset

```yaml
name: smoke
scenarios: [smoke-readme, add-webhook]
default_configs: [base, with-wiki]
```

---

## Isolation

Two concrete implementations behind a shared `IsolationContext` protocol. Both expose `worktree_path: Path`, `cfg_dir: Path`, `oauth_token: str | None`, and `meta_path: Path` as properties, and work as context managers.

### WorktreeIsolation

Mirrors the current `lattice-evals` implementation:
1. `git worktree add --detach <tmp>/wt <baseline_sha>` on `target_repo`
2. Create `<tmp>/cfg/` as `CLAUDE_CONFIG_DIR`
3. Symlink each `plugin_dir` into `cfg/plugins/`
4. Write `installed_plugins.json` + `known_marketplaces.json` (Claude Code registry format)
5. Write `settings.json` with `{"permissions": {"defaultMode": "acceptEdits"}, **extra_settings}`
6. Write `meta.json` with config/scenario/SHA metadata
7. On exit: `git worktree remove --force`, `shutil.rmtree(tmp)` unless `keep=True`

### FixtureIsolation

1. `shutil.copytree(fixture_dir, <tmp>/wt)`
2. Same `cfg/` setup as WorktreeIsolation
3. On exit: `shutil.rmtree(tmp)` unless `keep=True`

`GoldenVerifier` is incompatible with `isolation_mode: fixture`. `run_one()` checks for this combination at scenario load time and raises a clear `ValueError` before constructing any verifier — fail fast rather than at mid-run verifier construction when `isolation_mode` is no longer visible.

`run_one()` in `orchestrator.py` constructs the correct isolation impl based on `scenario.isolation_mode`. It accepts either via the protocol — it has no knowledge of which mode it's in beyond construction.

---

## Runner & Transcript

### Runner (`runner.py`)

Extracted from `lattice-evals` with Lattice-specific code removed:

- Two eval-mode system prompts retained verbatim (`implement` and `qa`) — generic enough to be reused
- `extra_env` from `Config` passed directly; no hardcoded env injection
- One-shot mode: prompt as final argv, `stdin=DEVNULL`, runs to first `result` event
- Multi-turn mode: `--input-format stream-json --replay-user-messages`, `stdin=PIPE`, `AutoUser` drives replies
- Budget enforcement: `max_turns`, `max_input_tokens`, `max_wall_seconds`
- Returns `RunResult` dataclass: `final_status`, `budget_exceeded`, `wall_seconds`, simulator token counts

### Transcript (`transcript.py`)

Unchanged from `lattice-evals` — already fully generic. Parses Claude Code stream-json JSONL into:
- Token usage (input, output, cache read/write)
- Assistant turn count
- Per-tool call counts + ordered tool call events
- Files read / edited / written
- Subagent dispatches, skill invocations, hook-loaded skills
- Permission prompt count

### Metrics (`metrics.py`) and Pricing (`pricing.py`)

Unchanged from `lattice-evals`. Metrics computes a flat dict from `Transcript` + verify result including `tool_calls_before_first_edit` and `distinct_paths_touched`. Pricing holds the hardcoded Claude model cost table.

---

## Verifiers

All three verifiers implement `deepeval.BaseMetric`. The `measure(test_case)` method runs the existing verification logic and sets `self.score` (0.0 or 1.0 for script/golden; float for rubric) and `self.reason`.

### ScriptVerifier

Runs `verify.sh` in the worktree. Pass/fail by exit code. `self.score = 1.0 if passed else 0.0`.

### GoldenVerifier

Applies `golden.patch` to the worktree and runs `git diff --exit-code`. `self.score = 1.0 if clean else 0.0`. Incompatible with `isolation_mode: fixture` — `run_one()` rejects this combination before any verifier is constructed.

### RubricVerifier

Wraps `GEval` with `ClaudeCodeJudge`. The judge prompt includes: rubric text, agent's final assistant message (all text blocks concatenated, capped at 16k chars), redacted tool-call summary (tool name + safe input keys only — no content), and git diff (capped at 16k chars, `git add -N` first to include untracked files).

`self.score` is GEval's raw 0–1 float. `self.threshold` defaults to `pass_threshold / 5` to normalise the 0–5 scale from `lattice-evals` rubrics (e.g. threshold 4 → 0.8). `self.reason` is GEval's reasoning string.

The privacy boundary from `lattice-evals` is preserved: `Edit`, `Write`, `Bash` inputs are scrubbed to identifier-only keys before being sent to the judge.

---

## Judge

`ClaudeCodeJudge(DeepEvalBaseLLM)` in `judge.py`:

```python
class ClaudeCodeJudge(DeepEvalBaseLLM):
    def __init__(self, model: str = "claude-haiku-4-5-20251001"):
        self.model = model

    def generate(self, prompt: str) -> str:
        result = _run_claude_judge(prompt, model=self.model)
        return result.stdout

    async def a_generate(self, prompt: str) -> str:
        # asyncio.to_thread wrapper around generate()

    def get_model_name(self) -> str:
        return self.model
```

`_run_claude_judge()` is the existing `run_judge()` logic from `lattice-evals`: spawns `claude -p --model <model> --output-format stream-json`, parses stream-json, returns text + token counts.

`RubricVerifier` constructs `ClaudeCodeJudge` and always passes it as `model=` to `GEval` — never omitted (mirrors the `eval-harness` T-06-18 rule: deepeval defaults to OpenAI GPT when `model=` is absent).

---

## pytest Integration

`pytest_plugin.py` is registered as a pytest plugin via `entry_points`:

```toml
[project.entry-points."pytest11"]
claude-code-evals = "claude_code_evals.pytest_plugin"
```

### Fixtures

```python
@pytest.fixture
def evals_root(request) -> Path:
    # resolves: --evals-root CLI flag → CLAUDE_CODE_EVALS_ROOT env → cwd

@pytest.fixture
def run_scenario(evals_root):
    # returns a callable: run_scenario(name, config=None) → ScenarioResult
```

### ScenarioResult

```python
@dataclass
class ScenarioResult:
    scenario: Scenario
    config: Config
    scenario_prompt: str       # contents of prompt.md — used as LLMTestCase.input
    run_dir: Path
    transcript: Transcript
    metrics: dict
    verify_result: dict        # {success: bool, verifiers: [...]}
    verifier_instances: list[BaseMetric]   # populated by run_scenario()
```

### assert_scenario

```python
def assert_scenario(result: ScenarioResult) -> None:
    """Bridge ScenarioResult → deepeval assert_test."""
    test_case = LLMTestCase(
        input=result.scenario_prompt,
        actual_output=_final_assistant_text(result.transcript),
    )
    deepeval.assert_test(test_case, result.verifier_instances)
```

### Consuming project test file

```python
@pytest.mark.eval
@pytest.mark.parametrize("scenario_name,config_name", [
    ("smoke-readme", "base"),
    ("smoke-readme", "with-wiki"),
    ("add-webhook",  "base"),
])
def test_scenario(scenario_name, config_name, run_scenario):
    result = run_scenario(scenario_name, config=config_name)
    assert_scenario(result)
```

Run gated by `CLAUDE_CODE_RUN_EVALS=1` via `pytest-evals` marker configuration in the consuming project's `pyproject.toml`.

---

## CLI

`cc-eval` entry point, three subcommands:

```
cc-eval list [--evals-root PATH]
    # prints scenarios + configs

cc-eval run <scenario> [--config NAMES] [--dry-run] [--keep-worktree]
cc-eval run --runset PATH [--dry-run]
    # calls run_one() directly (same as lattice-eval run today)
    # builds report after runset completes

cc-eval report <runset_path>
    # regenerates markdown+JSON from existing runs/
```

The CLI calls the orchestrator directly; it does not wrap pytest. pytest + pytest-evals is the separate consumer-facing path for users who want test-framework integration and deepeval reporting. Both paths call the same `run_one()` core.

`--evals-root` / `CLAUDE_CODE_EVALS_ROOT` / cwd resolution is identical to `lattice-evals`.

---

## Data Directory (Consuming Project)

```
evals/
  scenarios/<name>/
    scenario.yaml
    prompt.md
    verify.sh           # script verifier
    golden.patch        # golden verifier
    rubric.md           # rubric verifier
    auto_user.yaml      # optional multi-turn AutoUser config
    fixtures/           # optional, for isolation_mode: fixture
  configs/
    base.yaml
    with-plugin-x.yaml
  runsets/
    smoke.yaml
  runs/                 # gitignored or committed; 3-run retention per config
  reports/              # committed markdown+JSON reports
```

Run artifacts stored at `runs/<repo-sha>/<scenario>/<config>/<timestamp>/`:
- `transcript.json`, `stdout.log`, `diff.patch`
- `verify.json`, `metrics.json`, `meta.json`
- `preflight.log` (if preflight ran)
- `claude_config_dir/` snapshot (retained for last 3 runs per config)

---

## Dependencies

```toml
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
```

No dependencies on other `agent-research` packages. No `boto3`, `aiobotocore`, or `langchain`.

Added to root `pyproject.toml`:
```toml
[tool.uv.workspace]
members = [..., "packages/claude-code-evals"]
```

---

## What Is NOT Included

- Qualitative judge pass (`qualitative.py` from `lattice-evals`) — omitted; rubric verifier via GEval covers this use case with deepeval integration
- `lattice-eval verify` re-verify command — stubbed in `lattice-evals`; not included here
- Variance / multi-trial runs — single trial per (scenario × config); a future concern
- Bedrock judge backends — only `claude -p`; add via `DeepEvalBaseLLM` subclass in consuming project if needed
