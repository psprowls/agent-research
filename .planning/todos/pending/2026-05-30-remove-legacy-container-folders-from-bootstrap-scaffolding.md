---
created: 2026-05-30T18:18:11.237Z
title: Remove legacy container folders from bootstrap scaffolding
area: tooling
files:
  - packages/wiki-io/src/wiki_io/init_vault.py:46-54,190-196
---

## Problem

Bootstrap scaffolds `apps/`, `domains/`, `dependencies/`, and `packages/` folders
in the vault. These are remnants from before we switched to a single `entities/`
folder and should no longer be created.

Where they come from in `packages/wiki-io/src/wiki_io/init_vault.py`:

- **`dependencies`** — hardcoded in `FIXED_VAULT_DIRS` (line 52), created
  unconditionally for every vault.
- **`apps` / `packages` / `domains`** — created from `structural_dirs`
  (lines 190-196), derived from `_resolve_pinned_containers` /
  `_detect_containers`. They're written when the detector pins top-level
  containers of those kinds.

`entities` is already the canonical home (line 50, seeded with `_index.md` at
lines 210-220), making the per-container folders dead scaffolding.

## Solution

In `init_vault.py`:

- Drop `dependencies` from `FIXED_VAULT_DIRS`.
- Stop materializing `apps/` / `packages/` / `domains/` container folders during
  bootstrap (the `structural_dirs` loop at lines 195-196). Decide whether to keep
  detecting/pinning containers in the manifest (`containers` at line 270, used
  downstream) but simply not `mkdir` the vault folders — vs. ripping out the
  detection entirely. Default: keep detection metadata, stop creating the dirs.

Downstream references to audit/update when planning (not necessarily in scope, but
they describe or consume the old layout):
- `packages/wiki-io/src/wiki_io/scan_monorepo.py:909-926` — `_collect(vault/"apps")`,
  `_collect(vault/"packages")`, `domains_dir = vault/"domains"`.
- `packages/wiki-io/src/wiki_io/lint/container.py:19-21` — container name set.
- Templates/docs that describe the layout: `assets/log.md.template:12`,
  `assets/CLAUDE.md.template` & `AGENTS.md.template` (line ~33),
  `prompts/_fragments/architecture_overview.py:15-17`,
  `prompts/_fragments/page_categories.py:8-10`.
- Init success messages reference `wiki/packages/` (`init_vault.py:309,327`).

Confirm with the entities-folder migration intent: if `apps`/`packages`/`domains`
are fully superseded by `entities/`, these references likely all collapse to the
single folder. Scope the cleanup to bootstrap first; the broader scan/lint/prompt
alignment may warrant its own follow-up.
