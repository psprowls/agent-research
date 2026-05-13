---
title: lattice-evals — Context
category: package
summary: Concepts, decisions, sources, and history for lattice-evals
updated: 2026-05-09
tokens: 338
---

# lattice-evals — Context

## Concepts

- [[wiki/concepts/claude-code-auto-memory-isolation]] — isolation approach used by the harness runner
- [[wiki/concepts/prompt-caching]] — cache warmth affects cost metrics across scenario runs

## Decisions

- [[wiki/adrs/0009-uv-ruff-python-tooling]] — workspace member under the root `uv.lock`; ruff config and `.python-version` are root-only

## Sources

- 2026-05-eval-harness-design — design spec for the harness: architecture, isolation axes, verifier kinds, tiered metrics, CLI surface.
- 2026-05-eval-scenarios-v1-design — companion spec for the v1 scenario suite (7 scenarios, 4-config matrix, preflight.sh, rubric verifier).
- 2026-05-uv-ruff-monorepo-design — establishes the uv workspace + ruff + pytest standard; this package is a workspace member.

## Belongs to domain

(none)

## Used by

(none recorded — this is the eval harness itself)

## Related dependencies

- `pydantic>=2.6` — schema validation
- `click>=8.1` — CLI framework
- `jinja2>=3.1` — report templating
- `rich>=13.7` — terminal output
- `pyyaml>=6.0` — scenario/config parsing
