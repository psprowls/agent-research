---
created: 2026-05-21T17:43:14.204Z
title: Bootstrap should stub empty category index files
area: graph-wiki
files:
  - packages/vault-io/src/vault_io/init_vault.py
  - packages/vault-io/src/assets/page-templates/
---

## Problem

After `/graph-wiki:bootstrap` runs, `wiki/index.md` references category index
pages (`[[wiki/adrs/index]]`, `[[wiki/architecture/index]]`,
`[[wiki/concepts/index]]`, `[[wiki/sources/index]]`) that do not exist on disk.
Only `wiki/dependencies/index.md` is created. The first `/graph-wiki:lint` run
on a fresh wiki reports 4 broken wikilinks in `index.md` as a result.

Surfaced by lint of the 2026-05-21 fresh bootstrap of
`/Users/pat/Personal/wikis/deep-agents/wiki/`.

## Solution

Have `init_vault.py` write empty `index.md` stubs for every fixed vault
subdirectory in `FIXED_VAULT_DIRS` (currently: `concepts`, `architecture`,
`adrs`, `sources`, `dependencies`, `.templates`) — same way `dependencies/index.md`
is already shipped today.

Either:

1. Ship category `index.md.template` files under
   `packages/vault-io/src/assets/page-templates/<category>/index.md` and render
   them in the existing template loop, or
2. Synthesize a minimal stub inline (just frontmatter + a `## Pages` header)
   for each `FIXED_VAULT_DIRS` entry that lacks an asset template.

Acceptance:

- After `init_vault`, every category referenced from `wiki/index.md` has its
  own `index.md` on disk.
- `lint_wiki.py` on a fresh bootstrap reports zero broken wikilinks from
  `index.md`.

## References

- Lint report 2026-05-21, finding W4 (broken wikilinks in `index.md`)
- `packages/vault-io/src/vault_io/init_vault.py` — `FIXED_VAULT_DIRS` and
  the asset rendering loop
