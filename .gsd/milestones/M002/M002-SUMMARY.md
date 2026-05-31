---
id: M002
title: "v1.12 Package Split"
status: complete
completed_at: 2026-05-31T22:33:30.950Z
key_decisions:
  - Use graph-wiki-core / graph_wiki_core as the stable shared library package and import namespace.
  - Split CLI and MCP presentation surfaces into graph-wiki-cli / graph_wiki_cli and graph-wiki-mcp / graph_wiki_mcp packages that depend on graph-wiki-core.
  - Expose the CLI as gw only; do not provide graph-wiki-agent console-script aliases.
  - Do not provide backward-compatible graph_wiki_agent import shims.
  - Preserve graph-wiki-agent plugin identity in vault manifests during the package split.
key_files:
  - pyproject.toml
  - README.md
  - packages/graph-wiki-core/pyproject.toml
  - packages/graph-wiki-core/src/graph_wiki_core
  - packages/graph-wiki-cli/pyproject.toml
  - packages/graph-wiki-cli/src/graph_wiki_cli/cli.py
  - packages/graph-wiki-mcp/pyproject.toml
  - packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
  - plugins/graph-wiki/README.md
  - plugins/graph-wiki/skills/graph-wiki/scripts
lessons_learned:
  - Browser-observable validation gates may require browser assertion evidence embedded directly in milestone validation, even when slice assessments already record browser evidence.
  - MCP tool descriptions are runtime-facing guidance and must be included in stale CLI-name scans during command renames.
  - Plugin identity strings can be intentional and should be separated from stale package/import/CLI references by brand guards and allowlists.
---

# M002: v1.12 Package Split

**M002 completed the v1.12 package split into graph-wiki-core, graph-wiki-cli, and graph-wiki-mcp with gw/MCP entrypoints, package-only workspace integration, updated docs/shims, and passing validation.**

## What Happened

M002 completed the v1.12 package split by moving the shared Graph Wiki implementation into the library-only `graph-wiki-core` package, extracting the Typer CLI into `graph-wiki-cli` with the `gw` entrypoint, extracting the MCP server into `graph-wiki-mcp` with the `graph-wiki-mcp` entrypoint, rewiring runtime-facing docs and Bedrock plugin shims to `gw`, and removing the obsolete `agents/` layout from the active workspace. The milestone also added package-local tests, boundary tests, stale-reference/brand guards, command help smokes, MCP stdio verification, root sync verification, and full default-safe workspace tests. Remediation slice S06 closed validation gaps by explicitly documenting the R009 deferral, proving R013 non-regression, preserving plugin identity semantics, and adding requirement traceability evidence. Final validation passed after fresh browser actions with assertions verified README documentation for `gw`, `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp`.

## Success Criteria Results

- The repo is a package-only uv workspace under `packages/*`: met by S05 removal of `agents/` and root workspace sync verification.
- The graph-wiki implementation is split into `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp` with honest import namespaces and dependencies: met by S01-S03 and package boundary tests.
- Users and graph-wiki Bedrock shims use `gw`; MCP hosts use `graph-wiki-mcp`: met by S02-S04 entrypoint/shim/help verification and S03 MCP stdio tests.
- No old import shims or old CLI aliases are introduced: met by S02/S03/S05/S06 boundary and brand-guard evidence.
- Current user-facing docs match the v1.12 package layout and command usage: met by S04 docs updates plus final browser assertions against README.
- Full workspace verification including integration tests passes: met by S05 default-safe root/package/integration gate evidence, with live Bedrock tests explicitly opt-in.

## Definition of Done Results

- All six roadmap slices are complete.
- Milestone validation passed in remediation round 1.
- Root workspace is packages-only under `packages/*` and obsolete `agents/` layout is removed.
- Package boundaries are split into `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp` with honest import namespaces and entrypoints.
- Current docs and runtime-facing shims use `gw`; MCP hosts use `graph-wiki-mcp`.
- No old `graph_wiki_agent` import shims or `graph-wiki-agent` console-script alias were introduced.
- Full default-safe verification passed; live Bedrock paths remain explicitly environment/cost gated.

## Requirement Outcomes

- R001 validated: Graph Wiki is split into core, CLI, and MCP packages.
- R002 validated: `graph-wiki-core` is library-only under `graph_wiki_core`.
- R003 validated: `graph-wiki-cli` exposes the `gw` entrypoint.
- R004 validated: `graph-wiki-mcp` owns MCP server entrypoint and schemas.
- R005 validated: runtime-facing workflows and shims use `gw`.
- R006 validated: tests are colocated with the packages they validate.
- R007 validated for default-safe workspace and integration gates; live Bedrock paths remain explicit opt-in.
- R008 validated with docs updates and browser assertion evidence.
- R009 deferred with explicit evidence: public PyPI polish is outside M002.
- R010 validated: no backward-compatible `graph_wiki_agent` import shims.
- R011 validated: no `graph-wiki-agent` console-script alias.
- R012 validated: plugin identity remains `graph-wiki-agent` in manifests.
- R013 validated: product workflows unrelated to package split were not redesigned.

## Deviations

Public PyPI metadata polish (R009) was explicitly deferred outside M002 while local package metadata and workspace behavior were validated. Live Bedrock E2E tests remain environment/cost gated and were documented as such rather than silently omitted. Browser documentation evidence initially required remediation because the validator did not recognize prior S04 evidence until fresh browser assertions were embedded directly in milestone validation.

## Follow-ups

- Decide whether to address deferred public PyPI metadata polish in a later milestone.
- Consider improving the validation browser-evidence gate so persisted slice ASSESSMENT browser evidence is recognized without requiring fresh validation-level browser assertions.
- If preparing release artifacts, run any explicitly opted-in live Bedrock integration gates with credentials and cost approval.
