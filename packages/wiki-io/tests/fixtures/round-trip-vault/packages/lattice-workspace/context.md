---
title: lattice-workspace — Context
category: package
summary: Background on why a shared workspace package exists — the per-repo-layout decision, the stdlib-only constraint, and the consolidation of path resolution that previously lived ad-hoc in each plugin.
updated: 2026-05-09
tokens: 1993
---

# lattice-workspace — Context

## Concepts

Before `lattice-workspace`, every plugin that touched per-repo state had to answer "where is the lattice workspace?" on its own:

- [[wiki/plugins/lattice-wiki/lattice-wiki]] had a `--wiki <path>` flag.
- [[wiki/plugins/lattice-graph/lattice-graph]] hard-coded `<repo>/.lattice/graph/code.db` paths in its update + query CLIs.
- `regenerate_work_index.py` ([[wiki/plugins/lattice-work/lattice-work]]) walked up looking for a vault on its own.
- `/curator:init` ([[wiki/plugins/lattice-curator/lattice-curator]]) needed to find the same root the other plugins had picked.

That ad-hoc fan-out caused two problems:

1. **Inconsistency.** Different plugins could resolve to different roots in odd corner cases (worktrees, nested repos, symlinks).
2. **No override seam.** Users who wanted the workspace somewhere other than `<repo>/lattice/` had to patch each plugin separately. The motivating use cases — multiple worktrees, faster scratch volumes, CI cache trees — were impossible without one source of truth.

`lattice-workspace` consolidates discovery into `resolve()`, exposes a single override (`.lattice.local.yaml: lattice-directory`), and gives every plugin the same six path accessors so subdirectory layout drifts only when the package changes.

### Foundational decisions

**Per-repo layout — `<repo>/wiki/` + `<repo>/.lattice/`**

The original ecosystem layout split human-visible vault (`<repo>/wiki/`) from machine state (`<repo>/.lattice/graph/code.db`). `lattice-workspace`'s default of `<repo>/lattice/` (no dot, single root) departs from that original design. The current implementation consolidates everything (wiki, work, knowledge, graph) under one workspace root. The relevant constants:

- `DEFAULT_WORKSPACE_NAME = "lattice"` — `packages/lattice-workspace/src/lattice_workspace/config.py:17`
- `graph_dir(workspace) = <workspace>/.graph` — `packages/lattice-workspace/src/lattice_workspace/paths.py:31`

**Stdlib-only constraint — relaxed in v0.3.0**

`lattice-workspace` sits at the bottom of the per-repo-data plugin dependency graph; every plugin in that tier transitively depends on it. From the package's inception through v1.2.x, `pyproject.toml` declared `dependencies = []` and the package hand-rolled flat-YAML parsing in `manifest.py` and `_local_config.py` to keep a per-repo plugin install dependency-free.

v0.3.0 traded that posture for parser correctness when the v2 manifest schema (nested dicts inside a list, including `null` values) outgrew what the hand-rolled parser could reasonably handle. The package now declares `dependencies = ["pyyaml>=6.0"]` and `manifest.py` uses `yaml.safe_load` / `yaml.safe_dump`. `_local_config.py` keeps its hand-rolled parser (it runs *before* the manifest is loaded and reads only one key); `init.py` still shells out to `git` via `subprocess` rather than depending on a git library. See [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]] for the trade-off rationale.

**Cross-plugin contract — idempotent init, subprocess-friendly**

`init()`'s contract — idempotent, exits cleanly, leaves a parseable manifest — is the per-repo-data-tier expression of [[wiki/concepts/lattice-cross-plugin-contract]]. Every plugin's `/<plugin>:init` calls in here; running them in any order, any number of times, converges on the same workspace state.

### Relationship to concept pages

