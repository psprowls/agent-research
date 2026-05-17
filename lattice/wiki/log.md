# Log — wiki

> Append-only timeline. Every LLM operation leaves an entry here.
>
> Format: `## [YYYY-MM-DD] <op> | <title>` followed by an optional detail line.
> Valid ops: `scan`, `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.
>
> Grep the last 10 entries: `grep "^## \[" log.md | tail -10`

## [2026-05-14] scan | Initial monorepo scan — 5 new package stubs
5 new: `agents/code-wiki-agent`, `packages/eval-harness`, `packages/model-adapter`, `packages/subagent-runtime`, `packages/vault-io`. 0 renamed. 0 deleted. State gate: read-only (dirty working tree). Pages created; `last_sync_commit` deferred until tree is clean.

## [2026-05-14] note | Wiki initialized
Topic: **deep-agents monorepo — LangChain/deepagents wiki agent on AWS Bedrock**. Repo: **/Users/pat/Personal/deep-agents**.
Wiki created at `<workspace>/wiki/` with subdirs `concepts/`, `dependencies/`, `sources/`, `architecture/`, `adrs/`, `.templates/` (plus conditional `apps/`, `packages/`, `domains/` based on detected containers). `raw/` and `work/` live at the workspace level (owned by `lattice-workspace`).
Schema loader: `CLAUDE.md` + `AGENTS.md` + `.cursorrules`.
Next: run `/lattice-wiki:scan` to populate `packages/`.
