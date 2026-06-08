# Three-Arm Wiki-Context Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a three-arm evaluation framework (`base`, `injected`, `plugin`) to measure how the Graph Wiki improves Claude Code's behavior, with per-scenario verdicts and arm-comparison reporting.

**Architecture:** Extend `claude-code-evals` schemas to declare wiki-delivery mode per scenario + discriminator type. Wire `runner.py` to inject wiki text or pass workspace paths based on arm. Compute verdicts by comparing metrics across arms. Report as a scenario × arm matrix with per-scenario verdict (correctness, efficiency, or impossible-without-wiki).

**Tech Stack:** Python (Pydantic schemas, pytest), YAML (scenario configs), Jinja2 (report templates), existing `claude` CLI harness.

**Assumption:** Step zero (freeze the mono-repo wiki) is **already complete**. The frozen wiki exists at `~/Personal/graph-wiki/mono-repo-eval-551f7ed8/` with tag `eval-baseline-551f7ed8`.

---

## Task 1: Add `discriminator` block and `inject` list to `Scenario` schema

**Files:**
- Modify: `packages/claude-code-evals/src/schemas.py` (Scenario dataclass)
- Test: `packages/claude-code-evals/tests/unit/test_schemas.py`

- [ ] **Step 1: Read current Scenario schema**

Run: `grep -A 30 "class Scenario" packages/claude-code-evals/src/schemas.py`

Expected: Current Scenario has fields like `name`, `prompt`, `rubric`, `config`, `expected_pass_rate`, etc.

- [ ] **Step 2: Write test for discriminator block with correctness-gated type**

Add to `packages/claude-code-evals/tests/unit/test_schemas.py`:

```python
def test_scenario_with_correctness_gated_discriminator():
    """Correctness-gated scenarios have only a type."""
    data = {
        "name": "wiki-design-tokens",
        "prompt": "path/to/prompt.md",
        "rubric": "path/to/rubric.md",
        "discriminator": {
            "type": "correctness-gated"
        }
    }
    scenario = Scenario.from_yaml_dict(data)
    assert scenario.discriminator.type == "correctness-gated"
    assert scenario.discriminator.metric is None
    assert scenario.discriminator.min_improvement_pct is None
```

- [ ] **Step 3: Write test for discriminator block with efficiency-gated type**

Add to same test file:

```python
def test_scenario_with_efficiency_gated_discriminator():
    """Efficiency-gated scenarios declare metric and min_improvement_pct."""
    data = {
        "name": "wiki-api-client",
        "prompt": "path/to/prompt.md",
        "rubric": "path/to/rubric.md",
        "discriminator": {
            "type": "efficiency-gated",
            "metric": "files_read_count",
            "min_improvement_pct": 40
        }
    }
    scenario = Scenario.from_yaml_dict(data)
    assert scenario.discriminator.type == "efficiency-gated"
    assert scenario.discriminator.metric == "files_read_count"
    assert scenario.discriminator.min_improvement_pct == 40
```

- [ ] **Step 4: Write test for scenario with inject list**

Add to same test file:

```python
def test_scenario_with_inject_list():
    """Scenarios can declare which wiki pages to inject for the injected arm."""
    data = {
        "name": "wiki-design-tokens",
        "prompt": "path/to/prompt.md",
        "rubric": "path/to/rubric.md",
        "discriminator": {
            "type": "correctness-gated"
        },
        "inject": ["concepts/design-tokens.md"]
    }
    scenario = Scenario.from_yaml_dict(data)
    assert scenario.inject == ["concepts/design-tokens.md"]
```

- [ ] **Step 5: Run all three tests to verify they fail**

Run: `uv run --package claude-code-evals pytest tests/unit/test_schemas.py::test_scenario_with_correctness_gated_discriminator tests/unit/test_schemas.py::test_scenario_with_efficiency_gated_discriminator tests/unit/test_schemas.py::test_scenario_with_inject_list -v`

Expected: All three FAIL with "discriminator not found" or similar.

- [ ] **Step 6: Define Discriminator dataclass**

Add to `packages/claude-code-evals/src/schemas.py` before the Scenario class:

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

@dataclass
class Discriminator:
    """Per-scenario verdict type for three-arm eval.
    
    Attributes:
        type: One of 'correctness-gated', 'efficiency-gated', 'impossible-without-wiki'.
        metric: For efficiency-gated only; metric to compare (e.g. 'files_read_count').
        min_improvement_pct: For efficiency-gated only; wiki arm must beat base by this %.
    """
    type: Literal["correctness-gated", "efficiency-gated", "impossible-without-wiki"]
    metric: Optional[str] = None
    min_improvement_pct: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Discriminator":
        """Parse from scenario YAML dict."""
        return cls(**data)
```

- [ ] **Step 7: Add discriminator and inject fields to Scenario**

Modify the Scenario dataclass to add these fields:

```python
@dataclass
class Scenario:
    name: str
    prompt: str
    rubric: str
    config: str
    # ... existing fields ...
    discriminator: Optional[Discriminator] = None
    inject: list[str] = field(default_factory=list)
    
    @classmethod
    def from_yaml_dict(cls, data: dict) -> "Scenario":
        """Parse from scenario.yaml, converting discriminator dict to object."""
        discriminator_data = data.pop("discriminator", None)
        discriminator = None
        if discriminator_data:
            discriminator = Discriminator.from_dict(discriminator_data)
        
        inject = data.pop("inject", [])
        
        return cls(**data, discriminator=discriminator, inject=inject)
```

- [ ] **Step 8: Run the three tests again to verify they pass**

Run: `uv run --package claude-code-evals pytest tests/unit/test_schemas.py::test_scenario_with_correctness_gated_discriminator tests/unit/test_schemas.py::test_scenario_with_efficiency_gated_discriminator tests/unit/test_schemas.py::test_scenario_with_inject_list -v`

Expected: All three PASS.

- [ ] **Step 9: Run full test suite for schemas to ensure no regressions**

Run: `uv run --package claude-code-evals pytest tests/unit/test_schemas.py -v`

Expected: All tests PASS (existing + new).

- [ ] **Step 10: Commit**

```bash
git add packages/claude-code-evals/src/schemas.py packages/claude-code-evals/tests/unit/test_schemas.py
git commit -m "feat: add discriminator and inject fields to Scenario schema"
```

---

## Task 2: Create injected.yaml and plugin.yaml arm configs

**Files:**
- Create: `eval/configs/injected.yaml`
- Create: `eval/configs/plugin.yaml`
- Test: Manual verification that both parse without errors

- [ ] **Step 1: Examine existing base.yaml to understand structure**

Run: `cat eval/configs/base.yaml`

Expected: Output shows config structure (model, plugins, system prompts, etc.).

- [ ] **Step 2: Create injected.yaml (copy of base with plugins disabled)**

Create file `eval/configs/injected.yaml` with:

```yaml
# Injected arm: same as base but we'll prepend wiki pages to system prompt at runtime
# This is the "ceiling" — wiki knowledge is perfect, agent just needs to use it

