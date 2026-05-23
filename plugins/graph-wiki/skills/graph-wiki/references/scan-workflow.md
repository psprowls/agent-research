# Scan Workflow

The detailed flow the LLM follows when the user runs `/graph-wiki:scan` or dispatches the `graph-wiki:scanner` sub-agent.

## Purpose

Walk the monorepo, detect workspaces, and produce/update stub pages. Each app, package, and domain gets its own folder, with the overview file inside named to match the folder (e.g. `<workspace>/wiki/apps/web-next-ts/web-next-ts.md`, `<workspace>/wiki/packages/common-aws-node-ts/common-aws-node-ts.md`). The scan is the **entry point** for a fresh wiki: before you can ingest sources meaningfully, you need a page for every workspace so the ingestor has something to cross-reference.

## Inputs

- Path to the repo root (discovered automatically via `workspace_io`)
- The current state of `<workspace>/wiki/packages/`, `<workspace>/wiki/apps/`, and `<workspace>/wiki/domains/<d>/packages/` (to detect new / renamed / deleted)

## What gets detected

| Source | Package metadata |
|---|---|
| `package.json` (root + workspace entries) | name, version, scripts, dependencies, workspace declarations |
| `pnpm-workspace.yaml` | workspace glob patterns |
| `turbo.json` | pipeline info (build, test, etc.) |
| `pyproject.toml` | Python packages in a mixed monorepo |
| `Cargo.toml` (workspaces) | Rust crates |
| `go.mod` + `go.work` | Go modules |
| `BUILD` / `BUILD.bazel` | Bazel targets |

## Step-by-step

### 1. Discover workspaces

Run `uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/scan_monorepo.py --json` to get a structured inventory (repo discovered automatically via `workspace_io`):

```json
{
  "workspaces": [
    {
      "name": "@psprowls/common-aws-node-ts",
      "path": "packages/common-aws-node-ts",
      "type": "library",
      "language": "typescript",
      "depends_on": ["@psprowls/common-context-node-ts"],
      "exports": ["./src/handlers/baseApiHandler", "..."]
    },
    ...
  ],
  "diff": {
    "new": ["@psprowls/timeline-native-ts"],
    "renamed": [["@psprowls/old-name", "@psprowls/new-name"]],
    "deleted": ["@psprowls/removed-pkg"],
    "unchanged": [...]
  }
}
```

### 2. Present the diff

Before writing anything, report to the user:

- **New packages** detected — the scanner will create stub pages
- **Renames** (heuristic: same path, new name; or same name, new path)
- **Deletions** — packages that have a wiki page but no longer exist on disk
- **Dependency changes** — packages where `depends_on` has changed since last scan
- **New external dependencies** — suggest creating `dependencies/<name>.md` pages for load-bearing or unfamiliar libraries (not every `package.json` entry — just notable ones)

**Wait for the user to confirm or redirect** — especially on renames and deletions. The user should decide whether a "deleted" page should be removed (rename) or kept as a history note.

### 3. Create / update workspace pages

The scanner emits an explicit `wiki_relative_path` for every workspace — write the page there. Routing rules (also useful when reading back drift):

- `type: app` → `<workspace>/wiki/apps/<name>/<name>.md` (uses the **app** template)
- `type: library | service | tool` under a `domain` container → `<workspace>/wiki/domains/<domain>/packages/<name>/<name>.md` (uses the **package** template, with `domain: <domain>` set in frontmatter)
- `type: library | service | tool` everywhere else → `<workspace>/wiki/packages/<name>/<name>.md` (uses the **package** template, with `domain:` left empty)

Domain detection supports two on-disk layouts and the scanner handles both:

- **Flat:** `<container>/<domain>/<package>/` — packages sit directly under the domain dir.
- **Nested:** `<container>/<domain>/packages/<package>/` (or `libs/`, etc.) — the domain groups its packages under a package container.

Top-level `<workspace>/wiki/packages/` is reserved for single-package repos and globally shared (`packages/lib`-type) directories. A domain may consume a package owned by another domain — in that case the package keeps its home under its owning domain, and the consuming domain's page just links to it (see the **Linked packages from other domains** section in `domain.md`).

### Package-family containers (deep / nested manifests)

Use `classification: package-family` when the **package boundary** is a directory but its `package.json` (or other manifest) sits several levels deeper, often with multiple variants (e.g. an example shipped as both `private/` and `public/` HubSpot apps). The detector emits this classification automatically when it sees a directory whose children carry manifests **2+ levels deeper** and no immediate child carries a top-level manifest.

