---
title: "ADR-0015: Wiki-root-relative wikilink form"
category: adr
summary: Wikilinks in the lattice vault are wiki-root-relative — `[[concepts/...]]`, `[[adrs/...]]`, `[[packages/...]]`, and `[[work/<slug>]]` are canonical; the `[[wiki/...]]` prefix and `[[../work/...]]` are forbidden. Obsidian opens at `<workspace>/wiki/` and work/ lives under the wiki.
adr_id: "0015"
status: accepted
decision_date: 2026-05-09
deciders: ["@psprowls"]
supersedes: []
superseded_by:
tags: [wiki, obsidian, wikilinks, layout, conventions]
updated: 2026-06-05
tokens: 1519
---

# ADR-0015: Wiki-root-relative wikilink form

**Status:** accepted (2026-05-09; convention revised 2026-06-05)

## Context

Obsidian opens the vault at the **wiki root** (`<workspace>/wiki/`), and resolves
every wikilink relative to it. Work items live under the wiki at `work/`, so
`[[work/<slug>]]` resolves against the same base as `[[concepts/...]]`. The
immutable `raw/` sources sit beside the vault as a workspace sibling, reached on
disk at `../raw/` and never wikilinked.

Earlier schema docs and live content used two non-canonical forms:

1. `[[../work/<slug>]]` — Obsidian does not support relative-to-current-page
   wikilinks; the `../` prefix escapes the vault and never resolves.
2. `[[wiki/packages/foo/foo]]` — the legacy workspace-root form, which only
   resolved when Obsidian opened one level up at `<workspace>/`. Now that the
   vault opens at the wiki root, the `wiki/` segment points nowhere.

## Decision

All wikilinks in the lattice vault are **wiki-root-relative**. Canonical forms:

| Target | Canonical form |
|---|---|
| Work item | `[[work/<slug>]]` |
| Wiki page (any category) | `[[<category>/<path>]]` — e.g. `[[packages/foo/foo]]`, `[[concepts/bar]]`, `[[adrs/0011-single-workspace-root]]` |
| Folder shorthand | `[[packages/foo]]` resolves to `packages/foo/foo.md` |
| Stem shorthand | `[[foo]]` resolved via the linter's `stems` dict |
| Aliased | `[[foo|Display Text]]` — alias preserved on the right of the `|` |

==Forbidden:== the `[[wiki/...]]` prefix and `[[../work/...]]` / `[[../<anything>]]`.

Companion enforcement:
- The linter ([[packages/lattice-wiki-core/lattice-wiki-core]] `lint_wiki.py`) walks the
  wiki root and keys pages wiki-relative, so the canonical forms resolve and the
  forbidden forms are flagged as broken links.
- Schema docs and page templates lead by example with the wiki-root forms.

## Consequences

**Positive:**
- A single link base across every category — work items, entities, concepts,
  ADRs all resolve the same way.
- Obsidian's graph view and backlinks panel work for every link.
- The deprecated `[[wiki/...]]` and `[[../work/...]]` forms become regression
  guards — any reintroduction is flagged as a broken link.

**Negative:**
- Existing content carried the old `[[wiki/...]]` form and required a one-shot
  sweep (specified in [[sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]]).
- Authors writing by hand must use wiki-root paths; tooling and templates lead
  by example.

## Alternatives considered

- **Open Obsidian at `<workspace>/` and keep the `[[wiki/...]]` prefix** —
  rejected: that buries the vault's own pages one level down and leaves `raw/`
  (immutable, never linked) cluttering the graph. Opening at the wiki root gives
  one clean link base.
- **Auto-rewrite forbidden forms at lint time** — rejected for v1: a lint-time
  regex risks masking real authoring intent. Flagging as broken surfaces
  violations explicitly.

## Impact

- [[packages/lattice-wiki-core/lattice-wiki-core]] — `lint_wiki.py` walks the wiki root and keys pages wiki-relative.
- [[plugins/lattice-wiki/lattice-wiki]] — schema docs and page templates document the canonical forms.
- [[plugins/lattice-work/lattice-work]] — work items live under the wiki and are linted by the wiki-root walk; exempt from orphan detection.
- [[concepts/lattice-vault-terminology]] — vault-terminology reflects the wiki-root-as-vault model.
- [[concepts/per-repo-layout]] — wikilink form follows from the layout shape.

## Follow-ups

- After landing, run `grep -r '\[\[wiki/' lattice/wiki/` and confirm zero results.
- Watch for new authoring drift; consider a `--check-canonical-form` lint flag if drift recurs.
