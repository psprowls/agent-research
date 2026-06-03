---
name: scan
description: Build the code graph and write one page per admitted entity (repository, domain, package, app, agent_plugin, dependency, test_suite) into the wiki's single entities/ folder. Reports created/updated/deleted entities by URI; surfaces deletions for confirmation. Workspace and repo discovered automatically. Usage /graph-wiki:scan
---

# /graph-wiki:scan

Build the code graph and write one page per admitted entity into the wiki's single `entities/` folder. This is the **entry point** for a fresh wiki — run it right after `/graph-wiki:bootstrap`.

## Usage

```
/graph-wiki:scan
```

Workspace and repo are discovered automatically via `workspace_io`.

## What happens

1. **Graph build + write** — `scripts/scan_monorepo.py` builds the code graph and writes one page per admitted entity into `<workspace>/wiki/entities/` (kinds: `repository`, `domain`, `package`, `app`, `agent_plugin`, `dependency`, `test_suite`). Pages use URI-based filenames and are structural-only (`## Narrative` placeholder, `— TODO` file-map rows).
2. **Frontmatter** — scanner-owned keys (`uri`, `kind`, `depends_on`, `language`, …) are replaced from the graph each scan; human keys (`status`, `last_reviewed`, `owner`, `notes`) and a non-empty `summary` are preserved.
3. **Indexes + log** — `index.md`, per-folder sub-indexes, and `dependencies/index.md` are regenerated; a `scan` entry is appended to `log.md`.
4. **Report** — created / updated / deleted entities are reported by URI. Deletions are surfaced for confirmation (with a git-based undo when the wiki is versioned); >10 deletions is a stop-and-ask red flag.

This runs entirely **without Bedrock** (structural-only). No prose is generated.

## Sub-agent

This command dispatches the `scanner` sub-agent. See `agents/scanner.md`.

## Rules

- **Don't silently delete entity pages** — always surface deletions; >10 is a red flag.
- **Structural-only** — `## Narrative` and file-map descriptions are filled later by ingest/query, not by scan.
- **The graph is the source** — entity pages are rendered from the code graph, not hand-written.

## When to run

- Right after `/graph-wiki:bootstrap`
- After pulling main (new packages may have landed)
- After a big refactor that added/removed/renamed packages
- Before `/graph-wiki:lint` (so drift reports are accurate)

## Skill Reference

→ `graph-wiki/SKILL.md`
→ `graph-wiki/references/scan-workflow.md`
