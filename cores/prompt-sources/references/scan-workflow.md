# Scan Workflow

The detailed flow the LLM follows when the user runs `/lattice-wiki:scan` or dispatches the `lattice-wiki:scanner` sub-agent.

## Purpose

Walk the monorepo, detect workspaces, and produce/update stub pages. Each app, package, and domain gets its own folder, with the overview file inside named to match the folder (e.g. `<workspace>/wiki/apps/web-next-ts/web-next-ts.md`, `<workspace>/wiki/packages/common-aws-node-ts/common-aws-node-ts.md`). The scan is the **entry point** for a fresh wiki: before you can ingest sources meaningfully, you need a page for every workspace so the ingestor has something to cross-reference.

## Inputs

- Path to the repo root (discovered automatically via `lattice-workspace`)
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

Run `python scripts/scan_monorepo.py --json` to get a structured inventory (repo discovered automatically via `lattice-workspace`):

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

The scanner emits an explicit `vault_path` for every workspace — write the page there. Routing rules (also useful when reading back drift):

- `type: app` → `<workspace>/wiki/apps/<name>/<name>.md` (uses the **app** template)
- `type: library | service | tool` under a `domain` container → `<workspace>/wiki/domains/<domain>/packages/<name>/<name>.md` (uses the **package** template, with `domain: <domain>` set in frontmatter)
- `type: library | service | tool` everywhere else → `<workspace>/wiki/packages/<name>/<name>.md` (uses the **package** template, with `domain:` left empty)

Domain detection supports two on-disk layouts and the scanner handles both:

- **Flat:** `<container>/<domain>/<package>/` — packages sit directly under the domain dir.
- **Nested:** `<container>/<domain>/packages/<package>/` (or `libs/`, etc.) — the domain groups its packages under a package container.

Top-level `<workspace>/wiki/packages/` is reserved for single-package repos and globally shared (`packages/lib`-type) directories. A domain may consume a package owned by another domain — in that case the package keeps its home under its owning domain, and the consuming domain's page just links to it (see the **Linked packages from other domains** section in `domain.md`).

For each **new** workspace:
- Create the page from the appropriate template
- Seed frontmatter:
  - Apps: `title`, `category: app`, `app_path`, `platform`, `framework`, `language`, `entry_points`, `consumes_domains`, `depends_on`, `summary`
  - Packages: `title`, `category: package`, `package_path`, `package_type`, `language`, `exports`, `depends_on`, `summary`
- Leave stub sections (`## Purpose`, `## Public API` / `## Routes`, etc.) as TODOs — filled during ingests.
- Pre-populate the page's `## File map - <name>` block with the scan's `file_map` (sectioned format with file/folder bullets, derived from `git ls-files` so `.gitignore` is respected — see [[references/page-formats#File map convention (apps and packages)|page-formats]]). The scan emits the entire block (H2 heading + paragraph + bullets + sub-section headers); replace from the existing `## File map` heading through the next H2 heading. Per-entry descriptions are filled in later. For existing pages, backfill the same way only when the section is still the unfilled template — every bullet description is `— TODO` and every paragraph is the placeholder `TODO — describe what this directory contains.`; otherwise leave the section alone.

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
  ? docs/architecture.md  (run /lattice-wiki:ingest docs/architecture.md)
  ? docs/runbook.md       (run /lattice-wiki:ingest docs/runbook.md)
  ? docs/release-notes.md (run /lattice-wiki:ingest docs/release-notes.md)
```

The scanner does not auto-ingest; the user picks. Ingestion goes through the normal `/lattice-wiki:ingest` flow, which produces a `category: source` summary at `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md` and updates concepts/ADRs/packages from the doc's content. PDF, DOCX, and other doc formats are deferred — see `references/ingest-workflow.md` "Future formats".

### 6. Update cross-references

- Every package's `depends_on` becomes a wikilink on its own page
- Every package's `depended_on_by` count comes from the reverse graph; if the number changed significantly, flag for user attention

### 6a. Regenerate auto-rendered indexes

The scanner regenerates one marker-bounded index on every run (skip with `--no-index-regen`):

- **`<workspace>/wiki/dependencies/index.md`** — one row per external dependency aggregated across scanned manifests, plus service rows from hand-maintained `<workspace>/wiki/dependencies/services.yaml`. The marker contract is `<!-- auto:dependencies-index generated:<ISO> --> … <!-- /auto:dependencies-index -->`; content outside the markers is preserved.

Lint flags `dep-index-stale` against the regen marker (that rule lands in a follow-on plan once the index is in production use).

`<workspace>/work/.work-index.json` is owned by **`lattice-work`**, not by `lattice-wiki`. Run `/lattice-work:regen-index` to refresh it.

### 7. Update the index

Run `python scripts/update_index.py` or edit `<workspace>/wiki/index.md` inline.

### 8. Append to log

Run:
```bash
python scripts/append_log.py --op scan \
    --title "detected N new, M renamed, K deleted" \
    --detail "<bulleted list of touched pages>"
```

### 9. Report back

Summary the user sees:
- Pages created (with wikilinks)
- Pages updated (with wikilinks)
- Renames / deletions processed
- Packages with stale prose — suggest follow-up ingests
- Next steps (e.g. "run `/lattice-wiki:ingest raw/specs/x.md` to flesh out the timeline domain")

## After-scan tips

- **First scan?** Follow up with `/lattice-wiki:lint` to surface orphans and missing cross-references.
- **Dependency changes?** Consider updating `[[architecture/module-graph]]` if it exists.
- **New domain?** Domain pages (`<d>.md` and `details.md`) are created automatically via `ensure_domain_page()` and `ensure_domain_details()` in `layout_io.py` before the first package stub is written under that domain.

Sub-pages (`api.md`, `patterns.md`, `context.md`, `work.md`) are created lazily via `ensure_subpage()` in `layout_io.py` — they are written the first time an ingest or work-item script writes to them, not by the scanner itself. Domain pages follow the same lazy-creation pattern via `ensure_domain_page()` and `ensure_domain_details()`.

## Anti-patterns

- ❌ Silently deleting wiki pages for "deleted" packages — always confirm with user
- ❌ Overwriting prose sections on existing packages — frontmatter only, unless the user asks
- ❌ Creating stubs for every folder — only actual workspace entries (must have a manifest file)
- ❌ Running scan on every shell command — scan is user-initiated or on explicit triggers (e.g. after pulling main)
