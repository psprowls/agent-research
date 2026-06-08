---
title: wiki-io
uri: pkg:agent-research/wiki-io
kind: package
summary: Vault read/write, frontmatter parsing, layout IO, BM25 search, lint, and update_index.
updated: 2026-05-19
---

# wiki-io

## Overview

`wiki-io` is the on-disk vault layer of the post-rebrand `agent-research` monorepo. It owns the YAML frontmatter parser, the layout IO module (canonical page structure), the BM25 search index, the lint pass, and the `update_index` helper that maintains `index.md` after every write.

## Index, search, and writes

The package keeps wiki storage concerns out of Graph Wiki orchestration code. `frontmatter` reads page metadata, `layout_io` writes canonical markdown pages, `wiki_search` supports BM25 retrieval over vault content, `lint_wiki` reports wiki consistency issues, and `update_index` regenerates `index.md` after mutations. Path resolution is supplied by [[entities/pkg_workspace-io]] so wiki callers can operate on a workspace root instead of hard-coding vault paths.

## API

- `frontmatter.parse(text) -> (dict, str)` — pure-Python YAML frontmatter parser
- `layout_io.write_page(...)` — canonical page-writing entry point
- `wiki_search.bm25_scores(docs, query, k1=1.5, b=0.75)` — Okapi BM25 scorer
- `lint_wiki.scan(wiki, stale_days, log_gap_days, ...)` — vault lint pass
- `update_index.update_index(wiki)` — regenerate `index.md`

## Cross-refs

- Consumed by [[entities/app_graph-wiki-cli]] for every vault-mutating command
- Path resolution is delegated to [[entities/pkg_workspace-io]]
