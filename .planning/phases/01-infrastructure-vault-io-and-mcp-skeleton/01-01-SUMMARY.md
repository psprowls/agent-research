---
phase: 01-infrastructure-vault-io-and-mcp-skeleton
plan: 01
subsystem: infra
tags: [uv, workspace, ruff, pre-commit, github-actions, typer, mit-license]

# Dependency graph
requires: []
provides:
  - uv workspace root with members=["cores/*","agents/*"] and a single committed uv.lock
  - cores/vault-io skeleton (deps: python-frontmatter, tiktoken) pending Plan 01-02 fill-in
  - cores/model-adapter skeleton (deps: langchain-aws, boto3) pending Plan 01-03 fill-in
  - agents/code-wiki-agent skeleton with working `code-wiki-agent --help` CLI
  - code-wiki-mcp entry point pre-declared in pyproject (server.py lands in Plan 01-04)
  - GitHub Actions CI (ruff + per-member pytest) + eval workflow stub
  - MIT LICENSE, README, .gitignore, ruff pre-commit hooks
  - CLAUDE.md and REQUIREMENTS.md aligned with D-01 (cores/) and D-14 (code-wiki-mcp)
affects: [01-02-vault-io, 01-03-model-adapter, 01-04-mcp-skeleton]

# Tech tracking
tech-stack:
  added:
    - uv 0.11.14 (workspace tooling)
    - uv_build >=0.11.14,<0.12 (build backend)
    - ruff >=0.15 + ruff-format (lint + format, pre-commit + CI)
    - pytest >=8.3 + pytest-asyncio 1.3.0 + syrupy 5.1.0 (test stack)
    - typer 0.25.1 (CLI scaffolding)
    - python-frontmatter >=1.1, tiktoken >=0.7 (vault-io deps, declared only)
    - langchain-aws >=1.4.6, boto3 >=1.38 (model-adapter deps, declared only)
    - mcp >=1.27.1, pydantic >=2.0 (agent deps, declared only)
  patterns:
    - "Tiered workspace: cores/ for libraries, agents/ for user-facing packages"
    - "Per-member pyproject with testpaths=['tests'] for collection isolation"
    - "Workspace deps via [tool.uv.sources] X = { workspace = true }"
    - "Build backend uv_build for every member (replaces hatchling/setuptools)"
    - "Pre-declared [project.scripts] entry points so future plans only add module impl"
    - "from __future__ import annotations as first import in every new Python file"
    - "ruff config excludes **/fixtures/** so committed vault snapshots aren't linted"

key-files:
  created:
    - pyproject.toml
    - .python-version
    - .gitignore
    - LICENSE
    - README.md
    - .pre-commit-config.yaml
    - .github/workflows/ci.yml
    - .github/workflows/eval.yml
    - cores/vault-io/pyproject.toml
    - cores/vault-io/src/vault_io/__init__.py
    - cores/vault-io/tests/__init__.py
    - cores/model-adapter/pyproject.toml
    - cores/model-adapter/src/model_adapter/__init__.py
    - cores/model-adapter/tests/__init__.py
    - agents/code-wiki-agent/pyproject.toml
    - agents/code-wiki-agent/src/code_wiki_agent/__init__.py
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py
    - agents/code-wiki-agent/src/code_wiki_mcp/__init__.py
    - agents/code-wiki-agent/tests/__init__.py
    - agents/code-wiki-agent/tests/unit/__init__.py
    - agents/code-wiki-agent/tests/unit/test_cli_help.py
    - agents/code-wiki-agent/tests/integration/__init__.py
    - uv.lock
  modified:
    - CLAUDE.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "CI uses `uv run --directory <pkg-path> pytest` instead of `uv run --package <pkg> pytest` because uv 0.11 does not chdir on --package, which would let pytest's rootdir resolve to the workspace root and ignore per-member testpaths (violating INFRA-03)."
  - "code-wiki-mcp entry point is pre-declared in agents/code-wiki-agent/pyproject.toml even though code_wiki_mcp/server.py does not yet exist (D-14). Plan 01-04 only needs to add the implementation, not edit pyproject scripts."
  - "Build backend uv_build pinned to >=0.11.14,<0.12 for every member to match workspace tooling and avoid hatchling-vs-uv_build interop surprises."

patterns-established:
  - "Tier separation: cores/ (libraries) vs agents/ (delivery surfaces)"
  - "Per-member pytest isolation via testpaths in each member pyproject"
  - "[tool.uv.sources] for workspace deps; deps named bare in [project.dependencies]"
  - "Pre-declared [project.scripts] entry points (forward-compat with future plans)"

requirements-completed: [INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06]

# Metrics
duration: 5min
completed: 2026-05-13
---

# Phase 01 Plan 01: Workspace Bootstrap + Hygiene + CLI Stub Summary

