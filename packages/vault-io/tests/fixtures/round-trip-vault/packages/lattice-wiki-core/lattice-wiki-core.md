---
title: lattice-wiki-core
category: package
summary: Pure-Python (stdlib-only) library that powers the lattice-wiki plugin — scan, lint, ingest, index, search, and layout IO for an Obsidian-shaped Code Wiki.
status: active
package_path: packages/lattice-wiki-core
package_type: library
domain:
language: Python
depends_on: []
tags: [python, wiki, core, stdlib]
sources: 3
updated: 2026-05-11
last_sync_commit: c2a5068
last_sync_at: 2026-05-10
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
tokens: 3778
---

# lattice-wiki-core

## Purpose

`lattice-wiki-core` is the executable backbone of the [[wiki/plugins/lattice-wiki/lattice-wiki]] plugin. It implements the four core wiki operations — **scan**, **ingest**, **lint**, and **index** — plus supporting helpers for layout IO, git state, BM25 search, log appending, and Marp export. It is **pure stdlib** (no third-party dependencies; `pyproject.toml` declares `dependencies = []`) so the plugin works in any Python 3.11+ environment without a virtualenv. The plugin's `scripts/` directory ships only thin shims that vendor this package and dispatch to either it (default `claude` backend) or [[wiki/packages/lattice-wiki-agent/lattice-wiki-agent]] (optional `bedrock` backend).

## File map

- `pyproject.toml` — hatchling build config; `name = lattice-wiki-core`, `requires-python = ">=3.11"`, `dependencies = ["lattice-workspace"]`; version `0.4.0`

### lattice-wiki-core/src/assets/
Schema and page templates copied into a freshly-initialized wiki by `init_vault.py`.

- `AGENTS.md.template` — schema for Codex / Cursor / Antigravity / OpenCode / Gemini wikis
- `CLAUDE.md.template` — schema for Claude Code wikis (the default tool)
- `cursorrules.template` — `.cursorrules` companion installed when `--tool cursor` or `--tool all`
- `index.md.template` — starter `<vault>/index.md` written before the first scan
- `log.md.template` — starter `<vault>/log.md`

#### lattice-wiki-core/src/assets/page-templates/
Per-category page skeletons copied into `<vault>/.templates/` and consumed by `ensure_subpage` / `ensure_domain_page`.

- `adr.md`, `app.md`, `architecture.md`, `concept.md`, `concept-pattern.md`, `dependency.md`, `domain.md`, `index.md` (new in v0.3.1; updated in v0.3.2 with YAML frontmatter block), `package.md`, `package-family.md`, `source.md`, `work.md` — one skeleton per page category

#### lattice-wiki-core/src/assets/page-templates/domain/
Two-file domain layout used by `ensure_domain_page` / `ensure_domain_details`.

- `details.md` — domain details sub-page
- `overview.md` — domain `<domain>.md` overview

#### lattice-wiki-core/src/assets/page-templates/package/
Sub-page templates instantiated by `ensure_subpage`.

- `api.md`, `context.md`, `overview.md`, `patterns.md`, `work.md`

### lattice-wiki-core/src/lattice_wiki_core/
The importable Python package. Each `*.py` module is also a CLI entry point (`python -m lattice_wiki_core.<name> --help`).

