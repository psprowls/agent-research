---
title: tree-sitter
category: concept
summary: Incremental, error-tolerant parser used by lattice-source-parser to build concrete syntax trees from source code, enabling symbol extraction and graph projection without language-specific ad-hoc parsers.
tags: [parsing, tree-sitter, source-parser, graph, ast]
updated: 2026-05-09
tokens: 455
---

# tree-sitter

## What it is

[tree-sitter](https://tree-sitter.github.io/tree-sitter/) is a parser-generator and incremental parsing library. It produces a concrete syntax tree (CST) for a source file given a grammar for the language. Parses are incremental (only re-parses changed regions) and error-tolerant (produces a partial tree even for syntactically broken code). Language grammars are distributed as separate Python packages (e.g. `tree-sitter-python`, `tree-sitter-typescript`).

## How it's used in lattice

[[wiki/packages/lattice-source-parser/lattice-source-parser]] is the sole consumer. It uses tree-sitter to walk source files and extract:

- Top-level symbol definitions (functions, classes, constants)
- Import/dependency edges between modules
- File-level metadata fed into the [[wiki/packages/lattice-graph-core/lattice-graph-core]] SQLite store

The `tree-sitter` Python binding (`py-tree-sitter`) is declared as a dependency of `lattice-source-parser`; no other workspace package depends on it directly.

## Tradeoffs

| Pro | Con |
|---|---|
| Language-agnostic; one API for Python, TypeScript, Go, Rust, etc. | Grammar packages must be installed per language |
| Error-tolerant — partial parses are still useful for graph projection | CST is more verbose than an AST; query patterns are non-trivial |
| Incremental — fast for repeated scans of large repos | |

## Related

- [[wiki/packages/lattice-source-parser/lattice-source-parser]] — primary user
- [[wiki/packages/lattice-graph-core/lattice-graph-core]] — stores the extracted symbol graph
- [[wiki/adrs/0006-source-parser-sibling-package]] — decision to extract source parsing into a sibling package
