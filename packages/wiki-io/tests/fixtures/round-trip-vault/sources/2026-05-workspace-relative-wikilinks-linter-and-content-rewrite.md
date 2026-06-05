---
title: "Wiki-root-relative wikilinks — linter and content rewrite"
category: source
summary: Approved design aligning the lint_wiki.py walker and all wiki content with the wiki-root vault base — wikilinks become wiki-root-relative ([[work/...]] and [[concepts/...]]), the linter walks the wiki root and keys pages wiki-relative, and a sweep rewrites the legacy [[wiki/...]] prefix out of the existing vault.
source_path: lattice/specs/2026-05-09-lattice-wiki-root-wikilinks-design.md
source_type: spec
source_date: 2026-05-09
authors: ["@psprowls"]
ingested: 2026-05-09
updated: 2026-06-05
tokens: 1790
---

# Wiki-root-relative wikilinks — linter and content rewrite

## TL;DR
Obsidian opens the vault at the wiki root (`<workspace>/wiki/`), so wikilinks are
wiki-root-relative — `[[work/<slug>]]`, `[[concepts/...]]`, `[[packages/...]]` —
not `[[wiki/...]]` or `[[../work/...]]`. The spec aligns the linter (walk the wiki
root, key pages wiki-relative, work items live under the wiki) and the existing
content (a one-pass sweep of the legacy `wiki/` prefix) with this reality.

## Key claims
1. The legacy `[[wiki/...]]` prefix only resolved when Obsidian opened at
   `<workspace>/`. Opening at the wiki root makes `[[concepts/...]]`,
   `[[packages/...]]`, and `[[work/...]]` share one link base.
2. **Linter fix:** `lint_wiki.py` walks the wiki root and keys pages
   wiki-relative (e.g. `concepts/foo`, `packages/foo/foo`, `work/2026-05-09-foo`).
3. **Work items live under the wiki** at `work/`, so they are linted by the
   wiki-root walk and `[[work/<slug>]]` resolves like any other page. Work pages
   are exempt from orphan detection — they legitimately exist without backlinks.
4. **Wikilink resolution is unchanged in logic** — it now operates on
   wiki-relative keys, so `[[packages/foo/foo]]`, `[[work/2026-05-09-fix]]`,
   folder-shorthand `[[packages/foo]]`, and stem-shorthand `[[foo]]` all resolve.
5. **Content rewrite is a single sweep** over every `*.md` in the vault:
   `\[\[wiki/` → `[[`. Aliases (`[[foo|Display Text]]`) are preserved; `[[work/...]]`
   and bare stems are never touched (they never start with `wiki/`).
6. **Schema doc edits:** templates and `CLAUDE.md`/`AGENTS.md` document
   `[[work/<slug>]]` and `[[<category>/...]]` as canonical and drop the `wiki/`
   prefix and the `../work/` form.

## Proposed changes
- `lint_wiki.py` — walk the wiki root; key pages wiki-relative; work items under the wiki.
- page templates — wikilink examples use the wiki-root form.
- All `*.md` under the vault — one-pass `\[\[wiki/` → `[[` sweep.

## Acceptance criteria
- `grep -r '\[\[wiki/' lattice/wiki/` returns zero results.
- The linter reports zero broken links for the canonical forms.
- Schema docs document `[[work/<slug>]]` and `[[<category>/...]]` as canonical.

## Touches
- [[concepts/lattice-vault-terminology]]
- [[concepts/per-repo-layout]]
- [[concepts/lattice-work-namespace-schema]]
- [[packages/lattice-wiki-core/lattice-wiki-core]]
- [[plugins/lattice-wiki/lattice-wiki]]
- [[plugins/lattice-work/lattice-work]]

## Decisions triggered
- [[adrs/0015-workspace-root-wikilink-form]]

## Closes
- [[work/2026-05-09-fix-vault-rooted-wikilinks]]
- [[work/2026-05-09-adjust-linter-for-work-sibling-to-vault]]

## Where it's cited in this wiki
- [[adrs/0015-workspace-root-wikilink-form]]
- [[concepts/lattice-vault-terminology]]
- [[concepts/per-repo-layout]]
- [[packages/lattice-wiki-core/lattice-wiki-core]]
- [[plugins/lattice-wiki/lattice-wiki]]
- [[plugins/lattice-work/lattice-work]]
