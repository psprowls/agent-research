---
id: S05
parent: M002
milestone: M002
provides:
  - A package-only uv workspace under `packages/*`.
  - Final verified package boundaries for `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp`.
  - A passing default-safe full workspace test baseline for completing M002.
  - Validated launchability evidence for current `gw` and `graph-wiki-mcp` entrypoints.
requires:
  - slice: S02
    provides: `graph-wiki-cli` package and `gw` console entrypoint consumed by runtime guidance and entrypoint verification.
  - slice: S03
    provides: `graph-wiki-mcp` package and `graph-wiki-mcp` console entrypoint consumed by package-local and entrypoint verification.
  - slice: S04
    provides: Runtime docs and workflow rewiring to `gw`, consumed by final stale-guidance/brand verification.
affects:
  - M002 milestone completion and validation can proceed using S05 full-workspace evidence.
key_files:
  - pyproject.toml
  - uv.lock
  - tests/test_package_split_workspace.py
  - tests/test_integration_gate.py
  - scripts/check-brand.sh
  - .brand-grep-allow
  - packages/workspace-io/src/workspace_io/config.py
  - packages/workspace-io/tests/test_config.py
  - packages/wiki-io/src/wiki_io/_workspace.py
  - packages/wiki-io/tests/test_ports_importable.py
  - packages/graph-wiki-core/src/graph_wiki_core/config.py
  - packages/graph-wiki-core/tests
  - packages/graph-wiki-cli/tests
  - packages/graph-wiki-mcp/tests
  - packages/eval-harness/tests/test_models_toml_sweep_candidates.py
  - packages/model-adapter/tests/test_loader.py
  - packages/model-adapter/tests/test_narrator_role.py
key_decisions:
  - Root pytest excludes local `.claude` worktree artifacts so default-safe workspace verification covers only the active repository.
  - Package-era brand scopes scan active package/plugin/script/doc paths rather than deleted `agents/` paths.
  - Allowed `graph-wiki-agent` strings remain classified as plugin identity, provenance, historical artifact, or negative-test fixture rather than being reintroduced as executable guidance.
  - Model tests assert documented current package defaults after the Haiku quota purge, not stale pre-purge Haiku defaults.
  - Copied-bytecode boundary tests ignore runtime-created `__pycache__` directories and only fail on copied `.pyc` artifacts outside Python cache directories.
patterns_established:
  - Final package-split verification combines uv sync, root boundary tests, brand guard, package-local suites, console entrypoint smokes, and full default-safe pytest.
  - Recovery/runtime guidance must use `gw`; `graph-wiki-agent` may appear only in classified non-executable contexts.
  - Live Bedrock integration is treated as optional environment/cost-gated verification when credentials are unavailable.
observability_surfaces:
  - Test and guardrail based failure visibility: package-split boundary tests, integration gate tests, brand grep gate, package-local suites, console help smokes, and full pytest.
  - No runtime telemetry was added because this was a packaging/integration closeout slice.
drill_down_paths:
  - .gsd/milestones/M002/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S05/tasks/T04-SUMMARY.md
  - .gsd/exec/e25d422d-1ccc-44d2-93ed-95080fae1b5e.stdout
duration: ""
verification_result: passed
completed_at: 2026-05-31T18:00:40.852Z
blocker_discovered: false
---

# S05: Workspace integration and full verification

**Finalized the v1.12 package split by proving the repo is packages-only, deleting the obsolete agents workspace path, refreshing package-era guardrails, and passing default-safe full workspace verification.**

## What Happened

S05 closed the package-split milestone assembly. T01 cut the root uv workspace to `packages/*`, removed the obsolete `agents/` checkout tree, refreshed `uv.lock`, and added root package-split boundary tests. T02 updated active missing-workspace recovery guidance to tell users to run `gw bootstrap <path>` while preserving explicitly classified provenance/plugin-identity text. T03 refreshed repo guardrails for package-era boundaries, including integration-gate and brand checks, and cleaned a stale legacy runtime config field surfaced by those guardrails. T04 ran the final integration pass, fixed default-safe verification blockers in test/config guardrails, aligned model expectations with the documented post-Haiku-purge defaults, excluded local `.claude` worktree artifacts from root pytest recursion, and verified the assembled core/CLI/MCP packages compose from the root workspace. Requirements R001, R006, and R007 were updated to validated based on the final closeout evidence.

