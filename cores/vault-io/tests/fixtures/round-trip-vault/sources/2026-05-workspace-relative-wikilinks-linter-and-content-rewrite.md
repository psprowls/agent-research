---
title: "Workspace-relative wikilinks — linter and content rewrite"
category: source
summary: Approved design spec aligning the lint_wiki.py walker and all wiki content with ADR-0011's single workspace root — wikilinks become workspace-root-relative ([[work/...]] and [[wiki/...]]), the linter walks <workspace>/ and splits pages into linted vs resolvable-only tiers, and a two-pass regex rewrites the existing vault.
source_path: lattice/specs/2026-05-09-lattice-workspace-relative-wikilinks-design.md
source_type: spec
source_date: 2026-05-09
authors: [Patrick Sprowls]
ingested: 2026-05-09
updated: 2026-05-09
tokens: 1790
---

# Workspace-relative wikilinks — linter and content rewrite

## TL;DR
Obsidian opens the vault at `<workspace>/` (e.g. `lattice/`), so wikilinks are vault-root-relative — meaning workspace-root-relative — and must take the form `[[work/<slug>]]` and `[[wiki/packages/...]]` rather than `[[../work/...]]` or bare `[[packages/...]]`. The spec aligns both the linter (walk `<workspace>/`, split pages into linted (`wiki/**`, `work/**`) vs resolvable-only tiers) and the existing content (two-pass regex sweep) with this reality, closing the two open work items filed for the bug.

## Key claims
1. Both bugs — wrong link form in content and a linter blind to `work/` siblings — stem from [[wiki/adrs/0011-single-workspace-root]], which neither the linter nor existing wiki content was updated to match.
2. **Linter fix:** `lint_wiki.py` walks `<workspace>/` (`wiki.parent`) instead of `<workspace>/wiki/`. Pages are keyed workspace-relative (e.g. `wiki/packages/foo/foo`, `work/2026-05-09-foo`). No public signature change — `workspace = wiki.parent` is derived inside the function.
3. **Three lint tiers:**
   - **Linted:** `wiki/**` and `work/**` — structural lint runs (frontmatter, staleness, duplicate titles), wikilinks resolve.
   - **Resolvable-only:** all other non-dotdir top-levels (`raw/`, `knowledge/`, etc.) — wikilinks resolve to them but they aren't structurally linted.
   - **Excluded:** any path with a dotdir component (`.graph/`, `.obsidian/`) — invisible to the linter.
4. **Work pages are exempt from orphan detection.** A page-level `is_work` flag gates orphan checks: work items legitimately exist without wiki backlinks. Frontmatter / staleness / duplicate-title checks still apply to `work/**`.
5. **`work/archived/` continues to be skipped** under the new walk (lifecycle-managed by [[wiki/plugins/lattice-work/lattice-work]]).
6. **Wikilink resolution is unchanged in logic** — it now operates on workspace-relative keys, so `[[wiki/packages/foo/foo]]`, `[[work/2026-05-09-fix]]`, folder-shorthand `[[wiki/packages/foo]]`, and stem-shorthand `[[foo]]` all continue to resolve.
7. **Content rewrite is two regex passes** over every `*.md` under `<workspace>/wiki/`, plus `lattice/CLAUDE.md` and `lattice/wiki/CLAUDE.md`:
   - Pass 1 (must run first): `\[\[\.\./work/` → `[[work/`
   - Pass 2 (protect prefixed and sibling links): `\[\[(?!wiki/|work/|raw/|knowledge/)` → `[[wiki/`
   - Aliases (`[[foo|Display Text]]`) are preserved by both passes.
8. **Schema doc edits:** `lattice/CLAUDE.md` updates the citation guidance from `[[../work/<slug>]] (relative to a wiki page)` to `[[work/<slug>]] (vault-root-relative)`. `lattice/wiki/CLAUDE.md` updates its example and adds a note that wiki-internal links use `[[wiki/...]]` (workspace-root-relative, not wiki-root-relative).
9. **New fixture `sibling-work-resolution/`** plus 5 explicit test cases — including a regression guard (test 5) that `[[../work/foo]]` is flagged as broken.
10. **Out of scope:** structural lint for resolvable-only directories, lifecycle lint in `lattice-work` (unchanged), `graph_analyzer.py`, `wiki_search.py`, `append_log.py`, and the `lint/` sub-checks.

## Proposed changes
- `packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` — switch the page-discovery loop to a workspace-root walk; introduce per-page `linted` and `is_work` flags; gate structural checks on those flags; remove the now-redundant `work/archived/` guard from the old vault walk.
- `packages/lattice-wiki-core/src/lattice_wiki_core/assets/` — page-template wikilink examples reviewed for the new form.
- `packages/lattice-wiki-core/src/lattice_wiki_core/ingest_work_item.py` — review for any programmatically-generated wikilinks.
- `packages/lattice-wiki-core/tests/fixtures/sibling-work-resolution/` — new fixture with vault page, concept, and a sibling work item.
- `lattice/CLAUDE.md` and `lattice/wiki/CLAUDE.md` — schema docs updated to document `[[work/<slug>]]` and `[[wiki/...]]` as canonical.
- All `*.md` under `lattice/wiki/` — two-pass regex rewrite of existing wikilinks.

## Acceptance criteria
- `grep -r '\[\[\.\./work/' lattice/wiki/` returns zero results.
- `pytest packages/lattice-wiki-core/tests/` passes, including the new test cases.
- `python packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py` on the live wiki returns 0 broken links targeting `work/...` paths.
- Both schema docs document `[[work/<slug>]]` and `[[wiki/...]]` as canonical.

## Surprises / contradictions
- `[[wiki/concepts/lattice-vault-terminology]]` describes `wiki` as a "top-level directory holding both `raw/` and the vault" — that model predates [[wiki/adrs/0011-single-workspace-root]] and is now stale: today the workspace root *is* the vault, with `raw/`, `wiki/`, and `work/` as siblings. Flagged on the page.
- `[[wiki/concepts/per-repo-layout]]` ASCII tree shows `<workspace>/wiki/` containing `raw/` and a `<vault-name>/` subdirectory — same stale model. Flagged on the page.
- No vault↔code contradictions — the spec describes the fix; the work items it closes describe the broken state on disk.

## Touches
- [[wiki/concepts/lattice-vault-terminology]]
- [[wiki/concepts/per-repo-layout]]
- [[wiki/concepts/lattice-work-namespace-schema]]
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]]
- [[wiki/packages/lattice-wiki-core/work]]
- [[wiki/plugins/lattice-wiki/lattice-wiki]]
- [[wiki/plugins/lattice-work/lattice-work]]

## Decisions triggered
- [[wiki/adrs/0015-workspace-root-wikilink-form]]

## Closes
- [[work/2026-05-09-fix-vault-rooted-wikilinks]]
- [[work/2026-05-09-adjust-linter-for-work-sibling-to-vault]]

## Where it's cited in this wiki
- [[wiki/adrs/0015-workspace-root-wikilink-form]]
- [[wiki/concepts/lattice-vault-terminology]]
- [[wiki/concepts/per-repo-layout]]
- [[wiki/concepts/lattice-work-namespace-schema]]
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]]
- [[wiki/plugins/lattice-wiki/lattice-wiki]]
- [[wiki/plugins/lattice-work/lattice-work]]
