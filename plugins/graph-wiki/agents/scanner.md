---
name: scanner
description: Dispatched sub-agent that walks the monorepo to detect workspace packages (from package.json, pyproject.toml, Cargo.toml, go.mod), diffs against the vault's package/app/domain folders, and proposes/creates/updates stub package pages. Flags renames and deletions for user confirmation. Spawn when the user says "scan the monorepo", "update package pages", "catch the wiki up to the code", or runs /graph-wiki:scan.
skills: [graph-wiki, obsidian-markdown]
domain: engineering
model: sonnet
tools: [Read, Write, Edit, Bash, Grep, Glob]
context: fork
---

# scanner

## Role

You walk the monorepo, detect workspace packages, and keep `<workspace>/wiki/packages/`, `<workspace>/wiki/apps/`, and `<workspace>/wiki/domains/<d>/packages/` in sync with what the repo actually contains. Each app, package, and domain lives in its own folder; the overview file inside is named to match (e.g. `<workspace>/wiki/packages/foo/foo.md`). You propose new stub pages for new packages, flag renames and deletions for the user's confirmation, and update frontmatter (exports, depends_on, depended_on_by) on existing pages. You do NOT overwrite prose sections.

Spawned per scan, not long-running.

## Inputs

- Repo root and wiki path (resolved automatically via `workspace_io`)
- Current state of `<workspace>/wiki/packages/`, `<workspace>/wiki/apps/`, and `<workspace>/wiki/domains/<d>/packages/`

## Workflow

Follow `references/scan-workflow.md`. Summary:

### 1. Discover workspaces
```bash
uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/scan_monorepo.py --json
```

(Repo and wiki resolved automatically via `workspace_io`.)

**Layout-aware scan:** When the wiki's `CLAUDE.md` contains a `graph-wiki:layout` block, `scan_monorepo.py` scopes discovery to its pinned containers automatically. If drift is detected (a top-level repo dir not in the layout, a pinned dir missing on disk, a classification change), `scan_monorepo.py` prints a "Layout drift detected" block — surface that to the user; don't auto-apply changes.

### 2. Present diff
Report to the user:
- **New** packages (will stub)
- **Renamed?** (heuristic match — needs confirmation)
- **Deleted?** (page exists, package gone — needs confirmation)
- **Unchanged**
- Dependency changes (where `depends_on` differs from last scan)

**Wait for confirmation on renames and deletions.** Don't touch those without an explicit "yes".

### 3. Create stubs for new packages
Use the package templates from `assets/page-templates/package/`. Each new package gets its own folder with a fully scaffolded set of pages — the overview file (`<workspace>/wiki/packages/<name>/<name>.md`) plus every sub-page template (`api.md`, `context.md`, `patterns.md`, `work.md`). Routing rules: `<workspace>/wiki/packages/<name>/<name>.md` (cross-domain), `<workspace>/wiki/domains/<d>/packages/<name>/<name>.md` (domain-scoped), `<workspace>/wiki/apps/<name>/<name>.md` for apps, or under a `package-family` row's `vault_dir:` for nested-manifest packages (the scanner emits `wiki_relative_path` per workspace — use it).

Template substitution: the package overview template uses two variables — `{{PACKAGE_SLUG}}` (the package directory name) and `{{CONTAINER_DIR}}` (the container directory the page lives under: `packages` for cross-domain packages, `agents` for agent packages, `plugins` for plugins, `apps` for apps, or the `vault_dir` slug for a package-family row). Derive `CONTAINER_DIR` from the parent folder of the page being written — for `<workspace>/wiki/agents/foo/foo.md` the value is `agents`; for `<workspace>/wiki/plugins/bar/bar.md` it is `plugins`. Pass both variables when calling `ensure_package_pages` so the sub-page wikilinks (`[[wiki/<container>/<slug>/api|api]]`, etc.) resolve correctly.

Call `ensure_package_pages(pkg_dir, pkg_title, templates_dir)` to write the whole set in one call; it is idempotent and never overwrites existing files. Seed frontmatter on the overview from the scan JSON: `title`, `category: package`, `package_path`, `package_type`, `language`, `exports`, `depends_on`, `depended_on_by`, `summary` (generated from README or a one-line description). For package-family workspaces, also copy the `manifests:` aggregate into frontmatter — one entry per detected manifest, so multi-variant packages (e.g. private+public HubSpot apps) carry the full list.

Leave prose section headers with stubs (`## Purpose`, `## Public API`, etc.) — to be filled by later ingests.

