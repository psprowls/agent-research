---
estimated_steps: 11
estimated_files: 9
skills_used: []
---

# T03: Point eval-harness at graph-wiki-core

Expected executor skills: `uv-package-manager` and `python-testing-patterns`.

Why: `eval-harness` is an active package consumer of shared command logic. Rewiring it in S01 proves downstream packages can depend on the new core package rather than the executable agent package.

Do:
1. Change `packages/eval-harness/pyproject.toml` dependency and `[tool.uv.sources]` entry from `graph-wiki-agent` to `graph-wiki-core`.
2. Rewrite active imports in `packages/eval-harness/src/eval_harness/structural.py`, `sweep.py`, divergence modules, and eval-harness tests from `graph_wiki_agent.commands` to `graph_wiki_core.commands`.
3. Do not rewrite historical fixture text or vault content unless tests actively assert it; this task is about executable imports and package dependencies.
4. Keep eval-harness tests scoped to deterministic/unit paths; integration/eval opt-in behavior remains unchanged.

Requirement Impact (Q4): supports R001 and R007 by proving one real workspace package consumes core through uv metadata.
Failure Modes (Q5): if pyproject metadata changes but imports do not, tests fail at import time; if tests are over-broadened into eval/integration paths, they may require Bedrock credentials and become non-deterministic.
Negative Tests (Q7): targeted tests should fail if active eval-harness code still imports `graph_wiki_agent.commands`.
Done when: eval-harness imports command functions from `graph_wiki_core` and selected eval-harness tests run without depending on the old executable package.

## Inputs

- `packages/graph-wiki-core/pyproject.toml`
- `packages/graph-wiki-core/src/graph_wiki_core/commands`
- `packages/eval-harness/pyproject.toml`
- `packages/eval-harness/src/eval_harness/structural.py`
- `packages/eval-harness/src/eval_harness/sweep.py`
- `packages/eval-harness/src/eval_harness/divergence/synthesizer.py`
- `packages/eval-harness/src/eval_harness/divergence/code_reader.py`
- `packages/eval-harness/tests/eval_helpers.py`
- `packages/eval-harness/tests/test_structural.py`
- `packages/eval-harness/tests/test_sweep.py`
- `packages/eval-harness/tests/test_role_sweep.py`

## Expected Output

- `packages/eval-harness/pyproject.toml`
- `packages/eval-harness/src/eval_harness/structural.py`
- `packages/eval-harness/src/eval_harness/sweep.py`
- `packages/eval-harness/src/eval_harness/divergence/synthesizer.py`
- `packages/eval-harness/src/eval_harness/divergence/code_reader.py`
- `packages/eval-harness/tests/eval_helpers.py`
- `packages/eval-harness/tests/test_structural.py`
- `packages/eval-harness/tests/test_sweep.py`
- `packages/eval-harness/tests/test_role_sweep.py`

## Verification

uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py

## Observability Impact

Selected eval-harness pytest failures distinguish package dependency failures from command behavior regressions.
