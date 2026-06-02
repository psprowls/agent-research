# Test-suite file maps (`gw scan`)

**Date:** 2026-06-02
**Status:** Approved (design)
**Scope:** `graph-wiki-cli` / `gw scan` only. The `graph-wiki` plugin and
`plugins/graph-wiki/.../scan_monorepo.py` are **out of scope** (stale, to be
reworked separately).

## Goal

Extend the existing package/app **file map** functionality to `test_suite`
entity wiki pages, generated through the `gw scan` path. Each test-suite page
gains a populated `## File map` section whose tree **starts at the root of the
test-suite** (`node.attrs["path"]`), with per-file descriptions filled by the
same `code_reader` LLM fan-out packages and apps already use.

## Background — how package/app file maps work today

The relevant code lives in
`packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` (the `gw scan`
entry, `run_scan`) and `packages/wiki-io/src/wiki_io/`:

- **Step 4** (`scan.py:760`): for each discovered workspace, `build_file_map(repo / w["path"])`
  (in `wiki_io/scan_monorepo.py`) computes a deterministic `## File map - <name>`
  markdown block and stores it on `w["file_map"]`.
- **Step 9a/9b**: `write_entities` (re)renders entity pages from templates
  (wiping any injected file-map body), then a narrator fan-out fills the
  `## Narrative` section. The narrator receives `file_map` as a grounding hint
  **only for `kind == "package"`** (`scan.py:852`).
- **Step 10b** (`scan.py:925`): for every `package`/`app` page that was
  created/updated this scan, `inject_file_map(page_path, block, preserved=...)`
  replaces the `## File map` section with the deterministic block.
- **Step 10c** (`scan.py:991`): a `code_reader` fan-out reads representative
  files and fills each remaining `— TODO` description cell via
  `fill_file_map_descriptions`.

**File-map builder partition.** `build_file_maps()` (`scan_monorepo.py:519`)
splits files into prod vs. test via `_is_test_path()`. `build_file_map()`
returns the **prod-only** block. Test files therefore have **no home** in the
wiki today.

## Approach (selected: A — dedicated test-suite branch)

Add a self-contained test-suite file-map path rather than folding `test_suite`
into the package/app loops. The package/app loops assume workspace-dict-keyed
data and prod-only partitioning; test-suites have neither, and the scan code
already special-cases `test_suite` separately (e.g. the `_entity_page_path`
helper at `scan.py:888`). A parallel branch keeps each path readable.

### 1. New builder — `build_dir_file_map`

Add to `wiki_io/scan_monorepo.py`:

```
def build_dir_file_map(path: Path, max_depth: int = 4, max_entries: int = 80) -> str | None
```

- Returns a single `## File map - <root-basename>` block covering **all**
  tracked files under `path`, via the existing `_git_ls_files` +
  `_emit_file_map_block`. **No prod/test partition.**
- **Why unpartitioned:** everything under a test-suite root is test-related.
  Reusing `build_file_map` (prod-only) would mis-route a root `conftest.py`
  into the dropped test half, while a plain `helpers.py` would land in prod —
  so *either* partitioned half drops files. The suite map must list everything
  under its root.
- Mirrors `build_file_maps` contracts: returns `None` when `_git_ls_files`
  returns `None` (not git); emits the `- (no tracked files)` short-circuit for
  an empty root; honors `max_entries` truncation.
- `build_file_map` / `build_file_maps` are **untouched**; package/app maps stay
  prod-only.

### 2. New step — "Step 10b-ts" in `scan.py`

Immediately after the existing package/app file-map block (`scan.py:925-989`),
add a test-suite branch:

1. `refreshed = created | updated` (already computed at `scan.py:942`).
2. For each `test_suite` node from `list_test_suites(conn)` whose
   `node.attrs["uri"]` is in `refreshed`:
   - Resolve suite root: `suite_path = node.attrs["path"]`.
   - `block = build_dir_file_map(repo / suite_path, max_depth=max_depth)`;
     skip if `None`/empty.
   - Derive page path with the **suite-aware** slug — reuse the
     `suite_kind` + `pkg_for_suite` logic already in `_entity_page_path`
     (`scan.py:888-907`), **not** the plain `short_filename` the package loop
     uses. Factor that block into a small shared helper if convenient.
   - `inject_file_map(page_path, block, preserved=prior_file_map_descs.get(uri))`.
   - Append `(uri, node, page_path)` to the existing `file_mapped_pages` list so
     Step 10c picks it up.
