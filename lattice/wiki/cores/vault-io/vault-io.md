---
title: vault-io
category: package
summary: Vault read/write library — frontmatter parsing, page templates, log appending, lint checks, and monorepo scan for the code-wiki-agent
status: active
package_path: cores/vault-io
package_type: library
domain:
language: python
depends_on: []
tags: [vault, frontmatter, wiki, io, lint]
sources: 0
updated: 2026-05-14
tokens: 0
last_sync_commit:
last_sync_at:
---

# vault-io

## Purpose

Foundation library for all wiki file operations. Ported from the `lattice-wiki-core` Python vendor shim. Handles vault discovery, frontmatter round-trip read/write, page template instantiation, log appending, dependency index generation, BM25 search index, lint checks, monorepo scanning, and graph analysis. Keeps all filesystem and format logic out of the agent layer.

## Public API

Key modules (all under `src/vault_io/`):

- `_workspace.resolve_wiki_and_repo()` — discovers vault + repo root from env or `lattice-workspace`
- `layout_io.read_layout(claude_md)` / `write_layout(claude_md, layout)` — reads/writes the `<!-- lattice-wiki:layout -->` block
- `detect_containers.detect(repo)` — heuristic container detection (agents/, cores/, etc.)
- `scan_monorepo.scan(repo, wiki, layout)` — full monorepo scan; returns workspace list + diff
- `init_vault.init(wiki, topic, repo)` — bootstraps a fresh vault from templates
- `append_log.append(wiki, op, title, detail)` — appends a standardised log entry to `log.md`
- `update_index.update(wiki, workspaces)` — regenerates `index.md` from current vault state
- `ingest_source.prepare(path, wiki, repo)` — metadata extraction for a source before ingest
- `graph_analyzer.analyze(wiki)` — wikilink graph stats
- `git_state.state_gate(repo)` — checks whether the tree is clean and on `main`
- `lint.*` — mechanical lint sub-checkers (containers, packages, domains, file maps, source sync, dependency index, workflow hints)

## File map - vault-io

- `pyproject.toml` — package manifest; no workspace deps; depends on `python-frontmatter`, `boto3`

### vault-io/src/

#### vault-io/src/vault_io/

- `__init__.py` — package init; re-exports key public symbols
- `_workspace.py` — vault + repo path discovery; reads `LATTICE_WORKSPACE` env var or walks up for `.lattice.yaml`
- `append_log.py` — appends `## [YYYY-MM-DD] <op> | <title>` entries to `log.md`
- `detect_containers.py` — heuristic detection of `apps/`, `cores/`, `agents/` containers from repo structure
- `git_state.py` — `state_gate()`: checks working-tree cleanliness + branch; controls whether `last_sync_commit` is written
- `graph_analyzer.py` — walks wikilinks in vault pages; returns link-graph stats (orphans, hub pages, broken links)
- `ingest_source.py` — reads a source file and extracts metadata (frontmatter, word count, title) for pre-ingest discussion
- `ingest_work_item.py` — creates a work item page from a structured dict
- `init_vault.py` — bootstraps vault skeleton (`index.md`, `log.md`, `CLAUDE.md`, `AGENTS.md`, page-template dirs) from assets/
- `layout_io.py` — reads and writes the YAML layout block inside `wiki/CLAUDE.md`
- `scan_monorepo.py` — walks the repo, detects workspace packages, diffs against existing vault pages
- `update_index.py` — regenerates `index.md` content catalog from all vault pages
- `update_tokens.py` — updates `tokens:` frontmatter field using Bedrock `CountTokens` API

##### vault-io/src/vault_io/assets/

Bundled templates shipped with the package.

- `CLAUDE.md.template` — wiki CLAUDE.md template (rendered during init)
- `AGENTS.md.template` — AGENTS.md template
- `cursorrules.template` — `.cursorrules` template
- `index.md.template` — index.md skeleton
- `log.md.template` — log.md skeleton

###### vault-io/src/vault_io/assets/page-templates/

One `.md` template per page category.

- `package.md`, `app.md`, `domain.md`, `concept.md`, `concept-pattern.md` — structural page templates
- `adr.md`, `architecture.md`, `source.md`, `dependency.md`, `work.md`, `index.md` — supporting page templates
- `package-family.md` — multi-package family overview template
- `domain/`, `package/` — sub-templates for domain / package variants

##### vault-io/src/vault_io/lint/

Lint sub-checkers; each returns a list of `LintFinding`.

- `__init__.py` — aggregates all sub-checkers into `lint_all(wiki, repo)`
- `common.py` — shared types (`LintFinding`, severity enum) and helpers
- `container.py` — checks layout block vs on-disk container presence
- `dependency.py` — checks dependency index completeness
- `domain.py` — checks domain page / package page cross-references
- `file_map.py` — checks file-map sections for stale entries vs `git ls-files`
- `package_sync.py` — checks `last_sync_commit` freshness and flags packages with un-synced changes
- `source_sync.py` — checks source page `last_sync_commit` vs repo HEAD for in-repo docs
- `workflow_hints.py` — produces actionable hints when the vault is missing expected pages

### vault-io/tests/

- `__init__.py` — package init
- `conftest.py` — shared fixtures (in-memory vault, temp git repo)

#### vault-io/tests/fixtures/

Test vault fixtures.

##### vault-io/tests/fixtures/edge-case-vault/

Minimal vault for testing lint edge cases (broken wikilinks, missing frontmatter, truncated frontmatter).

- `CLAUDE.md`, `index.md`, `log.md` — vault skeleton
- `concepts/broken-wikilinks.md`, `concepts/missing-title.md`, `concepts/truncated-frontmatter.md`, `concepts/index.md`

##### vault-io/tests/fixtures/round-trip-vault/

Vault used for frontmatter round-trip and trace tests; contains trace files under `.code-wiki/traces/`.

## Key patterns

- `python-frontmatter` for all frontmatter parsing — never hand-rolled YAML
- `git_state.state_gate()` gates any write that bumps `last_sync_commit`; read-only on dirty trees
- Assets directory is bundled via `pyproject.toml [tool.uv.build.include]` so templates are available in installed packages
- Lint sub-checkers are independent; each takes `(wiki, repo)` and returns findings

## Used by
- [[agents/code-wiki-agent/code-wiki-agent]]

## Dependencies (external)
- [[dependencies/python-frontmatter]]
- [[dependencies/boto3]]
