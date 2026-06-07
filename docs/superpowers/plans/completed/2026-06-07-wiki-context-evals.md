# Wiki-Context Evals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two cc-eval scenarios that fail on a `base` config (no wiki plugin) and are designed to pass once wiki-context injection is wired in.

**Architecture:** Pure file creation — two new scenario directories under `eval/scenarios/`, a new `eval/configs/base.yaml`, and a schema-validation test in the `claude-code-evals` package. No changes to harness code. Both scenarios use `isolation_mode: worktree`, `eval_mode: implement`, and a combined `script + rubric` verifier.

**Tech Stack:** cc-eval harness (`claude_code_evals`), Pydantic v2, pytest, YAML, POSIX shell scripts.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `eval/configs/base.yaml` | Create | No-wiki agent config: claude-sonnet-4-6, temp=0.0, no plugin_dirs |
| `eval/scenarios/wiki-api-client/scenario.yaml` | Create | Scenario manifest for API client eval |
| `eval/scenarios/wiki-api-client/prompt.md` | Create | Agent task: implement timeline-summary.ts |
| `eval/scenarios/wiki-api-client/rubric.md` | Create | 5-criterion rubric for judging the output |
| `eval/scenarios/wiki-api-client/preflight.sh` | Create (chmod+x) | Delete target file before run |
| `eval/scenarios/wiki-api-client/verify.sh` | Create (chmod+x) | Assert target file exists |
| `eval/scenarios/wiki-design-tokens/scenario.yaml` | Create | Scenario manifest for design tokens eval |
| `eval/scenarios/wiki-design-tokens/prompt.md` | Create | Agent task: implement StatusBadge.tsx |
| `eval/scenarios/wiki-design-tokens/rubric.md` | Create | 5-criterion rubric for judging the output |
| `eval/scenarios/wiki-design-tokens/preflight.sh` | Create (chmod+x) | Delete target file before run |
| `eval/scenarios/wiki-design-tokens/verify.sh` | Create (chmod+x) | Assert target file exists |
| `packages/claude-code-evals/tests/test_wiki_context_scenarios.py` | Create | Schema-validation tests for both scenario files |

---

## Task 1: Write failing schema-validation tests

