---
title: lattice-evals
category: package
summary: Reproducible evaluation harness for Lattice Claude Code plugins — runs scenarios × configs × runs to measure plugin uplift via three isolation axes and three verifier kinds. Exposes the `lattice-eval` CLI.
status: active
package_path: packages/lattice-evals
package_type: library
domain:
language: Python
depends_on: []
tags:
  - python
  - evals
  - harness
  - cli
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 1819
---

# lattice-evals

## Purpose

Reproducible evaluation harness for the Lattice Claude Code plugins. The Python package lives at `packages/lattice-evals/`; the runtime data it operates on — `scenarios/`, `configs/`, `runsets/`, `runs/`, `reports/` — lives in the repo-root `evals/` directory. This split keeps the installable library separate from the data it processes. The CLI entry point is `lattice-eval`; the `--evals-root` flag (or `LATTICE_EVALS_ROOT` env var, or `cwd`) tells every subcommand where to find the data root.

## File map - lattice-evals

Root package directory containing the installable Python library, build config, and documentation.

- `.gitignore` — Ignores build artifacts and virtual environments for this package.
- `pyproject.toml` — Defines the `lattice-evals` package metadata, dependencies, and the `lattice-eval` CLI entry point.
- `README.md` — Usage guide covering installation, CLI subcommands, scenario authoring, and v1 limitations.

### lattice-evals/src/

Python source root; contains the single `lattice_evals` importable package.

#### lattice-evals/src/lattice_evals/

Core evaluation harness — CLI, orchestrator, runner, transcript parser, metrics, verifiers, and report generation.

- `__init__.py` — Exposes the package version string (`__version__ = "0.1.1"`).
- `cli.py` — CLI entry point implementing the `lattice-eval` command group (`list`, `show`, `run`, `report`, `verify` subcommands).
- `isolation.py` — Implements `IsolationContext`, which sets up a per-run git worktree, fresh `CLAUDE_CONFIG_DIR`, and plugin symlinks for hermetic runs.
- `judge.py` — Thin wrapper around `claude -p --output-format stream-json` for synchronous LLM judge calls, returning text and token usage.
- `metrics.py` — Computes tier A/B metrics (token counts, cost, wall time, tool-call shape) from a parsed transcript and verifier rollup.
- `orchestrator.py` — Coordinates one `(scenario × config)` run: sets up isolation, runs preflight, dispatches the headless or interactive runner, collects verifier outcomes, and writes `metrics.json`/`verify.json`/`meta.json`.
- `pricing.py` — Hardcoded per-model token pricing table and `cost_for_usage` helper; manually updated when Anthropic changes prices.
- `qualitative.py` — Optional tier C: prompts an LLM judge to score a transcript on named axes and returns a dict of 1–5 scores.
- `report.py` — Builds per-runset Markdown and JSON reports by loading run metrics and rendering the Jinja2 template.
- `runner_headless.py` — Spawns `claude -p` in stream-json mode, streams output to transcript and log files, and manages multi-turn `AutoUser` reply selection via trigger rules or an LLM simulator.
- `schemas.py` — Pydantic models for all YAML data files: `Scenario`, `Config`, `AutoUser`, `Runset`, `Budgets`, `VerifyEntry`, and trigger types.
- `transcript.py` — Parses `claude -p` stream-json JSONL into a typed `Transcript` dataclass, aggregating token usage, tool calls, file paths, and skill invocations.
- `user_simulator.py` — LLM-as-user reply generator for multi-turn scenarios; calls `judge.run_judge` with a persona system prompt to produce the next user message (or `<DONE>` to end the conversation).

##### lattice-evals/src/lattice_evals/templates/

Jinja2 templates used for rendering eval output.

- `report.md.j2` — Jinja2 template for the per-runset Markdown report, rendering a summary table, per-scenario metric tables, callouts, and run links.

##### lattice-evals/src/lattice_evals/verify/

Verifier implementations (script, golden patch, and rubric) plus the shared protocol and outcome type.

- `__init__.py` — Re-exports `VerifyOutcome` and `Verifier` as the subpackage's public surface.
- `base.py` — Defines the `VerifyOutcome` dataclass and the `Verifier` Protocol that all verifier implementations satisfy.
- `golden.py` — Implements `GoldenVerifier`, which compares the worktree's post-run `git diff` against a stored golden patch to determine pass/fail.
- `rubric.py` — Implements `RubricVerifier`, which sends a redacted transcript and the worktree diff to an LLM judge with a prose rubric, parses a 0–5 score, and passes if the score meets the threshold.
- `script.py` — Implements `ScriptVerifier`, which executes a shell script inside the worktree and passes if the exit code is zero.

### lattice-evals/tests/

Unit and integration tests for all core modules; uses `pytest`.

- `conftest.py` — Shared pytest fixtures and configuration for the test suite.
- `test_cli.py` — Unit tests for `cli.py`.
- `test_isolation.py` — Unit tests for `isolation.py`.
- `test_metrics.py` — Unit tests for `metrics.py`.
- `test_orchestrator.py` — Unit tests for `orchestrator.py`.
- `test_pricing.py` — Unit tests for `pricing.py`.
- `test_qualitative.py` — Unit tests for `qualitative.py`.
- `test_report.py` — Unit tests for `report.py`.
- `test_runner_headless.py` — Unit tests for `runner_headless.py`.
- `test_schemas.py` — Unit tests for `schemas.py`.
- `test_smoke.py` — End-to-end smoke tests verifying basic CLI invocations work without errors.
- `test_transcript.py` — Unit tests for `transcript.py`.
- `test_user_simulator.py` — Unit tests for `user_simulator.py`.
- `test_verify_golden.py` — Unit tests for `verify/golden.py`.
- `test_verify_rubric.py` — Unit tests for `verify/rubric.py`.
- `test_verify_script.py` — Unit tests for `verify/script.py`.

#### lattice-evals/tests/fixtures/

Static YAML and JSONL files used as test inputs for schema validation and runner tests.

- `auto_user_valid.yaml` — Valid `AutoUser` fixture with triggers and a default reply for runner tests.
- `auto_user_with_simulator.yaml` — Valid `AutoUser` fixture with a `user_model` block set for simulator tests.
- `config_valid.yaml` — Valid config fixture for orchestrator and isolation tests.
- `multi_turn_stdin.jsonl` — Fixture of stream-json stdin messages for multi-turn headless runner tests.
- `multi_turn_stdout.jsonl` — Fixture of stream-json stdout events for multi-turn headless runner tests.
- `runset_valid.yaml` — Valid runset definition fixture for report and CLI tests.
- `sample_stream.jsonl` — Sample stream-json transcript fixture for transcript parser tests.
- `scenario_missing_baseline.yaml` — Invalid scenario fixture (missing `baseline_sha`) for schema validation error tests.
- `scenario_valid.yaml` — Valid scenario definition fixture for schema and orchestrator tests.

## Sub-pages

- [[packages/lattice-evals/api]]      — public API, CLI subcommands, module layout
- [[packages/lattice-evals/patterns]] — key patterns, isolation axes, verifier kinds, tooling
- [[packages/lattice-evals/work]]     — bugs, tech debt, features, open questions
- [[packages/lattice-evals/context]]  — concepts, decisions, ADRs, sources
