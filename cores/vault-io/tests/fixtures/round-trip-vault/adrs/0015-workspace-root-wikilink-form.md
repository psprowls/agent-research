---
title: "ADR-0015: Workspace-root-relative wikilink form"
category: adr
summary: Wikilinks in the lattice vault are workspace-root-relative — `[[work/<slug>]]` and `[[wiki/<category>/...]]` are canonical; `[[../work/...]]` and bare `[[packages/...]]` are forbidden. Follows from ADR-0011 placing the Obsidian vault at `<workspace>/`.
adr_id: "0015"
status: accepted
decision_date: 2026-05-09
deciders: [Patrick Sprowls]
supersedes: []
superseded_by:
tags: [wiki, obsidian, wikilinks, layout, conventions]
updated: 2026-05-09
tokens: 1519
---

# ADR-0015: Workspace-root-relative wikilink form

**Status:** accepted (2026-05-09)

## Context

[[wiki/adrs/0011-single-workspace-root]] places the Obsidian vault at `<workspace>/` (e.g. `lattice/`), with `wiki/`, `work/`, and `raw/` as siblings under that root. Obsidian opens at the vault root and resolves all wikilinks relative to it.

Earlier schema docs and live wiki content used two non-canonical wikilink forms:

1. `[[../work/<slug>]]` — Obsidian does **not** support relative-to-current-page wikilinks; the `../` prefix escapes the vault entirely and the link never resolves.
2. Bare `[[packages/foo/foo]]`, `[[concepts/bar]]`, `[[adrs/0011-...]]` — these would only work if Obsidian opened at `<workspace>/wiki/`, which it does not.

A 2026-05-09 lint run found 22 broken `[[../work/...]]` links across 10 wiki pages plus 91 other broken links — all symptoms of the same mismatch. The two open work items [[work/2026-05-09-fix-vault-rooted-wikilinks]] and [[work/2026-05-09-adjust-linter-for-work-sibling-to-vault]] tracked the content fix and the linter fix respectively. Full design captured in [[wiki/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]].

## Decision

All wikilinks in the lattice vault are **workspace-root-relative**. The canonical forms are:

| Target | Canonical form |
|---|---|
| Work item | `[[work/<slug>]]` |
| Wiki page (any category) | `[[wiki/<category>/<path>]]` — e.g. `[[wiki/packages/foo/foo]]`, `[[wiki/concepts/bar]]`, `[[wiki/adrs/0011-single-workspace-root]]` |
| Folder shorthand | `[[wiki/packages/foo]]` resolves to `wiki/packages/foo/foo.md` |
| Stem shorthand | `[[foo]]` resolved via the linter's `stems` dict |
| Aliased | `[[wiki/foo|Display Text]]` — alias preserved on the right of the `|` |

==Forbidden:== `[[../work/...]]`, `[[../<anything>]]`, and bare `[[packages/...]]` / `[[concepts/...]]` / `[[adrs/...]]` without the `wiki/` prefix.

Companion enforcement:
- The linter ([[wiki/packages/lattice-wiki-core/lattice-wiki-core]] `lint_wiki.py`) walks `<workspace>/` and keys pages workspace-relative, so the canonical forms resolve and the forbidden forms are flagged as broken links.
- The schema docs `lattice/CLAUDE.md` and `lattice/wiki/CLAUDE.md` document the canonical forms and an explicit "wiki-internal links use `[[wiki/...]]`" note.

## Consequences

**Positive:**
- Obsidian's graph view and backlinks panel work correctly for every link.
- The linter no longer produces a tide of false-positive broken-link findings on `[[work/...]]` targets.
- The deprecated `[[../work/...]]` form, once rewritten, becomes a regression guard — any reintroduction is flagged as a broken link.
- One schema rule across all categories (everything under `<workspace>/` is reachable via its workspace-relative path).

**Negative:**
- Existing wiki content carries the old forms and required a one-shot two-pass regex rewrite (specified in [[wiki/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]]).
- Lint-report paths now show workspace-relative keys (e.g. `wiki/packages/lattice-wiki-core/lattice-wiki-core` instead of `packages/lattice-wiki-core/lattice-wiki-core`) — slightly longer, but unambiguous.
- Authors writing pages by hand must remember the `wiki/` prefix for wiki-internal links; tooling and templates need to lead by example.

## Alternatives considered

- **Keep `[[../work/...]]` and patch Obsidian-side resolution** — rejected: Obsidian has no setting that makes `../` work; this would require a forked Obsidian or a custom plugin. The vault layout already gives us a clean, standards-compliant path.
- **Open Obsidian at `<workspace>/wiki/` instead of `<workspace>/`** — rejected: that would re-hide `work/` and `raw/` from Obsidian (no graph, no backlinks, no jump-to), undoing the value of the single-workspace-root layout.
- **Auto-rewrite forbidden forms at lint time** — rejected for v1: a regex rewrite at lint time risks silently masking real authoring intent. The lint-as-broken-link approach surfaces violations explicitly so authors fix them.

## Impact

- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — `lint_wiki.py` walks `<workspace>/` and gates structural checks on per-page `linted` / `is_work` flags.
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — schema docs (`CLAUDE.md`, `AGENTS.md`) and page templates document the canonical forms.
- [[wiki/plugins/lattice-work/lattice-work]] — work items are linted for frontmatter / staleness / duplicate titles by the workspace-walking linter, but lifecycle lint stays here. Work items are exempt from orphan detection.
- [[wiki/concepts/lattice-vault-terminology]] — vault-terminology entries reflect the workspace-root-as-vault model.
- [[wiki/concepts/per-repo-layout]] — wikilink form follows from the layout shape.
- All existing wiki pages — one-shot two-pass regex rewrite per the source spec.

## Follow-ups

- Land the linter change and the content rewrite in the same change set (the linter relies on the rewritten content to pass, and the rewrite relies on the linter walking `<workspace>/` to validate).
- After landing, run `grep -r '\[\[\.\./work/' lattice/wiki/` and confirm zero results.
- Watch for new authoring drift; consider a `--check-canonical-form` flag on `lint_wiki.py` if drift recurs.