**uv workspace with three members (cores/vault-io, cores/model-adapter, agents/code-wiki-agent), MIT-licensed hygiene scaffolding, GitHub Actions CI with per-member pytest isolation, and a working `uv run code-wiki-agent --help`.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-13T17:15:46Z
- **Completed:** 2026-05-13T17:20:34Z
- **Tasks:** 3
- **Files created:** 23
- **Files modified:** 2

## Accomplishments

- `uv sync` from a fresh worktree exits 0 and produces a single workspace-root `uv.lock` (81 resolved packages)
- `uv run code-wiki-agent --help` exits 0 and prints help text mentioning the program name (INFRA-06)
- Per-member pytest isolation works: `uv run --directory cores/vault-io pytest --collect-only` collects 0 tests; `uv run --directory agents/code-wiki-agent pytest --collect-only` collects only the cli-help test (INFRA-03)
- Open-source hygiene shipped: MIT LICENSE, README, .gitignore, `.pre-commit-config.yaml` (ruff + ruff-format v0.15.12), `.github/workflows/ci.yml` (push + PR), eval workflow stub for Phase 4
- CLAUDE.md tier name aligned with D-01 (no remaining deep-agents-tier `packages/*` references); REQUIREMENTS.md MCP-07 launch command amended to `code-wiki-mcp` with D-14 provenance note
- `code-wiki-mcp` entry point pre-declared so Plan 01-04 only needs to add the server module

## Task Commits

1. **Task 1: Scaffold uv workspace root + hygiene + CI** — `29666a3` (feat)
2. **Task 2: Scaffold three workspace members + CLI stub + cli-help test** — `36c007c` (feat)
3. **Task 3: Fix CLAUDE.md packages→cores and REQUIREMENTS MCP-07** — `dfa64a6` (docs)

## Files Created/Modified

### Workspace root
- `pyproject.toml` — members=["cores/*","agents/*"], no [project] table, ruff (line-length 120, fixtures excluded, lint E/F/I), dev deps (pytest, pytest-asyncio, ruff, pre-commit, syrupy)
- `.python-version` — `3.11`
- `.gitignore` — Python, uv, env, IDE, OS; uv.lock intentionally not ignored (INFRA-02)
- `LICENSE` — MIT, Copyright 2026 Patrick Sprowls
- `README.md` — quickstart + workspace layout + license note
- `.pre-commit-config.yaml` — astral-sh/ruff-pre-commit v0.15.12 (ruff --fix + ruff-format)
- `.github/workflows/ci.yml` — setup-uv@v5 pinned 0.11.14, uv sync, ruff check, ruff format --check, per-member pytest via `--directory`
- `.github/workflows/eval.yml` — workflow_dispatch stub printing a Phase-4-deferred message
- `uv.lock` — committed; 81 resolved packages

### cores/vault-io
- `pyproject.toml` — name=vault-io, deps=python-frontmatter+tiktoken, uv_build backend, per-member testpaths
- `src/vault_io/__init__.py` — empty (Plan 01-02 fills)
- `tests/__init__.py` — empty

### cores/model-adapter
- `pyproject.toml` — name=model-adapter, deps=langchain-aws+boto3, uv_build backend, per-member testpaths
- `src/model_adapter/__init__.py` — empty (Plan 01-03 fills)
- `tests/__init__.py` — empty

### agents/code-wiki-agent
- `pyproject.toml` — name=code-wiki-agent; deps include workspace edges to vault-io/model-adapter via [tool.uv.sources]; [project.scripts] declares both `code-wiki-agent` and `code-wiki-mcp`; integration marker registered
- `src/code_wiki_agent/__init__.py` — empty
- `src/code_wiki_agent/cli.py` — Typer app `app` with `version` subcommand; `no_args_is_help=True`; `from __future__ import annotations` first
- `src/code_wiki_mcp/__init__.py` — empty (Plan 01-04 adds server.py)
- `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py` — empty package markers
- `tests/unit/test_cli_help.py` — subprocess test asserting `uv run code-wiki-agent --help` exits 0 with program name in stdout

### Modified
- `CLAUDE.md` — three `packages/` deep-agents-tier references replaced with `cores/` (lattice analog paths untouched)
- `.planning/REQUIREMENTS.md` — MCP-07 launch command `code-wiki-agent-mcp` → `code-wiki-mcp` with D-14 provenance note

## uv.lock Member Resolution

The committed `uv.lock` resolves all three workspace members as editable packages:

```
name = "code-wiki-agent"
name = "model-adapter"
name = "vault-io"
```

Verified via `grep -E '^name = "(vault-io|model-adapter|code-wiki-agent)"' uv.lock` — all three present.

## `code-wiki-agent --help` Stdout Snippet

```
 Usage: code-wiki-agent [OPTIONS]

 Print version and exit.

 Options
 --install-completion          Install completion for the current shell.
 --show-completion             Show completion for the current shell, to copy
                               it or customize the installation.
 --help                        Show this message and exit.
```

