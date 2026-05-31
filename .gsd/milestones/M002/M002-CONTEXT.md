# M002: v1.12 Package Split

**Gathered:** 2026-05-31
**Status:** Ready for planning

## Project Description

M002 is v1.12 for `agent-research`. It splits the current all-in-one `graph-wiki-agent` executable package into three `uv` workspace packages under `packages/`:

- `graph-wiki-core` / `graph_wiki_core` for shared graph-wiki Bedrock command implementation.
- `graph-wiki-cli` / `graph_wiki_cli` for the Typer CLI and the `gw` command.
- `graph-wiki-mcp` / `graph_wiki_mcp` for the stdio FastMCP server and MCP tool schemas.

The `agents/` directory should disappear. The milestone is a breaking package migration: no `graph_wiki_agent` import shims and no old `graph-wiki-agent` console-script alias.

## Why This Milestone

The current package shape no longer matches the actual architecture. `graph-wiki-agent` owns shared command logic, a Typer CLI, and a FastMCP stdio server in one workspace member under `agents/`. Pat wants v1.12 to make the package boundaries honest: a core library plus focused CLI and MCP surface packages, all under `packages/`.

This matters now because runtime-facing graph-wiki Bedrock workflows currently shell out to `graph-wiki-agent`. After the rename, those workflows must call `gw`, and the tests/docs need to prove the split is real rather than a cosmetic move.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Run `gw --help` and graph-wiki CLI subcommands from the new `graph-wiki-cli` package.
- Run `graph-wiki-mcp` from the new `graph-wiki-mcp` package and complete MCP stdio/schema tests.
- Use graph-wiki plugin Bedrock shims without breakage from the removed `graph-wiki-agent` command.
- Work in a package-only uv workspace where shared graph-wiki implementation lives in `graph-wiki-core`.

### Entry point / environment

- Entry point: `gw` CLI, `graph-wiki-mcp` stdio MCP server, graph-wiki plugin Bedrock shims.
- Environment: local `uv` workspace and subprocess-based integration tests.
- Live dependencies involved: local filesystem, uv workspace dependency resolution, stdio MCP framing, AWS Bedrock only for integration tests that already require it.

## Completion Class

- Contract complete means: package metadata, imports, console scripts, tests, and docs reflect the three-package design with no old active import/script surface.
- Integration complete means: CLI subprocess behavior, MCP stdio behavior, graph-wiki plugin shims, and workspace dependents all work through the new package names.
- Operational complete means: root `uv sync` and the full test suite including integration tests pass in the migrated workspace.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- Root `uv sync` succeeds with workspace members under `packages/*` only.
- Full test suite including integration tests passes after package split, import rename, and test relocation.
- `gw` works as the CLI command and graph-wiki plugin Bedrock shims call `gw` instead of `graph-wiki-agent`.
- `graph-wiki-mcp` still starts cleanly enough for stdio/MCP tests, preserving the stdout guard.
- No active code/tests/config require `agents/graph-wiki-agent`, `graph_wiki_agent`, or `graph-wiki-agent` as the CLI executable.

## Architectural Decisions

### Core Package Rename

**Decision:** Rename the core distribution to `graph-wiki-core` and the Python namespace to `graph_wiki_core`.

**Rationale:** With no backward compatibility requirement, keeping `graph_wiki_agent` as the shared library namespace would make the new architecture dishonest. The core should read as a reusable library consumed by CLI and MCP surfaces.

**Alternatives Considered:**
- Keep distribution/import as `graph-wiki-agent` / `graph_wiki_agent` — rejected because the user explicitly preferred `graph-wiki-core`, and because old naming would preserve the agent-shaped monolith concept.
- Rename only the distribution but not the import namespace — rejected because it would leave active code with the old architecture vocabulary.

### Presentation Package Split

**Decision:** Extract CLI and MCP into separate packages that depend on `graph-wiki-core`.

