# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

## Validated

### R001 — Split graph-wiki into core, CLI, and MCP packages.
- Class: core-capability
- Status: validated
- Description: Split graph-wiki into core, CLI, and MCP packages.
- Why it matters: The package layout should reflect the actual architecture so shared command logic, CLI presentation, and MCP presentation can evolve independently without keeping an agent-shaped monolith.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: M002/S01, M002/S02, M002/S03
- Validation: M002/S05 closeout validated the final package split: root workspace is packages-only, obsolete `agents/` workspace membership is removed, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp` package boundaries compose, and package/entrypoint/full-workspace verification passed. Evidence: gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e (`uv sync`, package boundary/integration/config/brand gates, core/CLI/MCP package suites, `gw` and `graph-wiki-mcp` help entrypoints, full pytest).
- Notes: Final proof comes from the integrated workspace after all three packages exist and depend on each other correctly.

### R002 — Core package is library-only and renamed to graph-wiki-core.
- Class: core-capability
- Status: validated
- Description: Core package is library-only and renamed to graph-wiki-core.
- Why it matters: A library-only core makes the package boundary honest: shared command/runtime implementation is reusable by both CLI and MCP without owning executable entrypoints.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S05
- Validation: M002/S01 closeout verified `graph-wiki-core` as a library-only workspace package with no core console scripts, importable `graph_wiki_core.commands`/`prompts`, colocated boundary tests, and temporary/eval consumers wired to `graph_wiki_core`. Evidence: gsd_exec 8dd7a539-a276-4a90-bf5e-abdee29b939d (`uv sync`, import smokes, 256 passed/7 skipped core tests, 17 passed eval-harness tests, temporary CLI help smoke).
- Notes: Core distribution/import names are graph-wiki-core and graph_wiki_core. The graph-wiki-agent plugin identity remains unchanged for vault manifest semantics.

### R003 — CLI package exposes only the gw entrypoint.
- Class: primary-user-loop
- Status: validated
- Description: CLI package exposes only the gw entrypoint.
- Why it matters: Users and graph-wiki workflow shims need one current command name that reflects the new CLI package surface.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04, M002/S05
- Validation: S02 closeout verified graph-wiki-cli owns exactly the gw console script via uv package boundary: import smoke printed gw, `gw --help` and `gw query --help` exited 0, and package boundary tests passed with negative checks against stale graph-wiki-agent CLI aliases.
- Notes: Validated by M002/S02 CLI package extraction; downstream S04 still needs to rewire runtime-facing workflows to invoke gw.

### R004 — MCP package owns the MCP server entrypoint and schemas.
- Class: integration
- Status: validated
- Description: MCP package owns the MCP server entrypoint and schemas.
- Why it matters: MCP hosts should depend on a focused server package rather than an all-in-one agent package.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S05
- Validation: M002/S03 completed: `packages/graph-wiki-mcp` owns `graph_wiki_mcp.server`, the `graph-wiki-mcp` console script, FastMCP schemas/tools, relocated MCP tests, and package-boundary checks. Closeout verification passed with `uv sync && uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests` (56 passed, 2 gated skips) plus static assertions that `graph_wiki_agent.mcp` is absent.
- Notes: The MCP server remains exposed as graph-wiki-mcp and must preserve its stdout protocol guard.

### R005 — Runtime-facing graph-wiki workflows use gw after the rename.
- Class: integration
- Status: validated
- Description: Runtime-facing graph-wiki workflows use gw after the rename.
- Why it matters: The package split must not break real graph-wiki Bedrock workflow execution just because the CLI command changed.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: M002/S02, M002/S05
- Validation: S04 closeout verified runtime-facing graph-wiki workflows use `gw`: five Bedrock plugin shim argv regression tests passed, focused `gw bootstrap --help` and `gw ingest source --help` entrypoint checks exited 0, graph command help checks exited 0, full `packages/graph-wiki-cli/tests` passed (86 tests), and the S04 runtime-facing scope scan found no stale `graph-wiki-agent` references.
- Notes: Includes plugin Bedrock shims and current user-facing command instructions where stale graph-wiki-agent invocation would break behavior.

### R006 — Tests are colocated with the packages they validate.
- Class: quality-attribute
- Status: validated
- Description: Tests are colocated with the packages they validate.
- Why it matters: Future maintainers should be able to run and understand each package's verification boundary without a monolithic old agent test tree.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: M002/S01, M002/S02, M002/S03
- Validation: M002/S05 closeout validated package-local test ownership by running `packages/graph-wiki-core/tests`, `packages/graph-wiki-cli/tests`, and `packages/graph-wiki-mcp/tests` through their package contexts, alongside repo boundary tests that enforce the deleted `agents/` tree and no active `graph_wiki_agent` package namespace. Evidence: gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e.
- Notes: Core tests move to graph-wiki-core, CLI tests to graph-wiki-cli, and MCP tests to graph-wiki-mcp.

### R007 — Full workspace verification including integration tests passes.
- Class: launchability
- Status: validated
- Description: Full workspace verification including integration tests passes.
- Why it matters: A packaging migration can appear correct while still breaking subprocess entrypoints, MCP stdio behavior, or workspace dependency resolution.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: M002/S01, M002/S02, M002/S03, M002/S04
- Validation: M002/S05 closeout ran default-safe full workspace verification successfully: `uv sync`, package split/integration/config/brand gates, package-local suites, console entrypoint smokes, and `uv run python -m pytest -q` all passed. Live Bedrock integration was classified as environment/cost gated because no AWS credential or explicit integration opt-in environment variables were present. Evidence: gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e.
- Notes: Completion requires root uv sync and full test suite including integration tests, not only unit tests or import checks.

### R008 — Current user-facing docs describe the new package layout and gw usage.
- Class: launchability
- Status: validated
- Description: Current user-facing docs describe the new package layout and gw usage.
- Why it matters: Users should not be instructed to run removed console scripts after v1.12.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: M002/S05
- Validation: S04 closeout verified current user-facing docs describe the v1.12 package layout and `gw` usage: runtime docs guard tests passed, edited docs were scanned for stale `graph-wiki-agent` executable guidance, and the full graph-wiki-cli test suite passed.
- Notes: Historical docs/fixtures may remain unchanged when they are not current user-facing instructions and do not affect tests/runtime behavior.

## Deferred

### R009 — Public PyPI metadata polish for the split packages.
- Class: admin/support
- Status: deferred
- Description: Public PyPI metadata polish for the split packages.
- Why it matters: Release-ready metadata will matter before publishing, but it is not necessary to prove the local workspace package split.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: Deferred with explicit coverage: public PyPI metadata polish is intentionally outside M002 closeout because `packages/graph-wiki-core/pyproject.toml`, `packages/graph-wiki-cli/pyproject.toml`, and `packages/graph-wiki-mcp/pyproject.toml` remain minimal by design until a public release is planned.
- Notes: M002 validates the local uv workspace package split, package boundaries, and entrypoints; release-facing metadata polish can be scheduled when public publishing is planned.

## Out of Scope

### R010 — Backward-compatible graph_wiki_agent import shims are not provided.
- Class: anti-feature
- Status: out-of-scope
- Description: Backward-compatible graph_wiki_agent import shims are not provided.
- Why it matters: No-shim behavior keeps the breaking migration clean and prevents old import paths from hiding incomplete package-boundary updates.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicit exclusion for v1.12; active code/tests should use graph_wiki_core, graph_wiki_cli, or graph_wiki_mcp directly.

### R011 — Temporary graph-wiki-agent console-script alias is not provided.
- Class: anti-feature
- Status: out-of-scope
- Description: Temporary graph-wiki-agent console-script alias is not provided.
- Why it matters: Keeping the old executable would undermine the entrypoint rename and let runtime-facing references stay stale.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicit exclusion for v1.12; gw is the CLI command users should run.

### R012 — Do not rename graph-wiki-agent plugin identity in vault manifests during this milestone.
- Class: constraint
- Status: out-of-scope
- Description: Do not rename graph-wiki-agent plugin identity in vault manifests during this milestone.
- Why it matters: Changing plugin identity would expand scope into vault config compatibility and migration, which is not required for the package split.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: Out-of-scope constraint explicitly covered by M002/S06/T01 bootstrap regression evidence and D004: generated workspace manifests keep plugin identity `graph-wiki-agent` even though installed/applied version metadata is read from the `graph-wiki-core` distribution.
- Notes: D004 is reaffirmed: package/distribution/import names changed, but `.graph-wiki.yaml` and workspace manifest plugin identity remain `graph-wiki-agent` for this milestone.

### R013 — Do not redesign graph-wiki product workflows unrelated to the package split.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not redesign graph-wiki product workflows unrelated to the package split.
- Why it matters: This milestone is about packaging and entrypoint migration; unrelated workflow redesign would dilute verification and increase risk.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: Out-of-scope anti-feature covered by focused non-regression checks: CLI shim tests preserve Bedrock shim argument mapping to `gw`, runtime-doc and CLI-boundary tests reject stale executable/import shims, package split and integration gate tests enforce the new package boundaries, `scripts/check-brand.sh` preserves allowed plugin identity/provenance strings, and M002/S06/T01 remediated package-rename fallout without redesigning unrelated graph-wiki product workflows.
- Notes: D003 and D004 are reaffirmed: no backward-compatible old imports or executable aliases are introduced, while classified plugin identity/provenance strings remain allowed where semantically required.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | validated | M002/S05 | M002/S01, M002/S02, M002/S03 | M002/S05 closeout validated the final package split: root workspace is packages-only, obsolete `agents/` workspace membership is removed, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp` package boundaries compose, and package/entrypoint/full-workspace verification passed. Evidence: gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e (`uv sync`, package boundary/integration/config/brand gates, core/CLI/MCP package suites, `gw` and `graph-wiki-mcp` help entrypoints, full pytest). |
| R002 | core-capability | validated | M002/S01 | M002/S05 | M002/S01 closeout verified `graph-wiki-core` as a library-only workspace package with no core console scripts, importable `graph_wiki_core.commands`/`prompts`, colocated boundary tests, and temporary/eval consumers wired to `graph_wiki_core`. Evidence: gsd_exec 8dd7a539-a276-4a90-bf5e-abdee29b939d (`uv sync`, import smokes, 256 passed/7 skipped core tests, 17 passed eval-harness tests, temporary CLI help smoke). |
| R003 | primary-user-loop | validated | M002/S02 | M002/S04, M002/S05 | S02 closeout verified graph-wiki-cli owns exactly the gw console script via uv package boundary: import smoke printed gw, `gw --help` and `gw query --help` exited 0, and package boundary tests passed with negative checks against stale graph-wiki-agent CLI aliases. |
| R004 | integration | validated | M002/S03 | M002/S05 | M002/S03 completed: `packages/graph-wiki-mcp` owns `graph_wiki_mcp.server`, the `graph-wiki-mcp` console script, FastMCP schemas/tools, relocated MCP tests, and package-boundary checks. Closeout verification passed with `uv sync && uv run --package graph-wiki-mcp python -m pytest packages/graph-wiki-mcp/tests` (56 passed, 2 gated skips) plus static assertions that `graph_wiki_agent.mcp` is absent. |
| R005 | integration | validated | M002/S04 | M002/S02, M002/S05 | S04 closeout verified runtime-facing graph-wiki workflows use `gw`: five Bedrock plugin shim argv regression tests passed, focused `gw bootstrap --help` and `gw ingest source --help` entrypoint checks exited 0, graph command help checks exited 0, full `packages/graph-wiki-cli/tests` passed (86 tests), and the S04 runtime-facing scope scan found no stale `graph-wiki-agent` references. |
| R006 | quality-attribute | validated | M002/S05 | M002/S01, M002/S02, M002/S03 | M002/S05 closeout validated package-local test ownership by running `packages/graph-wiki-core/tests`, `packages/graph-wiki-cli/tests`, and `packages/graph-wiki-mcp/tests` through their package contexts, alongside repo boundary tests that enforce the deleted `agents/` tree and no active `graph_wiki_agent` package namespace. Evidence: gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e. |
| R007 | launchability | validated | M002/S05 | M002/S01, M002/S02, M002/S03, M002/S04 | M002/S05 closeout ran default-safe full workspace verification successfully: `uv sync`, package split/integration/config/brand gates, package-local suites, console entrypoint smokes, and `uv run python -m pytest -q` all passed. Live Bedrock integration was classified as environment/cost gated because no AWS credential or explicit integration opt-in environment variables were present. Evidence: gsd_exec e25d422d-1ccc-44d2-93ed-95080fae1b5e. |
| R008 | launchability | validated | M002/S04 | M002/S05 | S04 closeout verified current user-facing docs describe the v1.12 package layout and `gw` usage: runtime docs guard tests passed, edited docs were scanned for stale `graph-wiki-agent` executable guidance, and the full graph-wiki-cli test suite passed. |
| R009 | admin/support | deferred | none | none | Deferred with explicit coverage: public PyPI metadata polish is intentionally outside M002 closeout because `packages/graph-wiki-core/pyproject.toml`, `packages/graph-wiki-cli/pyproject.toml`, and `packages/graph-wiki-mcp/pyproject.toml` remain minimal by design until a public release is planned. |
| R010 | anti-feature | out-of-scope | none | none | n/a |
| R011 | anti-feature | out-of-scope | none | none | n/a |
| R012 | constraint | out-of-scope | none | none | Out-of-scope constraint explicitly covered by M002/S06/T01 bootstrap regression evidence and D004: generated workspace manifests keep plugin identity `graph-wiki-agent` even though installed/applied version metadata is read from the `graph-wiki-core` distribution. |
| R013 | anti-feature | out-of-scope | none | none | Out-of-scope anti-feature covered by focused non-regression checks: CLI shim tests preserve Bedrock shim argument mapping to `gw`, runtime-doc and CLI-boundary tests reject stale executable/import shims, package split and integration gate tests enforce the new package boundaries, `scripts/check-brand.sh` preserves allowed plugin identity/provenance strings, and M002/S06/T01 remediated package-rename fallout without redesigning unrelated graph-wiki product workflows. |

## Coverage Summary

- Active requirements: 0
- Mapped to slices: 0
- Validated: 8 (R001, R002, R003, R004, R005, R006, R007, R008)
- Unmapped active requirements: 0
