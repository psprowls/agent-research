# Scan Workflow

## Purpose

Keep the wiki's single `entities/` folder in sync with the code graph. The scan is mechanical and structural-only — it builds the graph, renders one page per admitted entity, and never calls an LLM.

## Inputs

- Repo root + wiki path (resolved via `workspace_io`).
- The code graph itself — entity discovery is purely graph-driven; there is no folder-shape input or pinned scoping. The graph (built from the repo by `cg`) is the sole source for which entities exist.

## What gets written

One page per admitted entity into `<workspace>/wiki/entities/`, across the **7 admitted kinds**: `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite`. Filenames are URI-derived (`pkg_<name>.md`, `app_<name>.md`, `dep_<name>.md`, `domain_<name>.md`, `repo_<name>.md`, `agent-plugin_<name>.md`, suite-kind-aware `unit_tests_<pkg>.md` / `int_tests_<pkg>.md`), with a `__<6hex>` suffix on collision. See Appendix A in the plan / `wiki-schema.md` for the full vocabulary.

## Step-by-step

### 1. Run the mechanical scan
`scan_monorepo.py --json` builds the graph (`cg update`, incremental), calls `write_entities`, injects deterministic file maps (Description cells `— TODO`), regenerates indexes, and appends to the log. Structural-only: `## Narrative` keeps its `_(scanner will populate on next scan)_` placeholder.

### 2. Report entities
From the `ScanResult` JSON: `entities_created`, `entities_updated`, `entities_deleted` (URIs), `entity_errors`.

### 3. Surface deletions
`write_entities` hard-deletes pages for vanished graph nodes. Report them; never silently. Offer a git undo when the wiki is versioned. >10 deletions is a red flag (bad repo path / failed graph build) — stop and ask.

### 4. Update cross-references / indexes
Already done by the script (`index.md`, per-folder sub-indexes). No separate step.

### 5. Append to log
Already done by the script.

### 6. Report back
Bulleted wikilinks; suggest `/graph-wiki:lint` and `/graph-wiki:ingest` to flesh out narratives.

## Frontmatter contract

Scanner-owned keys (replaced every scan): `uri`, `kind`, `graph_name`, `last_scan_at`, plus per-kind edge/attr keys (`depends_on`, `domains`, `test_suites`, `entry_points`, `language`, `version`, `app_kind`, `app_signals`, `parent_domain`, `sub_domains`, `packages`, `tested_packages`, `suite_kind`, `file_count`, `ecosystem`, `used_by`, `versions_in_use`, `package_count`). Human keys preserved verbatim: `status`, `last_reviewed`, `owner`, `notes`. `summary` is fill-when-empty.

## Anti-patterns

- Hand-writing `entities/*.md` pages (the graph renders them).
- Filling `## Narrative` or file-map descriptions during scan (structural-only).
- Silently accepting a large deletion set.
- Expecting `apps/`, `packages/`, or `domains/` page folders — there are none; everything is in `entities/`.