**Rationale:** CLI and MCP are presentation/runtime surfaces over shared command logic. Separate packages let dependencies and tests live at the right boundary: `typer` belongs to CLI, `mcp` and MCP schemas belong to MCP, and command implementation belongs to core.

**Alternatives Considered:**
- Keep all scripts in one package — rejected because it does not solve the package-boundary problem.
- Move command implementations into CLI or MCP — rejected because both surfaces use those commands.

### No Compatibility Shims or Old Script Aliases

**Decision:** Do not provide `graph_wiki_agent` import shims or a `graph-wiki-agent` console-script alias.

**Rationale:** The user explicitly wants a clean v1.12 breaking migration. Old aliases would hide stale references and make it harder to prove the split is complete.

**Alternatives Considered:**
- Keep thin shims for one release — rejected because backward compatibility is not a concern for this milestone.

### Plugin Identity Remains graph-wiki-agent

**Decision:** Keep `.graph-wiki.yaml` and workspace manifest plugin identity as `graph-wiki-agent` for now.

**Rationale:** Package names and command entrypoints can change without forcing a vault manifest identity migration. Renaming plugin identity would expand scope into existing vault config compatibility.

**Alternatives Considered:**
- Rename plugin identity to `graph-wiki-core`, `graph-wiki`, or `graph-wiki-bedrock` — rejected for this milestone because it changes vault semantics beyond the package split.

## Error Handling Strategy

This is a breaking migration, so old imports and old console scripts do not need friendly compatibility behavior. Instead, errors should surface through tests and clear current instructions:

- `gw --help` and representative `gw <cmd> --help` must work.
- `graph-wiki-mcp` must preserve MCP stdio behavior and the hard stdout guard.
- Plugin Bedrock shims must call `gw`; if `gw` is unavailable, the failure should be attributable to the missing current command rather than a stale old executable.
- User-facing help/bootstrap/error text should point to `gw` where it tells users which command to run.
- Role/config failures should continue to refer to plugin identity `graph-wiki-agent` where that identity is read from `.graph-wiki.yaml`.
- Historical references can remain stale only when they are not executable instructions, not test assertions, and not runtime behavior.

## Risks and Unknowns

- Import rename blast radius — `graph_wiki_agent` appears across tests, eval harness, prompts, docs, and runtime code; stale active references can make the split incomplete.
- CLI/MCP dependency split — moving `typer`, `mcp`, and `pydantic` to the right package may reveal hidden import coupling.
- Plugin shim behavior — graph-wiki Bedrock scripts currently shell out to `graph-wiki-agent`; missing one breaks real workflows even if package tests pass.
- Integration test cost/environment — the user requires full tests including integration tests, so execution needs real integration preconditions or clear existing skip gates.

## Existing Codebase / Prior Art

- `agents/graph-wiki-agent/pyproject.toml` — currently declares both `graph-wiki-agent` and `graph-wiki-mcp` scripts; this is the package to split.
- `agents/graph-wiki-agent/src/graph_wiki_agent/cli.py` — current Typer CLI surface to move into `graph_wiki_cli`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/mcp/server.py` — current FastMCP server to move into `graph_wiki_mcp`.
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/` — shared command implementation to rename into `graph_wiki_core.commands` and keep in core.
- `packages/eval-harness/pyproject.toml` — depends on `graph-wiki-agent`; must move to `graph-wiki-core`.
- `plugins/graph-wiki/skills/graph-wiki/scripts/*.py` — Bedrock shims currently shell out to `graph-wiki-agent`; must call `gw`.
- `README.md` and `plugins/graph-wiki/README.md` — current user-facing docs include old CLI usage and package layout.

## Relevant Requirements

- R001 — M002 proves the three-package split is real across workspace integration.
- R002 — S01 owns the core rename and no-script library boundary.
- R003 — S02 owns the `gw` CLI package and entrypoint.
- R004 — S03 owns MCP extraction and `graph-wiki-mcp` entrypoint.
- R005 — S04 owns graph-wiki runtime-facing shim/doc updates to `gw`.
- R006 — S05 verifies tests are colocated by package.
- R007 — S05 owns full workspace and integration verification.
- R008 — S04 owns current user-facing docs.
- R009 — PyPI metadata polish is deferred.
- R010, R011, R012, R013 — explicit exclusions and constraints.

