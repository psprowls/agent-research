---
title: scan diff treats package companion pages as orphans
category: work
kind: bug
summary: /graph-wiki:scan flags wiki/packages/<pkg>/{api,context,patterns,work}.md as "deleted" because the diff only matches the overview page slug
status: open
severity: low
effort: small
blast_radius: package
affects:
  - packages/vault-io/src/vault_io/scan_monorepo.py
target:
owner:
opened: 2026-05-19
updated: 2026-05-19
tokens: 0
related_tickets: []
related_prs: []
resolved_in:
superseded_by:
mitigation:
rationale:
tags: [scan, vault-io, diff]
---

# scan diff treats package companion pages as orphans

## Summary
`scan_monorepo.py` discovers one workspace entry per package (e.g. `vault-io`) and `_load_existing_pages(wiki)` enumerates every page under `wiki/packages/<pkg>/`, treating each filename as a separate slug. The diff sees four "extra" pages per package — `<pkg> — API`, `<pkg> — Context`, `<pkg> — Patterns`, `<pkg> — Work` — and reports them as `deleted`.

On a healthy 7-package vault this produces 28 false "deleted" entries every scan run (verified 2026-05-19 against `/Users/pat/Personal/deep-agents/graph-wiki/`). The companion pages are part of the wiki schema (declared in `wiki/CLAUDE.md` under `workflow_hints`), not orphans.

## Options considered

- Option A — Fold companions into the parent slug in `_load_existing_pages`: treat `<pkg>.md`, `api.md`, `context.md`, `patterns.md`, `work.md` inside `wiki/packages/<pkg>/` as one logical page. Cleanest fix; matches the schema.
- Option B — Filter companion filenames out of the diff entirely. Less invasive but leaves them invisible to lint as well.
- Option C — Have `discover_workspaces` emit synthetic companion entries to match. Symmetrical but bloats the workspace list and confuses downstream consumers.

## Plan

| Action | Done when | Rationale |
|---|---|---|
| | | |

## Notes / log
- **2026-05-19** — Surfaced during first `/graph-wiki:scan` after `scan_monorepo.py` was patched to honor `layout["repo_root"]`. Diff: `0 new, 0 renamed, 28 deleted, 7 unchanged`. All 28 "deletions" are the four-per-package companions.