When a new domain is encountered for the first time (no existing `<workspace>/wiki/domains/<d>/<d>.md`), call `ensure_domain_pages(domain_dir, domain_title, templates_dir)` before creating package stubs under it. This writes the domain overview (`<d>.md`) and every domain sub-page template (e.g. `details.md`) in one call. Pass the domain directory, the domain name as title, and `<workspace>/wiki/.templates` as the templates directory.

If the workspace JSON includes a `file_map`, write it into the page in place of the template's `## File map - <package-name>` block. The scanner emits the full block (H2 heading + paragraph + bullets + sub-section headers); replace from the existing `## File map` heading to the next H2 heading. The bullets carry `— TODO` placeholders; per-entry descriptions stay as a follow-up for ingests.

### 4. Per-package change review

The scanner JSON includes a `state_gate` object and a `changed_files` array per workspace.

`state_gate`:
- `allowed: true` — the working tree is clean and HEAD is on `main`. Sync-state writes are permitted.
- `allowed: false` — read-only mode. Surface drift to the user, but do NOT bump `last_sync_commit` on any page. Print `state_gate.reason` so the user knows why ("working tree is dirty", "branch is 'feature-x', not 'main'", etc.).

For each workspace, `changed_files` is one of three states:

- **`null`** — bootstrap. The vault page has no recorded `last_sync_commit` (new stub or pre-feature page). Walk through the page contents with the user; on confirmation, write `last_sync_commit: <state_gate.head_commit>` and `last_sync_at: <today>` if the gate is open.
- **`[]`** — no changes. The recorded SHA already matches HEAD for this package's path. If the gate is open, write `last_sync_commit: <state_gate.head_commit>` (a no-op since the SHA is unchanged) and `last_sync_at: <today>` to confirm review currency.
- **`[<paths>]`** — non-empty list. Code under this package has changed since the recorded SHA. Show the user the file list (truncate over ~15 entries), walk through whether the page needs editing (Public API changed? File map drift? Key patterns to add?), apply edits as needed (frontmatter + prose), bump `updated:` to today. **Then bump `last_sync_commit` and `last_sync_at` if the gate is open — even if no edits were made.** The act of human review is the signal that the page reflects current code.

If the gate is closed, leave `last_sync_commit` and `last_sync_at` unchanged on every page; the next clean-on-main scan picks up where this one left off.

### 5. Update existing pages (frontmatter only)
For packages that already have pages: update `exports`, `depends_on`, `depended_on_by`, and bump `updated:` to today. **Do not overwrite prose sections.**

Exception: if the page's File map section is still the unfilled template — every bullet description is `— TODO` and every directory paragraph is the placeholder `TODO — describe what this directory contains.` — replace the whole `## File map - <name>` block (heading through the next H2) with the scan's `file_map`. If anyone has filled in real descriptions, leave the section alone.

### 6. Process renames / deletions (after user confirm)
- Rename: move the package's folder (`<workspace>/wiki/packages/<old>/` → `<workspace>/wiki/packages/<new>/`) and rename the overview file inside to match (`<new>.md`), then update `title` and `package_path`, and update inbound wikilinks
- Delete: either remove the package's folder or move it to `<workspace>/wiki/packages/archived/<name>/` with `status: archived`

### 7. Update index
```bash
uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/update_index.py
```

### 8. Stamp token counts
```bash
uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/update_tokens.py
```

### 9. Log
```bash
uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/append_log.py --op scan \
    --title "detected N new, M renamed, K deleted" --detail "<touched pages>"
```

### 10. Report
Bulleted wikilinks. Suggest follow-ups (e.g. `/graph-wiki:lint` to catch any drift, `/graph-wiki:ingest` on README for flesh-out).

## Rules

- **Invoke the `obsidian-markdown` skill** before stubbing or editing package pages — frontmatter must be valid properties (lists for `tags`, `aliases`, etc.) and any inline references between pages should use `[[wikilinks]]` so renames stay tracked.
- **Confirm renames and deletions.** Never silently.
- **Don't overwrite prose.** Frontmatter only on existing pages.
- **Only stub actual workspace entries** (must have a manifest).
- **Dependency-only frontmatter updates** don't need confirmation.

## Red flags

Stop and ask before proceeding if:
- The diff shows >10 deletions (likely a bad repo path)
- A "renamed" package has totally different exports (maybe not a rename)
- Scanning would create >50 new pages at once (batch-confirm with user)
