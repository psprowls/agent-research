# M002: v1.12 Package Split

**Vision:** Split the current graph-wiki-agent executable package into a core library plus separate CLI and MCP surface packages under packages, remove the obsolete agents layout, rename the core package to graph-wiki-core, and expose the CLI as gw while preserving existing graph-wiki workflow behavior.

## Success Criteria

- The repo is a package-only uv workspace under `packages/*`.
- The graph-wiki implementation is split into `graph-wiki-core`, `graph-wiki-cli`, and `graph-wiki-mcp` with honest import namespaces and dependencies.
- Users and graph-wiki Bedrock shims use `gw`; MCP hosts use `graph-wiki-mcp`.
- No old import shims or old CLI aliases are introduced.
- Current user-facing docs match the v1.12 package layout and command usage.
- Full workspace verification including integration tests passes.

## Slices

- [ ] **S01: Core package move and rename** `risk:high` `depends:[]`
  > After this: `packages/graph-wiki-core` exists as a library-only workspace member, imports use `graph_wiki_core`, and shared command tests prove core still works.

- [ ] **S02: CLI package extraction** `risk:high` `depends:[S01]`
  > After this: `packages/graph-wiki-cli` exposes `gw`, CLI tests import `graph_wiki_cli`, and representative `gw --help` and command help checks pass.

- [ ] **S03: MCP package extraction** `risk:high` `depends:[S01]`
  > After this: `packages/graph-wiki-mcp` exposes `graph-wiki-mcp`, MCP tests import `graph_wiki_mcp`, and stdio/schema tests prove the server still works.

- [ ] **S04: Runtime docs and graph-wiki workflow rewiring** `risk:medium` `depends:[S02]`
  > After this: Plugin Bedrock shims and current user-facing docs invoke `gw`; runtime-facing help and bootstrap messages no longer point users at `graph-wiki-agent`.

- [ ] **S05: Workspace integration and full verification** `risk:high` `depends:[S02,S03,S04]`
  > After this: Root workspace syncs as packages-only, `agents/` is gone, stale active references are cleaned up, and full tests including integration pass.

## Boundary Map

### S01 → S02

Produces:
- `packages/graph-wiki-core/pyproject.toml` as a library-only workspace member named `graph-wiki-core`.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/` as the stable shared command import surface.
- Core package tests proving shared command imports work under `graph_wiki_core`.

Consumes:
- S02 imports shared commands and helpers from `graph_wiki_core`.

### S01 → S03

Produces:
- `graph_wiki_core.commands` and shared command result types for MCP tool implementations.
- Core dependencies and workspace source declarations usable by downstream packages.

Consumes:
- S03 imports command functions and result models from `graph_wiki_core.commands`.

### S02 → S04

Produces:
- `gw` console script owned by `graph-wiki-cli`.
- CLI package dependency and invocation pattern for plugin shims and docs.

Consumes:
- S04 rewires plugin Bedrock subprocess calls and current docs to use `gw`.

### S02, S03, S04 → S05

Produces:
- Final package boundaries, entrypoints, runtime-facing docs/shims, and package-local tests.

Consumes:
- S05 performs full workspace integration, stale-reference cleanup, root sync, and full tests including integration.
