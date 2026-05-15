# Log — wiki

> Append-only timeline. Every LLM operation leaves an entry here.
>
> Format: `## [YYYY-MM-DD] <op> | <title>` followed by an optional detail line.
> Valid ops: `scan`, `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.

## [2026-05-14] note | Wiki initialized

Topic: **my-utils library**. Single-package fixture vault for eval-harness testing.
Wiki created with `packages/my-utils/` subtree. Represents the single-package shape.
Next: run `/lattice-wiki:scan` to populate.

## [2026-05-14] scan | Initial scan

Detected 1 package: `my-utils` (single-package at repo root). Created `packages/my-utils/my-utils.md` and sub-pages. Updated `index.md`.
