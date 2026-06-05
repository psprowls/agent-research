# Design: Part 1 cleanup boundary pass

**Date:** 2026-06-05
**Status:** Design approved; waiting for user review before implementation planning
**Source:** `docs/cleanup-backlog.md` — "Prioritized cleanup backlog (Part 1)"
**Topic:** Clean up Part 1 library-package boundary violations while correcting the backlog for APIs that are intentionally retained.

## Goal

Make the Part 1 packages reflect the repo boundary rule: library packages export importable behavior only, while command parsing, stdout/stderr formatting, and `if __name__ == "__main__"` blocks live in allowed delivery surfaces.

This pass also updates `docs/cleanup-backlog.md` so the backlog matches the decisions made during review. The target is not "delete every symbol with no production caller"; the target is a clean library/executable boundary plus removal of genuinely orphaned functionality.

## Locked Decisions

1. **Use one Part 1 cleanup spec** with independent implementation slices.
2. **Class A `wiki-io` modules lose executable surfaces only.** Keep their library functions.
3. **Class B plugin shims become standalone scripts.** Each plugin script owns argparse/output and calls library functions directly. No shared plugin command-helper module in this pass.
4. **Keep `wiki_io.graph_analyzer` as library behavior.** Remove its `main()` and `__main__`; move graph-analyzer CLI parsing/output into the plugin script.
5. **Delete `wiki_io.link_rewriter.py`.** The migrate-vault functionality was removed, and no command should be wired now.
6. **Keep `workspace_io.versions.py`.** It is an intentional manifest/plugin update-state API, currently reserved/unwired in production.
7. **Keep `graph_io.queries.list_entry_points`.** It is an intentional symmetric public query helper for the `entry_point` node kind.

## Scope

### In Scope

- Remove executable `main()` / `__main__` surfaces from `wiki-io` Class A modules:
  - `update_index.py`
  - `update_tokens.py`
  - `append_log.py`
- Invert Class B plugin scripts:
  - `plugins/graph-wiki/skills/graph-wiki/scripts/init_vault.py`
  - `plugins/graph-wiki/skills/graph-wiki/scripts/ingest_source.py`
  - `plugins/graph-wiki/skills/graph-wiki/scripts/wiki_search.py`
  - `plugins/graph-wiki/skills/graph-wiki/scripts/lint_wiki.py`
  - `plugins/graph-wiki/skills/graph-wiki/scripts/graph_analyzer.py`
- Remove `workspace_io.config._main()` / `__main__` and the orphaned `sys` import.
- Delete `wiki_io.link_rewriter.py` and its tests.
- Update tests for the new boundaries.
- Update `docs/cleanup-backlog.md` to reclassify retained APIs and remove completed/deleted items from active cleanup guidance.

### Out Of Scope

- Low-priority graph-io style cleanup.
- Unused `ctx` parameter removal.
- Type-hint modernization of legacy wiki-io modules.
- Frontmatter parser consolidation.
- Promoting graph analysis to `graph-wiki-core` or a `gw` command.
- Wiring `workspace_io.versions` into command-entry stale-version checks.

## Module Design

### `wiki-io` Class A

`update_index.py`, `update_tokens.py`, and `append_log.py` keep their importable functions and lose their executable CLI wrappers.

- Remove `main()` and `if __name__ == "__main__"` blocks.
- Remove usage docstrings that claim direct `python ...` execution.
- Remove CLI-only imports when they are no longer needed.
- Preserve library error semantics that current callers rely on. In particular, `append_log.append_log(..., raise_exception=True)` must still raise instead of exiting for MCP/file-work-item callers.

The allowed user-facing paths for this behavior are existing core/CLI/plugin surfaces, not `python -m wiki_io.<module>`.

### `wiki-io` Class B And Plugin Scripts

The five plugin shims currently import `main` from `wiki_io`. After this cleanup, they become standalone executable scripts:

- Each script keeps `_uv_reexec.ensure()` as the first runtime setup step where it exists today.
- Each script imports the relevant library functions from `wiki_io`.
- Each script owns argparse, workspace/repo resolution, JSON/text formatting, exit behavior, and stderr/stdout choices.
- The matching `wiki_io` module exposes library functions only.

This intentionally duplicates small CLI wrappers in the delivery surface rather than introducing a shared command-runner abstraction.

