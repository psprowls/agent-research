---
title: eval-harness
category: package
summary: Divergence checks (per-role programmatic + judge rubrics), two-gate scoring protocol, and the model-sweep runner that explores the cost frontier.
status: active
package_path: packages/eval-harness
package_type: library
domain:
language: Python
depends_on: [subagent-runtime, model-adapter]
tags: [python, eval, sweep, divergence]
sources: 0
updated: 2026-05-19
---

# eval-harness

## Overview

`eval-harness` is the model-evaluation layer of the post-rebrand `deep-agents` monorepo. It owns the per-role divergence checks (one module per role under `src/eval_harness/divergence/`), the matching judge rubrics under `src/eval_harness/divergence/rubrics/`, the two-gate scoring protocol (`two_gate.py`), and the model-sweep runner (`sweep.py`) used to explore the cost frontier under the D-06 single-role-swap protocol.

Phase 16 D-06 extended `ROLES_WITH_DIVERGENCE` to the full set of six in-scope roles (librarian, ingestor, linter, scanner, code_reader, synthesizer); the prior D-08 skip for code_reader + synthesizer is superseded.

## API

- `divergence.ROLE_CHECKS: dict[role, list[DivergenceCheck]]`
- `divergence.ROLE_RUBRICS: dict[role, Path]`
- `two_gate.score_two_gate(role, divergence_metric_or_none, agent_outputs_by_case, baselines_dir, panel_mean, default_panel_mean, threshold) -> TwoGateOutcome`
- `sweep.run_sweep(...)` — async (model_id × case) sweep runner

## Cross-refs

- Reads canonical role definitions from [[wiki/packages/prompt-sources/prompt-sources]]
- Uses [[wiki/packages/subagent-runtime/subagent-runtime]] trace records for token accounting