## Scope

### In Scope

- Move from `agents/graph-wiki-agent` to `packages/graph-wiki-core`, `packages/graph-wiki-cli`, and `packages/graph-wiki-mcp`.
- Rename core distribution/import namespace to `graph-wiki-core` / `graph_wiki_core`.
- Rename shared command imports to `graph_wiki_core.commands`.
- Extract CLI code to `graph_wiki_cli` and expose `gw` only.
- Extract MCP server code to `graph_wiki_mcp` and expose `graph-wiki-mcp`.
- Split dependencies by actual package surface.
- Move tests next to the package they validate.
- Update `eval-harness` and other active workspace dependents.
- Update behavior-facing `graph-wiki-agent` CLI references to `gw`.
- Update current user-facing docs for package layout and command usage.
- Run full tests including integration tests.

### Out of Scope / Non-Goals

- No `graph_wiki_agent` import shims.
- No `graph-wiki-agent` console-script alias.
- No plugin identity rename in `.graph-wiki.yaml` or workspace manifests.
- No public PyPI polish beyond minimal metadata.
- No unrelated graph-wiki workflow redesign.
- No wholesale editing of historical docs/fixtures that do not affect runtime behavior or tests.

## Technical Constraints

- Python 3.11+ and `uv` workspace conventions remain.
- Use `uv_build>=0.11.14,<0.12` for workspace packages.
- Workspace dependencies should use `[tool.uv.sources] <package> = { workspace = true }`.
- Root workspace members should be `packages/*` after `agents/` removal.
- Existing Bedrock-only and `model-adapter.make_llm(role)` constraints still apply.
- MCP stdout guard must stay installed before imports that could write to stdout.

## Integration Points

- uv workspace — package membership, workspace sources, lockfile, and per-package test discovery.
- graph-wiki plugin shims — Bedrock branch subprocess command changes from `graph-wiki-agent` to `gw`.
- eval harness — imports shared commands from `graph_wiki_core.commands` and depends on `graph-wiki-core`.
- MCP host protocol — `graph-wiki-mcp` must preserve stdio JSON-RPC framing and tool schemas.
- CLI subprocess tests — `gw` must be discoverable through `uv run --package graph-wiki-cli gw ...` and relevant root commands.

## Testing Requirements

- Run `uv sync` at the root after workspace/package metadata changes.
- Run full test suite including integration tests.
- Include package-local tests for core, CLI, and MCP.
- Include subprocess checks for `gw --help`, representative `gw <cmd> --help`, and `graph-wiki-mcp` stdio/MCP handshake behavior.
- Include stale-reference checks for active code/tests/config where useful.
- Verify graph-wiki plugin Bedrock shims invoke `gw`.

## Acceptance Criteria

- S01: `packages/graph-wiki-core` exists, owns shared implementation under `graph_wiki_core`, has no scripts, and core command tests pass.
- S02: `packages/graph-wiki-cli` exists, owns Typer CLI under `graph_wiki_cli`, exposes only `gw`, and CLI tests/subprocess help checks pass.
- S03: `packages/graph-wiki-mcp` exists, owns FastMCP server under `graph_wiki_mcp`, exposes `graph-wiki-mcp`, and MCP schema/stdout/stdio tests pass.
- S04: Runtime-facing graph-wiki shims and current user-facing docs use `gw`; bootstrap/help text points to current commands; plugin identity remains `graph-wiki-agent`.
- S05: Root workspace is package-only, `agents/` is gone, dependents use `graph-wiki-core`, tests are colocated by package, `uv sync` succeeds, and full tests including integration pass.

## Open Questions

- Exact integration-test invocation may need to respect existing skip gates for Bedrock-costing tests; the user wants full integration coverage, so any skipped integration test must be existing/environment-driven rather than silently excluded by the plan.
