# Design: de-containerize graph-wiki — remove container detection + layout block

**Date:** 2026-06-03
**Status:** Approved — ready for implementation planning
**Companion:** `2026-06-03-graph-wiki-plugin-staleness-audit.md` (findings report — the evidence base)
**Topic:** Remove the container concept entirely from the shared `wiki_io` / `graph_wiki_core` core (and therefore from both `gw` and the `graph-wiki` plugin): no container classification, no pinned layout block, no `package-family`, no docs-container support. Entity discovery becomes purely graph-driven, which it already effectively is.

## Goal

The graph (`cg build`, filesystem-driven) is already the sole source of truth for wiki entity pages via `write_entities(conn, ...)`. Container detection + the pinned layout block are a pre-graph remnant: the layout block's only live consumer is the legacy `discover_workspaces` walk, whose output now feeds just file-map text (re-sourceable from graph node paths) and a diff the code marks "legacy view only." Remove the whole apparatus so the codebase says what it does: scan the graph, write entities.

## Locked decisions (2026-06-03 brainstorm)

1. **Remove from shared core** — lands on both `gw` and the plugin (they share `wiki_io.init_vault` + `graph_wiki_core.run_scan`). `gw bootstrap` stops pinning a layout block; `gw scan` is always graph-scoped.
2. **Re-source package/app file maps from graph node paths** — mirror the existing `test_suite` branch (`scan.py:1014-1045`: `node.attrs["path"]` → `build_*_file_map(repo / path)`), eliminating `discover_workspaces`.
3. **Remove `package-family` everywhere** — including the dependency `kind` enum. Zero production-code references; docs + a few tests only.
4. **Remove docs-container support** — drop in-repo-doc auto-surfacing as ingest candidates; no replacement.
5. **Drift:** remove container/layout drift + source-sync drift; keep package-sync drift + structural code-drift. Scan's `entities +N ~M -D` report + deletion confirmation remain the structural-change signal.

## The change, by area

### A. `graph_wiki_core/commands/scan.py` — the core refactor (highest risk)

This is the only meaty code change; everything else is deletion or doc edits. `run_scan` currently does, in its middle section:

- Step 2 (`:759-772`) read layout block → `pinned`
- Step 3 (`:774-775`) `discover_workspaces(repo, pinned_containers=pinned)`
- Step 3.5 (`:777-811`) decorate workspaces with graph URIs/domain
- Step 4 (`:813-819`) `build_file_map` per workspace → `w["file_map"]`
- Steps 5-7 (`:821-828`) `existing_pages.legacy`, `attach_changed_files`, `compute_diff` (all "legacy view only — D-12")
- Step 10b (`:973-1012`) inject package/app file maps, looking up text via `ws_fm_by_name` (built from `workspaces`)

**Target:** delete Steps 2, 3, 3.5, 4, 6, 7 and the `pinned`/`workspaces`/`ws_by_name` plumbing. Rewrite Step 10b to iterate graph package/app nodes (`queries.list_packages` / app query already used at `:986-987` via `fm_list_fns`) and build each file map from `node.attrs["path"]` — `build_file_map(repo / path, max_depth)` for packages/apps (preserving the **prod/test partitioning** `build_file_map` does — *not* the unpartitioned `build_dir_file_map` the suite branch uses). The snapshot→merge durability path (`prior_file_map_descs`, `preserved=`) is unchanged.

**Collapse the legacy `ScanResult` fields.** The dataclass carries legacy name-keyed fields alongside the URI-keyed entity fields (`:262`). With the legacy view gone, remove the legacy fields and any reporting/`--json` paths that emit them. Find all `ScanResult(...)` consumers (CLI formatter, plugin shim, tests) and update.

**Remove docs-container ingest-candidate surfacing.** The candidate-list (in-repo `.md` under a pinned `docs` container) flows through the legacy scan path / `ScanResult` candidate fields. Remove the surfacing and its result fields. (Exact site is in `wiki_io.scan_monorepo` + the `ScanResult` candidate fields — the plan locates precise lines.)

### B. `wiki_io/init_vault.py` — stop pinning

- Remove `_detect_containers` import + `_resolve_pinned_containers` (`:96-118`), the `pinned` flow (`:189`), and the `_write_layout` call (`:260-270`). `init_wiki` creates the fixed vault tree (`entities/` + curated dirs + templates) and the schema files, with **no layout block** and no detection prompt. Drop the `--non-interactive`/`interactive` container-prompt plumbing that exists only for ambiguous-container resolution.

### C. `wiki_io` deletions

