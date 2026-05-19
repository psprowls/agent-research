---
title: eval-harness
category: package
summary: Deterministic eval checks, pricing, and sweep runner for code-wiki-agent
status: active
package_path: packages/eval-harness
package_type: library
language: python
exports: []
depends_on: [code-wiki-agent, subagent-runtime, model-adapter]
depended_on_by: 0
tags: []
sources: 0
updated: 2026-05-18
tokens: 0
last_sync_commit:
last_sync_at:
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
---

# eval-harness

## Purpose
Deterministic eval checks, pricing, and sweep runner for code-wiki-agent

## File map - eval-harness
TODO — describe what this directory contains.

- `pyproject.toml` — TODO

### eval-harness/baselines/
TODO — describe what this directory contains.

- `divergence-ingestor.json` — TODO
- `divergence-librarian.json` — TODO
- `divergence-linter.json` — TODO
- `divergence-scanner.json` — TODO

### eval-harness/src/
TODO — describe what this directory contains.


#### eval-harness/src/eval_harness/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `baseline.py` — TODO
- `isolation.py` — TODO
- `judge.py` — TODO
- `preflight.py` — TODO
- `pricing.py` — TODO
- `report.py` — TODO
- `structural.py` — TODO
- `sweep.py` — TODO
- `two_gate.py` — TODO

##### eval-harness/src/eval_harness/divergence/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `check.py` — TODO
- `ingestor.py` — TODO
- `librarian.py` — TODO
- `linter.py` — TODO
- `metric.py` — TODO
- `scanner.py` — TODO

###### eval-harness/src/eval_harness/divergence/rubrics/
TODO — describe what this directory contains.

- `ingestor.md` — TODO
- `librarian.md` — TODO
- `linter.md` — TODO
- `scanner.md` — TODO

### eval-harness/tests/
TODO — describe what this directory contains.

- `conftest.py` — TODO
- `eval_helpers.py` — TODO
- `test_baseline.py` — TODO
- `test_divergence.py` — TODO
- `test_divergence_baseline.py` — TODO
- `test_divergence_checks.py` — TODO
- `test_divergence_metric.py` — TODO
- `test_isolation.py` — TODO
- `test_models_toml_sweep_candidates.py` — TODO
- `test_preflight_estimator.py` — TODO
- `test_preflight_module_red.py` — TODO
- `test_pricing.py` — TODO
- `test_recommendation_block.py` — TODO
- `test_report.py` — TODO
- `test_report_role_doc.py` — TODO
- `test_role_sweep.py` — TODO
- `test_structural.py` — TODO
- `test_sweep.py` — TODO
- `test_two_gate_scorer.py` — TODO

#### eval-harness/tests/eval/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `test_sweep_dry_run.py` — TODO
- `test_sweep_eval.py` — TODO

## Sub-pages
- [[api]]      — public API, exports, CLI subcommands
- [[patterns]] — key patterns and conventions
- [[work]]     — bugs, tech debt, features, open questions
- [[context]]  — concepts, decisions, ADRs, sources
