# Design: `.gitkeep` placeholder for `wiki/entities/`

**Date:** 2026-06-01
**Status:** Approved

## Problem

When bootstrapping a vault, `wiki-io/src/wiki_io/init_vault.py` writes
`wiki/entities/_index.md` — a sentinel-comment markdown file that is never
populated. Its only job is to keep `entities/` non-empty so git commits the
directory. It is dead weight: a fake page that the entity walks then have to
explicitly skip in two places.

## Goal

Replace the never-populated `entities/_index.md` with a `.gitkeep` placeholder
that exists only while `entities/` is empty, and is self-healed away by `gw scan`
once real entity pages exist.

## Why `write_entities()` is the hook

`gw scan` populates entities exclusively through `write_entities()`
(`packages/wiki-io/src/wiki_io/entity_writer.py:704`). That function owns the
`entities/` directory: it `mkdir`s it (`:720`), runs the per-kind create/merge
loop, and runs the deletion sweep. Hooking the placeholder lifecycle there means
*every* scan maintains it correctly, with no separate orchestration in the scan
command layer.

## Changes

### 1. `init_vault.py` (lines ~208-218)

Swap the `_index.md` block for `.gitkeep`:

- Write an empty `entities/.gitkeep`.
- Record `entities/.gitkeep` in `installed_files`.
- Update the inline comment — drop the Obsidian-visibility rationale; the file is
  now purely a git placeholder.

A fresh bootstrap still produces a committable `entities/` directory, via the
dotfile instead of a fake page.

### 2. `entity_writer.py` → `write_entities()`

Two edits, both inside the existing `_acquire_scan_lock` block:

- **Remove** the `_index.md` skip in the deletion sweep (`:824`).
  `entities_dir.glob("*.md")` already excludes `.gitkeep`, so nothing replaces it.
- **Add** self-healing at the *end* of the lock block (after create/merge and the
  deletion sweep, so it reflects post-sweep state):

  ```
  if any(entities_dir.glob("*.md")):
      remove entities_dir / ".gitkeep"   # if present
  else:
      (re)create empty entities_dir / ".gitkeep"
  ```

  This covers both directions: the first populated scan deletes the placeholder;
  a scan whose deletion sweep empties the directory restores it.

### 3. `scan_monorepo.py` (line ~967)

Remove the `_index.md` skip in the entity index walk. `glob("*.md")` excludes
`.gitkeep`, so no replacement is needed.

## Tests

- `packages/wiki-io/tests/test_init_vault.py:227-261` — rewrite to assert
  `.gitkeep` is created and listed in `installed_files`; drop the `_index.md`
  assertions.
- `packages/wiki-io/tests/test_load_existing_pages.py:92`
  (`test_entities_walk_skips_index_md`) — remove. The `_index.md` skip it covered
  is gone, and `.gitkeep` is never matched by the `*.md` walk.
- `packages/wiki-io/tests/integration/test_entity_writer_integration.py:259` —
  drop the `!= "_index.md"` filter; use plain `glob("*.md")`.
- **New** `write_entities` coverage:
  - After a scan that creates ≥1 entity page, `entities/.gitkeep` is absent.
  - After a scan that leaves `entities/` empty (e.g. deletion sweep removes the
    last entity), `entities/.gitkeep` is present.

## Not doing

- No backward-compat handling for existing `_index.md` files — no production
  vaults exist; they will be deleted and rebuilt (per
  `.claude/rules/backward-compatibility.md`).
- No `.gitignore` change — the wiki `.gitignore` patterns
  (`.obsidian/*`, `.DS_Store`) do not touch `.gitkeep`.