model: claude-opus-4-8
plugins: []  # Disabled; wiki text is injected directly into context

system_prompt: |
  You are an expert developer tasked with solving programming problems.
  [Wiki pages will be prepended here at runtime by the injected arm orchestrator]

max_turns: 100
timeout_seconds: 600
```

- [ ] **Step 3: Create plugin.yaml (includes graph-wiki plugin)**

Create file `eval/configs/plugin.yaml` with:

```yaml
# Plugin arm: agent has graph-wiki plugin and can query via /graph-wiki:query
# This is the "realistic" end-to-end arm

model: claude-opus-4-8
plugins:
  - graph-wiki

system_prompt: |
  You are an expert developer tasked with solving programming problems.
  You have access to a Graph Wiki via the /graph-wiki:query command.
  Use it to understand the codebase when needed.

max_turns: 100
timeout_seconds: 600
environment:
  GRAPH_WIKI_WORKSPACE: "~/Personal/graph-wiki/mono-repo-eval-551f7ed8"
```

- [ ] **Step 4: Verify both configs parse without errors**

Run: `uv run --package claude-code-evals python -c "from src.schemas import Config; import yaml; conf = yaml.safe_load(open('eval/configs/injected.yaml')); print('injected.yaml parses:', conf)"`

Expected: No errors, output shows config dict.

Run: `uv run --package claude-code-evals python -c "from src.schemas import Config; import yaml; conf = yaml.safe_load(open('eval/configs/plugin.yaml')); print('plugin.yaml parses:', conf)"`

Expected: No errors, output shows config dict.

- [ ] **Step 5: Commit**

```bash
git add eval/configs/injected.yaml eval/configs/plugin.yaml
git commit -m "feat: add injected and plugin arm configs for three-arm eval"
```

---

## Task 3: Update existing scenarios with discriminator blocks

**Files:**
- Modify: `eval/scenarios/wiki-design-tokens/scenario.yaml`
- Modify: `eval/scenarios/wiki-api-client/scenario.yaml`
- Test: Manual verification that both parse correctly

- [ ] **Step 1: Read wiki-design-tokens/scenario.yaml**

Run: `cat eval/scenarios/wiki-design-tokens/scenario.yaml`

Expected: Shows scenario definition with name, prompt, rubric, config, expected_pass_rate.

- [ ] **Step 2: Add correctness-gated discriminator to wiki-design-tokens**

Modify `eval/scenarios/wiki-design-tokens/scenario.yaml` to add:

```yaml
# ... existing fields ...
discriminator:
  type: correctness-gated

inject:
  - concepts/design-tokens.md
```

(Add at the end of the file, after existing fields.)

- [ ] **Step 3: Read wiki-api-client/scenario.yaml**

Run: `cat eval/scenarios/wiki-api-client/scenario.yaml`

Expected: Shows scenario definition.

- [ ] **Step 4: Add efficiency-gated discriminator to wiki-api-client**

Modify `eval/scenarios/wiki-api-client/scenario.yaml` to add:

```yaml
# ... existing fields ...
discriminator:
  type: efficiency-gated
  metric: files_read_count
  min_improvement_pct: 40

inject:
  - concepts/shared-api-client.md
```

(Add at the end of the file. The `min_improvement_pct: 40` is derived from the spec: 29 files baseline to beat.)

- [ ] **Step 5: Verify both updated scenarios parse**

Run: `uv run --package claude-code-evals python -c "from src.schemas import Scenario; import yaml; s = yaml.safe_load(open('eval/scenarios/wiki-design-tokens/scenario.yaml')); print('wiki-design-tokens:', s.get('discriminator'))"`

Expected: Shows discriminator: {type: correctness-gated}.

Run: `uv run --package claude-code-evals python -c "from src.schemas import Scenario; import yaml; s = yaml.safe_load(open('eval/scenarios/wiki-api-client/scenario.yaml')); print('wiki-api-client:', s.get('discriminator'))"`

Expected: Shows discriminator: {type: efficiency-gated, metric: files_read_count, min_improvement_pct: 40}.

- [ ] **Step 6: Commit**

```bash
git add eval/scenarios/wiki-design-tokens/scenario.yaml eval/scenarios/wiki-api-client/scenario.yaml
git commit -m "feat: add discriminator blocks to existing scenarios"
```

---

## Task 4: Create impossible-without-wiki scenario

**Files:**
- Create: `eval/scenarios/impossible-without-wiki/`
- Create: `eval/scenarios/impossible-without-wiki/scenario.yaml`
- Create: `eval/scenarios/impossible-without-wiki/prompt.md`
- Create: `eval/scenarios/impossible-without-wiki/rubric.md`
- Create: `eval/scenarios/impossible-without-wiki/preflight.sh`
- Create: `eval/scenarios/impossible-without-wiki/verify.sh`

- [ ] **Step 1: Create scenario directory**

Run: `mkdir -p eval/scenarios/impossible-without-wiki`

- [ ] **Step 2: Create scenario.yaml for impossible-without-wiki**

The spec notes this should be grounded in `adrs/0006-auto-create-activities-from-presence-events.md` from the frozen wiki. Create `eval/scenarios/impossible-without-wiki/scenario.yaml`:

```yaml
name: impossible-without-wiki
description: |
  Knowledge required only from wiki: a design decision (auto-create activities)
  that is not derivable from reading the code.

prompt: eval/scenarios/impossible-without-wiki/prompt.md
rubric: eval/scenarios/impossible-without-wiki/rubric.md
config: base  # Will be parameterized by orchestrator

expected_pass_rate: 0.5

discriminator:
  type: impossible-without-wiki

inject:
  - adrs/0006-auto-create-activities-from-presence-events.md
```

- [ ] **Step 3: Create prompt.md**

Create `eval/scenarios/impossible-without-wiki/prompt.md`:

```markdown
# Impossible-Without-Wiki Scenario

You are tasked with implementing a feature to handle presence events.

The codebase has two competing patterns for event handling:
1. Manual event dispatch in the controller
2. Automatic activity creation from presence data

Which approach should you use for presence events, and why?

Hint: The answer is a design decision, not something that can be inferred from reading the code alone.
Look for guidance in the wiki about how the team handles this.
```

- [ ] **Step 4: Create rubric.md**

Create `eval/scenarios/impossible-without-wiki/rubric.md`:

```markdown
# Rubric: Impossible-Without-Wiki

## Passing Criteria (1.0)

- Correctly identifies that presence events should auto-create activities
- Cites or references the design decision from the wiki (ADR 0006)
- Explains the rationale (reduces manual dispatch burden)

## Partial Credit (0.5)

- Identifies one of: the correct approach OR the rationale
- Shows awareness that a design decision exists, but doesn't fully cite it

## Failing (0.0)

- Chooses the manual dispatch pattern
- No reference to wiki or design decision
- Contradicts the decision from ADR 0006
```

- [ ] **Step 5: Create preflight.sh**

Create `eval/scenarios/impossible-without-wiki/preflight.sh`:

```bash
#!/bin/bash
# Preflight: verify the frozen wiki contains the required ADR