- [[wiki/concepts/per-repo-layout]] — this is the conceptual page; `lattice-workspace` is its implementation.
- [[wiki/concepts/per-repo-data-vs-global-tooling-tier]] — `lattice-workspace` lives in the per-repo-data tier; it's the substrate every per-repo plugin builds on.
- [[wiki/concepts/lattice-vault-terminology]] — disambiguates "workspace" (the directory `lattice-workspace` resolves to), "vault" (`<workspace>/wiki/<vault>/`), and "repo" (the consumer's git tree).
- [[wiki/concepts/lattice-naming-convention]] — the package follows the convention: `lattice-` prefix, kebab-case, single purpose.

## Decisions

- [[wiki/adrs/0011-single-workspace-root]] — establishes the single `<repo>/lattice/` workspace root this package implements.
- [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]] — the v0.3.0 schema bump, `warn_if_stale` / `pending_updates` API, required `version=` kwarg on `init()`, and the explicit decision to accept PyYAML as a runtime dep on this foundational package (superseding the implicit stdlib-only posture).
- ADR-0017-stdlib-only-per-repo-tier — was originally mooted to mandate the zero-dependency posture (never written as an ADR; constraint lived only in `pyproject.toml` and patterns docs). Effectively superseded by ADR-0014.
- [[wiki/adrs/0010-lattice-curator-as-fifth-plugin]] — adds `knowledge_dir` as a first-class workspace child.

## Sources

- [[wiki/sources/2026-05-plans-specs-path-redesign]] — adopts `python -m lattice_workspace.config` as the workspace-resolution entry point for `lattice-workflows`'s brainstorming + writing-plans skills; relies on `.lattice.yaml` presence as the existence check.
- [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] — design spec for v0.3.0: v2 `.lattice.yaml` schema, `warn_if_stale` / `pending_updates` / `init(version=)` API, lazy v1→v2 coercion, PyYAML swap. Drove the major rewrite of `api.md` and `patterns.md` (both were stale against the shipped code).

## Belongs to domain

Per-repo data tier — the substrate layer that all per-repo plugins build on.

## Used by

| Consumer | Imports | Use |
|---|---|---|
| [[wiki/packages/lattice-graph-core/lattice-graph-core]] | `paths.graph_dir` | locate `<workspace>/.graph/code.db` for the SQLite store |
| [[wiki/plugins/lattice-curator/lattice-curator]] | `init`, `paths.knowledge_dir` | `/curator:init` bootstraps the workspace and seeds `<workspace>/knowledge/` |
| [[wiki/plugins/lattice-work/lattice-work]] | `config.resolve` | `regenerate_work_index.py` auto-discovers the workspace when `--vault` isn't passed |
| [[wiki/plugins/lattice-workflows/lattice-workflows]] | `python -m lattice_workspace.config` (subprocess) | `brainstorming` and `writing-plans` skills resolve the workspace before writing specs/plans into `<workspace>/{specs,plans}/`; falls back to `Path("lattice").resolve()` and asserts `.lattice.yaml` exists per [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]] |

[[wiki/plugins/lattice-wiki/lattice-wiki]] does not (yet) import `lattice-workspace`. Its CLI takes `--wiki <path>` directly. Migrating it is a likely follow-up — see [[wiki/packages/lattice-workspace/work]].

## Related dependencies

- No runtime dependencies (`dependencies = []` in `pyproject.toml`).
- Dev/test: `pytest` only.
- Consumed as a uv workspace path-dep by [[wiki/packages/lattice-graph-core/lattice-graph-core]], [[wiki/packages/lattice-wiki-core/lattice-wiki-core]], and [[wiki/packages/lattice-source-parser/lattice-source-parser]].

## History

- 2026-05-08 — `.lattice.yaml` initialized in this repo at version 1; workspace pinned at `<repo>/lattice/`.
- 2026-05-09 — Wiki pages fleshed out from source code; contradictions vs. original per-repo layout ADR flagged in [[wiki/packages/lattice-workspace/work]].
- 2026-05-09 (v0.3.0) — Manifest schema bumps to v2 (per-plugin `installed_version` / `applied_version`); `init()` gains required `version=` kwarg; new `warn_if_stale` / `pending_updates` / `PendingUpdate` surface in `versions.py`; PyYAML replaces the hand-rolled YAML reader. Stdlib-only posture is no longer in force. Reference plugin integration: `lattice-wiki` via `_version_check.py`. See [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]].