- Delete `detect_containers.py`, `layout_io.py`, `lint/container.py`, `lint/source_sync.py`.
- `scan_monorepo.py`: remove `discover_workspaces` (pinned + heuristic), `_discover_from_pinned`, `reconcile_layout`, `_wiki_relative_path_for` (legacy apps/domains/packages routing), and the docs-candidate logic. Keep genuinely shared helpers still used by the graph path (`unscope`, `_is_test_path`, `build_file_map`, file-map builders) — audit each for remaining callers before deleting.

### D. `graph_wiki_core` — lint + prompt

- `commands/lint.py`: drop the container-drift and source-sync checks from the registry; keep package-sync + structural code-drift.
- `prompts/project_context.py`: remove the layout-block injection (no block to read).

### E. `package-family` removal

- No production code references. Remove from: `wiki-schema.md`, `lint-workflow.md` (the `dep-kind-not-in-enum` enum + `dep-family-without-members` rule), `page-formats.md`, and the dependency template/asset if it enumerates the kind. Update the dependency `kind` enum (wherever validated) to `package | service`. Fix the affected tests (`test_uri.py`, `test_cli_main.py`, `test_assets.py`, `test_entity_writer.py`, `test_entity_templates.py`).

### F. Plugin — scripts + markdown (Category A + B from the findings report)

- **Delete** `skills/graph-wiki/scripts/detect_containers.py` and `references/detection-workflow.md`.
- **Edit** per findings Category A: `bootstrap.md` (drop the "Container detection" section), `scan.md` (drop drift/reconcile + docs-candidate flow), `ingest.md` (drop docs-container path), `scanner.md` (drop "Layout-aware"), `linter.md` (drop container-drift; the source-sync line too), `SKILL.md`, `CLAUDE.md`, `README.md`, `skills/graph-wiki/README.md`, `.claude-plugin/plugin.json` (rewrite description).
- **Fix Category B drift:** template inventories (`SKILL.md:186`, `README.md:29`) → real `entity-*.md` names; `README.md:27` "7 tools" → 6; `page-formats.md:17` rewrite the prod-vs-test File-map section from the old `overview.md`+`testing.md` model to the single entity-page `## File map` model.
- **Do NOT touch** (findings Category C): Obsidian references, code-path citations, `graph_analyzer.py`, `_config.py`/`_uv_reexec.py`.
- Update plugin `CLAUDE.md`'s "when changing layout, update these refs" list (drop `detection-workflow.md`).

## Verification / success criteria

- **Scan parity (the load-bearing test):** on the fixture repos (`fixtures/single-package`, `mono-shaped`, `non-standard` + `graph-wiki-cli` sample monorepo), the `entities/*.md` set, filenames, frontmatter, and file-map blocks produced *after* the refactor match those produced *before* — for both `gw scan --no-narrate` and the plugin shim. File maps must stay prod/test-partitioned for package/app pages.
- **Bootstrap:** `gw bootstrap` and the plugin produce a vault with **no `graph-wiki:layout` block** in `CLAUDE.md`/`AGENTS.md`, and an otherwise-identical tree to today.
- **No container surface remains:** `grep -rn "detect_container\|layout_io\|reconcile_layout\|package-family\|pinned_container" packages/ plugins/` returns only intentional history (none in `src/`).
- **Lint:** container-drift + source-sync checks gone; package-sync + code-drift still fire on a fixture with a deleted/renamed package.
- **Lazy-import / Bedrock-free** invariant from the prior parity work still holds: plugin scan runs without `model_adapter`/`subagent_runtime`.
- **Full suite green:** `uv run pytest packages/` after test updates.

## Suggested slicing (for writing-plans)

- **Slice A — shared-core decontainerize:** D + C deletions, B (init_vault), A (scan.py refactor + ScanResult collapse + docs-candidate removal), E (package-family code/tests). Gate on scan/bootstrap parity tests. This is where the risk lives — sequence scan.py last, behind the parity harness.
- **Slice B — plugin sweep:** F (script + markdown). Pure docs/deletion; depends on Slice A's vocabulary being settled.

## Risks

- **scan.py touches the working `gw` path.** Mitigate with a before/after parity snapshot harness built *first*, run against all fixtures.
- **File-map partitioning regression.** Packages use `build_file_map` (prod/test split); the suite branch uses `build_dir_file_map` (unpartitioned). Copy the *path-from-node* pattern, not the builder.
- **Hidden `ScanResult` legacy-field consumers** (CLI `--json`, plugin shim output, eval baselines). Enumerate before removing fields.
- **`scan_monorepo.py` shared helpers.** Some functions there are still called by the graph path — delete only after confirming no callers.
