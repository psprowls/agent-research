---
title: lattice-evals — API
category: package
summary: Public API and module layout for lattice-evals
updated: 2026-05-09
tokens: 571
---

# lattice-evals — API

## Public API

CLI: `lattice-eval [--evals-root <path>] <subcommand>`

Key modules under `src/lattice_evals/`:

- `cli.py` — Click-based CLI entry point; exposes `list`, `show`, `run`, `report`, `verify` subcommands.
- `orchestrator.py` — Drives scenario runs end-to-end: isolation setup, preflight, runner dispatch, verifier collection, artifact writing.
- `runner_headless.py` — Invokes `claude -p` as a subprocess in stream-json mode; manages multi-turn `AutoUser` reply selection via trigger rules or LLM simulator.
- `judge.py` — Thin wrapper around `claude -p --output-format stream-json` for synchronous LLM judge calls; returns text and token usage.
- `metrics.py` — Cost, token, and timing aggregation (tier A/B metrics) from a parsed transcript and verifier rollup.
- `schemas.py` — Pydantic models for all YAML data files: `Scenario`, `Config`, `AutoUser`, `Runset`, `Budgets`, `VerifyEntry`, and trigger types.
- `isolation.py` — `IsolationContext`: sets up per-run git worktree, fresh `CLAUDE_CONFIG_DIR`, and plugin symlinks for hermetic runs.
- `transcript.py` — Parses `--output-format stream-json` JSONL into a typed `Transcript` dataclass; aggregates token usage, tool calls, file paths, and skill invocations.
- `qualitative.py` — Optional tier C qualitative scoring: prompts an LLM judge on named axes (e.g. `plan_following`, `citation_use`), returns a dict of 1–5 scores.
- `pricing.py` — Hardcoded per-model token pricing table and `cost_for_usage` helper.
- `report.py` — Builds per-runset Markdown and JSON reports by loading run metrics and rendering the Jinja2 template.

### Verifier subpackage (`verify/`)

- `base.py` — `VerifyOutcome` dataclass and `Verifier` Protocol.
- `script.py` — `ScriptVerifier`: executes a shell script inside the worktree; passes on exit code 0.
- `golden.py` — `GoldenVerifier`: compares post-run `git diff` against a stored golden patch.
- `rubric.py` — `RubricVerifier`: sends redacted transcript + worktree diff to an LLM judge with a prose rubric; passes if score ≥ threshold.
