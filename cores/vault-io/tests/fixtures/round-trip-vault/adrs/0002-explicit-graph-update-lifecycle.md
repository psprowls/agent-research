---
title: "ADR-0002: Explicit, hook-surfaced graph update lifecycle (no auto-update, no FS watcher)"
category: adr
summary: Graph updates are explicit (slash commands + a SessionStart staleness banner); no auto-update, no filesystem watcher.
adr_id: "0002"
status: accepted
decision_date: 2026-05-03
deciders: [Patrick Sprowls]
supersedes:
superseded_by:
tags: [architecture, code-graph, lifecycle, hooks]
updated: 2026-05-03
tokens: 856
---

# ADR-0002: Explicit, hook-surfaced graph update lifecycle (no auto-update, no FS watcher)

**Status:** accepted (2026-05-03)

## Context
[[wiki/plugins/lattice-graph/lattice-graph]] needs a strategy for keeping its SQLite index current as code changes. Three plausible approaches:

1. Auto-update at session start.
2. Watch the filesystem and re-parse changed files in real time.
3. Make updates explicit (user-initiated slash command + CLI).

See the update lifecycle spec (`raw/specs/architecture/3.4-update-lifecycle.md`).

## Decision
**Updates are explicit, not magic.** The user (or a slash command, or a session hook surfacing a recommendation) initiates updates. The graph never silently re-parses behind the user's back.

Concretely:

- Four operations: `/lattice-graph:update` (incremental), `/lattice-graph:update --full` (full rebuild), `/lattice-graph:status`, `/lattice-graph:dump`. CLI mirrors: `cg update`, `cg status`, `cg dump`.
- Incremental update is `git diff`-driven and runs in a single SQLite transaction (atomic).
- A SessionStart hook checks `metadata.last_indexed_commit` against `git rev-parse HEAD` and emits a banner when stale. The hook never auto-updates.
- No filesystem watcher.

See [[wiki/concepts/explicit-not-magic-update-lifecycle]] for the full lifecycle shape.

## Consequences

**Positive:**
- User retains agency over when long-running parses happen.
- Branch switches don't trigger massive cascades of "changed file" re-parses.
- Failure modes are visible — the user sees an update fail and can act.
- The MCP server stays a *query daemon* (reads SQLite) — not also an FS-watching daemon.
- Cross-platform: no need to implement FSEvents / inotify / ReadDirectoryChangesW.

**Negative:**
- The graph can be silently stale if the user ignores the banner. Mitigated by `cg_status.is_stale: true` flag for agents that check.
- Updates are blocking (~5–60 s for a full rebuild, much shorter incrementally). Background updates are a v2 consideration.

## Alternatives considered
- **Auto-update at session start** — rejected: surprise factor (30 s blocking update is jarring), branch-switch ambiguity (intent unclear), failure handling (auto-update can leave graph in unknown state).
- **Filesystem watcher** — rejected: cross-platform burden, fights git on branch switches, wrong cadence (millisecond-fresh isn't needed), process-lifecycle pain.
- **Trigger from git hooks** (post-commit, post-merge) — rejected: couples graph updates to git plumbing; user might not want graph rebuilt every commit during a long debugging session.
- **CI-built graphs** — held open as v2 deployment option per [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]].

## Impact
- [[wiki/plugins/lattice-graph/lattice-graph]]
- [[wiki/concepts/explicit-not-magic-update-lifecycle]]
- [[wiki/concepts/code-graph-schema]] — `metadata.last_indexed_commit`, `last_updated_at`, `schema_version` rows

## Follow-ups
- v2: `auto_update_threshold` config flag (silently update if fewer than N commits behind).
- v2: background update — kick off async after session start.
- v2: uncommitted-changes indexing — shadow overlay over committed graph.
