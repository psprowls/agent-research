---
title: lattice-wiki-core — Work
category: package
summary: Open bugs, tech debt, and gaps for lattice-wiki-core; plus a backlog of related work items already filed.
updated: 2026-05-09
sources: 2
tokens: 1623
---

# lattice-wiki-core — Work

> Note: most existing work items target the *plugin* paths (`plugins/lattice-wiki/skills/lattice-wiki/scripts/...`) because they predate the package extraction. Those scripts now live at `packages/lattice-wiki-core/src/lattice_wiki_core/...`. Treat the work item paths as historical and update them as the items are picked up.

## Bugs

- [[work/2026-05-04-state-gate-self-inflicted-closure]] — **bug, open.** `compute_state_gate` runs after `regenerate_dependencies_index`, so the gate sees the scanner's own writes as a dirty tree. Mitigation already shipped: `regenerate_dependencies_index` skips the write when the table body is unchanged (`scan_monorepo.py:1033`). The underlying ordering bug — gate computed *after* the regen — remains, and any future auto-regen that does mutate content will re-trip it.
- 2026-05-05-scanner-file-map-renderer-omits-scripts-in-lattice-wiki-package-page — **bug, open, low severity.** File-map renderer (`scan_monorepo.build_file_map`) was missing top-level `scripts/` entries from the `lattice-wiki` page. The underlying root cause (truncation/sorting edge case) hasn't been confirmed fixed. Verify against a fresh scan.
- [[work/2026-05-09-fix-vault-rooted-wikilinks]] / [[work/2026-05-09-adjust-linter-for-work-sibling-to-vault]] — **bug, open.** Linter walks `<workspace>/wiki/` only and 22+ wiki pages use `[[../work/...]]`; both downstream of [[wiki/adrs/0011-single-workspace-root]]. Resolution path approved in [[wiki/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]] — switch the walk to `<workspace>/`, key pages workspace-relative, gate structural checks via `linted` / `is_work` flags, and rewrite content with a two-pass regex. Decision: [[wiki/adrs/0015-workspace-root-wikilink-form]].

### Resolved (bundled in [[wiki/sources/2026-05-lattice-wiki-core-three-wiki-bug-fixes]])

- [[work/2026-05-09-fix-index-taxonomy-and-top-level-sections]] — **resolved.** `SUBPAGE_STEMS` += `"work"` and `_ALWAYS_IN_MORE` introduced so package work sub-pages don't leak into the Package nav and the More section never goes invisible (`update_index.py:57, 174`).
- [[work/2026-05-09-lint-json-drift-fields-emit-null]] — **resolved.** `_SKIPPED = {"skipped": True}` sentinel replaces `None` initialization for the five drift fields so JSON consumers can distinguish skipped from clean (`lint_wiki.py:55, 168, 223-231`).
- [[work/2026-05-09-remove-agents-md-claim-from-claude-md-template]] — **resolved.** Unconditional `AGENTS.md` reference removed from `CLAUDE.md.template:6`; live `lattice/wiki/CLAUDE.md` patched to match.

## Tech debt

- **`__init__.py` is empty.** No `__all__`, no top-level convenience re-exports, no version. Fine for now, but if external code starts depending on the API, a curated `__all__` would help.
- **No version field surfaced.** `pyproject.toml:7` pins `version = "1.0.0"`, but nothing in the package surfaces it (no `__version__`, no `--version` flag on any CLI). Will matter if/when installed via PyPI or pinned by [[wiki/packages/lattice-wiki-agent/lattice-wiki-agent]].
- **Hand-rolled YAML parsers diverge.** `layout_io._parse_yaml` (`layout_io.py:114`), `update_index.parse_frontmatter` (`update_index.py:80`), `graph_analyzer._parse_frontmatter_lists` (`graph_analyzer.py:32`), `ingest_work_item._parse_frontmatter` (`ingest_work_item.py:60`), and `lint/common.parse_frontmatter` (`lint/common.py:34`) are five separate parsers with slightly different semantics. Drift between them is likely. Worth consolidating into `lint/common.py` and re-exporting.
- **Wikilink resolution is duplicated.** `lint_wiki.py:91-100` and `graph_analyzer.py:93-102` both implement the folder-shorthand + stem-fallback resolver. Must be kept in sync by hand.
- **`detect_containers.py` returns plain dicts.** The classifications are stringly-typed. A `typing.Literal` would catch typos at type-check time.
- **`scan_monorepo.py` is large (~1180 lines).** Workspace discovery, file-map rendering, diffing, state-gate, doc surfacing, and dependency-index regeneration all in one module. The dependency-index code (`scan_monorepo.py:830-1046`) is a candidate for its own module.
- **`update_index.py` doesn't read the layout block.** It uses a hardcoded `CATEGORY_DIRS` map (`update_index.py:55`) for category inference when frontmatter is missing. Any vault with layout-pinned containers using non-default `vault_dir` won't have those pages categorized correctly without explicit `category:` frontmatter.
- **`_parse_pyproject` only finds `[project]` name.** No version, no scripts, no dependencies. Python packages always come back with `version: None`, `exports: []`, `scripts: []`, `depends_on: []` (`scan_monorepo.py:203`). Node packages have a much richer dict — asymmetric.
- **`build_file_map` truncates at 80 entries silently.** The truncation note doesn't say which sub-path was cut off. Could lead to silent file-map gaps on large packages.
- **No tests for `export_marp.py` or `wiki_search.py`.** Both are user-facing CLIs and pure-functional. Easy adds.
- **`graph_analyzer.py` doesn't write back to the vault.** Stats are printed/json'd but never persisted.

## Features

*(none currently tracked)*

## Open questions

- **Is `lattice-wiki-core` a public API?** If truly internal, parsers don't need to be carefully de-duplicated. If public-stable, the hand-rolled YAML and missing `__all__` become real liabilities.
- **Does the state-gate ordering bug need the gate to move *before* any auto-regen?** Or is content-comparison-skip enough? Today "enough" because the only auto-regen is the dependencies-index and it skips on no-change — but the next auto-regen feature will re-open this.
- **Should `ingest_work_item.py` live in this package?** It's deeply cross-plugin (used by `lattice-workflows` and `lattice-work`) and changes to work-page schema force `lattice-wiki-core` releases. Consider whether it belongs in [[wiki/packages/lattice-wiki-agent/lattice-wiki-agent]] or a new `lattice-work-core` package.
