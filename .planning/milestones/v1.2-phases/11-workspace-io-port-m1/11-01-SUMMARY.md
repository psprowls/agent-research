---
phase: 11-workspace-io-port-m1
plan: 01
subsystem: packaging
tags: [scaffold, uv-workspace, hatchling]
requires: []
provides:
  - workspace-io package skeleton (importable, empty)
  - workspace-io member in uv.lock
affects:
  - uv.lock (added workspace-io entry)
tech-stack:
  added:
    - hatchling (build backend, transitive — first hatchling consumer at scaffold time)
    - pyyaml>=6.0 (declared as runtime dep; already present in workspace closure)
  patterns:
    - hatchling build backend (departs from uv_build used elsewhere — required to auto-include assets/ subdir)
    - "[tool.hatch.build.targets.wheel] packages = [\"src/workspace_io\"]"
    - "[tool.pytest.ini_options] addopts = \"--import-mode=importlib\""
key-files:
  created:
    - packages/workspace-io/pyproject.toml
    - packages/workspace-io/src/workspace_io/__init__.py
    - packages/workspace-io/src/workspace_io/assets/.gitkeep
    - packages/workspace-io/tests/.gitkeep
    - packages/workspace-io/README.md
  modified:
    - uv.lock
decisions:
  - "Use hatchling (not uv_build) for workspace-io to auto-include assets/CLAUDE.md.template"
  - "Defer `__init__.py` re-exports to Plan 02 (no symbols exist yet)"
  - "Root pyproject.toml unchanged — `packages/*` glob already covers the new member"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_changed: 6
  completed_date: 2026-05-18
---

# Phase 11 Plan 01: workspace-io Scaffold Summary

Scaffolded a new `packages/workspace-io/` uv workspace member using the hatchling build backend; `uv sync` discovers it and `import workspace_io` succeeds under `uv run --package workspace-io`.

## What Was Built

- `packages/workspace-io/pyproject.toml` — hatchling backend, `name = "workspace-io"`, `version = "0.1.0"`, `requires-python = ">=3.11"`, `dependencies = ["pyyaml>=6.0"]`, `[tool.hatch.build.targets.wheel] packages = ["src/workspace_io"]`, pytest config with `--import-mode=importlib`.
- `packages/workspace-io/src/workspace_io/__init__.py` — minimal docstring-only module. Re-exports intentionally deferred to Plan 02 once `config`, `init`, and `versions` modules exist.
- `packages/workspace-io/src/workspace_io/assets/.gitkeep` — placeholder for the upcoming `CLAUDE.md.template` (Plan 03).
- `packages/workspace-io/tests/.gitkeep` — placeholder for tests (Plans 02-05).
- `packages/workspace-io/README.md` — points back to the lattice-workspace source and the phase 11 plan tree for provenance.

## Verification Results

- `test -f packages/workspace-io/pyproject.toml` → pass
- `test -f packages/workspace-io/src/workspace_io/__init__.py` → pass
- `grep -q 'name = "workspace-io"' packages/workspace-io/pyproject.toml` → pass
- `grep -q 'hatchling.build' packages/workspace-io/pyproject.toml` → pass
- `grep -c 'uv_build' packages/workspace-io/pyproject.toml` → `0` (RESEARCH anti-pattern avoided)
- `git diff pyproject.toml` (root) → empty (no edits)
- `uv sync` → exit 0; output line: `+ workspace-io==0.1.0 (from file:///.../packages/workspace-io)`
- `uv run --package workspace-io python -c "import workspace_io; print(workspace_io.__doc__)"` → prints docstring
- `uv run --package workspace-io pytest --collect-only` → exit 5 (no tests collected, expected)
- `grep -c 'name = "workspace-io"' uv.lock` → `1`

## Commits

| Task | Commit  | Description                                              |
| ---- | ------- | -------------------------------------------------------- |
| 1    | f8d34f7 | feat(11-01): scaffold workspace-io package skeleton      |
| 2    | 9eba716 | chore(11-01): record workspace-io in uv.lock after uv sync |

## Decisions Made

1. **hatchling over uv_build for this package.** Every other agent-research workspace member uses `uv_build`. workspace-io diverges because subsequent plans ship `assets/CLAUDE.md.template` inside the package; hatchling auto-includes any subdirectory of `src/workspace_io/` in the wheel without extra `[tool.hatch.build] include` or `package-data` configuration. The RESEARCH.md anti-pattern call-out ("do NOT use `uv_build` despite other packages using it") is honored.
2. **Empty `__init__.py` for this plan.** PATTERNS.md prescribes a re-export block referencing `config`, `init`, and `versions` modules — none of which exist yet. Adding the imports now would break `uv sync` resolution. Re-exports are added in Plan 02 after the modules land.
3. **No root `pyproject.toml` edit.** The existing `[tool.uv.workspace] members = ["packages/*", "agents/*"]` glob already discovers `packages/workspace-io/`. Per the plan's `<action>` and `<acceptance_criteria>`, leaving the root unchanged is the correct outcome.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

None — this plan only adds scaffolding files. No new trust boundaries, network endpoints, auth paths, or file-access patterns introduced. T-11-01 (hatchling tampering) and T-11-SC (supply chain) accepted in plan; no new third-party packages beyond `pyyaml>=6.0` (already in workspace closure) and `hatchling` (already a transitive build dep of `model-adapter`).

## Requirements Satisfied

- **WS-01** — workspace member exists at `packages/workspace-io/` with `pyproject.toml`, `src/workspace_io/`, and `tests/` directories; `uv sync` resolves it.

## Phase 11 Success Criterion Progress

- **SC #1 (uv sync resolves workspace-io and tests pass)** — partially satisfied. `uv sync` resolves cleanly; the "tests pass" half of SC #1 lands in Plans 02-05 once source modules and tests are ported.

## Next Plan

Plan 02 ports the leaf utility modules (`_local_config.py`, `paths.py`) plus their tests; the `__init__.py` re-export block is added once the dependent modules exist (`config`, `init`, `versions` land in later plans).

## Self-Check: PASSED

- Created files verified on disk:
  - FOUND: packages/workspace-io/pyproject.toml
  - FOUND: packages/workspace-io/src/workspace_io/__init__.py
  - FOUND: packages/workspace-io/src/workspace_io/assets/.gitkeep
  - FOUND: packages/workspace-io/tests/.gitkeep
  - FOUND: packages/workspace-io/README.md
- Commits verified in git log:
  - FOUND: f8d34f7
  - FOUND: 9eba716
