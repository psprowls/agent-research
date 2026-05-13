---
title: "lattice-wiki-core: lint code_drift slug normalization (design)"
category: source
summary: Design spec that fixes 47 false-positive orphaned_in_vault entries by narrowing vault_pkg_pages to overview pages (structural invariant Path(k).parent.name == Path(k).name) and replacing every title-based lookup with path-derived slugs in both code_drift and exports_drift. Shipped 2026-05-10.
source_path: lattice/specs/2026-05-10-lattice-wiki-core-lint-code-drift-slug-normalization-design.md
source_type: doc
source_date: 2026-05-10
authors: []
ingested: 2026-05-11
updated: 2026-05-11
tags: [lattice-wiki-core, lint, code-drift, slug, false-positive]
tokens: 1464
---

# lattice-wiki-core: lint code_drift slug normalization (design)

## TL;DR

Approved design spec for the fix that eliminated 47 false-positive `orphaned_in_vault` entries on a clean wiki. Root cause: `lint_wiki.py` keyed `vault_names` by `fm.get("title")` and matched every page with `category: package` — so facet pages (`api.md`, `context.md`, `patterns.md`, `work.md`) with titles like `lattice-curator — API` got diffed against scanner slugs like `lattice-curator`. Fix narrows `vault_pkg_pages` to overview pages via the structural invariant `Path(k).parent.name == Path(k).name`, then keys every set off `Path(k).name`. The same swap covers `exports_drift`.

## Key claims

1. **Root cause is two-fold.** Both `code_drift` and `exports_drift` shared title-based lookups: `vault_names = {_unscope(p["fm"].get("title", Path(k).name)) ...}` (`packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py:178` at spec time) and `title = _unscope(p["fm"].get("title", ""))` (`lint_wiki.py:202`). Facet sub-pages inherit `category: package` from the overview convention, so they leaked into the diff.
2. **Structural invariant beats suffix stripping.** A package overview lives at `<container>/<slug>/<slug>.md`, so `Path(k).parent.name == Path(k).name` selects exactly overview pages without enumerating sub-page suffixes (` — API`, ` — Context`, ` — Patterns`, ` — Work`, ` (plugin)`). Adding a new facet (e.g. `examples.md`) does not regress the filter.
3. **`Path(k).name` is already an unscoped slug.** Filesystem convention enforces what `_unscope()` was approximating; the helper is no longer needed on this path.
4. **Tests.** Spec required a new `test_lint_code_drift.py` with a two-package fixture (each with overview + four facets) asserting `code_drift["orphaned_in_vault"] == []` and `code_drift["missing_in_vault"] == []`, plus a second case adding an on-disk-only package and asserting it lands in `missing_in_vault`.
5. **Out of scope.** No `category: package-facet` introduced; `missing_in_vault` unchanged; no rename of `vault_pkg_pages`.

## Proposed changes (as shipped)

- `packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py:177` — narrow `vault_pkg_pages` filter
- `lint_wiki.py:178` — `vault_names` keyed by `Path(k).name`
- `lint_wiki.py:184-188` — `planned_names` same swap
- `lint_wiki.py:202` — `exports_drift` title lookup same swap

Shipped in commit `1a036fc` (per `[[work/2026-05-09-lint-code-drift-slug-normalization]]` frontmatter). The live file shows the filter at `lint_wiki.py:236-239`, slug-based names at `lint_wiki.py:241,247`, and `title = Path(k).name` at `lint_wiki.py:261`.

Regression test shipped as `packages/lattice-wiki-core/tests/test_lint_code_drift_slug.py` (note: spec proposed `test_lint_code_drift.py`; the as-shipped file uses the `_slug` suffix).

## Evidence / rationale

- Lint run on 2026-05-09 surfaced 47 `orphaned_in_vault` entries on a wiki the user knew was in sync — every entry was a facet title (`<pkg> — API`, `<pkg> — Context`, etc.) or a plugin overview (`<pkg> (plugin)`). See `wiki/log.md` `[2026-05-09] lint | 2026-05-09 health check`.
- Suffix stripping was rejected because the page-format convention is itself flexible (new facets could ship), whereas the `<container>/<slug>/<slug>.md` invariant is enforced by `ensure_subpage` / `_vault_path_for` and by the scanner's stub-creation path.

## Surprises / contradictions

- None against the code. Verified live at `packages/lattice-wiki-core/src/lattice_wiki_core/lint_wiki.py:236-261` — the shipped implementation matches the spec exactly.
- The pre-fix vault page [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] already mentions this change ("`vault_pkg_pages` filter now also requires `Path(k).parent.name == Path(k).name` (overview-file guard, prevents sub-pages from being treated as package pages)") under the v0.3.2 changelog bullet, but it was previously uncited. This ingest backfills the citation.

## Touches

- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — source citation added to v0.3.2 changelog bullet for `lint_wiki.py`
- [[wiki/packages/lattice-wiki-core/api]] — slug-based `vault_pkg_pages` filter and `code_drift` semantics documented under the `lint_wiki` section

## Decisions triggered

None. The structural-invariant filter is a small implementation choice scoped to one module — no ADR warranted. The work item [[work/2026-05-09-lint-code-drift-slug-normalization]] (status: resolved) captures the trade-off between this fix and the suffix-stripping alternative.

## Related work items

- [[work/2026-05-09-lint-code-drift-slug-normalization]] — resolved in commit `1a036fc`

## Where it's cited in this wiki

- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]]
- [[wiki/packages/lattice-wiki-core/api]]
