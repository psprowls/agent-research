# Log — wiki

> Append-only timeline. Every LLM operation leaves an entry here.
>
> Format: `## [YYYY-MM-DD] <op> | <title>` followed by an optional detail line.
> Valid ops: `scan`, `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.

## [2026-05-14] note | Wiki initialized

Topic: **edge-case testing**. This vault intentionally contains malformed pages to test
parser and agent robustness: truncated frontmatter, missing title fields, broken wikilinks,
and an empty containers list.