(Typer collapses help to the single `version` subcommand body; the Usage line still contains the program name, satisfying INFRA-06's "prints help text mentioning the program name" truth.)

## Decisions Made

1. **CI invokes pytest with `uv run --directory <pkg-path>` instead of `--package`** — see Deviations.
2. **`code-wiki-mcp` entry point pre-declared in pyproject** — matches plan intent so Plan 01-04 only edits the module, not the script registration.
3. **`uv_build` build backend on every member** — matches plan PATTERNS.md; lattice analog used `hatchling`, swapped per plan instruction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CI pytest invocation changed from `--package` to `--directory`**
- **Found during:** Task 2 (verifying `uv run --package vault-io pytest --collect-only` only collects vault-io tests)
- **Issue:** Plan's CI workflow and the truth "uv run --package vault-io pytest --collect-only collects only vault-io tests" assume `uv run --package <pkg> pytest` changes cwd into the package directory. uv 0.11 (0.11.7 locally, 0.11.14 pinned in CI) does not chdir on `--package` — it only narrows dependency resolution scope. With cwd at workspace root, pytest's rootdir algorithm resolves to the workspace-root pyproject (which has `[tool.pytest.ini_options]` but no `testpaths`), so pytest falls back to recursive discovery from cwd and collects whichever member happens to have tests on disk (in Phase 1, only `agents/code-wiki-agent/tests/`). Violates INFRA-03.
- **Fix:** Updated `.github/workflows/ci.yml` to invoke pytest as `uv run --directory <pkg-path> pytest`. The `--directory` global flag does chdir, which lets each member's `pyproject.toml` `[tool.pytest.ini_options]` drive discovery. Per-member testpaths themselves are unchanged.
- **Files modified:** `.github/workflows/ci.yml`
- **Verification:** `uv run --directory cores/vault-io pytest --collect-only` reports `collected 0 items`; `uv run --directory agents/code-wiki-agent pytest --collect-only` reports the single cli-help test; the previously failing `uv run --package vault-io pytest --collect-only` mis-collection is gone.
- **Committed in:** `36c007c` (folded into the Task 2 commit since it was discovered while verifying Task 2 acceptance)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Plan's per-member isolation intent is preserved; only the invocation pattern changed. All INFRA-01..06 acceptance criteria still pass. The plan truth "uv run --package vault-io pytest --collect-only collects only vault-io tests" should be re-stated in future docs as "uv run --directory cores/vault-io pytest --collect-only" — flagging for orchestrator's STATE.md decisions log.

## Issues Encountered

- Local `uv` is 0.11.7 (Homebrew); CI pins `setup-uv@v5` to `0.11.14`. The `[build-system]` requires `uv_build>=0.11.14,<0.12`, which uv pulls in itself, so the local-vs-CI version skew on the *tool* is non-blocking for the build backend.
- Typer collapses help output when only a single `@app.command()` exists; "Usage: code-wiki-agent" is still present in stdout, so the cli-help test passes. Future plans adding subcommands will see the full multi-command help layout.

## User Setup Required

None — workspace is fresh-clone-ready. `uv sync && uv run code-wiki-agent --help` works without any AWS credentials (Bedrock calls land in Plan 01-03 onward).

## Next Phase Readiness

- **Plan 01-02 (vault-io)** unblocked: `cores/vault-io/src/vault_io/` is empty and ready for the verbatim ports per PATTERNS.md.
- **Plan 01-03 (model-adapter)** unblocked: `cores/model-adapter/src/model_adapter/` is empty and `models.toml` location at the package root is reserved.
- **Plan 01-04 (mcp-skeleton)** unblocked: `code-wiki-mcp` entry point is pre-declared in pyproject; 01-04 only adds `src/code_wiki_mcp/server.py` with the `_StdoutGuard` + FastMCP wiring.

## Self-Check

Files claimed:
- `pyproject.toml` — FOUND
- `.python-version` — FOUND
- `LICENSE` — FOUND
- `README.md` — FOUND
- `.gitignore` — FOUND
- `.pre-commit-config.yaml` — FOUND
- `.github/workflows/ci.yml` — FOUND
- `.github/workflows/eval.yml` — FOUND
- `cores/vault-io/pyproject.toml` — FOUND
- `cores/model-adapter/pyproject.toml` — FOUND
- `agents/code-wiki-agent/pyproject.toml` — FOUND
- `agents/code-wiki-agent/src/code_wiki_agent/cli.py` — FOUND
- `agents/code-wiki-agent/tests/unit/test_cli_help.py` — FOUND
- `uv.lock` — FOUND
- `CLAUDE.md` — FOUND (modified)
- `.planning/REQUIREMENTS.md` — FOUND (modified)

Commits claimed:
- `29666a3` — FOUND
- `36c007c` — FOUND
- `dfa64a6` — FOUND

## Self-Check: PASSED

---
*Phase: 01-infrastructure-vault-io-and-mcp-skeleton*
*Completed: 2026-05-13*
