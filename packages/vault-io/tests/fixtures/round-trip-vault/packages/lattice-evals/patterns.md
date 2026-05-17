---
title: lattice-evals — Patterns
category: package
summary: Key patterns, tooling, and dependency notes for lattice-evals
updated: 2026-05-09
tokens: 616
---

# lattice-evals — Patterns

## Key patterns

- **Data/code split** — installable library under `packages/lattice-evals/`; scenario data stays at `evals/` in the repo root. The CLI resolves the data root via `--evals-root`, `LATTICE_EVALS_ROOT`, or `cwd`.
- **Three isolation axes** — (1) `git worktree add` at `baseline_sha`; (2) remove wiki when `config.includes_wiki: false`; (3) fresh `CLAUDE_CONFIG_DIR` tmpdir per run with only the config's plugins.
- **Isolation per run** — `isolation.py` builds an empty `CLAUDE_CONFIG_DIR` per run; auth is passed via `CLAUDE_CODE_OAUTH_TOKEN`.
- **Scenario directory shape** — `evals/scenarios/<slug>/` contains `scenario.yaml`, `prompt.md`, optional `auto_user.yaml`, `verify.sh`, `golden.patch`, `rubric.md`, and `preflight.sh`.
- **Configs as named plugin combinations** — `evals/configs/<name>.yaml` pins `plugins`, `includes_wiki`, `model`, `temperature`. The v1 4-config matrix: `base`, `workflows`, `wiki`, `workflows+wiki`.
- **Runset = batch of scenarios → one report** — `evals/runsets/<name>.yaml` lists scenarios; produces `evals/reports/<YYYY-MM-DD>-<runset>.{md,json}`.
- **Three verifier kinds with AND rollup** — `script` (exit 0 = pass), `golden` (semantic diff), `rubric` (LLM judge).
- **Pinned Haiku judge** — `claude-haiku-4-5-20251001` for cross-report comparability; input is rubric + redacted transcript.
- **Tiered metrics** — Tier A: tokens, cost, time, turns, success; Tier B: tool-call shape; Tier C: LLM-judge scores (opt-in).
- **Pure pydantic schemas** — `schemas.py` drives all serialization.
- **uv workspace member** — single root `uv.lock`; ruff config and `.python-version` are root-only.

## Conventions

- Each scenario dir is self-contained: prompt, auto_user, verifiers, and preflight all live together under `evals/scenarios/<slug>/`.
- Verifier outcomes are AND-rolled up: all verifiers must pass for a run to count as passing.
- Tier C qualitative scoring is opt-in per runset; tiers A and B run unconditionally.
- Pricing constants in `pricing.py` are manually maintained; update whenever Anthropic changes model costs.