3. Fold counts into the existing `file maps injected:` log line.

### 3. Step 10c (describer) — reused, with a synthesized dict

`build_file_describer_prompt` (`scan.py:416`) reads only `name`, `path`, `type`,
`language` from its `pkg` dict and resolves snippets via
`pick_representative(repo_root / path)`. The current scoping does
`ws_dict = ws_by_name.get(node.name)`, which returns `None` for suites
(`scan.py:1006`). Replace with: if the node is a `test_suite`, synthesize

```
{"name": <suite display name>,
 "path": <suite root path>,
 "type": "test_suite",
 "language": node.attrs.get("language", "unknown")}
```

so `pick_representative` samples files from the suite root. Everything else in
Step 10c (parse, `fill_file_map_descriptions`) is unchanged.

### 4. Narrator hint (small extension)

Extend `scan.py:852` so the test-suite's file map is passed to the narrator for
`kind == "test_suite"` too (grounds the suite narrative in its tree). Cheap and
consistent; the file-map text is computed in Step 10b-ts and can be looked up by
URI. Optional — may be dropped to keep scope minimal without affecting the core
feature.

## Durability (cross-rescan preservation)

Expensive `code_reader` descriptions must survive rescans exactly as they do for
packages. **This reuses the existing machinery with no new durability code:**

1. **Snapshot** — `_snapshot_file_map_descriptions` (`scan.py:135`) already
   globs **all** `entities/*.md` and keys by frontmatter `uri` *without
   filtering by kind*, so it captures test-suite pages automatically. It runs at
   `scan.py:797`, before `write_entities` resets bodies.
2. **Merge** — Step 10b-ts passes `preserved=prior_file_map_descs.get(suite_uri)`
   to `inject_file_map`, which restores filled cells onto the fresh block via
   `_merge_preserved_descriptions`.
3. **Fill** — Step 10c's `file_map_todo_paths` then returns only *unfilled*
   rows, so a fully-described suite triggers **no model call** on rescan.
   Steady-state cost is zero, identical to packages.

**The one obligation this imposes.** The snapshot→merge round-trip keys
descriptions by *suite-root-relative paths*, reconstructed by stripping the
`pkg_name` label out of the `## File map - <pkg_name>` heading and
`### <pkg_name>/…` section headers (`_section_path_context` /
`_file_map_full_path`). For restore to line up across rescans:

- the `pkg_name` passed to `build_dir_file_map` **must be deterministic and
  stable** for a given suite — use the **suite root directory basename**
  (stable unless the suite physically moves; matches how packages use their dir
  name). No counters/timestamps/collision-suffixed slugs feed the label.
- the page's frontmatter `uri` **must match** `node.attrs["uri"]` — already true
  (`write_entities` sets it).

Both hold, so durability is satisfied by reuse alone.

## Out of scope / unchanged

- Package/app file maps stay prod-only; the test-suite page is the new home for
  the test file tree (no double-listing).
- `entity-test-suite.md` already carries a `## File map` section — no template
  change.
- `max_depth` / `max_entries` reuse the same scan defaults.
- The `graph-wiki` plugin and its `scan_monorepo.py`.

## Testing

- **Unit — `build_dir_file_map`:** unpartitioned output (a root `conftest.py`
  *is* listed), empty root → `- (no tracked files)`, non-git → `None`,
  truncation marker at `max_entries`.
- **Integration** (mirror `packages/graph-wiki-core/tests/unit/test_scan_graph_integration.py`):
  a `test_suite` entity page gets its `## File map` section injected from the
  suite root with `— TODO` rows; a second scan with a pre-filled description
  preserves it (durability) and triggers no describer call for that suite.

## Touch list

- `packages/wiki-io/src/wiki_io/scan_monorepo.py` — add `build_dir_file_map`.
- `packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py` — Step 10b-ts;
  describer-dict synthesis in Step 10c; narrator-hint extension.
- Tests as above.