### `wiki_io.graph_analyzer`

`graph_analyzer.py` remains a library module because its analysis behavior is useful and the plugin linter still depends on graph stats. The executable surface moves to `plugins/graph-wiki/skills/graph-wiki/scripts/graph_analyzer.py`.

Keep:

- `_parse_frontmatter_lists`
- `build_graph`
- `connected_components`
- `analyze`

Move to plugin script:

- argparse setup
- `resolve_wiki_and_repo()`
- JSON/text output

Remove from `wiki_io.graph_analyzer`:

- shebang
- executable usage docstring
- `main()`
- `if __name__ == "__main__"`
- CLI-only imports after verifying they are not needed by library functions

### `workspace_io.config`

Remove the executable module behavior:

- delete `_main()`
- delete `if __name__ == "__main__"`
- delete orphaned `import sys`

Update or remove `test_cli_prints_workspace_to_stdout`, since `python -m workspace_io.config` is no longer a supported surface. Tests should exercise `resolve()` directly.

### `wiki_io.link_rewriter`

Delete the module and its tests. The previously promised `cg migrate-vault` command is not part of the current product direction, and retaining the unwired module would preserve a dead feature hook.

### `workspace_io.versions`

Retain the module and re-exports:

- `PendingUpdate`
- `pending_updates`
- `warn_if_stale`

Clarify in `docs/cleanup-backlog.md` that this is an intentional reserved API for manifest/plugin update-state. It is currently unwired in production, but it is backed by manifest schema behavior and focused tests. Do not add command-entry checks in this cleanup pass.

### `graph_io.queries.list_entry_points`

Retain the helper and its tests. It is a symmetric public query API alongside `list_packages`, `list_test_suites`, `list_domains`, `list_dependencies`, `list_apps`, and related helpers. Update the backlog so future cleanup does not treat it as dead code.

## Backlog Corrections

After implementation, `docs/cleanup-backlog.md` should reflect:

- Class A executable surfaces removed.
- Class B shim contract inverted.
- `graph_analyzer` retained as importable library behavior, not relocated wholesale.
- `workspace_io.config` executable block removed.
- `wiki_io.link_rewriter` deleted because migrate-vault is intentionally absent.
- `workspace_io.versions` retained as reserved update-state API.
- `graph_io.queries.list_entry_points` retained as symmetric public query API.

The backlog should still list unresolved low-priority cleanup items that remain out of scope.

## Testing

Run focused package tests first:

- `uv run --package wiki-io pytest`
- `uv run --package workspace-io pytest`
- `uv run --package graph-io pytest`

Also run static cleanup checks:

- `rg -n "def main\\(|if __name__ == [\"']__main__[\"']|argparse" packages/wiki-io/src/wiki_io packages/workspace-io/src/workspace_io`
- `rg -n "from wiki_io\\..* import main|import main" plugins/graph-wiki/skills/graph-wiki/scripts`

Expected result:

- No executable `main()` / `__main__` surfaces remain in `wiki-io` or `workspace-io`.
- Plugin scripts still execute as the allowed command surfaces.
- `wiki-io`, `workspace-io`, and `graph-io` tests pass after updates.

## Suggested Implementation Slices

1. **Class A library cleanup** — remove `wiki-io` executable wrappers and update tests/imports.
2. **Class B shim inversion** — rewrite the five plugin scripts, then remove `main()`/executable surfaces from the matching library modules.
3. **Workspace config cleanup** — remove `workspace_io.config` executable behavior and update tests.
4. **Dead-feature deletion** — remove `wiki_io.link_rewriter` and its tests.
5. **Backlog correction** — update `docs/cleanup-backlog.md` for completed work and retained APIs.

Each slice should be testable independently. The Class B slice has the most behavioral risk because it must preserve existing plugin script output and JSON shapes.

## Risks

- **Plugin script output drift.** The linter and command markdown expect existing JSON/text behavior. Preserve output shapes when moving argparse/output into plugin scripts.
- **Accidental library behavior deletion.** Remove only executable wrappers from Class A modules; keep all functions used by core commands.
- **Over-correcting `graph_analyzer`.** Do not relocate the whole module. Only move executable behavior to the plugin script.
- **Backlog ambiguity recurring.** Update `docs/cleanup-backlog.md` in the same implementation effort so future agents do not re-open settled deletion decisions.