## Verification

Fresh closeout verification passed in gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e: `uv sync`; focused workspace/package gates plus brand guard (`uv run python -m pytest tests/test_package_split_workspace.py tests/test_integration_gate.py packages/workspace-io/tests/test_config.py packages/wiki-io/tests/test_ports_importable.py -q && bash scripts/check-brand.sh`); package-local core/CLI/MCP suites via `uv run --package ...`; console entrypoint smokes for `gw --help`, `gw query --help`, `gw graph --help`, and `graph-wiki-mcp --help`; and full default-safe workspace pytest via `uv run python -m pytest -q`. Live Bedrock integration was not run because no AWS credential keys or explicit integration/cost opt-in environment variables were present, so live paths remain correctly environment-gated. A prior ad hoc stale-reference check was too strict for allowed classified provenance/test-fixture strings and was replaced by the supported boundary and brand gates; no source failure was indicated by that attempt.

## Requirements Advanced

- R001 — Completed and verified the core/CLI/MCP package split in a packages-only workspace.
- R006 — Verified package-local test suites and root boundary tests for package-owned verification.
- R007 — Ran full default-safe workspace verification and entrypoint smokes.

## Requirements Validated

- R001 — gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e passed uv sync, boundary/integration/brand gates, package-local suites, entrypoint smokes, and full pytest for the split packages.
- R006 — Package-local core, CLI, and MCP test suites passed through `uv run --package ...`; root boundary tests enforce the removed agent namespace/workspace member.
- R007 — Full default-safe verification passed in gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e; live Bedrock integration was correctly classified as environment/cost gated.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

T04 was planned as verification-only, but full default-safe pytest exposed stale local-test guardrails and stale model expectations that blocked final verification. Minimal test/config guardrail updates were made to keep the intended default-safe suite executable and aligned with current documented model defaults. During final closeout, an over-strict ad hoc stale-reference scan failed on allowed classified provenance/test-fixture strings; the supported package boundary and brand gates passed and were used as canonical verification.

## Known Limitations

Live Bedrock integration was not executed because no AWS credential keys or explicit integration/cost-acceptance opt-in environment variables were present. Those tests remain environment-gated by design.

## Follow-ups

When credentials and cost acceptance are available, run the live Bedrock integration path with `GRAPH_WIKI_RUN_INTEGRATION=1` as an optional confidence pass.

## Files Created/Modified

- `pyproject.toml` — Root workspace and pytest recursion guard updated for package-only default-safe verification.
- `uv.lock` — Lockfile refreshed without obsolete graph-wiki-agent workspace membership.
- `tests/test_package_split_workspace.py` — Root package-split boundary tests added/refreshed.
- `tests/test_integration_gate.py` — Integration gate updated for package-era paths and entrypoints.
- `scripts/check-brand.sh` — Brand guard refreshed for active package-era scopes.
- `.brand-grep-allow` — Allowed classified legacy strings scoped to provenance/identity/negative-test contexts.
- `packages/workspace-io/src/workspace_io/config.py` — Active recovery guidance updated to `gw bootstrap`.
- `packages/wiki-io/src/wiki_io/_workspace.py` — Active missing-workspace guidance updated to `gw bootstrap`.
- `packages/graph-wiki-core/src/graph_wiki_core/config.py` — Legacy runtime config field cleaned during guardrail refresh.
- `packages/eval-harness/tests/test_models_toml_sweep_candidates.py` — Model defaults expectations aligned with current packaged models.toml.
- `packages/graph-wiki-core/tests/test_package_boundary.py` — Bytecode boundary check narrowed to copied `.pyc` artifacts outside runtime cache directories.
- `packages/model-adapter/tests/test_loader.py` — Model-adapter default expectations aligned with current model defaults.
- `packages/model-adapter/tests/test_narrator_role.py` — Narrator role expectation aligned with current model defaults.