WIKI_ROOT="${GRAPH_WIKI_WORKSPACE:-~/Personal/graph-wiki/mono-repo-eval-551f7ed8}"
ADR_PATH="$WIKI_ROOT/wiki/adrs/0006-auto-create-activities-from-presence-events.md"

if [ ! -f "$ADR_PATH" ]; then
  echo "FAIL: ADR 0006 not found at $ADR_PATH"
  exit 1
fi

if ! grep -q "auto-create" "$ADR_PATH"; then
  echo "FAIL: ADR 0006 does not contain 'auto-create'"
  exit 1
fi

echo "OK: Wiki has required ADR"
exit 0
```

- [ ] **Step 6: Create verify.sh**

Create `eval/scenarios/impossible-without-wiki/verify.sh`:

```bash
#!/bin/bash
# Verify.sh: check that the scenario setup is correct

# This is a placeholder; actual verification happens in the rubric eval
echo "OK: Scenario setup verified"
exit 0
```

- [ ] **Step 7: Make shell scripts executable**

Run: `chmod +x eval/scenarios/impossible-without-wiki/preflight.sh eval/scenarios/impossible-without-wiki/verify.sh`

- [ ] **Step 8: Verify scenario.yaml parses**

Run: `uv run --package claude-code-evals python -c "import yaml; s = yaml.safe_load(open('eval/scenarios/impossible-without-wiki/scenario.yaml')); print('Scenario:', s.get('name'), 'Discriminator:', s.get('discriminator'))"`

Expected: Shows "Scenario: impossible-without-wiki Discriminator: {'type': 'impossible-without-wiki'}".

- [ ] **Step 9: Commit**

```bash
git add eval/scenarios/impossible-without-wiki/
git commit -m "feat: add impossible-without-wiki scenario grounded in ADR 0006"
```

---

## Task 5: Create scenario template

**Files:**
- Create: `eval/scenarios/TEMPLATE/`
- Create: `eval/scenarios/TEMPLATE/scenario.yaml`
- Create: `eval/scenarios/TEMPLATE/prompt.md`
- Create: `eval/scenarios/TEMPLATE/rubric.md`
- Create: `eval/scenarios/TEMPLATE/preflight.sh`
- Create: `eval/scenarios/TEMPLATE/verify.sh`

- [ ] **Step 1: Create TEMPLATE directory**

Run: `mkdir -p eval/scenarios/TEMPLATE`

- [ ] **Step 2: Create TEMPLATE/scenario.yaml**

Create `eval/scenarios/TEMPLATE/scenario.yaml`:

```yaml
# Template: Use this as a skeleton for new scenarios
#
# Instructions:
# 1. Copy this entire directory and rename to your scenario name (kebab-case)
# 2. Edit the fields below:
#    - name: scenario identifier (matches directory name)
#    - description: one sentence about what the scenario tests
#    - prompt: path to prompt.md (edit that file with your scenario)
#    - rubric: path to rubric.md (define scoring criteria)
#    - discriminator.type: choose one:
#        * correctness-gated: base fails, wiki arm passes rubric
#        * efficiency-gated: both pass, wiki arm beats declared metric threshold
#        * impossible-without-wiki: base cannot pass; knowledge only in wiki
#    - inject: list of wiki page paths (relative to wiki/ root) to inject for injected arm
# 3. Update prompt.md and rubric.md with your scenario specifics
# 4. Run: `uv run --package claude-code-evals pytest` to verify scenario loads

name: TEMPLATE_SCENARIO_NAME
description: |
  One-sentence description of what this scenario tests.

prompt: eval/scenarios/TEMPLATE/prompt.md
rubric: eval/scenarios/TEMPLATE/rubric.md
config: base  # Will be parameterized by orchestrator

expected_pass_rate: 0.5

discriminator:
  type: correctness-gated
  # For efficiency-gated, add:
  # metric: files_read_count  # or turn_count, output_tokens, tool_calls_before_first_edit
  # min_improvement_pct: 40

inject:
  # List wiki pages relevant to this scenario, e.g.:
  # - concepts/some-concept.md
  # - adrs/0001-some-decision.md
  - concepts/TEMPLATE.md
```

- [ ] **Step 3: Create TEMPLATE/prompt.md**

Create `eval/scenarios/TEMPLATE/prompt.md`:

```markdown
# TEMPLATE Scenario Prompt

## Context

[Describe the problem or task the agent is solving]

## Task

[What should the agent do? Be specific and measurable.]

## Success Criteria