Layout block fields:

```yaml
- source: references/hubspot/hubspot-ui-extensions
  vault_dir: domains/hubspot/packages           # where pages land in wiki/
  classification: package-family
  package_depth: 1                               # children of source are the packages
  manifest_glob: "**/package.json"               # how to find manifests within each
  slug_source: dirname                           # use dir name as page slug (avoids manifest-name collisions)
  domain: hubspot                                # optional — stamped on each pkg's frontmatter
```

Scanner behavior:

- Walks to `package_depth` below `source`; each directory at that depth is one workspace entry.
- Recursively globs `manifest_glob` inside each package dir; every matched manifest becomes a row in the page's `manifests:` frontmatter.
- Slug is the directory name (default) — so two siblings whose `package.json` both declare `name: "charts"` get distinct pages.
- If `domain:` is set on the row, each pkg's `wiki_relative_path` lands at `domains/<d>/packages/<slug>/<slug>.md` (overrides the explicit `vault_dir`).

`source` may be a slashed path; the row need not point at a top-level directory.

For each **new** workspace:
- Create the page from the appropriate template
- Seed frontmatter:
  - Apps: `title`, `category: app`, `app_path`, `platform`, `framework`, `language`, `entry_points`, `consumes_domains`, `depends_on`, `summary`
  - Packages: `title`, `category: package`, `package_path`, `package_type`, `language`, `exports`, `depends_on`, `summary`