**Files:**
- Create: `packages/claude-code-evals/tests/test_wiki_context_scenarios.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests that wiki-context eval scenario files parse correctly via Scenario.from_path()."""

from __future__ import annotations

from pathlib import Path

import pytest
from claude_code_evals.schemas import Config, Scenario

EVAL_ROOT = Path(__file__).parent.parent.parent.parent / "eval"
SCENARIOS_ROOT = EVAL_ROOT / "scenarios"
CONFIGS_ROOT = EVAL_ROOT / "configs"


def test_base_config_parses():
    c = Config.from_path(CONFIGS_ROOT / "base.yaml")
    assert c.name == "base"
    assert c.model == "claude-sonnet-4-6"
    assert c.temperature == 0.0
    assert c.plugin_dirs == []


def test_wiki_api_client_scenario_parses():
    s = Scenario.from_path(SCENARIOS_ROOT / "wiki-api-client" / "scenario.yaml")
    assert s.name == "wiki-api-client"
    assert s.isolation_mode == "worktree"
    assert s.target_repo == "~/Personal/mono-repo"
    assert s.baseline_sha == "551f7ed8b9c0b4f51a4000302548e24284729652"
    assert s.configs == ["base"]
    assert s.mode == "headless"
    assert s.eval_mode == "implement"
    assert s.preflight == "preflight.sh"
    assert len(s.verify) == 2
    assert s.verify[0].kind == "script"
    assert s.verify[0].path == "verify.sh"
    assert s.verify[1].kind == "rubric"
    assert s.verify[1].path == "rubric.md"
    assert s.verify[1].pass_threshold == 4.0
    assert s.budgets.max_turns == 40
    assert s.budgets.max_input_tokens == 4_000_000
    assert s.budgets.max_wall_seconds == 300
    assert s.metrics.tool_shape is True
    assert s.metrics.judge_qualitative is False


def test_wiki_api_client_prompt_exists():
    prompt = SCENARIOS_ROOT / "wiki-api-client" / "prompt.md"
    assert prompt.exists()
    text = prompt.read_text()
    assert "timeline-summary.ts" in text
    assert "getRecentTimeline" in text


def test_wiki_api_client_rubric_exists():
    rubric = SCENARIOS_ROOT / "wiki-api-client" / "rubric.md"
    assert rubric.exists()
    text = rubric.read_text()
    assert "uses_domain_client" in text
    assert "no_raw_http" in text
    assert "no_hardcoded_url" in text
    assert "no_manual_auth" in text
    assert "correct_types" in text


def test_wiki_api_client_scripts_executable():
    for name in ("preflight.sh", "verify.sh"):
        p = SCENARIOS_ROOT / "wiki-api-client" / name
        assert p.exists(), f"{name} missing"
        assert p.stat().st_mode & 0o111, f"{name} not executable"


def test_wiki_design_tokens_scenario_parses():
    s = Scenario.from_path(SCENARIOS_ROOT / "wiki-design-tokens" / "scenario.yaml")
    assert s.name == "wiki-design-tokens"
    assert s.isolation_mode == "worktree"
    assert s.target_repo == "~/Personal/mono-repo"
    assert s.baseline_sha == "551f7ed8b9c0b4f51a4000302548e24284729652"
    assert s.configs == ["base"]
    assert s.mode == "headless"
    assert s.eval_mode == "implement"
    assert s.preflight == "preflight.sh"
    assert len(s.verify) == 2
    assert s.verify[0].kind == "script"
    assert s.verify[0].path == "verify.sh"
    assert s.verify[1].kind == "rubric"
    assert s.verify[1].path == "rubric.md"
    assert s.verify[1].pass_threshold == 4.0
    assert s.budgets.max_turns == 40
    assert s.budgets.max_input_tokens == 4_000_000
    assert s.budgets.max_wall_seconds == 300
    assert s.metrics.tool_shape is True
    assert s.metrics.judge_qualitative is False


def test_wiki_design_tokens_prompt_exists():
    prompt = SCENARIOS_ROOT / "wiki-design-tokens" / "prompt.md"
    assert prompt.exists()
    text = prompt.read_text()
    assert "StatusBadge" in text
    assert "status" in text


def test_wiki_design_tokens_rubric_exists():
    rubric = SCENARIOS_ROOT / "wiki-design-tokens" / "rubric.md"
    assert rubric.exists()
    text = rubric.read_text()
    assert "uses_semantic_tokens" in text
    assert "no_hex_values" in text
    assert "uses_cva_pattern" in text
    assert "dark_mode_safe" in text
    assert "uses_cn_utility" in text


def test_wiki_design_tokens_scripts_executable():
    for name in ("preflight.sh", "verify.sh"):
        p = SCENARIOS_ROOT / "wiki-design-tokens" / name
        assert p.exists(), f"{name} missing"
        assert p.stat().st_mode & 0o111, f"{name} not executable"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --package claude-code-evals pytest tests/test_wiki_context_scenarios.py -v
```

