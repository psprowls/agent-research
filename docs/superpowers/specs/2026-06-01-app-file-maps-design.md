# Design: Extend `gw scan` file maps to app wiki pages

**Date:** 2026-06-01
**Status:** Approved (brainstorm)

## Problem

`gw scan` populates a deterministic `## File map` section (plus durable LLM-filled
per-file descriptions) on **package** entity pages, but not on **app** entity pages.
App pages ship the same template section but it is never filled. We want apps to
receive the identical file-map treatment as packages.

## Goal

App entity pages get the same `## File map` population that package pages already
get: deterministic rows (path/kind) injected, then the code-reader fan-out fills the
per-file Description cells, with descriptions preserved across rescans.

**Decision (approved):** full parity — apps get both the deterministic rows (Step 10b)
*and* the LLM code-reader description fill (Step 10c). No app-only "rows-only" mode.

## Kind coverage

The graph exposes kinds `repository`, `package`, `app`, `domain`
(`wiki_io/entity_writer.py:_kind_list_fns`). The filesystem `type` heuristic
(`_infer_package_type`) returns app/service/tool/library, but **only `app` becomes its
own graph kind** — service/tool/library all land under `package`. So `package` + `app`
together cover every workspace with a source tree. `repository` (repo root) and
`domain` (abstract grouping) have no file tree and need no file map.

## What is already in place (no change required)

1. **File-map build** — `commands/scan.py:760` (Step 4) builds a file map for *every*
   workspace, apps included. `ws_fm_by_name` already contains app file maps.
2. **Durability snapshot** — `_snapshot_file_map_descriptions` (`commands/scan.py:135`)
   walks all entity pages by URI, kind-agnostic. App descriptions are already preserved
   across rescans.
3. **App template** — `wiki_io/assets/page-templates/entity-app.md:36-44` already has a
   `## File map` section to inject into.
4. **Step 10c (LLM fill)** — keys off `file_mapped_pages`, populated by Step 10b. Once
   apps appear in that list, the code-reader fan-out covers them with no extra wiring.

## The change (single locus)

**Step 10b** in `commands/scan.py` (lines 941–975) currently iterates
`_kind_list_fns().get("package")`. Extend it to iterate **both** `package` and `app`
node lists, applying the identical inject logic to each:

```python
list_fns = _kind_list_fns()
fm_list_fns = [list_fns.get("package"), list_fns.get("app")]
nodes = [n for fn in fm_list_fns if fn for n in fn(conn)]
for node in nodes:
    ...  # existing inject_file_map logic unchanged
```

`_compute_collision_set` and `inject_file_map(preserved=...)` are already
kind-agnostic and remain unchanged. The `refreshed`-set guard (only created/updated
entities) still applies, so app pages are only touched when they were (re)written.

## Side adjustment

- **Log wording** — Step 10c's log line says `"... package(s) ..."`
  (`commands/scan.py:1062`). Broaden to read accurately for apps (e.g. "entity(s)").
  Step 10b's "file maps injected: N" line needs no change.

## Testing

Follow the existing scan file-map test pattern (pytest + syrupy snapshots; LLM mocked
at the fake-Bedrock boundary).

1. **App injection** — add an app workspace to the scan fixture; assert its entity page
   receives an injected `## File map` block, and that an unfilled row carries a TODO
   Description cell before the (mocked) code-reader fill.
2. **App description fill** — with the code-reader response mocked, assert the app
   page's TODO cells are filled.
3. **Rescan durability** — a filled app description survives a second scan (proves the
   snapshot path covers apps).

## Out of scope (YAGNI)

- No app-specific `max_depth` / `max_entries` tuning — apps use the same caps as packages.
- No app-only `--no-file-map`-equivalent toggle.

## Key references

| Concern | Location |
|---|---|
| Scan entry / `run_scan` | `commands/scan.py:556` |
| File-map build per workspace | `commands/scan.py:760` |
| Durability snapshot | `commands/scan.py:135` |
| Step 10b (inject — change here) | `commands/scan.py:941-975` |
| Step 10c (LLM fill — flows through) | `commands/scan.py:989-1067` |
| Kind list fns | `wiki_io/entity_writer.py:_kind_list_fns` |
| `inject_file_map` | `wiki_io/entity_writer.py:1065` |
| App template | `wiki_io/assets/page-templates/entity-app.md:36-44` |
