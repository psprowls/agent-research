---
name: scan
description: Walk the monorepo, detect workspace packages from manifests (package.json, pyproject.toml, Cargo.toml, go.mod), diff against the vault's package/app/domain folders, and create/update stub pages (one folder per workspace, with overview file named to match). Flags renames and deletions for user confirmation. Workspace and repo discovered automatically. Usage /graph-wiki:scan
---

# /graph-wiki:scan

Walk the monorepo and make sure every workspace package has a page in the vault. This is the **entry point** for a fresh wiki — run it right after `/graph-wiki:init`.

## Usage

```
/graph-wiki:scan
```

Workspace and repo are discovered automatically via `workspace_io`.

## What happens

1. **Inventory** — runs `scripts/scan_monorepo.py` to detect workspaces from `package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `Cargo.toml`, `go.mod`
2. **Diff** — compares against `<workspace>/wiki/packages/`, `<workspace>/wiki/apps/`, and `<workspace>/wiki/domains/<d>/packages/`:
   - new (on disk, no page)
   - renamed? (heuristic: same path, new name)
   - deleted? (page exists, not on disk)
   - unchanged
3. **Confirm** — presents the diff to you. Renames and deletions require confirmation.
4. **Create / update** — stub pages for new packages; frontmatter updates (`exports`, `depends_on`, `depended_on_by`) for existing pages. Prose sections on existing pages are left alone.
5. **Per-package review** — for each package whose source has changed since its `last_sync_commit`, walk through the diff with you and update the page. Bumps `last_sync_commit` to HEAD on confirmation — but only when the working tree is clean and HEAD is on `main`. Otherwise scan runs in read-only mode.
6. **Index** — updates `<workspace>/wiki/index.md`
7. **Log** — appends a `scan` entry

## Sub-agent

This command dispatches the `scanner` sub-agent. See `agents/scanner.md`.

## Rules

- **Don't silently delete vault pages** for "deleted" packages — always confirm with the user
- **Don't overwrite prose sections** on existing package pages — frontmatter only
- **Only stub new pages** for actual workspace entries (must have a manifest file)

## Layout reconcile

When `/graph-wiki:scan` runs against an initialized wiki, it re-detects containers and compares the result to the pinned layout. If `scan_monorepo.py` prints a "Layout drift detected" block, surface the drift to the user and offer:

- **Re-run `/graph-wiki:init`** — full re-detection. Overwrites the existing layout block.
- **Edit the layout block manually** — the user can change a row's `classification` or `vault_dir` directly in `<workspace>/wiki/CLAUDE.md`.
- **Ignore for now** — drift remains until next scan.

Don't auto-apply changes. Layout decisions are the user's.

## In-repo docs

When a `docs` container is pinned, scan walks its top-level `.md` files and reports any without an existing source summary as ingest candidates:

```
Docs to ingest: 3
  ? docs/architecture.md  (run /graph-wiki:ingest docs/architecture.md)
  ? docs/runbook.md       (run /graph-wiki:ingest docs/runbook.md)
  ? docs/release-notes.md (run /graph-wiki:ingest docs/release-notes.md)
```

Scan does not auto-ingest. Pass each path to `/graph-wiki:ingest`; the regular ingest flow produces a `category: source` summary at `<workspace>/wiki/sources/<YYYY-MM>-<slug>.md` and updates concepts/ADRs/packages from the doc's content. PDF, DOCX, and other formats are deferred — md only for now (see `references/ingest-workflow.md` "Future formats").

## When to run

- Right after `/graph-wiki:init`
- After pulling main (new packages may have landed)
- After a big refactor that added/removed/renamed packages
- Before `/graph-wiki:lint` (so drift reports are accurate)

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/scan-workflow.md`
