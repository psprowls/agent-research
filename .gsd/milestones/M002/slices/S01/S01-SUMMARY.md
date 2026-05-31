---
id: S01
parent: M002
milestone: M002
provides:
  - `packages/graph-wiki-core` as a library-only workspace member.
  - `graph_wiki_core.commands` and shared command result/helper types for CLI and MCP packages.
  - Core package tests and boundary assertions proving the shared command contract.
requires:
  []
affects:
  - S02
  - S03
  - S05
key_files:
  - packages/graph-wiki-core/pyproject.toml
  - packages/graph-wiki-core/src/graph_wiki_core
  - packages/graph-wiki-core/tests
  - agents/graph-wiki-agent/pyproject.toml
  - agents/graph-wiki-agent/src/graph_wiki_agent/cli.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py
  - packages/eval-harness/pyproject.toml
  - packages/eval-harness/src/eval_harness
  - packages/eval-harness/tests/test_structural.py
  - packages/eval-harness/tests/test_sweep.py
  - uv.lock
key_decisions:
  - Use `graph-wiki-core` / `graph_wiki_core` as the stable shared library package and import namespace.
  - Keep `graph-wiki-core` library-only with no console scripts.
  - Make temporary presentation consumers import command logic directly from `graph_wiki_core` instead of adding old-namespace command shims.
  - Keep CLI/MCP presentation-only tests out of the core package and leave them for S02/S03.
patterns_established:
  - Package-local tests live under the package they validate.
  - Boundary tests should assert package metadata, import namespace ownership, no presentation leakage, and no copied bytecode/cache artifacts.
  - Downstream presentation packages should depend on `graph-wiki-core` and import shared command modules from `graph_wiki_core.commands`.
observability_surfaces:
  - No runtime observability changes were planned or introduced.
  - Failure visibility is provided by package-local pytest failures, import-smoke failures, and explicit boundary tests.
drill_down_paths:
  - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T04-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T05-SUMMARY.md
  - .gsd/exec/8dd7a539-a276-4a90-bf5e-abdee29b939d.stdout
duration: ""
verification_result: passed
completed_at: 2026-05-31T16:17:59.402Z
blocker_discovered: false
---

# S01: Core package move and rename

**Created the library-only `graph-wiki-core` workspace package, moved shared graph-wiki implementation into `graph_wiki_core`, and verified temporary consumers plus eval-harness compile against the new core boundary.**

## What Happened

S01 split the shared graph-wiki command, prompt, runtime, config, graph tooling, and URI slug implementation out of the temporary executable package and into `packages/graph-wiki-core/src/graph_wiki_core`. The new workspace member is named `graph-wiki-core`, has no console scripts, and exposes `graph_wiki_core.commands` and related library modules as the stable shared import surface for later CLI and MCP extraction. The temporary `graph-wiki-agent` presentation package now depends on `graph-wiki-core`; its CLI and FastMCP server import command logic from `graph_wiki_core` without introducing backward-compatible command shims. `eval-harness` was also rewired to depend on and import from `graph-wiki-core`. Core-facing deterministic tests were relocated into `packages/graph-wiki-core/tests`, imports and snapshots were updated to the new namespace, and package-boundary assertions were added for library-only metadata, stale old command imports, presentation leakage, and bytecode cleanliness. Final closeout reran the authoritative S01 verification chain and confirmed the package boundary is ready for downstream S02/S03 consumers.

## Verification

Closeout verification passed via gsd_exec `8dd7a539-a276-4a90-bf5e-abdee29b939d`: `uv sync` resolved and checked 132 packages; import smokes passed for `graph_wiki_core.commands.query`, `graph_wiki_core.commands.scan`, and `graph_wiki_core.prompts.scanner`; `uv run --package graph-wiki-core python -m pytest packages/graph-wiki-core/tests` passed with 256 passed, 7 skipped, and 21 snapshots passed; `uv run --package eval-harness python -m pytest packages/eval-harness/tests/test_structural.py packages/eval-harness/tests/test_sweep.py` passed with 17 passed; and `uv run --package graph-wiki-agent graph-wiki-agent --help` exited 0 and rendered the expected temporary command surface.

## Requirements Advanced

- R001 — Established the core/shared-logic package boundary required before CLI and MCP package extraction.
- R006 — Moved deterministic core-facing tests into `packages/graph-wiki-core/tests` and added boundary assertions.
- R007 — Ran targeted workspace/package verification covering sync, imports, core tests, eval-harness consumer tests, and temporary CLI help.

## Requirements Validated

- R002 — Validated by S01 closeout evidence: library-only `graph-wiki-core`, `graph_wiki_core` imports, no core scripts, core boundary tests, and passing temporary/eval consumer verification.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

The temporary `graph-wiki-agent` package and script names remain in place for S01 because CLI and MCP extraction are owned by S02 and S03. Some CLI/MCP presentation-only tests were not relocated into core; they remain deferred to the presentation-package slices.

## Known Limitations

S01 does not claim final `gw` CLI behavior, final `graph-wiki-mcp` behavior, docs/shim rewiring, removal of the obsolete `agents/` layout, or full integration-test closure. Those are explicitly owned by S02-S05.

## Follow-ups

S02 should consume `graph_wiki_core.commands` from the new `graph-wiki-cli` package and expose `gw`. S03 should consume `graph_wiki_core.commands` from `graph-wiki-mcp`. S05 should remove the obsolete agents layout and run full workspace/integration verification.

## Files Created/Modified

- `packages/graph-wiki-core/pyproject.toml` — Defined the new library-only `graph-wiki-core` workspace package and dependencies.
- `packages/graph-wiki-core/src/graph_wiki_core` — Moved shared command, prompt, runtime/config, graph tooling, and URI slug implementation into the new core namespace.
- `packages/graph-wiki-core/tests` — Relocated deterministic core tests and added package-boundary assertions.
- `agents/graph-wiki-agent/pyproject.toml` — Made the temporary presentation package depend on `graph-wiki-core`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — Rewired temporary CLI command imports to consume `graph_wiki_core`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` — Rewired temporary MCP server command imports to consume `graph_wiki_core`.
- `packages/eval-harness/pyproject.toml` — Made eval-harness depend on `graph-wiki-core`.
- `packages/eval-harness/src/eval_harness` — Updated active eval-harness command imports to `graph_wiki_core.commands`.
- `uv.lock` — Updated workspace lockfile for the new core package dependency graph.
