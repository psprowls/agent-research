# Design: `gw wiki` command group + `migrate-vault` removal

**Date:** 2026-06-01
**Status:** Approved (ready for implementation plan)
**Scope:** `graph-wiki-cli` command surface restructuring

## Summary

Two changes to the `gw` CLI command surface:

1. **Remove `migrate-vault` entirely.** No production vaults exist, and vaults are
   rebuilt rather than migrated until v2.0 (per `.claude/rules/backward-compatibility.md`),
   so the migration command and its implementation are dead weight.
2. **Introduce a `gw wiki` command group**, mirroring the existing `gw graph` group,
   and move the wiki-maintenance commands under it:
   - `gw log`           → `gw wiki log`
   - `gw lint`          → `gw wiki lint`
   - `gw query`         → `gw wiki query`
   - `gw ingest source` → `gw wiki ingest source`
   - `gw ingest work-item` → `gw wiki ingest work-item`

`scan`, `bootstrap`, `trace`, `version`, `help`, and the `graph` group stay at the
top level — `scan`/`bootstrap` are more general and relate to graph functionality as
well, so they are intentionally NOT moved.

## Decisions (resolved during brainstorming)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| migrate-vault removal depth | **Full removal** | Remove CLI command, `run_migrate_vault` implementation, and its tests. No vaults to migrate pre-v2.0. |
| Move `scan`/`bootstrap` under `wiki`? | **No** | They are more general and relate to graph functionality too. |
| Where does `wiki_app` live? | **Extracted `wiki_cli/` module** | Mirror `graph_cli/main.py` for structural symmetry. |
| Backward-compat aliases for old paths? | **No** | Pre-v2.0, no production vaults; clean break. |

## Architecture

### New module: `wiki_cli/`

Create `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, mirroring
`graph_cli/main.py`. It exposes:

```python
wiki_app = typer.Typer(
    name="wiki",
    help="Wiki maintenance operations.",
    no_args_is_help=True,
)
```

The following are moved **verbatim** out of `cli.py` (command bodies unchanged — same
options, exit codes, `--json` handling, error translation):

- `query`  → `@wiki_app.command()`
- `log`    → `@wiki_app.command()`
- `lint`   → `@wiki_app.command()`
- the `ingest` sub-app (`source`, `work-item`) → `wiki_app.add_typer(ingest_app, name="ingest")`,
  so the nested path becomes `gw wiki ingest source` / `gw wiki ingest work-item`.

The `run_query` / `run_log` / `run_lint` / `run_ingest_source` / `run_ingest_work_item`
imports (and `_gio_exit_codes` for the ingest NOT_INITIALIZED exit code) move with their
commands into `wiki_cli/main.py`. A `main()` entry mirrors `graph_cli/main.py`.

### `cli.py` changes

- Delete the `migrate-vault` command function and the
  `from graph_wiki_core.commands.migrate_vault import run_migrate_vault` import.
- Delete the `query`, `log`, `lint` command functions and the `ingest_app` block
  (now living in `wiki_cli/main.py`); drop their now-unused imports.
- Add `from graph_wiki_cli.wiki_cli.main import wiki_app` and
  `app.add_typer(wiki_app, name="wiki")` (placed alongside the existing
  `app.add_typer(graph_app, name="graph")`).
- `trace`, `version`, `help`, `bootstrap`, `scan` remain as top-level commands;
  `bootstrap`/`scan` keep their `run_init` / `run_scan` imports, so
  `from graph_wiki_core.commands…` still appears in `cli.py`.

### Full migrate-vault removal

- Delete `packages/graph-wiki-core/src/graph_wiki_core/commands/migrate_vault.py`.
- Delete `packages/graph-wiki-core/tests/test_migrate_vault.py`.
- Grep-sweep for any other `migrate_vault` references (e.g. a `commands/__init__.py`
  re-export) and clean them.

## Coupled consumers (must move in lockstep)

### Bedrock plugin shims
`plugins/graph-wiki/skills/graph-wiki/scripts/`:
- `wiki_search.py`   : `["gw", "query"]`            → `["gw", "wiki", "query"]`
- `ingest_source.py` : `["gw", "ingest", "source"]` → `["gw", "wiki", "ingest", "source"]`
- `lint_wiki.py`     : `["gw", "lint"]`             → `["gw", "wiki", "lint"]`

`scan_monorepo.py` (`gw scan`) and `init_vault.py` (`gw bootstrap`) are unchanged.
No shim exists for `log` or `ingest work-item`.

### Tests
- `packages/graph-wiki-cli/tests/unit/test_commands_log.py` — `["log", …]` → `["wiki", "log", …]`.
- `packages/graph-wiki-cli/tests/unit/test_cli_query.py` — 3 invocations `["query", …]` → `["wiki", "query", …]`.
- `packages/graph-wiki-cli/tests/unit/test_plugin_bedrock_shims.py` — update `expected_argv`
  for the query/ingest/lint shim cases.
- `packages/graph-wiki-cli/tests/unit/test_cli_boundary.py` — `test_cli_module_imports_core_commands_not_agent_cli_shim`
  asserts `from graph_wiki_core.commands.query import run_query` lives in `cli.py`; update so
  it asserts the import now lives in `wiki_cli/main.py`, and that neither module imports
  `graph_wiki_agent`. Optionally add a symmetry test like the existing
  `test_graph_package_exposes_moved_cli_module_for_gw_graph_namespace`.
- `packages/graph-wiki-cli/tests/unit/test_cli_help.py` — scan for assumptions about which
  commands appear at the top level (the `init`/`ingest` whole-word check); ensure it still
  holds with `ingest` no longer top-level.

### Docs
- `docs/gw-cli.md` — update all `gw log` / `gw lint` / `gw query` / `gw ingest …` references
  to the `gw wiki …` paths and drop `migrate-vault`.

## Unaffected

- **MCP server** (`packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`) — imports the
  `run_*` functions directly and its tool names are already `wiki_*`; no command-path
  coupling.

## Verification

- `uv run --package graph-wiki-cli pytest`
- `uv run --package graph-wiki-core pytest`
- Spot-check: `gw wiki --help`, `gw wiki ingest --help`, `gw wiki query --help`;
  confirm `gw migrate-vault` no longer exists and `gw --help` no longer lists
  `log`/`lint`/`query`/`ingest`/`migrate-vault` at the top level.
