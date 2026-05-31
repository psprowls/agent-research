# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R001 — Split graph-wiki into core, CLI, and MCP packages.
- Class: core-capability
- Status: active
- Description: Split graph-wiki into core, CLI, and MCP packages.
- Why it matters: The package layout should reflect the actual architecture so shared command logic, CLI presentation, and MCP presentation can evolve independently without keeping an agent-shaped monolith.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: M002/S01, M002/S02, M002/S03
- Validation: mapped
- Notes: Final proof comes from the integrated workspace after all three packages exist and depend on each other correctly.

### R002 — Core package is library-only and renamed to graph-wiki-core.
- Class: core-capability
- Status: active
- Description: Core package is library-only and renamed to graph-wiki-core.
- Why it matters: A library-only core makes the package boundary honest: shared command/runtime implementation is reusable by both CLI and MCP without owning executable entrypoints.
- Source: user
- Primary owning slice: M002/S01
- Supporting slices: M002/S05
- Validation: mapped
- Notes: Core distribution/import names are graph-wiki-core and graph_wiki_core. The graph-wiki-agent plugin identity remains unchanged for vault manifest semantics.

### R003 — CLI package exposes only the gw entrypoint.
- Class: primary-user-loop
- Status: active
- Description: CLI package exposes only the gw entrypoint.
- Why it matters: Users and graph-wiki workflow shims need one current command name that reflects the new CLI package surface.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S04, M002/S05
- Validation: mapped
- Notes: No graph-wiki-agent console alias should be kept in v1.12.

### R004 — MCP package owns the MCP server entrypoint and schemas.
- Class: integration
- Status: active
- Description: MCP package owns the MCP server entrypoint and schemas.
- Why it matters: MCP hosts should depend on a focused server package rather than an all-in-one agent package.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S05
- Validation: mapped
- Notes: The MCP server remains exposed as graph-wiki-mcp and must preserve its stdout protocol guard.

### R005 — Runtime-facing graph-wiki workflows use gw after the rename.
- Class: integration
- Status: active
- Description: Runtime-facing graph-wiki workflows use gw after the rename.
- Why it matters: The package split must not break real graph-wiki Bedrock workflow execution just because the CLI command changed.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: M002/S02, M002/S05
- Validation: mapped
- Notes: Includes plugin Bedrock shims and current user-facing command instructions where stale graph-wiki-agent invocation would break behavior.

### R006 — Tests are colocated with the packages they validate.
- Class: quality-attribute
- Status: active
- Description: Tests are colocated with the packages they validate.
- Why it matters: Future maintainers should be able to run and understand each package's verification boundary without a monolithic old agent test tree.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: M002/S01, M002/S02, M002/S03
- Validation: mapped
- Notes: Core tests move to graph-wiki-core, CLI tests to graph-wiki-cli, and MCP tests to graph-wiki-mcp.

### R007 — Full workspace verification including integration tests passes.
- Class: launchability
- Status: active
- Description: Full workspace verification including integration tests passes.
- Why it matters: A packaging migration can appear correct while still breaking subprocess entrypoints, MCP stdio behavior, or workspace dependency resolution.
- Source: user
- Primary owning slice: M002/S05
- Supporting slices: M002/S01, M002/S02, M002/S03, M002/S04
- Validation: mapped
- Notes: Completion requires root uv sync and full test suite including integration tests, not only unit tests or import checks.

### R008 — Current user-facing docs describe the new package layout and gw usage.
- Class: launchability
- Status: active
- Description: Current user-facing docs describe the new package layout and gw usage.
- Why it matters: Users should not be instructed to run removed console scripts after v1.12.
- Source: user
- Primary owning slice: M002/S04
- Supporting slices: M002/S05
- Validation: mapped
- Notes: Historical docs/fixtures may remain unchanged when they are not current user-facing instructions and do not affect tests/runtime behavior.

## Validated

## Deferred

### R009 — Public PyPI metadata polish for the split packages.
- Class: admin/support
- Status: deferred
- Description: Public PyPI metadata polish for the split packages.
- Why it matters: Release-ready metadata will matter before publishing, but it is not necessary to prove the local workspace package split.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred because the user is not planning a public release soon; package metadata can remain minimal for now.

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
- Validation: n/a
- Notes: The Python package/distribution is renamed, but .graph-wiki.yaml and workspace manifest plugin identity remain graph-wiki-agent for now.

### R013 — Do not redesign graph-wiki product workflows unrelated to the package split.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not redesign graph-wiki product workflows unrelated to the package split.
- Why it matters: This milestone is about packaging and entrypoint migration; unrelated workflow redesign would dilute verification and increase risk.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Workflow-facing code must be updated when needed to avoid breakage from gw/package rename, but unrelated product behavior redesign is excluded.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | active | M002/S05 | M002/S01, M002/S02, M002/S03 | mapped |
| R002 | core-capability | active | M002/S01 | M002/S05 | mapped |
| R003 | primary-user-loop | active | M002/S02 | M002/S04, M002/S05 | mapped |
| R004 | integration | active | M002/S03 | M002/S05 | mapped |
| R005 | integration | active | M002/S04 | M002/S02, M002/S05 | mapped |
| R006 | quality-attribute | active | M002/S05 | M002/S01, M002/S02, M002/S03 | mapped |
| R007 | launchability | active | M002/S05 | M002/S01, M002/S02, M002/S03, M002/S04 | mapped |
| R008 | launchability | active | M002/S04 | M002/S05 | mapped |
| R009 | admin/support | deferred | none | none | unmapped |
| R010 | anti-feature | out-of-scope | none | none | n/a |
| R011 | anti-feature | out-of-scope | none | none | n/a |
| R012 | constraint | out-of-scope | none | none | n/a |
| R013 | anti-feature | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 8
- Mapped to slices: 8
- Validated: 0
- Unmapped active requirements: 0
