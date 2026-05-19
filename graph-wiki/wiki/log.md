# Log — wiki

> Append-only timeline. Every LLM operation leaves an entry here.
>
> Format: `## [YYYY-MM-DD] <op> | <title>` followed by an optional detail line.
> Valid ops: `scan`, `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.
>
> Grep the last 10 entries: `grep "^## \[" log.md | tail -10`

## [2026-05-18] note | Wiki initialized
Topic: **deep-agents monorepo**. Repo: **/Users/pat/Personal/deep-agents**.
Wiki created at `<workspace>/wiki/` with subdirs `concepts/`, `dependencies/`, `sources/`, `architecture/`, `adrs/`, `.templates/` (plus conditional `apps/`, `packages/`, `domains/` based on detected containers). `raw/` and `work/` live at the workspace level (owned by `graph-wiki workspace`).
Schema loader: `CLAUDE.md` + `AGENTS.md` + `.cursorrules`.
Next: run `/graph-wiki:scan` to populate `packages/`.

## [2026-05-18] scan | detected 7 new, 0 renamed, 0 deleted

Pages created (35 total):
- agents/code-wiki-agent/code-wiki-agent.md (+ api, context, patterns, work)
- packages/eval-harness/eval-harness.md (+ api, context, patterns, work)
- packages/model-adapter/model-adapter.md (+ api, context, patterns, work)
- packages/subagent-runtime/subagent-runtime.md (+ api, context, patterns, work)
- packages/vault-io/vault-io.md (+ api, context, patterns, work)
- packages/workspace-io/workspace-io.md (+ api, context, patterns, work)
- plugins/graph-wiki/graph-wiki.md (+ api, context, patterns, work)
State gate: CLOSED (working tree dirty) — last_sync_commit not written.
Ingest candidates: docs/cancellation.md, docs/trace-schema.md

## [2026-05-18] scan | marked stale: code-wiki-agent — API


## [2026-05-18] scan | marked stale: code-wiki-agent — Context


## [2026-05-18] scan | marked stale: code-wiki-agent — Patterns


## [2026-05-18] scan | marked stale: code-wiki-agent — Work


## [2026-05-18] scan | marked stale: eval-harness — API


## [2026-05-18] scan | marked stale: eval-harness — Context


## [2026-05-18] scan | marked stale: eval-harness — Patterns


## [2026-05-18] scan | marked stale: eval-harness — Work


## [2026-05-18] scan | marked stale: graph-wiki — API


## [2026-05-18] scan | marked stale: graph-wiki — Context


## [2026-05-18] scan | marked stale: graph-wiki — Patterns


## [2026-05-18] scan | marked stale: graph-wiki — Work


## [2026-05-18] scan | marked stale: model-adapter — API


## [2026-05-18] scan | marked stale: model-adapter — Context


## [2026-05-18] scan | marked stale: model-adapter — Patterns


## [2026-05-18] scan | marked stale: model-adapter — Work


## [2026-05-18] scan | marked stale: subagent-runtime — API


## [2026-05-18] scan | marked stale: subagent-runtime — Context


## [2026-05-18] scan | marked stale: subagent-runtime — Patterns


## [2026-05-18] scan | marked stale: subagent-runtime — Work


## [2026-05-18] scan | marked stale: vault-io — API


## [2026-05-18] scan | marked stale: vault-io — Context


## [2026-05-18] scan | marked stale: vault-io — Patterns


## [2026-05-18] scan | marked stale: vault-io — Work


## [2026-05-18] scan | marked stale: workspace-io — API


## [2026-05-18] scan | marked stale: workspace-io — Context


## [2026-05-18] scan | marked stale: workspace-io — Patterns


## [2026-05-18] scan | marked stale: workspace-io — Work


## [2026-05-18] scan | scan complete: +0 ~0 -28

