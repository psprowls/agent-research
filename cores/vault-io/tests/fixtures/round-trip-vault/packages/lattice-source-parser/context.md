---
title: lattice-source-parser — Context
category: package
summary: Concepts, decisions, sources, and history for lattice-source-parser
updated: 2026-05-09
tokens: 595
---

# lattice-source-parser — Context

## Concepts

- [[wiki/concepts/source-tree-model]] — the span-bearing intermediate this package produces
- [[wiki/concepts/language-parser-abstraction]] — per-language module shape, `attrs_json` convention, additivity contract
- [[wiki/concepts/code-graph-schema]] — the SQLite schema this package's `GraphRecords` feeds into

## Decisions

- [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]] — graph records produced here feed the SQLite store
- [[wiki/adrs/0005-sourcetree-sole-domain-model]] — SourceTree (SourceNode + Reference + Span) is the only domain object the package exports; all consumer outputs are pure projections on top of it
- [[wiki/adrs/0006-source-parser-sibling-package]] — lattice-source-parser ships as a sibling Python package free of storage and transport concerns
- [[wiki/adrs/0009-uv-ruff-python-tooling]] — workspace member under the root `uv.lock`; ruff config and `.python-version` are root-only

## Sources

- 2026-05-lattice-source-parser-readme — public-facing README; thin orientation declaring tree-sitter backing, the two-step pipeline, and v1 Python/JS/TS scope. Notes the README's stale pointer to a now-deleted `docs/lattice-graph/specs/...-design.md` path.
- 2026-05-lattice-source-parser-design — **authoritative v1 design spec.** Significantly richer than the README — covers the SourceTree model, the `LanguageParser` interface and config-driven vs. custom-walk asymmetry, the `GraphRecords` projection and how it aligns 1:1 with the SQLite schema, the package vs. plugin concern split, the v1 scope and non-goals, the deferred follow-on items, and open questions.
- 2026-05-uv-ruff-monorepo-design — establishes the `packages/`-wide uv workspace + ruff + pytest tooling standard; this package is a workspace member contributing to the single root `uv.lock`.

## Belongs to domain

(none — cross-cutting infrastructure)

## Used by

- [[wiki/packages/lattice-graph-core/lattice-graph-core]] — primary consumer; upserts `GraphRecords` into the SQLite store and runs cross-file resolution

## Related dependencies

- `tree-sitter>=0.23.0` — binary grammar engine (Language API v2)
- `tree-sitter-language-pack>=0.8.0` — pre-compiled grammar wheels for macOS/Linux/Windows (Python, JS, TS at v1)
