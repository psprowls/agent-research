---
title: eval-harness
category: package
summary: Deterministic eval checks, cost tracking, and model-sweep runner for validating code-wiki-agent answer quality
status: active
package_path: packages/eval-harness
package_type: library
domain:
language: python
depends_on:
  - code-wiki-agent
  - subagent-runtime
  - model-adapter
tags: [eval, deepeval, bedrock, quality, cost]
sources: 0
updated: 2026-05-14
tokens: 0
last_sync_commit:
last_sync_at:
---

# eval-harness

## Purpose

Drives the cost-vs-quality decision loop. Records lattice-wiki (Claude Code) query outputs as the gold baseline, then runs `code-wiki-agent` queries against multiple Bedrock model configurations. Scores each run with structural checks and `deepeval` LLM-judge metrics, then produces a comparison report showing quality delta and cost per query. Used to pick the cheapest model combination that meets the quality bar.

## Public API

- `baseline.load_baseline(path)` / `baseline.record(path, results)` — `src/eval_harness/baseline.py` — load or write the gold JSONL baseline
- `sweep.run_sweep(configs, questions, baseline)` — `src/eval_harness/sweep.py` — async sweep; returns list of `SweepResult`
- `judge.score(result, baseline_item)` — `src/eval_harness/judge.py` — runs deepeval `GEval` metric against a single result
- `structural.check(result)` — `src/eval_harness/structural.py` — fast deterministic checks (wikilinks present, code citations present)
- `pricing.cost(result)` — `src/eval_harness/pricing.py` — computes USD cost from token counts and per-model rates
- `report.render(sweep_results)` — `src/eval_harness/report.py` — markdown table: model config × quality score × cost
- `isolation.run_isolated(config, question)` — `src/eval_harness/isolation.py` — runs a single query in a subprocess to avoid model-state bleed

## File map - eval-harness

- `pyproject.toml` — package manifest; workspace deps on code-wiki-agent, subagent-runtime, model-adapter

### eval-harness/src/

#### eval-harness/src/eval_harness/

- `__init__.py` — package init
- `baseline.py` — JSONL baseline load/write; each record has `question`, `answer`, `pages_read`, `tokens`
- `isolation.py` — subprocess isolation to prevent model/state leakage between sweep runs
- `judge.py` — deepeval `GEval` + `AmazonBedrockModel` wrapper; judges answer faithfulness and completeness
- `pricing.py` — per-model token pricing table; computes cost from `ChatBedrockConverse` usage metadata
- `report.py` — renders markdown comparison table from sweep results
- `structural.py` — deterministic checks: wikilinks present, code citations present, answer length in range
- `sweep.py` — async model-config sweep; calls `isolation.run_isolated` for each `(config, question)` pair

### eval-harness/tests/

- `conftest.py` — shared fixtures (minimal baseline, fake model configs)
- `test_baseline.py` — baseline load/write round-trip
- `test_isolation.py` — subprocess isolation logic
- `test_pricing.py` — cost calculation for known token counts
- `test_report.py` — markdown report rendering
- `test_structural.py` — deterministic check cases (pass / fail conditions)
- `test_sweep.py` — sweep orchestration with mocked agent

#### eval-harness/tests/eval/

Full eval suite — requires `CODE_WIKI_RUN_EVAL=1` and real Bedrock credentials.

- `__init__.py` — package init
- `test_sweep_eval.py` — parametrised over all model configs; asserts structural pass-rate ≥ threshold

## Key patterns

- Gold baseline is JSONL at `eval/baselines/<date>-<slug>.jsonl`; never overwritten, only appended
- `deepeval` metrics use `AmazonBedrockModel` — stays on Bedrock, no Anthropic direct API
- Structural checks run first (fast); LLM judge only fires if structural checks pass
- Eval tests are gated by `CODE_WIKI_RUN_EVAL=1` env var to keep CI fast

## Used by
_(leaf — nothing depends on eval-harness)_

## Related concepts
- [[concepts/eval-baseline-workflow]]
- [[concepts/cost-quality-tradeoff]]

## Dependencies (external)
- [[dependencies/deepeval]]
- [[dependencies/pytest-evals]]
- [[dependencies/python-frontmatter]]