- `__init__.py` — package marker; exports `__version__`
- `_version_check.py` — **new in v0.3.0.** `check_for_updates(workspace)` calls `lattice_workspace.warn_if_stale` and prints a banner to stderr if the installed plugin version differs from `applied_version` in the manifest. Imported at the top of `scan_monorepo`, `wiki_search`, and `append_log` main entries. Swallows all exceptions (fail-open).
- `_workspace.py` — workspace discovery helper; provides `resolve_wiki_and_repo()` returning `(wiki_dir, repo_root)`. Falls back gracefully when `lattice-workspace` is unavailable (test compat).
- `append_log.py` — append a standardized `## [YYYY-MM-DD] <op> | <title>` entry; validates op against `VALID_OPS`; calls `check_for_updates` at entry.
- `detect_containers.py` — classify top-level repo dirs (`app`/`package`/`domain`/`docs`/`single-package`/`ambiguous`) using manifest + .md heuristics
- `export_marp.py` — render a page or directory subtree as a Marp slide deck
- `git_state.py` — `head_commit`, `is_clean_main`, `changed_files_since`; the gate that controls `last_sync_commit` writes
- `graph_analyzer.py` — wikilink graph stats; treats `depends_on:` frontmatter as edges. **v0.3.3:** strips the `wiki/` workspace prefix from wikilink targets before lookup so sub-page wikilinks like `[[wiki/packages/foo/api]]` resolve correctly instead of appearing as isolated single-node components. **v0.4.0:** index/log pages are no longer excluded from graph traversal — they contribute inbound links (so pages linked only from an index are not flagged as orphans), but their outbound links are excluded from the graph to prevent index pages from inflating hub scores.
- `ingest_source.py` — produce a brief for `/lattice-wiki:ingest` (text, preview, sha, suggested page, state-gate)
- `ingest_work_item.py` — non-interactive `category: work` page filer with strict schema validation
- `init_vault.py` — bootstrap a fresh wiki from `<repo>` and chosen tool; now passes `version=__version__` to `workspace_init`; next-steps text updated to use `/lattice-wiki:scan` and `/lattice-wiki:ingest`
- `layout_io.py` — YAML layout block read/write, `resolve_vault_dir`, `ensure_subpage`, `ensure_domain_page`, `ensure_domain_details`
- `lint_wiki.py` — health-check dispatcher; orchestrates `lint/` modules. **v0.4.0:** new `missing_tokens` lint group — pages without a `tokens:` frontmatter field are collected and reported; `print_report` shows the list and prompts to run `update_tokens`. Per [[wiki/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]] (design approved 2026-05-09) this walks `<workspace>/` (= `wiki.parent`) instead of `<workspace>/wiki/`, keys pages workspace-relative, and splits discovery into linted (`wiki/**`, `work/**`) and resolvable-only tiers via per-page `linted` and `is_work` flags. Work items get base structural lint but are exempt from orphan detection. Closes [[work/2026-05-09-fix-vault-rooted-wikilinks]] and [[work/2026-05-09-adjust-linter-for-work-sibling-to-vault]]; canonical link forms recorded in [[wiki/adrs/0015-workspace-root-wikilink-form]]. **v0.3.2:** wikilink scan calls `strip_frontmatter` before `strip_code` (fixes false-positive broken-link reports on YAML scalar values that happen to look like wikilinks); code-drift uses folder name (`Path(k).name`) instead of `title:` frontmatter for vault slug matching (fixes slug mismatches when `title:` diverges from folder name); `vault_pkg_pages` filter now also requires `Path(k).parent.name == Path(k).name` (overview-file guard, prevents sub-pages from being treated as package pages) — eliminated 47 false-positive `orphaned_in_vault` entries on a clean wiki. See [[wiki/sources/2026-05-lattice-wiki-core-lint-code-drift-slug-normalization]]. **v0.3.3:** `index.md` files are now included in the outbound link graph so broken links in index pages are caught and pages only linked from an index are not incorrectly flagged as orphans. New `_is_placeholder_target()` helper — wikilinks whose target contains `...`, `<`, or `>` are silently skipped rather than reported as broken links, preventing false positives from template tokens (e.g. `[[wiki/...]]`, `[[work/<slug>]]`) in schema and template pages. A separate `link_targets` set now tracks all discovered page paths (including `index.md` files) so that `[[wiki/adrs/index]]`-style wikilinks resolve correctly even though `index.md` files are excluded from the `pages` dict used for orphan/frontmatter checks.
- `scan_monorepo.py` — workspace discovery, file-map rendering, diff, state-gate, dependency-index regeneration; layout-drift message updated to reference `/lattice-wiki:init`; `doc_candidates` message updated to `/lattice-wiki:ingest`
- `update_index.py` — regenerate `<vault>/index.md` and per-category sub-indexes. v0.3.0 changes: `dependency` category added to `CATEGORY_INDEX_FILES`; `work` added to `SUBPAGE_STEMS` (excluded from nav); wikilinks in index now prefixed `wiki/` (workspace-root-relative); five "always show" categories in More section even at 0 pages. **v0.3.1:** `render_category_index` emits YAML frontmatter (`title`, `category: index`, `summary`, `updated`) so sub-index files pass the frontmatter lint check. **v0.3.2:** work index is written at `<workspace>/work/index.md` (sibling of the wiki, not inside it) and linked from the main index's "More" section as `[[work/index]]`; `cat_path.parent.mkdir(parents=True, exist_ok=True)` ensures sub-index directories are created; `_entry_link` helper normalizes workspace-rooted vs wiki-rooted wikilinks for entries depending on their vault location; `scan_work(wiki.parent)` populates the work category from the workspace work directory.
- `update_tokens.py` — **new in v0.4.0.** Walks every wiki page (plus `<workspace>/work/`) and writes `tokens: <N>` frontmatter based on `tiktoken` `cl100k_base` (GPT-4 BPE; close approximation to Claude's tokenizer). Called by the scanner agent after `update_index.py`. Strips any existing `tokens:` line before counting so re-runs are byte-idempotent. Guards against truncated frontmatter, skips files without frontmatter, and rewrites the YAML line-by-line (no `frontmatter.dumps()` reformat) to keep diffs minimal. CLI: `--dry-run`, `--json`. See [[wiki/sources/2026-05-lattice-wiki-core-tokens-frontmatter-field]].
- `wiki_search.py` — stdlib BM25 search; calls `check_for_updates` at entry

#### lattice-wiki-core/src/lattice_wiki_core/lint/
Per-check-group modules. Each exports `check(...) -> list[str]` and a `GROUP` constant.

- `common.py` — shared regex constants and helpers (`parse_frontmatter`, `strip_code`, `strip_frontmatter`, `parse_inline_list`, etc.). **v0.3.2:** `BULLET_RE` updated to capture leading indent group (group 1 = indent, group 2 = token); new `strip_frontmatter()` helper strips leading YAML front-matter before wikilink scanning; `parse_section_entries` now maintains a `dir_stack: list[tuple[int, str]]` of in-scope directory bullets per section, enabling nested bullet resolution (fixes file-map lint false positives for bullets nested under directory bullets). **v0.3.3:** `FILE_MAP_SECTION_RE` regex tightened to require a literal ` - ` separator between `## File map` and the package name (was `\s+-\s+`, which could greedily consume a newline + a bullet dash, causing nameless `## File map` headings to falsely match with a bullet line as the captured name).
- `container.py` — pinned-vs-disk container drift; orphan / legacy vault dirs
- `dependency.py` — optional `dependency_layer` group: kind discriminator, family back-pointers, stub detail pages
- `domain.py` — package pages whose vault location disagrees with `domain:` frontmatter
- `file_map.py` — `## File map - <name>` entries that no longer exist on disk
- `package_sync.py` — package/app pages whose source has changed since `last_sync_commit`
- `source_sync.py` — in-repo source pages whose underlying file has changed since `last_sync_commit`
- `workflow_hints.py` — `workflow_hints:` frontmatter pointing at missing sub-pages

### lattice-wiki-core/tests/
Stdlib `unittest` + pytest-discoverable test suite.

- `conftest.py` — pytest fixtures
- `helpers.py` — `tmp_repo`, `write_pkg`, `write_file`, `write_claude_plugin` for inline repo construction
- `test_*.py` — one file per concern (smoke, layout IO, scan, lint group, ingest, etc.). New in v0.3.0: `test_init_vault_dirs.py`, `test_lint_json_drift.py`, `test_lint_wikilink_resolution.py`, `test_lint_work_archived_skip.py`, `test_lint_workspace_sibling_resolution.py`, `test_update_index_categories.py`, `test_version_check.py`. New/updated in v0.3.2: `test_lint_file_map_nested_bullets.py` (negative + positive assertions for nested-bullet indentation in file-map lint); `test_lint_common_strip_frontmatter.py` (strip_frontmatter helper); `test_lint_code_drift_slug.py` (folder-name-based slug matching); `test_lint_wikilink_resolution.py` (strip-frontmatter-before-scan regression); `test_update_index_categories.py` (work index at workspace root, sub-index frontmatter). New in v0.3.3: `test_graph_analyzer_workspace_prefix.py` (wikilink prefix stripping in graph_analyzer); `test_lint_index_links.py` (index.md inclusion in outbound link graph); `test_lint_file_map_section_re.py` (regression: nameless `## File map` heading must not match `FILE_MAP_SECTION_RE`); `test_lint_wikilink_index_targets.py` (index.md pages are valid wikilink targets but excluded from orphan/frontmatter checks); `test_lint_wikilink_placeholders.py` (unit tests for `_is_placeholder_target` helper); `test_lint_wikilink_template_tokens.py` (integration: template-token wikilinks skipped from broken-link reports, real broken links alongside them still reported). New in v0.4.0: `test_graph_analyzer_index_inbound.py` (index/log pages contribute inbound edges but not outbound); `test_lint_missing_tokens.py` (missing_tokens group collects pages without `tokens:` field); `test_update_tokens.py` (update_tokens module writes correct `tokens:` counts and guards against truncated frontmatter).

## Sub-pages

- [[wiki/packages/lattice-wiki-core/api]] — public API reference, function signatures, CLI flags
- [[wiki/packages/lattice-wiki-core/patterns]] — key patterns and conventions
- [[wiki/packages/lattice-wiki-core/work]] — bugs, tech debt, open questions
- [[wiki/packages/lattice-wiki-core/context]] — design history, ADRs, vendor sync, concepts

## Appears in sources

- [[wiki/sources/2026-05-lattice-wiki-core-three-wiki-bug-fixes]] — bundled spec for three small fixes (index taxonomy, lint `--json` skipped sentinel, CLAUDE.md.template AGENTS.md claim). All three shipped.
- [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] — `lattice-wiki-core` is the **reference integration** for the v0.3.0 per-plugin version-tracking API; `_version_check.py` calls `lattice_workspace.warn_if_stale` from the entry points of `scan_monorepo`, `lint_wiki`, `ingest_source`, `wiki_search`, and `append_log`, and `init_vault.py` passes `version=__version__` through to `workspace_init`.
- [[wiki/sources/2026-05-lattice-wiki-core-lint-code-drift-slug-normalization]] — design spec for the v0.3.2 `lint_wiki.code_drift` slug normalization that narrowed `vault_pkg_pages` to overview pages and migrated `vault_names`, `planned_names`, and `exports_drift` to path-derived slugs; eliminated 47 false-positive orphan entries. Shipped in commit `1a036fc`.
- [[wiki/sources/2026-05-lattice-wiki-core-tokens-frontmatter-field]] — design spec for the v0.4.0 `tokens:` frontmatter field plus the dedicated `update_tokens.py` script (`tiktoken` `cl100k_base`, `python-frontmatter` round-trip, `--dry-run` / `--json`, idempotent by stripping the existing `tokens:` line before counting), and the soft `missing_tokens` lint group. All 19 page templates seed `tokens: 0`. Shipped.