[What does "correct" look like from the agent's perspective?]
```

- [ ] **Step 4: Create TEMPLATE/rubric.md**

Create `eval/scenarios/TEMPLATE/rubric.md`:

```markdown
# TEMPLATE Rubric

## Passing (1.0)

[What does a perfect answer look like?]

## Partial (0.5)

[What does a mostly-correct answer look like?]

## Failing (0.0)

[What counts as incorrect or off-topic?]

## Notes

[Any special considerations for grading?]
```

- [ ] **Step 5: Create TEMPLATE/preflight.sh**

Create `eval/scenarios/TEMPLATE/preflight.sh`:

```bash
#!/bin/bash
# Preflight: check that scenario setup is valid
# Run before executing scenario to verify dependencies

set -e

# Example: Check that a required wiki page exists
# WIKI_ROOT="${GRAPH_WIKI_WORKSPACE:-~/Personal/graph-wiki/mono-repo-eval-551f7ed8}"
# if [ ! -f "$WIKI_ROOT/wiki/concepts/TEMPLATE.md" ]; then
#   echo "FAIL: Required wiki page not found"
#   exit 1
# fi

echo "OK: Scenario ready"
exit 0
```

- [ ] **Step 6: Create TEMPLATE/verify.sh**

Create `eval/scenarios/TEMPLATE/verify.sh`:

```bash
#!/bin/bash
# Verify: run any post-scenario cleanup or verification
# (Most verification happens in the rubric eval)

echo "OK: Scenario complete"
exit 0
```

- [ ] **Step 7: Make shell scripts executable**

Run: `chmod +x eval/scenarios/TEMPLATE/preflight.sh eval/scenarios/TEMPLATE/verify.sh`

- [ ] **Step 8: Commit**

```bash
git add eval/scenarios/TEMPLATE/
git commit -m "docs: add scenario template for future eval scenarios"
```

---

## Task 6: Implement injected arm wiring in runner/orchestrator

**Files:**
- Modify: `packages/claude-code-evals/src/runner.py` (or orchestrator.py, depending on structure)
- Test: `packages/claude-code-evals/tests/unit/test_runner.py`

- [ ] **Step 1: Examine current runner.py structure**

Run: `head -100 packages/claude-code-evals/src/runner.py`

Expected: Shows how configs are loaded, scenarios run, etc.

- [ ] **Step 2: Write test for injected arm context injection**

Add to `packages/claude-code-evals/tests/unit/test_runner.py`:

```python
def test_injected_arm_prepends_wiki_pages():
    """Injected arm prepends wiki page text to the system prompt."""
    # Mock the wiki file system
    wiki_root = "/tmp/test-wiki"
    os.makedirs(f"{wiki_root}/wiki/concepts", exist_ok=True)
    with open(f"{wiki_root}/wiki/concepts/design-tokens.md", "w") as f:
        f.write("# Design Tokens\n\nTokens are defined in config.ts")
    
    scenario = Scenario(
        name="test",
        prompt="path/to/prompt.md",
        rubric="path/to/rubric.md",
        config="injected",
        inject=["concepts/design-tokens.md"]
    )
    
    injected_config = load_config("injected")
    context = prepare_injected_context(
        base_prompt=injected_config.system_prompt,
        wiki_root=wiki_root,
        inject_paths=scenario.inject
    )
    
    assert "Design Tokens" in context
    assert "Tokens are defined in config.ts" in context
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --package claude-code-evals pytest tests/unit/test_runner.py::test_injected_arm_prepends_wiki_pages -v`

Expected: FAIL with "prepare_injected_context not found".

- [ ] **Step 4: Implement prepare_injected_context function**

Add to `packages/claude-code-evals/src/runner.py`:

```python
def prepare_injected_context(
    base_prompt: str,
    wiki_root: str,
    inject_paths: list[str]
) -> str:
    """Prepend wiki page contents to system prompt for injected arm.
    
    Args:
        base_prompt: The base system prompt from the config
        wiki_root: Path to wiki root (e.g. ~/Personal/graph-wiki/mono-repo-eval-551f7ed8)
        inject_paths: List of wiki page paths relative to wiki/
    
    Returns:
        Combined prompt with wiki pages prepended
    """
    wiki_sections = []
    
    for inject_path in inject_paths:
        full_path = os.path.join(wiki_root, "wiki", inject_path)
        try:
            with open(full_path, "r") as f:
                content = f.read()
                wiki_sections.append(content)
        except FileNotFoundError:
            raise ValueError(f"Wiki page not found: {inject_path}")
    
    wiki_text = "\n\n---\n\n".join(wiki_sections)
    return f"{wiki_text}\n\n{base_prompt}"
```

- [ ] **Step 5: Run test again to verify it passes**

Run: `uv run --package claude-code-evals pytest tests/unit/test_runner.py::test_injected_arm_prepends_wiki_pages -v`

Expected: PASS.

- [ ] **Step 6: Write test for plugin arm environment setup**

Add to same test file:

```python
def test_plugin_arm_sets_wiki_workspace_env():
    """Plugin arm sets GRAPH_WIKI_WORKSPACE env var for the subprocess."""
    scenario = Scenario(
        name="test",
        prompt="path/to/prompt.md",
        rubric="path/to/rubric.md",
        config="plugin"
    )
    
    plugin_config = load_config("plugin")
    env = prepare_plugin_env(plugin_config)
    
    assert "GRAPH_WIKI_WORKSPACE" in env
    assert env["GRAPH_WIKI_WORKSPACE"] == "~/Personal/graph-wiki/mono-repo-eval-551f7ed8"
```

- [ ] **Step 7: Implement prepare_plugin_env function**

Add to `packages/claude-code-evals/src/runner.py`:

```python
def prepare_plugin_env(config: Config) -> dict:
    """Prepare environment vars for plugin arm (includes GRAPH_WIKI_WORKSPACE).
    
    Args:
        config: The plugin config loaded from plugin.yaml
    
    Returns:
        Environment dict with GRAPH_WIKI_WORKSPACE set
    """
    env = os.environ.copy()
    
    if "environment" in config:
        for key, value in config["environment"].items():
            # Expand ~ in paths
            if value.startswith("~"):
                value = os.path.expanduser(value)
            env[key] = value
    
    return env
```

- [ ] **Step 8: Run both runner tests to verify they pass**

Run: `uv run --package claude-code-evals pytest tests/unit/test_runner.py::test_injected_arm_prepends_wiki_pages tests/unit/test_runner.py::test_plugin_arm_sets_wiki_workspace_env -v`

Expected: Both PASS.

- [ ] **Step 9: Run full runner test suite**

Run: `uv run --package claude-code-evals pytest tests/unit/test_runner.py -v`

Expected: All tests PASS (existing + new).

- [ ] **Step 10: Commit**

```bash
git add packages/claude-code-evals/src/runner.py packages/claude-code-evals/tests/unit/test_runner.py
git commit -m "feat: implement injected and plugin arm wiring in runner"
```

---

## Task 7: Implement verdict computation logic

**Files:**
- Create: `packages/claude-code-evals/src/verdict.py` (new file)
- Modify: `packages/claude-code-evals/src/runner.py` (import and use verdict logic)
- Test: `packages/claude-code-evals/tests/unit/test_verdict.py` (new file)

- [ ] **Step 1: Create test file for verdict computation**

Create `packages/claude-code-evals/tests/unit/test_verdict.py`:

```python
import pytest
from src.verdict import compute_verdict, Verdict

def test_correctness_gated_verdict_base_fails_injected_passes():
    """Correctness-gated: if base fails and injected passes, verdict is WIKI_HELPED."""
    base_score = 0.0
    injected_score = 1.0
    plugin_score = 0.8
    
    verdict = compute_verdict(
        discriminator_type="correctness-gated",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score
    )
    
    assert verdict.verdict == "WIKI_HELPED"
    assert verdict.reason == "correctness: base failed, injected passed"

def test_correctness_gated_verdict_both_fail():
    """Correctness-gated: if both base and injected fail, verdict is NO_WIKI_VALUE."""
    base_score = 0.2
    injected_score = 0.3
    plugin_score = 0.2
    
    verdict = compute_verdict(
        discriminator_type="correctness-gated",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score
    )
    
    assert verdict.verdict == "NO_WIKI_VALUE"

def test_efficiency_gated_verdict_wiki_helps():
    """Efficiency-gated: if plugin beats base by threshold, verdict is WIKI_HELPED."""
    base_files = 29
    injected_files = 8
    plugin_files = 11
    
    verdict = compute_verdict(
        discriminator_type="efficiency-gated",
        base_metric=base_files,
        injected_metric=injected_files,
        plugin_metric=plugin_files,
        metric="files_read_count",
        min_improvement_pct=40  # plugin must be 40% better than base
    )
    
    # 11 files vs 29 = 62% improvement > 40% threshold
    assert verdict.verdict == "WIKI_HELPED"
    assert "-62%" in verdict.reason or "62%" in verdict.reason

def test_efficiency_gated_verdict_wiki_doesnt_help():
    """Efficiency-gated: if plugin doesn't beat threshold, verdict is NO_WIKI_VALUE."""
    base_files = 29
    plugin_files = 25
    
    verdict = compute_verdict(
        discriminator_type="efficiency-gated",
        base_metric=base_files,
        plugin_metric=plugin_files,
        metric="files_read_count",
        min_improvement_pct=40
    )
    
    # 25 files vs 29 = 14% improvement < 40% threshold
    assert verdict.verdict == "NO_WIKI_VALUE"

def test_impossible_without_wiki_base_fails_plugin_passes():
    """Impossible-without-wiki: if base fails and plugin passes, verdict is WIKI_HELPED."""
    base_score = 0.0
    injected_score = 1.0
    plugin_score = 0.9
    
    verdict = compute_verdict(
        discriminator_type="impossible-without-wiki",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score
    )
    
    assert verdict.verdict == "WIKI_HELPED"

def test_impossible_without_wiki_base_passes_plugin_fails():
    """Impossible-without-wiki: if base passes but plugin fails, verdict is PLUGIN_MISS."""
    base_score = 0.9
    injected_score = 1.0
    plugin_score = 0.2
    
    verdict = compute_verdict(
        discriminator_type="impossible-without-wiki",
        base_score=base_score,
        injected_score=injected_score,
        plugin_score=plugin_score
    )
    
    assert verdict.verdict == "PLUGIN_MISS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package claude-code-evals pytest tests/unit/test_verdict.py -v`

Expected: All tests FAIL with "Module not found: src.verdict" or similar.

- [ ] **Step 3: Create verdict.py with verdict computation logic**

Create `packages/claude-code-evals/src/verdict.py`:

```python
"""Verdict computation for three-arm wiki eval."""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class Verdict:
    """Result of comparing metrics across three arms."""
    verdict: Literal["WIKI_HELPED", "NO_WIKI_VALUE", "PLUGIN_MISS", "INCOMPLETE"]
    reason: str
    injected_ceiling_score: Optional[float] = None
    discovery_cost: Optional[float] = None


def compute_verdict(
    discriminator_type: str,
    base_score: Optional[float] = None,
    base_metric: Optional[float] = None,
    injected_score: Optional[float] = None,
    injected_metric: Optional[float] = None,
    plugin_score: Optional[float] = None,
    plugin_metric: Optional[float] = None,
    metric: Optional[str] = None,
    min_improvement_pct: Optional[float] = None,
) -> Verdict:
    """Compute verdict by comparing arms.
    
    Args:
        discriminator_type: One of 'correctness-gated', 'efficiency-gated', 'impossible-without-wiki'
        base_score: Score (0.0–1.0) for base arm
        injected_score: Score for injected arm
        plugin_score: Score for plugin arm
        base_metric: Numeric metric for base arm
        injected_metric: Numeric metric for injected arm
        plugin_metric: Numeric metric for plugin arm
        metric: Name of metric (for efficiency-gated)
        min_improvement_pct: Threshold for improvement (for efficiency-gated)
    
    Returns:
        Verdict object with verdict and reason
    """
    
    if discriminator_type == "correctness-gated":
        return _verdict_correctness_gated(base_score, injected_score, plugin_score)
    elif discriminator_type == "efficiency-gated":
        return _verdict_efficiency_gated(
            base_metric, plugin_metric, injected_metric, metric, min_improvement_pct
        )
    elif discriminator_type == "impossible-without-wiki":
        return _verdict_impossible_without_wiki(base_score, injected_score, plugin_score)
    else:
        return Verdict("INCOMPLETE", f"Unknown discriminator type: {discriminator_type}")


def _verdict_correctness_gated(
    base_score: float, injected_score: float, plugin_score: float
) -> Verdict:
    """Judge correctness-gated scenario.
    
    Wiki helps if:
    - Base fails (< 0.5)
    - Injected passes (>= 0.5)
    """
    base_passes = base_score >= 0.5
    injected_passes = injected_score >= 0.5
    
    if not base_passes and injected_passes:
        discovery_cost = injected_score - plugin_score
        return Verdict(
            "WIKI_HELPED",
            f"correctness: base failed ({base_score:.1%}), injected passed ({injected_score:.1%})",
            injected_ceiling_score=injected_score,
            discovery_cost=discovery_cost,
        )
    elif injected_passes:
        return Verdict(
            "NO_WIKI_VALUE",
            f"correctness: both base and injected passed; base was sufficient",
        )
    else:
        return Verdict(
            "NO_WIKI_VALUE",
            f"correctness: scenario is broken; even injected failed ({injected_score:.1%})",
        )


def _verdict_efficiency_gated(
    base_metric: float,
    plugin_metric: float,
    injected_metric: Optional[float],
    metric: str,
    min_improvement_pct: float,
) -> Verdict:
    """Judge efficiency-gated scenario.
    
    Wiki helps if plugin beats base by min_improvement_pct.
    """
    if plugin_metric is None:
        return Verdict("INCOMPLETE", "plugin metric not recorded")
    
    improvement_pct = (1.0 - plugin_metric / base_metric) * 100
    
    if improvement_pct >= min_improvement_pct:
        return Verdict(
            "WIKI_HELPED",
            f"efficiency: {metric} improved {improvement_pct:.0f}% (threshold {min_improvement_pct:.0f}%)",
            discovery_cost=injected_metric - plugin_metric if injected_metric else 0,
        )
    else:
        return Verdict(
            "NO_WIKI_VALUE",
            f"efficiency: {metric} improved {improvement_pct:.0f}%, below threshold {min_improvement_pct:.0f}%",
        )


def _verdict_impossible_without_wiki(
    base_score: float, injected_score: float, plugin_score: float
) -> Verdict:
    """Judge impossible-without-wiki scenario.
    
    Wiki helps if:
    - Base fails (< 0.5)
    - Plugin passes (>= 0.5)
    
    Plugin miss if:
    - Base passes (>= 0.5)
    - Plugin fails (< 0.5)
    """
    base_passes = base_score >= 0.5
    injected_passes = injected_score >= 0.5
    plugin_passes = plugin_score >= 0.5
    
    if base_passes and not plugin_passes:
        return Verdict(
            "PLUGIN_MISS",
            f"impossible-without-wiki: base passed ({base_score:.1%}), "
            f"but plugin failed ({plugin_score:.1%}); agent didn't query wiki",
        )
    elif not base_passes and plugin_passes:
        return Verdict(
            "WIKI_HELPED",
            f"impossible-without-wiki: base failed ({base_score:.1%}), "
            f"plugin passed ({plugin_score:.1%})",
            injected_ceiling_score=injected_score,
        )
    elif not base_passes and not plugin_passes:
        return Verdict(
            "NO_WIKI_VALUE",
            f"impossible-without-wiki: both base and plugin failed; "
            f"wiki page may not be discoverable or not help",
        )
    else:
        return Verdict(
            "NO_WIKI_VALUE",
            f"impossible-without-wiki: base passed ({base_score:.1%}); "
            f"not actually impossible without wiki",
        )
```

- [ ] **Step 4: Run all verdict tests**

Run: `uv run --package claude-code-evals pytest tests/unit/test_verdict.py -v`

Expected: All tests PASS.

- [ ] **Step 5: Add verdict import and usage to runner.py**

At the top of `packages/claude-code-evals/src/runner.py`, add:

```python
from src.verdict import compute_verdict, Verdict
```

In the scenario run function (wherever results are aggregated), add logic to compute verdict:

```python
# After collecting base, injected, and plugin results:
verdict = compute_verdict(
    discriminator_type=scenario.discriminator.type,
    base_score=results["base"]["score"],
    injected_score=results["injected"]["score"],
    plugin_score=results["plugin"]["score"],
    base_metric=results["base"].get("files_read_count"),
    plugin_metric=results["plugin"].get("files_read_count"),
    metric=scenario.discriminator.metric,
    min_improvement_pct=scenario.discriminator.min_improvement_pct,
)
results["verdict"] = verdict
```

- [ ] **Step 6: Run full test suite**

Run: `uv run --package claude-code-evals pytest tests/unit/ -v`

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/claude-code-evals/src/verdict.py packages/claude-code-evals/tests/unit/test_verdict.py packages/claude-code-evals/src/runner.py
git commit -m "feat: implement verdict computation for three-arm eval"
```

---

## Task 8: Implement report generation with scenario × arm matrix

**Files:**
- Modify: `packages/claude-code-evals/src/report.py`
- Create: `packages/claude-code-evals/templates/report_matrix.md.j2` (new Jinja2 template)
- Test: `packages/claude-code-evals/tests/unit/test_report.py`

- [ ] **Step 1: Examine current report.py structure**

Run: `head -100 packages/claude-code-evals/src/report.py`

Expected: Shows current report format (probably row-per-scenario-config).

- [ ] **Step 2: Write test for matrix report generation**

Add to `packages/claude-code-evals/tests/unit/test_report.py`:

```python
def test_report_generates_scenario_by_arm_matrix():
    """Report includes a scenario × arm matrix with verdicts."""
    results = {
        "wiki-design-tokens": {
            "base": {"score": 0.2, "files_read_count": 15},
            "injected": {"score": 1.0, "files_read_count": 8},
            "plugin": {"score": 0.8, "files_read_count": 12},
            "verdict": {
                "verdict": "WIKI_HELPED",
                "reason": "correctness: base failed, injected passed"
            }
        },
        "wiki-api-client": {
            "base": {"score": 1.0, "files_read_count": 29},
            "injected": {"score": 1.0, "files_read_count": 8},
            "plugin": {"score": 1.0, "files_read_count": 11},
            "verdict": {
                "verdict": "WIKI_HELPED",
                "reason": "efficiency: files_read_count improved 62%"
            }
        }
    }
    
    report = generate_matrix_report(results)
    
    assert "scenario" in report.lower()
    assert "base" in report
    assert "injected" in report
    assert "plugin" in report
    assert "wiki_design_tokens" in report or "wiki-design-tokens" in report
    assert "WIKI_HELPED" in report
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run --package claude-code-evals pytest tests/unit/test_report.py::test_report_generates_scenario_by_arm_matrix -v`

Expected: FAIL with "generate_matrix_report not found".

- [ ] **Step 4: Create Jinja2 template for matrix report**

Create `packages/claude-code-evals/templates/report_matrix.md.j2`:

```jinja2
# Three-Arm Wiki Eval Report

**Date:** {{ timestamp }}

## Scenario × Arm Matrix

| Scenario | Base | Injected | Plugin | Verdict |
|----------|------|----------|--------|---------|
{% for scenario_name, data in results.items() %}
| {{ scenario_name }} | {{ data.base.score or data.base.files_read_count }} | {{ data.injected.score or data.injected.files_read_count }} | {{ data.plugin.score or data.plugin.files_read_count }} | {{ data.verdict.verdict }} |
{% endfor %}

## Verdicts

{% for scenario_name, data in results.items() %}
### {{ scenario_name }}

- **Verdict:** {{ data.verdict.verdict }}
- **Reason:** {{ data.verdict.reason }}
{% if data.verdict.discovery_cost %}
- **Agentic Discovery Cost:** {{ data.verdict.discovery_cost }}
{% endif %}

{% endfor %}

## Derived Signals

| Signal | Calculation |
|--------|-------------|
| Knowledge Value (Ceiling) | injected − base |
| Product Value (Realistic) | plugin − base |
| Agentic Discovery Cost | injected − plugin |
```

- [ ] **Step 5: Implement generate_matrix_report function**

Add to `packages/claude-code-evals/src/report.py`:

```python
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, Template
import json

def generate_matrix_report(results: dict, format: str = "markdown") -> str:
    """Generate scenario × arm matrix report.
    
    Args:
        results: Dict of {scenario_name: {arm_name: metrics, verdict: ...}}
        format: Output format ('markdown' or 'json')
    
    Returns:
        Rendered report string
    """
    
    if format == "json":
        return json.dumps(results, indent=2)
    
    # Markdown with Jinja2 template
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("report_matrix.md.j2")
    
    report = template.render(
        timestamp=datetime.now().isoformat(),
        results=results
    )
    
    return report
```

- [ ] **Step 6: Run test again**

Run: `uv run --package claude-code-evals pytest tests/unit/test_report.py::test_report_generates_scenario_by_arm_matrix -v`

Expected: PASS.

- [ ] **Step 7: Write test for JSON report**

Add to same test file:

```python
def test_report_generates_json_matrix():
    """Report can be generated in JSON format for programmatic diffing."""
    results = {
        "wiki-design-tokens": {
            "base": {"score": 0.2},
            "verdict": {"verdict": "WIKI_HELPED"}
        }
    }
    
    report_json = generate_matrix_report(results, format="json")
    parsed = json.loads(report_json)
    
    assert parsed["wiki-design-tokens"]["verdict"]["verdict"] == "WIKI_HELPED"
```

- [ ] **Step 8: Run both report tests**

Run: `uv run --package claude-code-evals pytest tests/unit/test_report.py -v`

Expected: Both PASS.

- [ ] **Step 9: Run full test suite**

Run: `uv run --package claude-code-evals pytest tests/unit/ -v`

Expected: All tests PASS.

- [ ] **Step 10: Commit**

```bash
git add packages/claude-code-evals/src/report.py packages/claude-code-evals/templates/report_matrix.md.j2 packages/claude-code-evals/tests/unit/test_report.py
git commit -m "feat: implement scenario × arm matrix report with verdicts"
```

---

## Task 9: Implement OAuth token loading from git-ignored file

**Files:**
- Modify: `packages/claude-code-evals/src/runner.py` (or orchestrator.py)
- Test: `packages/claude-code-evals/tests/unit/test_runner.py`

- [ ] **Step 1: Write test for token loading from file**

Add to `packages/claude-code-evals/tests/unit/test_runner.py`:

```python
def test_load_oauth_token_from_env_var():
    """Token is read from CLAUDE_CODE_OAUTH_TOKEN env var if set."""
    os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = "test-token-123"
    token = load_oauth_token()
    assert token == "test-token-123"
    del os.environ["CLAUDE_CODE_OAUTH_TOKEN"]

def test_load_oauth_token_from_git_ignored_file():
    """Token falls back to git-ignored file if env var not set."""
    # Create a temp git-ignored file
    token_file = "/tmp/cc-eval-token"
    with open(token_file, "w") as f:
        f.write("token-from-file")
    
    token = load_oauth_token(token_file_path=token_file)
    assert token == "token-from-file"
    
    os.remove(token_file)

def test_load_oauth_token_missing_raises():
    """Raises error if token not found in env var or file."""
    os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    
    with pytest.raises(ValueError, match="OAuth token not found"):
        load_oauth_token(token_file_path="/nonexistent/path")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --package claude-code-evals pytest tests/unit/test_runner.py::test_load_oauth_token_from_env_var tests/unit/test_runner.py::test_load_oauth_token_from_git_ignored_file tests/unit/test_runner.py::test_load_oauth_token_missing_raises -v`

Expected: All three FAIL with "load_oauth_token not found".

- [ ] **Step 3: Implement load_oauth_token function**

Add to `packages/claude-code-evals/src/runner.py`:

```python
import os
from pathlib import Path


def load_oauth_token(token_file_path: str = None) -> str:
    """Load Claude OAuth token from env var or git-ignored file.
    
    Priority:
    1. CLAUDE_CODE_OAUTH_TOKEN env var
    2. Token file (default: eval/.secrets or ~/.config/cc-eval/token)
    
    Args:
        token_file_path: Optional override for token file path
    
    Returns:
        OAuth token string
    
    Raises:
        ValueError: If token not found in either location
    """
    
    # Try env var first
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        return token.strip()
    
    # Determine token file path if not provided
    if token_file_path is None:
        # Try project-local first: eval/.secrets
        project_token_file = Path(__file__).parent.parent.parent / "eval" / ".secrets"
        if project_token_file.exists():
            token_file_path = str(project_token_file)
        else:
            # Fall back to global: ~/.config/cc-eval/token
            token_file_path = os.path.expanduser("~/.config/cc-eval/token")
    
    # Try token file
    token_file = Path(token_file_path)
    if token_file.exists():
        with open(token_file, "r") as f:
            token = f.read().strip()
            if token:
                return token
    
    raise ValueError(
        f"OAuth token not found. Set CLAUDE_CODE_OAUTH_TOKEN env var "
        f"or create {token_file_path}"
    )
```

- [ ] **Step 4: Run the three tests**

Run: `uv run --package claude-code-evals pytest tests/unit/test_runner.py::test_load_oauth_token_from_env_var tests/unit/test_runner.py::test_load_oauth_token_from_git_ignored_file tests/unit/test_runner.py::test_load_oauth_token_missing_raises -v`

Expected: All three PASS.

- [ ] **Step 5: Add eval/.secrets to .gitignore**

Run: `echo "eval/.secrets" >> .gitignore && git add .gitignore && git commit -m "chore: add eval/.secrets to .gitignore"`

- [ ] **Step 6: Run full test suite**

Run: `uv run --package claude-code-evals pytest tests/unit/ -v`

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/claude-code-evals/src/runner.py packages/claude-code-evals/tests/unit/test_runner.py
git commit -m "feat: implement OAuth token loading from env var or git-ignored file"
```

---

## Task 10: Create runbook documentation for step zero

**Files:**
- Create: `docs/runbooks/freeze-mono-repo-wiki-for-eval.md`

- [ ] **Step 1: Create runbooks directory**

Run: `mkdir -p docs/runbooks`

- [ ] **Step 2: Write runbook for freezing the wiki**

Create `docs/runbooks/freeze-mono-repo-wiki-for-eval.md`:

```markdown
# Runbook: Freeze Mono-Repo Wiki for Eval

## Overview

This runbook documents how to freeze the mono-repo wiki at a specific baseline SHA for use in the three-arm eval framework. The frozen wiki is immutable and describes the code at a fixed commit, ensuring fair comparison across evaluation runs.

## Prerequisites

- Graph Wiki is installed and working (`gw --help` shows the CLI)
- `mono-repo/.graph-wiki.local.yaml` points to `~/Personal/graph-wiki/mono-repo-live` (the working wiki)
- The mono-repo is checked out at the baseline SHA (`551f7ed8b9c0b4f51a4000302548e24284729652`)

## Step 1: Build the Wiki at Baseline SHA

```bash
cd ~/Personal/agent-research  # the mono-repo
git checkout 551f7ed8b9c0b4f51a4000302548e24284729652

# Ensure .graph-wiki.local.yaml points to the live workspace
# (should already be configured)

# Run a full scan to rebuild the wiki from scratch
# This ensures the wiki describes exactly what's in this commit
export GRAPH_WIKI_WORKSPACE=~/Personal/graph-wiki/mono-repo-live
gw scan --workspace "$GRAPH_WIKI_WORKSPACE" --no-narrate --full
```

Expected: Scan completes with entity graph and curated pages (concepts, ADRs, architecture, sources) intact.

## Step 2: Lint and Fix Issues

```bash
gw lint --workspace "$GRAPH_WIKI_WORKSPACE"
```

Expected: Lint report shows any orphaned pages, broken links, or stale claims. Fix any issues found.

## Step 3: Freeze the Wiki

```bash
# Create the frozen directory
FROZEN_DIR=~/Personal/graph-wiki/mono-repo-eval-551f7ed8
mkdir -p "$FROZEN_DIR"

# Copy the live wiki to the frozen location
rsync -a --delete "$GRAPH_WIKI_WORKSPACE/wiki/" "$FROZEN_DIR/wiki/"
rsync -a --delete "$GRAPH_WIKI_WORKSPACE/.graph-wiki/" "$FROZEN_DIR/.graph-wiki/"

# Create a git repo in the frozen directory to track the frozen state
cd "$FROZEN_DIR"
git init
git add .
git commit -m "eval-baseline: frozen wiki at mono-repo SHA 551f7ed8"
git tag -a eval-baseline-551f7ed8 -m "Frozen wiki for eval framework"
```

Expected: The frozen directory is now a git repo with one commit and one tag.

## Step 4: Verify the Frozen Wiki

```bash
# Spot-check that key pages are present
cd ~/Personal/graph-wiki/mono-repo-eval-551f7ed8

# Check entity graph
test -d wiki/entities && echo "✓ Entity graph present" || echo "✗ Entity graph missing"

# Check curated pages
test -f wiki/adrs/0006-auto-create-activities-from-presence-events.md && echo "✓ ADR 0006 present" || echo "✗ ADR 0006 missing"
test -f wiki/concepts/design-tokens.md && echo "✓ Design tokens concept present" || echo "✗ Design tokens concept missing"
test -f wiki/concepts/shared-api-client.md && echo "✓ API client concept present" || echo "✗ API client concept missing"
```

Expected: All key pages are present.

## Step 5: Configure Eval to Use the Frozen Wiki

Update `eval/configs/plugin.yaml` and ensure `GRAPH_WIKI_WORKSPACE` points to the frozen directory:

```yaml
environment:
  GRAPH_WIKI_WORKSPACE: "~/Personal/graph-wiki/mono-repo-eval-551f7ed8"
```

This is already set in the configs created by the eval implementation task.

## Troubleshooting

**Scan fails with "ambiguous argument HEAD":**
- Verify you're in the mono-repo directory, not elsewhere
- Check that `git rev-parse --git-dir` returns `.git` (not a worktree)

**Wiki is missing pages after scan:**
- Run `gw scan --workspace "$GRAPH_WIKI_WORKSPACE" --no-narrate --full` again
- If pages still missing, check the scan log for errors

**rsync fails with permission denied:**
- Ensure `~/Personal/graph-wiki/` directory is writable
- Check file permissions on the source wiki

## After Freezing

- Do NOT modify the frozen wiki directly
- All future scans should target `~/Personal/graph-wiki/mono-repo-live`, not the frozen one
- The frozen wiki is read-only for the eval framework
```

- [ ] **Step 3: Commit the runbook**

```bash
git add docs/runbooks/freeze-mono-repo-wiki-for-eval.md
git commit -m "docs: add runbook for freezing mono-repo wiki for eval"
```

---

## Task 11: Integration test for the full three-arm eval flow

**Files:**
- Create: `packages/claude-code-evals/tests/integration/test_three_arm_flow.py` (if integration tests are separate)
- Modify: Existing integration test suite

- [ ] **Step 1: Write integration test for full flow**

Create or add to integration test file:

```python
@pytest.mark.integration
def test_three_arm_eval_full_flow(tmp_path):
    """Integration test: run a scenario through all three arms."""
    # Setup: create a minimal frozen wiki
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir()
    (wiki_root / "wiki").mkdir()
    (wiki_root / "wiki" / "concepts").mkdir()
    
    with open(wiki_root / "wiki" / "concepts" / "test.md", "w") as f:
        f.write("# Test Concept\n\nThis is test wiki content.")
    
    # Create a minimal scenario
    scenario = Scenario(
        name="test",
        prompt="eval/scenarios/wiki-design-tokens/prompt.md",
        rubric="eval/scenarios/wiki-design-tokens/rubric.md",
        config="base",
        inject=["concepts/test.md"],
        discriminator=Discriminator(type="correctness-gated")
    )
    
    # Test injected arm
    injected_context = prepare_injected_context(
        base_prompt="Base prompt",
        wiki_root=str(wiki_root),
        inject_paths=scenario.inject
    )
    assert "Test Concept" in injected_context
    assert "Base prompt" in injected_context
    
    # Test verdict computation
    verdict = compute_verdict(
        discriminator_type="correctness-gated",
        base_score=0.2,
        injected_score=1.0,
        plugin_score=0.8
    )
    assert verdict.verdict == "WIKI_HELPED"
    
    # Test report generation
    results = {
        "test": {
            "base": {"score": 0.2},
            "injected": {"score": 1.0},
            "plugin": {"score": 0.8},
            "verdict": verdict.__dict__
        }
    }
    report = generate_matrix_report(results)
    assert "test" in report
    assert "WIKI_HELPED" in report
```

- [ ] **Step 2: Run integration test**

Run: `uv run --package claude-code-evals pytest tests/integration/test_three_arm_flow.py -v`

Expected: Test PASSES (assuming frozen wiki is set up).

- [ ] **Step 3: Commit**

```bash
git add packages/claude-code-evals/tests/integration/test_three_arm_flow.py
git commit -m "test: add integration test for three-arm eval flow"
```

---

## Task 12: Verify all tests pass and no regressions

**Files:**
- No files modified, test-only task

- [ ] **Step 1: Run full test suite for claude-code-evals**

Run: `uv run --package claude-code-evals pytest -v`

Expected: All tests PASS (unit + integration, excluding any marked eval-only).

- [ ] **Step 2: Run linter and formatter check**

Run: `uv run ruff check packages/claude-code-evals && uv run ruff format --check packages/claude-code-evals`

Expected: No linting errors or formatting issues.

- [ ] **Step 3: Verify CLI still works**

Run: `uv run --package claude-code-evals cc-eval --help`

Expected: Help text displays without errors.

- [ ] **Step 4: Commit (if any formatting changes)**

Run: `git status`

If any files changed due to formatting:

```bash
git add packages/claude-code-evals/
git commit -m "chore: auto-format code"
```

---

## Summary of Changes

After completing all tasks, the following will be true:

1. **Schemas updated** with `Discriminator` and `inject` fields on `Scenario`
2. **Arm configs created**: `injected.yaml` and `plugin.yaml`
3. **Existing scenarios updated** with `discriminator` blocks
4. **New impossible-without-wiki scenario** created (grounded in ADR 0006)
5. **Scenario template** created for future portfolio growth
6. **Runner wired** to inject wiki text for injected arm, set workspace env for plugin arm
7. **Verdict computation** implemented with three discriminator types
8. **Reporting** generates scenario × arm matrix with per-scenario verdicts
9. **OAuth token loading** from env var or git-ignored file
10. **Runbook documentation** for freezing the wiki
11. **Integration tests** verify the full flow
12. **All tests pass** with no regressions

### File Structure Final State

```
packages/claude-code-evals/
├── src/
│   ├── schemas.py (updated: Discriminator, inject)
│   ├── runner.py (updated: arm wiring, token loading)
│   ├── verdict.py (new: verdict computation)
│   └── report.py (updated: matrix report)
├── templates/
│   └── report_matrix.md.j2 (new: Jinja2 template)
└── tests/
    ├── unit/
    │   ├── test_schemas.py (updated: discriminator tests)
    │   ├── test_runner.py (updated: arm wiring, token tests)
    │   ├── test_verdict.py (new: verdict tests)
    │   └── test_report.py (updated: matrix tests)
    └── integration/
        └── test_three_arm_flow.py (new: full flow test)

eval/
├── configs/
│   ├── base.yaml (existing)
│   ├── injected.yaml (new)
│   └── plugin.yaml (new)
└── scenarios/
    ├── wiki-design-tokens/scenario.yaml (updated: discriminator)
    ├── wiki-api-client/scenario.yaml (updated: discriminator)
    ├── impossible-without-wiki/ (new directory)
    │   ├── scenario.yaml
    │   ├── prompt.md
    │   ├── rubric.md
    │   ├── preflight.sh
    │   └── verify.sh
    └── TEMPLATE/ (new directory)
        ├── scenario.yaml
        ├── prompt.md
        ├── rubric.md
        ├── preflight.sh
        └── verify.sh

docs/
├── runbooks/
│   └── freeze-mono-repo-wiki-for-eval.md (new)
└── superpowers/
    └── plans/
        └── 2026-06-07-cc-eval-wiki-design-PLAN.md (this file)

.gitignore
└── eval/.secrets (added)
```

---

## Testing Strategy

- **Unit tests** cover schema parsing, verdict computation, and report generation
- **Integration tests** verify the full flow from scenario to verdict to report
- **Manual testing** of the CLI with a real scenario (not automated)
- **Existing tests remain green** (no regressions)

## Success Criteria Checklist

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Linter and formatter pass
- [ ] `cc-eval --help` works
- [ ] A full three-arm sweep runs without errors
- [ ] Report matrix is generated correctly
- [ ] Each scenario type (correctness, efficiency, impossible) produces a clean verdict
- [ ] Frozen wiki is used for both injected and plugin arms
- [ ] OAuth token loads from env var or file
