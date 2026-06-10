# Archive Immediate Terminal — Design

**Date:** 2026-06-10
**Status:** approved

## Summary

Two changes to the `gw work archive` / `/graph-wiki:archive` command:

1. **Remove the `min_age_days` age gate.** Sweep mode previously only archived terminal items that were at least 7 days old. Terminal items are now archived immediately — no age check.
2. **Rename the archive directory** from `wiki/work/archived/` to `wiki/work/_archived/`.

## Motivation

The age gate was a hedge against accidental terminal-status assignments. For a single-developer project where archiving is intentional, it is dead weight. The `_archived` prefix makes the directory sort below active work items in most file browsers and tooling, visually separating done-and-gone items from the live set.

## Approach

Approach A (clean removal) — remove `min_age_days` entirely at every layer. No backwards-compatibility shim.

## Changes by Layer

### `packages/work-io/src/work_io/archive.py`

- `plan_archive(work_dir, slugs, min_age_days)` → `plan_archive(work_dir, slugs)`.
- Sweep mode: remove the `age >= min_age_days` predicate. Only filter is terminal status.
- `archived_dir = work_dir / "archived"` → `work_dir / "_archived"`.

### `packages/graph-wiki-core/src/graph_wiki_core/commands/work.py`

- `run_work_archive(…, min_age_days)` → drop the parameter.
- Remove the `min_age_days` kwarg from the `plan_archive()` call.

### `packages/graph-wiki-cli/src/graph_wiki_cli/work_cli/main.py`

- Remove the `--min-age-days` Typer option from `archive()`.

### `plugins/graph-wiki/commands/archive.md`

- Remove documentation of `min_age_days` default (7 days) and the age gate description.

### `packages/work-io/src/work_io/lifecycle_lint.py`

- Rule 14 ("archive-eligible"): remove the `updated >= 7 days` age condition. Fires on any item with terminal status (`resolved`, `wontfix`, `superseded`).

## Tests

### `packages/work-io/tests/unit/test_archive.py`

Remove:
- Test asserting sweep skips items younger than `min_age_days`.
- Test asserting sweep archives items older than `min_age_days`.

Add/update:
- Sweep archives all terminal items immediately (no age involved).
- Sweep still skips non-terminal items.
- Targeted mode destination path uses `_archived/`.

### Lifecycle lint tests

- Any test asserting Rule 14 only fires after 7 days: update to assert it fires immediately on terminal status.

## Migration

No migration code. Existing `wiki/work/archived/` directories are left in place (no-migration-until-v2 convention). Manual `git mv wiki/work/archived wiki/work/_archived` in the workspace is available but out of scope.

## Out of Scope

- Any other references to `archived` as a status value (distinct from the directory name).
- Changes to how targeted mode selects slugs.