- Leave stub sections (`## Purpose`, `## Public API` / `## Routes`, etc.) as TODOs — filled during ingests.
- Pre-populate the page's `## File map - <name>` block with the scan's `file_map` (H2 + per-major-folder H3 sections with markdown tables `Path | Kind | Description`, derived from `git ls-files` so `.gitignore` is respected — see [[references/page-formats#File map convention (apps and packages)|page-formats]]). Replace from the existing `## File map` heading through the next H2 heading. Per-row descriptions are filled in later. For existing pages, backfill the same way only when the section is still the unfilled template — every table row's Description cell is `— TODO` and every per-folder paragraph is the placeholder `TODO — describe what this directory contains.` (or for legacy pages, all bullet descriptions are `— TODO`); otherwise leave the section alone.

If a workspace's type changes (e.g. a package grows into an app), flag the move for user confirmation — it requires relocating the page between `packages/` and `apps/`.

For each **renamed** package (user-confirmed):
- `git mv <workspace>/wiki/packages/<old>/ <workspace>/wiki/packages/<new>/` then `git mv <workspace>/wiki/packages/<new>/<old>.md <workspace>/wiki/packages/<new>/<new>.md` (or Write-then-delete if not git)
- Update `title` and `package_path` frontmatter
- Update all inbound wikilinks

For each **deleted** package (user-confirmed):
- Option A: delete the package's folder
- Option B: mark with `status: archived` in frontmatter and move to `<workspace>/wiki/packages/archived/<name>/<name>.md`
- The user chooses per-package

For **existing** packages with changed metadata:
- Update frontmatter fields (`exports`, `depends_on`, `depended_on_by`)
- Do NOT overwrite prose sections — leave the LLM-authored summaries alone
- Bump `updated:` to today

### 4. Per-package change review

The scanner JSON includes a top-level `state_gate` object and a `changed_files` field per workspace entry.

`state_gate` fields:
- `allowed: true` — the working tree is clean and HEAD is on `main`. Sync-state writes are permitted.
- `allowed: false` — read-only mode. Report drift to the user but do NOT write `last_sync_commit` or `last_sync_at` on any page. Display `state_gate.reason` so the user understands the block ("working tree is dirty", "branch is 'feature-x', not 'main'", etc.).

For each workspace, `changed_files` is one of three states — do not conflate them:

- **`null`** — bootstrap. The wiki page has no recorded `last_sync_commit` (new stub or a page that predates the sync-state feature). Walk through the page contents with the user; on confirmation, write `last_sync_commit: <state_gate.head_commit>` and `last_sync_at: <today>` if the gate is open.
- **`[]`** (empty list) — no changes. The recorded SHA already matches HEAD for this package's path. If the gate is open, write `last_sync_commit: <state_gate.head_commit>` (a no-op since the SHA is unchanged) and `last_sync_at: <today>` to confirm review currency.
- **`[<paths>]`** (non-empty list) — code under this package has changed since the recorded SHA. Present the file list to the user (truncate display if over ~15 entries); walk through whether the page needs editing (Public API changed? File map drift? Key patterns to add?). Apply any edits (frontmatter + prose) and bump `updated:` to today. **Then bump `last_sync_commit: <state_gate.head_commit>` and `last_sync_at: <today>` if the gate is open — even when no edits were needed.** The act of human review is the signal that the page reflects current code.

If the gate is closed, leave `last_sync_commit` and `last_sync_at` unchanged on every page; the next clean-on-main scan resumes from where this one stopped.

### 5. Surface in-repo doc candidates

For every pinned `docs` container, the scanner walks `.md` files recursively (so nested layouts like `docs/<area>/plans/<date>-<slug>.md` are surfaced) and emits a `doc_candidates` array — one entry per file that has no existing source summary page.

Report these to the user as ingest candidates:

```
Docs to ingest: 3
  ? docs/architecture.md  (run /graph-wiki:ingest docs/architecture.md)
  ? docs/runbook.md       (run /graph-wiki:ingest docs/runbook.md)
  ? docs/release-notes.md (run /graph-wiki:ingest docs/release-notes.md)
```

The scanner does not auto-ingest; the user picks. Ingestion goes through the normal `/graph-wiki:ingest` flow, which produces a `category: source` summary at `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md` and updates concepts/ADRs/packages from the doc's content. PDF, DOCX, and other doc formats are deferred — see `references/ingest-workflow.md` "Future formats".

### 6. Update cross-references

- Every package's `depends_on` becomes a wikilink on its own page
- Every package's `depended_on_by` count comes from the reverse graph; if the number changed significantly, flag for user attention

### 6a. Regenerate auto-rendered indexes

The scanner regenerates one marker-bounded index on every run (skip with `--no-index-regen`):

- **`<workspace>/wiki/dependencies/index.md`** — one row per external dependency aggregated across scanned manifests, plus service rows from hand-maintained `<workspace>/wiki/dependencies/services.yaml`. The marker contract is `<!-- auto:dependencies-index generated:<ISO> --> … <!-- /auto:dependencies-index -->`; content outside the markers is preserved.

Lint flags `dep-index-stale` against the regen marker (that rule lands in a follow-on plan once the index is in production use).

`<workspace>/work/.work-index.json` is owned by **`graph-wiki`**. Run `/graph-wiki:regen-index` to refresh it.

> **Note:** The work-layer subsystem (regen-index) is not ported in graph-wiki v1.2. This note applies when/if work-layer support is added in a future version.

### 7. Update the index

Run `uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/update_index.py` or edit `<workspace>/wiki/index.md` inline.

### 8. Append to log

Run:
```bash
uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/append_log.py --op scan \
    --title "detected N new, M renamed, K deleted" \
    --detail "<bulleted list of touched pages>"
```

### 9. Report back

Summary the user sees:
- Pages created (with wikilinks)
- Pages updated (with wikilinks)
- Renames / deletions processed
- Packages with stale prose — suggest follow-up ingests
- Next steps (e.g. "run `/graph-wiki:ingest raw/specs/x.md` to flesh out the timeline domain")

## After-scan tips

- **First scan?** Follow up with `/graph-wiki:lint` to surface orphans and missing cross-references.
- **Dependency changes?** Consider updating `[[architecture/module-graph]]` if it exists.
- **New domain?** Domain pages (`<d>.md` plus `details.md` and any other `templates/domain/*.md` template) are scaffolded together via `ensure_domain_pages()` in `layout_io.py` before the first package stub is written under that domain.

Package sub-pages (`api.md`, `patterns.md`, `context.md`, `work.md`) are created eagerly by the scanner via `ensure_package_pages()` in `layout_io.py` — the whole set is written when a new package folder is first stubbed, so the wiki layout is always fully scaffolded after a scan. Ingests and work-item filers may continue to call the single-file `ensure_subpage()` helper for legacy packages whose folders were created before this behavior shipped; for fully-scaffolded packages those calls are silent no-ops.

## Anti-patterns

- Do not silently delete wiki pages for "deleted" packages — always confirm with user
- Do not overwrite prose sections on existing packages — frontmatter only, unless the user asks
- Do not create stubs for every folder — only actual workspace entries (must have a manifest file)
- Do not run scan on every shell command — scan is user-initiated or on explicit triggers (e.g. after pulling main)