Expected: all 10 tests FAIL with `FileNotFoundError` or `AssertionError` (files don't exist yet).

---

## Task 2: Create the base config

**Files:**
- Create: `eval/configs/base.yaml`

- [ ] **Step 1: Create the directory and file**

Create `eval/configs/base.yaml` with this exact content:

```yaml
name: base
model: claude-sonnet-4-6
temperature: 0.0
```

- [ ] **Step 2: Run the base-config test only**

```
uv run --package claude-code-evals pytest tests/test_wiki_context_scenarios.py::test_base_config_parses -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add eval/configs/base.yaml
git commit -m "feat: add base eval config for wiki-context scenarios"
```

---

## Task 3: Create the wiki-api-client scenario

**Files:**
- Create: `eval/scenarios/wiki-api-client/scenario.yaml`
- Create: `eval/scenarios/wiki-api-client/prompt.md`
- Create: `eval/scenarios/wiki-api-client/rubric.md`
- Create: `eval/scenarios/wiki-api-client/preflight.sh`
- Create: `eval/scenarios/wiki-api-client/verify.sh`

- [ ] **Step 1: Create scenario.yaml**

Create `eval/scenarios/wiki-api-client/scenario.yaml`:

```yaml
name: wiki-api-client
description: >
  Agent must use the project's sanctioned domain HTTP client (TimelineApiClient)
  to fetch timeline data. Without wiki context the agent copies the raw-axios
  pattern visible in nextauth-api.ts and fails the rubric.
isolation_mode: worktree
target_repo: ~/Personal/mono-repo
baseline_sha: 551f7ed8b9c0b4f51a4000302548e24284729652
configs: [base]
mode: headless
eval_mode: implement
preflight: preflight.sh
verify:
  - kind: script
    path: verify.sh
  - kind: rubric
    path: rubric.md
    pass_threshold: 4.0
budgets:
  max_turns: 40
  max_input_tokens: 4000000
  max_wall_seconds: 300
metrics:
  tool_shape: true
  judge_qualitative: false
```

- [ ] **Step 2: Create prompt.md**

Create `eval/scenarios/wiki-api-client/prompt.md`:

```markdown
Implement `apps/web-next-ts/src/lib/timeline-summary.ts`.

Requirements:
- Export a single async function `getRecentTimeline(limit: number = 10)`
- Use the project's sanctioned domain HTTP client — do NOT use raw `fetch`, `axios`, or hardcode API URLs
- Return a typed list of timeline events using types from the timeline domain package
- Do not manage auth tokens manually — the client handles that
```

- [ ] **Step 3: Create rubric.md**

Create `eval/scenarios/wiki-api-client/rubric.md`:

```markdown
Score the agent's `timeline-summary.ts` 0–5, 1 pt per criterion. Pass threshold 4.

Criteria:

1. `uses_domain_client` — Imports `TimelineApiClient` from `@psprowls/timeline-domain-ts` (or another sanctioned domain client). What is forbidden: importing `axios` directly, using `fetch`, using `SharedApiClient` for data fetching, or constructing a raw HTTP call.
2. `no_raw_http` — Does not call `axios(...)`, `axios.get(...)`, `fetch(...)`, or `XMLHttpRequest` anywhere in the file.
3. `no_hardcoded_url` — Does not hardcode an API base URL string (e.g. `https://ts-api.psprowls.io`); relies on the client's built-in configuration.
4. `no_manual_auth` — Does not attach Authorization headers, manage Cognito tokens, or otherwise handle authentication — that is the domain client's responsibility.
5. `correct_types` — The return type is statically inferable as a typed list from `@psprowls/timeline-domain-ts`, not `any` or `unknown`.

Return JSON: `{"score": 0-5, "reasoning": str, "criteria_hits": [str]}`.
```

- [ ] **Step 4: Create preflight.sh**

Create `eval/scenarios/wiki-api-client/preflight.sh`:

```sh
#!/bin/sh
set -eu
rm -f apps/web-next-ts/src/lib/timeline-summary.ts
```

Then make it executable:
```bash
chmod +x eval/scenarios/wiki-api-client/preflight.sh
```

- [ ] **Step 5: Create verify.sh**

Create `eval/scenarios/wiki-api-client/verify.sh`:

```sh
#!/bin/sh
set -eu
test -f apps/web-next-ts/src/lib/timeline-summary.ts
```

Then make it executable:
```bash
chmod +x eval/scenarios/wiki-api-client/verify.sh
```

- [ ] **Step 6: Run wiki-api-client tests**

```
uv run --package claude-code-evals pytest tests/test_wiki_context_scenarios.py -k "api_client" -v
```

Expected: all 4 `api_client` tests PASS.

- [ ] **Step 7: Commit**

```bash
git add eval/scenarios/wiki-api-client/
git commit -m "feat: add wiki-api-client eval scenario"
```

---

## Task 4: Create the wiki-design-tokens scenario

**Files:**
- Create: `eval/scenarios/wiki-design-tokens/scenario.yaml`
- Create: `eval/scenarios/wiki-design-tokens/prompt.md`
- Create: `eval/scenarios/wiki-design-tokens/rubric.md`
- Create: `eval/scenarios/wiki-design-tokens/preflight.sh`
- Create: `eval/scenarios/wiki-design-tokens/verify.sh`

- [ ] **Step 1: Create scenario.yaml**

Create `eval/scenarios/wiki-design-tokens/scenario.yaml`:

```yaml
name: wiki-design-tokens
description: >
  Agent must create a StatusBadge component using the project's semantic color
  token system and CVA variant pattern. Without wiki context the agent uses
  hex values or raw Tailwind palette classes and fails the rubric.
isolation_mode: worktree
target_repo: ~/Personal/mono-repo
baseline_sha: 551f7ed8b9c0b4f51a4000302548e24284729652
configs: [base]
mode: headless
eval_mode: implement
preflight: preflight.sh
verify:
  - kind: script
    path: verify.sh
  - kind: rubric
    path: rubric.md
    pass_threshold: 4.0
budgets:
  max_turns: 40
  max_input_tokens: 4000000
  max_wall_seconds: 300
metrics:
  tool_shape: true
  judge_qualitative: false
```

- [ ] **Step 2: Create prompt.md**

Create `eval/scenarios/wiki-design-tokens/prompt.md`:

```markdown
Create a `StatusBadge` component at `apps/web-next-ts/src/components/StatusBadge.tsx`.

Requirements:
- Accept a `status` prop: `"running" | "completed" | "failed" | "pending"`
- Each status renders with appropriate color styling
- Follow the project's design system conventions — use semantic color tokens, not hardcoded hex values or raw Tailwind palette classes like `bg-green-500`
- Follow the component variant patterns established in the shared UI packages
- Export `StatusBadge` as a named export
```

- [ ] **Step 3: Create rubric.md**

Create `eval/scenarios/wiki-design-tokens/rubric.md`:

```markdown
Score the agent's `StatusBadge.tsx` 0–5, 1 pt per criterion. Pass threshold 4.

Criteria:

1. `uses_semantic_tokens` — Color classes use CSS custom property token utilities (`bg-primary`, `bg-destructive`, `bg-muted`, `text-foreground`, `text-primary-foreground`, etc.) rather than raw Tailwind palette classes (`bg-green-500`, `text-red-600`, etc.).
2. `no_hex_values` — No hardcoded hex color strings (e.g. `#16a34a`, `#dc2626`) appear anywhere in the file.
3. `uses_cva_pattern` — Uses `cva` from `class-variance-authority` to define the variant map (matching the pattern in `common-ui-shadcn-ts/src/components/button.tsx`).
4. `dark_mode_safe` — Only semantic token classes are used for color; these resolve correctly under the `.dark` class automatically without additional `dark:` overrides on raw palette classes.
5. `uses_cn_utility` — Imports and uses the `cn` utility (from `@psprowls/common-ui-shadcn-ts/lib/utils` or `@psprowls/shared-ui-react-ts`) to merge class names.

Return JSON: `{"score": 0-5, "reasoning": str, "criteria_hits": [str]}`.
```

- [ ] **Step 4: Create preflight.sh**

Create `eval/scenarios/wiki-design-tokens/preflight.sh`:

```sh
#!/bin/sh
set -eu
rm -f apps/web-next-ts/src/components/StatusBadge.tsx
```

Then make it executable:
```bash
chmod +x eval/scenarios/wiki-design-tokens/preflight.sh
```

- [ ] **Step 5: Create verify.sh**

Create `eval/scenarios/wiki-design-tokens/verify.sh`:

```sh
#!/bin/sh
set -eu
test -f apps/web-next-ts/src/components/StatusBadge.tsx
```

Then make it executable:
```bash
chmod +x eval/scenarios/wiki-design-tokens/verify.sh
```

- [ ] **Step 6: Run wiki-design-tokens tests**

```
uv run --package claude-code-evals pytest tests/test_wiki_context_scenarios.py -k "design_tokens" -v
```

Expected: all 4 `design_tokens` tests PASS.

- [ ] **Step 7: Commit**

```bash
git add eval/scenarios/wiki-design-tokens/
git commit -m "feat: add wiki-design-tokens eval scenario"
```

---

## Task 5: Run full test suite and commit test file

- [ ] **Step 1: Run the complete wiki-context test suite**

```
uv run --package claude-code-evals pytest tests/test_wiki_context_scenarios.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 2: Run the full claude-code-evals suite to check for regressions**

```
uv run --package claude-code-evals pytest -m "not integration" -v
```

Expected: all tests PASS (same count as before + 10 new ones).

- [ ] **Step 3: Commit the test file**

```bash
git add packages/claude-code-evals/tests/test_wiki_context_scenarios.py
git commit -m "test: add schema-validation tests for wiki-context eval scenarios"
```

---

## Self-Review

**Spec coverage check:**
- ✅ `eval/configs/base.yaml` — Task 2
- ✅ `wiki-api-client` scenario, prompt, rubric, preflight.sh, verify.sh — Task 3
- ✅ `wiki-design-tokens` scenario, prompt, rubric, preflight.sh, verify.sh — Task 4
- ✅ Both scenarios: `isolation_mode: worktree`, `baseline_sha: 551f7ed8b9c0b4f51a4000302548e24284729652`, `configs: [base]`, `eval_mode: implement`, `mode: headless` — checked in schema tests
- ✅ Both `preflight.sh` and `verify.sh` are `chmod +x` — Steps 4 & 5 in Tasks 3/4
- ✅ Pass threshold `4.0` on rubric verifier — in scenario.yaml and asserted in tests
- ✅ Budgets: `max_turns: 40`, `max_input_tokens: 4000000`, `max_wall_seconds: 300` — in scenario.yaml and asserted in tests
- ✅ `metrics.tool_shape: true`, `metrics.judge_qualitative: false` — in scenario.yaml and asserted in tests
- ✅ All 5 rubric criteria for each scenario match spec exactly
- ✅ `preflight` field in scenario.yaml matches schema (`preflight: str | None` in `Scenario`)

**Note on `eval/runsets/wiki-context.yaml`:** The spec marks this as a follow-up item, so it is intentionally excluded from this plan.
