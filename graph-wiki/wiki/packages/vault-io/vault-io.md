---
title: vault-io
category: package
summary: Vault IO for code-wiki-agent
status: active
package_path: packages/vault-io
package_type: library
language: python
exports: []
depends_on: [workspace-io]
depended_on_by: 0
tags: []
sources: 0
updated: 2026-05-18
tokens: 0
last_sync_commit:
last_sync_at:
workflow_hints:
  brainstorming: [context.md]
  planning:      [api.md, patterns.md]
  debugging:     [api.md, work.md]
---

# vault-io

## Purpose
Vault IO for code-wiki-agent

## File map - vault-io
TODO — describe what this directory contains.

- `DRIFT-DECISIONS-RAW.md` — TODO
- `DRIFT-DECISIONS.md` — TODO
- `pyproject.toml` — TODO

### vault-io/src/
TODO — describe what this directory contains.


#### vault-io/src/vault_io/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `_workspace.py` — TODO
- `append_log.py` — TODO
- `detect_containers.py` — TODO
- `git_state.py` — TODO
- `graph_analyzer.py` — TODO
- `ingest_source.py` — TODO
- `ingest_work_item.py` — TODO
- `init_vault.py` — TODO
- `layout_io.py` — TODO
- `lint_wiki.py` — TODO
- `scan_monorepo.py` — TODO
- `update_index.py` — TODO
- `update_tokens.py` — TODO
- `wiki_search.py` — TODO

##### vault-io/src/vault_io/assets/
TODO — describe what this directory contains.

- `AGENTS.md.template` — TODO
- `CLAUDE.md.template` — TODO
- `cursorrules.template` — TODO
- `index.md.template` — TODO
- `log.md.template` — TODO

###### vault-io/src/vault_io/assets/page-templates/
TODO — describe what this directory contains.

- `adr.md` — TODO
- `app.md` — TODO
- `architecture.md` — TODO
- `concept-pattern.md` — TODO
- `concept.md` — TODO
- `dependency.md` — TODO
- `domain.md` — TODO
- `index.md` — TODO
- `package-family.md` — TODO
- `package.md` — TODO
- `source.md` — TODO
- `work.md` — TODO
- `domain/` — TODO
- `package/` — TODO

##### vault-io/src/vault_io/lint/
TODO — describe what this directory contains.

- `__init__.py` — TODO
- `common.py` — TODO
- `container.py` — TODO
- `dependency.py` — TODO
- `domain.py` — TODO
- `file_map.py` — TODO
- `package_sync.py` — TODO
- `source_sync.py` — TODO
- `workflow_hints.py` — TODO

### vault-io/tests/
TODO — describe what this directory contains.

- `conftest.py` — TODO

#### vault-io/tests/fixtures/
TODO — describe what this directory contains.


##### vault-io/tests/fixtures/edge-case-vault/
TODO — describe what this directory contains.

- `CLAUDE.md` — TODO
- `index.md` — TODO
- `log.md` — TODO

###### vault-io/tests/fixtures/edge-case-vault/concepts/
TODO — describe what this directory contains.

- `broken-wikilinks.md` — TODO
- `index.md` — TODO
- `missing-title.md` — TODO
- `truncated-frontmatter.md` — TODO

##### vault-io/tests/fixtures/round-trip-vault/
TODO — describe what this directory contains.


###### vault-io/tests/fixtures/round-trip-vault/.code-wiki/
TODO — describe what this directory contains.

- `search.db` — TODO
- `bm25/` — TODO
- `traces/` — TODO

> Truncated at 80 files.

## Sub-pages
- [[api]]      — public API, exports, CLI subcommands
- [[patterns]] — key patterns and conventions
- [[work]]     — bugs, tech debt, features, open questions
- [[context]]  — concepts, decisions, ADRs, sources
