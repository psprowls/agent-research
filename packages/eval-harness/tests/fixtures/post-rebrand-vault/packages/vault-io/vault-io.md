---
title: vault-io
category: package
summary: Vault read/write, frontmatter parsing, layout IO, BM25 search, lint, and update_index.
status: active
package_path: packages/vault-io
package_type: library
domain:
language: Python
depends_on: [workspace-io]
tags: [python, vault, frontmatter, bm25]
sources: 0
updated: 2026-05-19
---

# vault-io

## Overview

`vault-io` is the on-disk vault layer of the post-rebrand `deep-agents` monorepo. It owns the YAML frontmatter parser, the layout IO module (canonical page structure), the BM25 search index, the lint pass, and the `update_index` helper that maintains `index.md` after every write.

## API

- `frontmatter.parse(text) -> (dict, str)` — pure-Python YAML frontmatter parser
- `layout_io.write_page(...)` — canonical page-writing entry point
- `wiki_search.bm25_scores(docs, query, k1=1.5, b=0.75)` — Okapi BM25 scorer
- `lint_wiki.scan(wiki, stale_days, log_gap_days, ...)` — vault lint pass
- `update_index.update_index(wiki)` — regenerate `index.md`

## Cross-refs

- Consumed by [[wiki/agents/code-wiki-agent/code-wiki-agent]] for every vault-mutating command
- Path resolution is delegated to [[wiki/packages/workspace-io/workspace-io]]
