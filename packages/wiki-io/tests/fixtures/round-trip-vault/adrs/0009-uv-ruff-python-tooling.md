---
title: "ADR-0009: uv workspace + ruff as Python tooling standard across `packages/`"
category: adr
summary: All Python packages under packages/ are members of a single uv workspace with a root-level pyproject.toml (workspace coordinator, no [project] table) and a single uv.lock; ruff is the lint+format tool with root-only config; pytest is the test runner; Python 3.12 pinned via .python-version.
adr_id: "0009"
status: accepted
decision_date: 2026-05-07
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [adr, packages, python-tooling, uv, ruff, pytest, monorepo]
updated: 2026-05-07
tokens: 677
---

# ADR-0009: uv workspace + ruff as Python tooling standard across `packages/`

**Status:** accepted (2026-05-07) — implemented

## Context

`packages/` hosts multiple Python libraries — currently [[wiki/packages/lattice-source-parser/lattice-source-parser]] and [[wiki/packages/lattice-evals/lattice-evals]], with more expected. Without a shared tooling standard, each package would pick its own resolver (pip / poetry / pdm / hatch), its own lint/format stack (black / ruff / flake8 / isort), and its own test runner — fragmenting CI, contributor onboarding, and developer ergonomics. A monorepo-friendly tool that locks once and resolves cross-package deps natively was needed.

## Decision

All Python packages under `packages/` are members of a **single uv workspace**:

- A **root-level `pyproject.toml`** acts as workspace coordinator and declares `[tool.uv.workspace]` members. The root file has **no `[project]` table** — it is not itself a publishable package.
- A **single `uv.lock`** at the repo root locks resolution for the entire workspace.
- **ruff** is the lint and format tool, configured **root-only** (per-package config files are not allowed).
- **pytest** is the test runner.
- **Python 3.12** is pinned via a root-level `.python-version`.

## Consequences

- One resolver invocation locks the entire workspace; cross-package dev installs are coherent.
- ruff's root-only config means style is uniform across `packages/` — no drift, no per-package overrides to audit.
- Contributors onboard with `uv sync` from the repo root and have a working environment for every package.
- The repo CLAUDE.md's existing prescription of `pytest` is now consistent with the standard (resolves prior ambiguity around test runners).
- Plugins under `plugins/` that take Python deps (e.g. `lattice-graph`) are **not** workspace members — they have their own packaging story per Claude Code plugin conventions; the workspace standard is local to `packages/`.
- Migrating a package to the workspace requires removing per-package lockfiles and lint configs; the migration is one-time and tracked.

## Related

- [[wiki/packages/lattice-source-parser/lattice-source-parser]]
- [[wiki/packages/lattice-evals/lattice-evals]]
