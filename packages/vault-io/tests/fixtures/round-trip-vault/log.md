# Log — wiki

> Append-only timeline. Every LLM operation leaves an entry here.
>
> Format: `## [YYYY-MM-DD] <op> | <title>` followed by an optional detail line.
> Valid ops: `scan`, `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.
>
> Grep the last 10 entries: `grep "^## \[" log.md | tail -10`

## [2026-05-09] note | Wiki initialized
Topic: **lattice plugins + packages**. Repo: **/Users/pat/Personal/lattice**.
Wiki created at `<workspace>/wiki/` with subdirs `concepts/`, `dependencies/`, `sources/`, `architecture/`, `adrs/`, `.templates/` (plus conditional `apps/`, `packages/`, `domains/` based on detected containers). `raw/` and `work/` live at the workspace level (owned by `lattice-workspace`).
Schema loader: `CLAUDE.md` + `AGENTS.md` + `.cursorrules`.
Next: run `/lattice-wiki:scan` to populate `packages/`.

## [2026-05-09] lint | 2026-05-09 health check

137 pages; 75 broken links (68 are sub-page sibling shorthand [[wiki/api]] etc., 7 are false positives from wikilinks-in-frontmatter or intra-backtick examples), 43 orphans (mostly sub-pages api/context/patterns/work without backlinks from the parent overview), 4 missing frontmatter (CLAUDE + 3 auto-generated indexes), 109 file_map_drift entries (false positives — parser doesn't follow nested bullets under commands/ src/ etc.), 47 orphaned_in_vault entries from code_drift (false positive — slug normalization mismatch between scanner names and vault titles). Real issues: index.md says 0 pages while wiki has 137; ADR-0010 still 'proposed' though lattice-curator is shipped; sub-page shorthand [[wiki/api]] is universally broken across all package overviews.

## [2026-05-09] lint | 2026-05-09 post-fix verification

Fixed high-impact issues: regenerated wiki/index.md (now lists 111 pages instead of 0); promoted ADR-0010 from proposed → accepted; rewrote 72 [[wiki/api]]/[[wiki/context]]/[[wiki/patterns]]/[[wiki/work]]/[[wiki/<pkg>]] sub-page sibling-shorthand wikilinks → full vault paths across 28 package/plugin pages. Broken links 75 → 10 (7 are linter false positives in frontmatter/code-spans, 3 are remaining false positives or unrelated source-spec citations). Orphans 43 → 4 (all auto-generated index pages — orphan by design).

## [2026-05-09] ingest | lattice-wiki-core: three wiki bug fixes

Source: sources/2026-05-lattice-wiki-core-three-wiki-bug-fixes.md

## [2026-05-09] ingest | Per-plugin version tracking in .lattice.yaml

Source: sources/2026-05-per-plugin-version-tracking-in-lattice-yaml.md → ADR-0014

## [2026-05-09] ingest | Plans & Specs path redesign

Source: sources/2026-05-plans-specs-path-redesign.md → ADR-0013

## [2026-05-09] ingest | Workspace-relative wikilinks linter and content rewrite

Source: sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite.md → ADR-0015

## [2026-05-09] create | ADRs 0011–0015 batch

Created ADR-0011 (single workspace root), ADR-0012 (Python+Bedrock+LangChain stack for curator), ADR-0013 (plans/specs under workspace), ADR-0014 (per-plugin version tracking in .lattice.yaml), ADR-0015 (workspace-root-relative wikilink form). All decision_date 2026-05-09.

## [2026-05-09] update | Wikilinks rewrite + concept page touches

Two-pass regex sweep per ADR-0015: [[../work/...]] → [[work/...]] and bare [[<container>/...]] → [[wiki/<container>/...]] across every concept, ADR, package/plugin, and sources page (~31 concept pages bumped). Stale-layout flags added to concepts/lattice-vault-terminology.md and concepts/per-repo-layout.md.

## [2026-05-09] update | Concept page rewrites — vault-terminology + per-repo-layout

Rewrote stale Structural-table rows in concepts/lattice-vault-terminology.md (workspace/vault/wiki/raw/work entries reflect post-ADR-0011 single-root model). Removed stale-tree warning callout and fixed path-ownership table in concepts/per-repo-layout.md.

## [2026-05-09] create | Filed three lint tooling bugs

work/2026-05-09-lint-code-drift-slug-normalization.md (47 false-positive orphans), work/2026-05-09-lint-file-map-nested-bullets.md (109 false-positive missing files), work/2026-05-09-lint-wikilink-scan-includes-frontmatter.md (7 false-positive broken links). All open, blast_radius: lint, target 2026-Q2.

## [2026-05-09] lint | 2026-05-09 health check

140 pages, 0 stale, 0 real broken links (7 reported are linter false positives — link-shaped tokens inside prose/quoted examples, tracked in work/2026-05-09-lint-wikilink-scan-includes-frontmatter.md), 0 real orphans (4 reported are auto-generated indexes + CLAUDE.md, by design), 0 missing-frontmatter issues (same 4 by-design files), 0 real code-drift (49 orphaned_in_vault are slug-normalization false positives tracked in work/2026-05-09-lint-code-drift-slug-normalization.md), 0 real file_map_drift (109 reported are nested-bullet parser misses tracked in work/2026-05-09-lint-file-map-nested-bullets.md). 12 packages on disk all have overview pages, all share last_sync_commit a184373 which is reachable from HEAD, all 15 ADRs accepted with no chain conflicts, callouts well-formed, no Markdown-style .md links. Vault is healthy; remaining noise is all in lint tooling, not in the vault.

## [2026-05-10] update | lint file_map nested-bullet false positives resolved
parse_section_entries now tracks bullet indentation; live wiki file_map issues dropped from 109 → 20. The 5 nested-bullet false positives (lattice-graph commands/) are eliminated. Remaining 20 are a pre-existing section-header parser bug (### hooks/ without pkg_name/ prefix in lattice-workflows wiki page) — 15 parser false positives + 5 genuine drift (.version-bump.json, AGENTS.md, GEMINI.md, lib/lattice_invoke.py, scripts/bump-version.sh not present in plugin tree). Closes [[work/2026-05-09-lint-file-map-nested-bullets]].

## [2026-05-10] lint | 2026-05-10 health check

145 pages; 4 orphans (auto-generated indexes + CLAUDE.md, by design); 7 broken links (all link-shaped tokens in prose, not real broken — fix in source not yet rebuilt to dist); 1 missing frontmatter (wiki/CLAUDE.md by design); 0 stale; 49 orphaned_in_vault and 109 file_map_drift findings (false positives from outdated dist build — source has fixes for BULLET_RE indent + strip_frontmatter that are not in dist); 1 real package_sync_drift (lattice-wiki-core 9 files changed since a184373d, all lint-fix commits); 7 real file_map drift on plugins/lattice-wiki (assets/ moved to packages/lattice-wiki-core/src/assets/); 2 broken nav links in index.md ([[wiki/architecture-index]] and [[wiki/dependencies-index]] don't exist); graph_analyzer reports 47 sub-page orphans (false positive — graph builder doesn't strip wiki/ prefix from wikilink targets after ADR-0015). Two new bugs to file: (a) FILE_MAP_SECTION_RE matches '## File map' sans -name, capturing first bullet as pkg_name; (b) graph_analyzer.py not workspace-relative-aware. All 15 ADRs accepted; ADR chain healthy. 16 work items: 8 resolved, 1 closed, 7 open. No real contradictions vault↔code beyond lattice-wiki-core sync drift.

## [2026-05-10] scan | v0.3.1 release scan — lattice-wiki-core and lattice-wiki plugin updated

Reviewed changed files since a184373: lint/common.py nested-bullet dir_stack + strip_frontmatter, lint_wiki.py folder-name slug matching + strip_frontmatter in wikilink scan, update_index.py frontmatter on sub-index files, new page-templates/index.md template, plugin.json version bump to 1.3.1. Updated packages/lattice-wiki-core/lattice-wiki-core.md, packages/lattice-wiki-core/api.md, plugins/lattice-wiki/lattice-wiki.md. No new packages; 0 new stubs. State gate closed (dirty working tree — .pyc files + uv.lock + .lattice.yaml); last_sync_commit not bumped.

## [2026-05-10] scan | v0.3.2 release — 12 workspaces, 2 changed (lattice-wiki, lattice-wiki-core)

lattice-wiki plugin.json: version 1.3.2; lattice-wiki-core: version 1.3.2, strip_frontmatter in lint, dir_stack in parse_section_entries, work index at workspace root, overview-file guard in code-drift

## [2026-05-10] update | rename lattice-curator package to lattice-curator-core
Renamed the Python package directory and module to `packages/lattice-curator-core` (`lattice_curator_core`). Plugin-facing identifiers (plugin name, MCP server, `.lattice-curator.json`, `~/.cache/lattice-curator/`) unchanged. Touched: [[wiki/packages/lattice-curator-core/lattice-curator-core]], [[wiki/index]], plus wikilink/path sweep across concepts, ADRs, and plugin pages.

## [2026-05-10] scan | 12 workspaces detected, 0 new, 0 deleted — lattice-curator-core + lattice-wiki-core + lattice-wiki changes surfaced (state gate closed; last_sync_commit not bumped)

Changed: lattice-curator-core (130+ files since rename), lattice-wiki-core (10 files, v0.3.2 lint/index fixes), lattice-wiki plugin (plugin.json v0.3.2). Unchanged: lattice-evals, lattice-graph, lattice-graph-core, lattice-source-parser, lattice-wiki-agent, lattice-work, lattice-workflows, lattice-workspace. State gate blocked by dirty working tree (uv.lock + lattice/.lattice.yaml).

## [2026-05-10] lint | 2026-05-10 health check

143 pages, 12/12 packages aligned with disk (no code drift), 7 orphan concept pages (tree-sitter, sqlite-as-store, bedrock-langgraph-stack, claude-code-hook-points, lattice-skill-resolution-order, experimental-skills-at-claude-skills + wiki/CLAUDE by design), 4 package_sync_drift entries since a184373 (lattice-curator-core 156-file rename diff already incorporated into vault; lattice-wiki-core 10 lint-fix commits already documented; lattice-wiki + lattice-curator plugin.json bumps), 1 missing-frontmatter (wiki/CLAUDE.md by design), 0 stale, 0 duplicate titles, log current. Real findings: (a) wiki/index.md links [[wiki/architecture/index]] but architecture/index.md is absent (linter blind-spot — excludes index.md from page-set, so outbound links in index.md never get checked); (b) plugins/lattice-wiki page file map still references skills/lattice-wiki/assets/ which moved to packages/lattice-wiki-core/src/assets/; (c) plugins/lattice-workflows page file map declares scripts/, .version-bump.json, AGENTS.md, GEMINI.md, examples/, lib/lattice_invoke.py, scripts/bump-version.sh — none present on disk (likely stale fork-import); (d) orphan concept pages tree-sitter, sqlite-as-store, bedrock-langgraph-stack, claude-code-hook-points are mentioned in 5-10 sibling pages as plain text — missing wikilinks. file_map_drift parser bug still emitting ~85 false-positive entries against lattice-curator-core/lattice-wiki-core/lattice-graph-core whose headers are well-formed (root cause already tracked in resolved work/2026-05-09-lint-file-map-nested-bullets but dist not rebuilt to match source). a184373 reachable from HEAD (38 commits since); all 15 ADRs accepted, no chain conflicts; index.md categories list matches actual category folders.

## [2026-05-10] lint | 2026-05-10 health check

143 pages, 12/12 packages aligned with disk (0 real code drift). 7 reported orphans all false positives (6 concepts linked only from concepts/index.md which linter excludes from page-set + wiki/CLAUDE.md schema file by design). 0 stale, 0 broken links, 0 duplicate titles, 1 missing-frontmatter (wiki/CLAUDE.md by design), log current. 4 package_sync_drift entries since a184373d (38 commits): lattice-curator-core 156-file rename already merged into vault; lattice-wiki-core 10 lint-fix commits already documented; lattice-wiki + lattice-curator plugin.json bumps. 104 file_map_drift entries: ~95 false positives from documented section-header parser bug; ~9 real drift (plugins/lattice-wiki file map still references skills/lattice-wiki/assets/ path — assets moved to packages/lattice-wiki-core/src/assets/ as part of vendor-package build). Real semantic findings: (a) wiki/index.md links [[wiki/architecture/index]] but architecture/index.md does not exist (architecture/ folder empty); (b) plugins/lattice-wiki file map references the pre-vendor-build asset path (real drift); (c) plugin pages do not record current plugin.json versions (no version frontmatter), so lint cannot detect plugin-version drift; (d) lattice-curator wiki page depends_on still uses long path form 'packages/lattice-curator-core/lattice-curator-core' rather than the bare-slug form used elsewhere (cosmetic). All 15 ADRs accepted, chain healthy; no chain conflicts. a184373d reachable from HEAD. 6 open work items (5 are 2026-Q2/Q3 lattice-graph and workflow tasks; 1 has no target). Callouts well-formed, no Markdown-style internal links.

## [2026-05-10] update | Wiki lint fixes — architecture stub, file map, last_sync_commit bumps, tooling bugs

Created wiki/architecture/index.md stub (fixes broken wikilink). Fixed lattice-wiki.md file map — removed stale assets/ section, added cross-reference to lattice-wiki-core. Bumped last_sync_commit to 1e47472 on 4 pages. Filed work/2026-05-10-lint-index-outbound-links-not-validated.md and work/2026-05-10-graph-analyzer-workspace-prefix-blindness.md.

## [2026-05-10] lint | 2026-05-10 health check

145 pages, 12/12 packages aligned with disk (0 real code drift). 13 broken wikilinks — all false positives: workspace-relative [[wiki/...]] links per ADR-0015 not resolved by lint (known issue). 97 file_map_drift: ~20 real on plugins/lattice-workflows (stale fork-import entries: .version-bump.json, AGENTS.md, GEMINI.md, lib/lattice_invoke.py, scripts/bump-version.sh — none on disk); ~77 false positives from FILE_MAP_SECTION_RE bug. 4 package_sync_drift since 1e47472: lattice-curator + lattice-wiki (plugin.json v0.3.3 bump), lattice-wiki-core (5 files, v0.3.3 release), lattice-curator-core (pyproject.toml v0.3.3 bump) — wiki descriptions remain accurate, only version numbers changed. 1 orphan + 1 missing-frontmatter (wiki/CLAUDE.md, by design). 0 stale, 0 duplicate titles, log current. Graph: 2 components; 7 orphans + 13 sinks all false positives (concept pages linked from index.md excluded from inbound edge set; sink sub-pages are stubs). No vault<->code contradictions. All 15 ADRs accepted, chain healthy. Action items: (a) clean lattice-workflows.md file map of stale scripts/ section; (b) bump last_sync_commit on 4 sync-drifted package pages to 4989f8e.

## [2026-05-10] update | lint wikilink resolver: index.md targets + placeholder-token filtering

Implemented two-part fix for workspace-relative wikilink resolution in lint_wiki.py: (1) index.md pages now resolve as valid wikilink targets (e.g., [[wiki/adrs/index]]) via a separate link_targets set; (2) template-token placeholders (targets containing `...`, `<`, or `>`) are skipped before resolution, eliminating 6 false-positive "broken" wikilinks. Live lint run dropped from 13 false-positive broken links → 1 genuine false positive ([[wiki/packages/foo/api]] example in work-item description). Filed [[work/2026-05-10-example-wikilinks-in-work-descriptions]] for the remaining case. Closes [[work/2026-05-10-lint-wikilink-resolver-workspace-prefix-unaware]].

## [2026-05-10] scan | synced 12 pages to HEAD 33a712a

lattice-wiki-core: prose updated (FILE_MAP_SECTION_RE fix, _is_placeholder_target, link_targets, 4 new test files, version 0.3.3); 11 other workspaces: routine last_sync_commit bump

## [2026-05-10] ingest | Execution Skills Comparison: executing-plans vs subagent-driven-development vs dispatching-parallel-agents

Wrote [[wiki/sources/2026-05-execution-skills-comparison]] + new concept [[wiki/concepts/execution-skills-comparison]]; updated [[wiki/plugins/lattice-workflows/lattice-workflows]], [[wiki/plugins/lattice-workflows/api]], [[wiki/plugins/lattice-workflows/patterns]], [[wiki/concepts/subagent-vs-teammate]]; regenerated index.

## [2026-05-10] ingest | Model Selection Guidelines

Added [[wiki/sources/2026-05-model-selection-guidelines]] + new concept [[wiki/concepts/model-selection-per-skill]]; updated [[wiki/plugins/lattice-workflows/patterns]] (new pattern bullet), [[wiki/plugins/lattice-workflows/api]] (model: frontmatter note), and [[wiki/plugins/lattice-workflows/lattice-workflows]] (sources++). Flagged vault-vs-code contradiction: code-reviewer is an agent (not a skill) and code-scanner does not exist in the codebase.

## [2026-05-10] ingest | Superpowers fork selection (pcvelz vs obra)

sources/2026-05-superpower-fork-selection; concepts/superpowers-fork-vs-upstream (new); adrs/0016-track-pcvelz-superpowers-fork (new); plugins/lattice-workflows/lattice-workflows (sources 3->4); plugins/lattice-workflows/context (concept + ADR + source + Related dependencies); adrs/index; sources/index; concepts/index; wiki/index

## [2026-05-11] update | lattice-graph-core api.md — imported-by/exports/exported-by shipped
Promoted three commands out of "Deferred to v1.1" into the CLI table.

## [2026-05-10] lint | 2026-05-10 post-ingest health check

162 pages, 580 edges; 1 orphan (wiki/CLAUDE — schema loader, expected), 1 broken link (work/index has illustrative [[wiki/packages/foo/api]] in a work-item description — known-tracked), 0 stale, 1 missing-frontmatter (wiki/CLAUDE — schema loader, expected). Code drift clean (12/12 packages aligned). Container/source/package-sync drift all clean. File-map drift: wiki/plugins/lattice-wiki/lattice-wiki references skills/lattice-wiki/scripts/lint/ and scripts/tests/ — those dirs no longer exist in skills/ (moved to packages/lattice-wiki-core/src/.../lint/ and packages/lattice-wiki-core/tests/). Index drift: wiki/index.md says Work (22 pages) but work/index.md and disk show 23. Semantic: new ingest batch (execution-skills-comparison, model-selection-per-skill, superpowers-fork-vs-upstream + ADR-0016) cleanly cross-linked into plugins/lattice-workflows/{lattice-workflows,api,patterns,context}; 19/20 skills/agents already carry the model: field claimed by patterns.md (using-workflows is the lone exception, plausibly intentional); code-scanner-missing contradiction correctly inline-flagged on both source and concept pages.

## [2026-05-11] scan | v2026.05.11.1 post-release sync: 6 packages reviewed, 4 prose-updated

lattice-graph (0.1.0→0.2.0): 4 new commands (imported-by, exports, exported-by, sync-wiki); lattice-graph-core (0.1.0→0.2.0): queries.py exports/exported_by/imported_by, sync_wiki.py, ops_sync_wiki.py, 4 new tests; lattice-wiki (0.3.3→0.4.0): update_tokens.py wired into scanner; lattice-wiki-core (0.3.3→0.4.0): update_tokens.py module, missing_tokens lint group, graph_analyzer inbound-index fix; lattice-wiki-agent (dep bump); lattice-workflows (internal SKILL.md fix). State gate closed (lattice/.lattice.yaml dirty); last_sync_commit not bumped.

## [2026-05-11] lint | 2026-05-11 health check

143 wiki pages + 27 work pages; 12/12 packages aligned with disk (0 code drift); 1 broken link (work/index → wiki/packages/foo/api — known placeholder example, tracked in work/2026-05-10-example-wikilinks-in-work-descriptions, open); 1 orphan + 1 missing-frontmatter (wiki/CLAUDE.md schema loader, by design); 2 missing_tokens (wiki/CLAUDE + concepts/lattice-dependencies-tiering — second is real); 6 package_sync_drift entries since 33a712ad (all incorporated into v2026.05.11.1 post-release scan log but last_sync_commit not bumped because state gate closed on dirty lattice/.lattice.yaml — same pattern as previous 5 release scans); 0 stale, 0 container/source/file-map drift, 0 duplicate titles, log current; ADR chain healthy (16 accepted, no supersedes); 8 open work items, no roadmap target overruns (all 2026-Q2/Q3 still in window); concept gap: bedrock-langgraph-stack concept page mentioned-as-plain-text across 10 package/plugin pages with no wikilinks; lattice-dependencies-tiering concept is a graph sink with only index inbound (forward-looking spec, OK); architecture/index.md and dependencies/index.md are stub-only — both registered in main index. Graph: 2 components (1 = CLAUDE schema loader, by design). Action items: file follow-on tasks for (a) sync-drift release-scan dirty-tree pattern, (b) bedrock-langgraph wikification, (c) lattice-dependencies-tiering tokens stamping.

## [2026-05-11] scan | post-release sync for v2026.05.11.2 — lattice-graph 0.2.0 → 0.2.1

Updated wiki/plugins/lattice-graph/lattice-graph.md: version bump 0.2.0→0.2.1, hook config migration from plugin.json to hooks/hooks.json, added license/keywords/env metadata. Stamped last_sync_commit=81208fe, last_sync_at=2026-05-11. Regenerated index.md (144 pages), updated token counts.

## [2026-05-11] scan | post-release scan for v2026.05.11.3 — 2 pages updated

Updated: plugins/lattice-curator (version 0.1.0→0.2.0), plugins/lattice-graph (version 0.2.1→0.3.0, plugin.json commands array removed, CLAUDE.md step fix). State gate closed (dirty tree — lattice/.lattice.yaml). last_sync_commit not bumped.

## [2026-05-11] lint | 2026-05-11 post-release v2026.05.11.3 health check

175 wiki pages + 26 work pages; 12/12 packages aligned with disk (0 code drift); 1 broken link (work/index → wiki/packages/foo/api, known placeholder, tracked open in work/2026-05-10-example-wikilinks-in-work-descriptions); 1 orphan + 1 missing-frontmatter + 1 missing-token (wiki/CLAUDE.md schema loader, by design); 2 package_sync_drift entries (lattice-graph 2 files since 81208fe, lattice-curator 1 file since c2a5068 — both are plugin.json commands-array removal from v2026.05.11.3 release; last_sync_commit not bumped because state gate closed on dirty lattice/.lattice.yaml — same recurring pattern tracked in work/2026-05-11-last-sync-commit-drift-accumulates-across-wiki, open); 0 stale, 0 container/source/file-map drift, 0 duplicate titles, 0 exports drift; log current (33 entries, last is today); graph 2 components (1 = CLAUDE schema loader, by design), 13 sinks (sub-page stubs, by design); 16 ADRs accepted, chain healthy; index.md taxonomies aligned with disk (Package 12 + 26 work pages); no real contradictions vault↔code.

## [2026-05-11] lint | 2026-05-11 health check

175 wiki pages + 26 work pages; 12/12 packages aligned with disk (0 code drift); 1 broken link (work/index -> wiki/packages/foo/api, known placeholder in work-item description, tracked in work/2026-05-10-example-wikilinks-in-work-descriptions, open); 1 orphan + 1 missing-frontmatter + 1 missing-token (wiki/CLAUDE.md schema loader, by design); 0 stale; 0 container/source/file-map/package-sync drift (last_sync_commit c2a5068 and 97a27ff both ancestors of HEAD, 17 commits since c2a5068 touched only plugin.json/CLAUDE.md/hooks.json on lattice-graph and lattice-curator and wiki was bumped a0d074b); 0 duplicate titles; 0 exports drift; log current; 16 ADRs all accepted with no chain conflicts; graph 2 components (1 = CLAUDE schema loader, by design); concept gap closure verified - bedrock-langgraph-stack now wikilinked from 12 pages; architecture/index.md and dependencies/index.md remain stub-only; no real vault<->code contradictions.

## [2026-05-11] ingest | lattice-wiki-core: lint code_drift slug normalization (design)

Source: sources/2026-05-lattice-wiki-core-lint-code-drift-slug-normalization.md. Touched: lattice-wiki-core.md (cited source on v0.3.2 lint_wiki bullet, +1 source ref), api.md (slug-based vault_pkg_pages filter and code_drift semantics).

## [2026-05-11] ingest | lattice-graph-core documents edge / cg sync-wiki

Touched sources/2026-05-lattice-graph-core-documents-edge (new), packages/lattice-graph-core/{api,context}, plugins/lattice-graph/context, concepts/code-graph-schema, index.

## [2026-05-11] ingest | lattice-graph-core symmetric commands (imported-by / exports / exported-by)

Source: sources/2026-05-lattice-graph-core-symmetric-commands.md (shipped in v0.2.0). Touched packages/lattice-graph-core/{api,context}.md and plugins/lattice-graph/{api,context}.md (fixed stale 'v1.1 deferred' claim).

## [2026-05-11] ingest | /release: branch gate + post-release wiki sync (spec)

Ingested lattice/specs/2026-05-11-lattice-release-wiki-sync-design.md as source_type:doc. Spec proposes Step 0 (branch gate, abort if not main) and Step 9 (post-push wiki sync offer dispatching lattice-wiki:scanner) in .claude/commands/release.md; both shipped, with implementation adding a Step 9c (cg update + cg sync-wiki) on top of the spec. Touched: sources/2026-05-lattice-release-wiki-sync.md (new), plugins/lattice-wiki/lattice-wiki.md, concepts/explicit-not-magic-update-lifecycle.md, index.md, log.md. No ADR proposed (workflow-level precondition, not architecture).

## [2026-05-11] ingest | lattice-wiki-core: tokens frontmatter field (design)

Source: sources/2026-05-lattice-wiki-core-tokens-frontmatter-field.md (lattice/specs/2026-05-11-...-tokens-frontmatter-field-design.md, source_type:doc). Shipped in lattice-wiki-core v0.4.0. Touched: packages/lattice-wiki-core/lattice-wiki-core.md (corrected stale 'whitespace-split word count' description to tiktoken cl100k_base; added source ref, sources 2->3), packages/lattice-wiki-core/api.md (new update_tokens section, missing_tokens added to lint report shape, sources 2->3). Deltas captured in source 'Surprises' section: baseline strip for idempotency, frontmatter-required skip, truncated-fence guard, line-level YAML rewrite, walks work/ in addition to wiki/.

## [2026-05-11] scan | post-release sync v2026.05.11.4 — lattice-work 0.1.1, lattice-workflows 0.3.2

lattice-work: bumped last_sync_commit to 1e59687 (sidecar.py null-guard fix, no prose changes needed); lattice-workflows: updated agents/code-reviewer.md description to reflect 5-dimension review + structured output format; updated requesting-code-review/SKILL.md description (template file deleted, dispatch now inline via Agent tool); bumped last_sync_commit to 1e59687

## [2026-05-11] lint | 2026-05-11 health check

183 wiki pages + 28 work pages (27 + index); 12/12 packages aligned with disk (0 code drift); 0 container/source/file-map/package-sync drift (last_sync_commit c2a5068 and 97a27ff both reachable from HEAD); 1 broken link (work/index -> wiki/packages/foo/api, known placeholder in work-item description, open as work/2026-05-10-example-wikilinks-in-work-descriptions); 1 orphan + 1 missing-frontmatter + 1 missing-token (wiki/CLAUDE.md schema loader, by design); 0 stale, 0 duplicate titles, 0 exports drift; log current (today). Semantic findings: (a) architecture/index.md says '15 ADRs' but disk now has 16 (ADR-0016 added); (b) dependencies/index.md auto-block remains empty (no detail pages yet — opt-in by schema, informational); (c) plugins/lattice-curator/lattice-curator.md last_sync_at=2026-05-10 inconsistent with last_sync_commit=97a27ff (commit dated 2026-05-11); (d) graph: 2 components (CLAUDE schema-loader is the standalone, by design). All 16 ADRs accepted, no chain conflicts. 5 open work items (2 lattice-graph Q3, 3 various Q2), none past target. New ingest batch from ded7b0f (5 spec ingests on 2026-05-11) cleanly cross-linked into lattice-wiki-core/lattice-graph-core/lattice-wiki pages and sources/index. No real vault<->code contradictions.

## [2026-05-12] lint | 2026-05-12 health check

166 wiki pages + 11 live work pages (17 newly archived); 12/12 packages aligned with disk (0 code drift); 1 package_sync_drift (lattice-work: 1 uncommitted change to scripts/regenerate_work_index.py since 1e59687 — trivial bug-fix, no prose update needed); 0 container/source/file-map drift; 42 broken links all symptomatic of stale work/index.md (still lists 27 entries) and historical wiki references to work items moved to work/archived/ (17 items archived per git status: 2026-05-06 + 2026-05-09 + 2026-05-10 batches); 1 orphan + 1 missing-frontmatter + 1 missing-token (wiki/CLAUDE.md schema loader, by design); 0 stale, 0 duplicate titles, 0 exports drift; log current. Semantic findings: (a) work/index.md auto-block stale — needs /lattice-work regen so resolved items move out; (b) architecture/index.md still says '15 ADRs' but disk has 16 (carryover from prior lint, ADR-0016 added); (c) dependencies/index.md auto-block remains empty (informational, opt-in by schema); (d) graph still 2 components (CLAUDE schema-loader standalone by design). All 16 ADRs accepted, no chain conflicts. Open question: should historical wikilinks in ADR-0015 and patterns/api/work pages be rewritten to work/archived/* or left as-is for historical fidelity (linter flags them either way unless resolver follows archive moves).
