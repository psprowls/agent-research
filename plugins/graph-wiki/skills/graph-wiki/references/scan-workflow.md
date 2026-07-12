# Scan Workflow

## Purpose

Keep the wiki's single `entities/` folder in sync with the code graph. The scan builds the graph, renders one page per admitted entity, then fills placeholders (`## Narrative`, file/dir descriptions, overview, `## Purpose`/`## Public API`) via a commit-gated Claude subagent fan-out. A bare / `--no-narrate` invocation runs the mechanical write only.

## Inputs

- Repo root + wiki path (resolved via `workspace_io`).
- The code graph itself — entity discovery is purely graph-driven; there is no folder-shape input or pinned scoping. The graph (built from the repo by `cg`) is the sole source for which entities exist.

## What gets written

One page per admitted entity into `<workspace>/wiki/entities/`, across the **7 admitted kinds**: `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite`. Filenames are URI-derived (`pkg_<name>.md`, `app_<name>.md`, `dep_<name>.md`, `domain_<name>.md`, `repo_<name>.md`, `agent-plugin_<name>.md`, suite-kind-aware `unit_tests_<pkg>.md` / `int_tests_<pkg>.md`), with a `__<6hex>` suffix on collision. See Appendix A in the plan / `wiki-schema.md` for the full vocabulary.

## Step-by-step

### 1. Emit → fan-out → apply

The default scan runs as a three-phase pipeline:

**Phase 1 — Emit** (`--emit-worklist <path>`): builds the code graph (`cg update`, incremental), calls `write_entities`, injects deterministic file maps, computes the commit-gate, and serializes the worklist (`fill_tasks`, `drift_tasks`, `propagate_tasks`, `short_head`) to `<workspace>/.graph-wiki/worklist.json`.

**Phase 2 — Fan-out**: read-only subagents (one per entity in `fill_tasks`/`drift_tasks`) inspect source files and return structured records — narrative, file/dir descriptions, overview, `## Purpose`/`## Public API`, drift judgements. Subagents are strictly read-only (Read/Grep/Glob only); no page writes happen here.

**Phase 3 — Apply** (`--apply-worklist <results.json> --short-head <sha>`): injects all structured results, runs the M2c refill-gated anchor stamp, writes M2e `drift_review` flags, regenerates indexes and backlinks, and appends to `log.md`.

A bare invocation (or `--no-narrate` on `gw scan`) is the mechanical structural-only fast path — no worklist written, no prose generated. `## Narrative` and file-map descriptions keep their placeholders on this path only.

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

Provenance keys (scanner-stamped but deliberately NOT in `SCANNER_OWNED_KEYS` — preserved verbatim across re-scan):
- `last_updated_commit` — HEAD at which `## Narrative` was last regenerated; gates commit-driven narrative refresh (Living Wiki M2a).
- `drift_checked_commit` — HEAD at which the human-section drift judge last evaluated this page's curated sections; prevents re-running the judge against an unchanged page.
- `drift_propagated_commit` — the entity's `last_updated_commit` value at which M4's drift producer last proposed against curated pages backlinking it; gates the M4 cross-page drift pass (proposal ledger) and keeps repeat runs idempotent.

The state gate (`last_updated_commit` stamping on scan/ingest) is configurable per-workspace via the `state_gate:` block in `<workspace>/.graph-wiki.yaml` (`enabled` + allowed `branches`); absent config gates on a clean `main`. See the workspace-io README for the schema.

## Contract

Two JSON files live under `<workspace>/.graph-wiki/` across the emit/apply boundary:

**`worklist.json`** — written by `--emit-worklist`, consumed by the fan-out and `--apply-worklist`:
- `fill_tasks` — list of per-entity records describing what prose/descriptions need generation.
- `drift_tasks` — list of per-entity records for human-section drift judging.
- `propagate_tasks` — list of cross-page drift propagation tasks (M4).
- `short_head` — abbreviated HEAD SHA at emit time; passed as `--short-head` to apply so anchors are stamped to the correct commit.

**`results.json`** — written by the fan-out (assembled by the scanner agent), consumed by `--apply-worklist`:
- `fills` — structured fill records (narrative, file/dir descriptions, overview, purpose, public_api) keyed by entity URI.
- `drift` — per-section drift judgement records (`{section, stale, reason}`).
- `propagate` — cross-page drift propagation records.
- `schema: 1` — version sentinel; apply phase validates before writing.

Both files are transient workspace artifacts; they are safe to delete and are overwritten on each scan.

## Anti-patterns

- Hand-writing `entities/*.md` pages (the graph renders them).
- Letting fill subagents write pages directly (they are read-only; the apply phase performs all writes).
- Silently accepting a large deletion set.
- Expecting `apps/`, `packages/`, or `domains/` page folders — there are none; everything is in `entities/`.
