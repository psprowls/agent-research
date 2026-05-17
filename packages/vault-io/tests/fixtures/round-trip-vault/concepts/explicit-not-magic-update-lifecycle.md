---
title: Explicit-not-magic update lifecycle
category: concept
summary: lattice-graph updates are user-initiated (slash command + CLI). The SessionStart hook surfaces staleness as a banner; never auto-updates; no FS watcher. The same banner-not-auto-apply discipline now extends to per-plugin code drift via `lattice_workspace.warn_if_stale`.
tags: [lifecycle, code-graph, hooks, principles, versioning, plugins, release]
updated: 2026-05-11
tokens: 1965
---

# Explicit-not-magic update lifecycle

## Definition
[[wiki/plugins/lattice-graph/lattice-graph]] updates its index only when the user (or a slash command, or a session hook surfacing a recommendation) explicitly initiates them. The graph never silently re-parses behind the user's back. The same discipline now extends to per-plugin code drift — when a plugin ships a newer version than the one last applied to a workspace, the plugin surfaces a banner and waits for an explicit init/upgrade, never auto-running its update logic.

## Motivation

### Why staleness banners, not auto-update

Three reasons not to auto-update at session start:

1. **Surprise factor.** A 30-second blocking update at session start is jarring; the user came here to do something specific.
2. **Branch-switch ambiguity.** If the user just checked out a branch with thousands of changed files, the "right" graph state depends on intent (building for that branch or just visiting?). The hook can't read intent.
3. **Failure handling.** Auto-update that fails leaves the graph in an unknown state. Manual update means the user sees the failure and can act.

### Why no FS watcher

Four reasons:

- **Cross-platform burden** — macOS FSEvents, Linux inotify, Windows ReadDirectoryChangesW each have different semantics and failure modes.
- **Fights git** — branch switches, rebases, stashes trigger massive cascades of "changed files" that aren't semantically changed.
- **Wrong cadence** — agents don't need millisecond-fresh graphs; commit-fresh is enough.
- **Process-lifecycle pain** — a daemon watching the FS is another thing to start, monitor, restart, and debug.

The MCP server runs as a daemon, but it's a *query daemon* — it serves reads from SQLite, doesn't watch the FS.

## Shape

### Four operations

| Operation | Slash command | When |
|---|---|---|
| Incremental update | `/lattice-graph:update` | After commits land, before relying on graph for fresh code |
| Full rebuild | `/lattice-graph:update --full` | First-time bootstrap; corrupted DB; schema migration; unreachable `last_indexed_commit` |
| Status check | `/lattice-graph:status` | "How current is the graph?" |
| Dump | `/lattice-graph:dump` | Debugging; sharing a snapshot; visualization export |

CLI mirrors: `cg update`, `cg status`, `cg dump`. MCP exposes `cg_status` (read-only); writes go through slash commands or CLI.

### Incremental algorithm

1. Read `metadata.last_indexed_commit` from the graph DB.
2. `git diff --name-status <last_indexed_commit>..HEAD`.
3. Per file (deleted/added/modified/renamed): delete, add, or replace nodes+edges. Renames = delete-old + add-new (tree-sitter doesn't preserve identity across renames).
4. Update `metadata.last_indexed_commit = HEAD`, `last_indexed_at = <ISO now>`, bump `last_updated_at` sentinel.
5. Whole update inside a single SQLite transaction (atomic semantics).

### SessionStart hook

When a Claude Code session starts in a repo with `lattice-graph` installed:

```
lattice-graph: 3 commits behind HEAD (12 changed files). Run /lattice-graph:update.
```

A more pointed warning fires if more than `--graph-stale-threshold` (default: 50 commits or 7 days) behind. Banner only — never updates automatically.

### Concurrent safety

- **WAL mode** opened at server startup — many readers + one writer.
- **Single-transaction updates** — readers see pre-update state until commit; new state visible atomically.
- **Cache invalidation via `metadata.last_updated_at`** — server query path checks this single-row SELECT before serving from cache.

Server doesn't need restart after an update.

## Per-plugin staleness — the same pattern, applied to plugin code

The same discipline governs **per-plugin code drift** (introduced in `lattice-workspace` v0.3.0). When a plugin's installed version differs from the `applied_version` recorded for it in `<workspace>/.lattice.yaml`, the plugin surfaces a one-line banner at command entry and stops. It never silently re-runs its setup, never re-templates pages, never re-touches state — exactly because the same three failure modes apply:

1. **Surprise factor.** A plugin that silently re-templates pages or rewrites frontmatter at command entry is jarring; the user came here to do something specific.
2. **Branch-switch / partial-state ambiguity.** If the user just checked out a branch with a different plugin version (or has a half-finished local edit), the "right" upgrade target depends on intent. The plugin can't read intent.
3. **Failure handling.** Auto-applied upgrades that fail leave the workspace in an unknown state. Banner-then-explicit-init means the user sees the failure and can act.

### Shape

| Concern | Tool / API |
|---|---|
| Detect drift | `lattice_workspace.warn_if_stale(workspace, plugin=<name>, version=__version__) -> bool` |
| Surface drift | One-line banner printed by the plugin (plugin owns the copy) |
| Apply drift | The plugin's own init/upgrade slash command (e.g. `/lattice-wiki:init`) |
| Record success | The plugin's init flow calls `lattice_workspace.init(repo_root, plugin=..., version=__version__)` after its update logic completes |

`warn_if_stale` returns `True` only on mismatch and writes `installed_version=version` (leaving `applied_version` untouched) so subsequent `pending_updates(workspace)` reads can aggregate signals across plugins. The plugin's own init flow, after running its update logic end-to-end, calls `init(version=...)` which sets *both* versions atomically. The asymmetry — `warn_if_stale` bumps only `installed_version`; `init` bumps both — is the same explicit-not-magic split: "I noticed an update is available" is recorded passively at the moment any command runs; "I successfully applied the update" only happens on explicit user action.

The reference integration is [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] via `_version_check.py`. See [[wiki/concepts/plugin-versioning-and-update-mechanism]] for the full mechanism (manifest schema, lazy v1→v2 coercion, banner-not-auto-apply contract). The graph case here and the plugin case share one intuition: **surface staleness, never auto-apply**.

## Used in
- [[wiki/plugins/lattice-graph/lattice-graph]] — the original lifecycle this concept governs (graph data freshness)
- [[wiki/packages/lattice-workspace/lattice-workspace]] — the per-plugin extension (`warn_if_stale`, `pending_updates`, version-recording `init`)
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — reference integration via `_version_check.py`

## Related patterns
- [[wiki/concepts/code-graph-schema]] — `metadata.schema_version` and `last_indexed_commit` rows
- [[wiki/concepts/plugin-versioning-and-update-mechanism]] — the per-plugin analog: `installed_version` / `applied_version` in `.lattice.yaml` v2
- [[wiki/concepts/lattice-cross-plugin-contract]] — banner-not-auto-apply is the install/upgrade-time complement to subprocess-not-import

## Decisions
- [[wiki/adrs/0002-explicit-graph-update-lifecycle]] — the original ADR, scoped to graph data
- [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]] — extends the discipline to per-plugin code drift

## Sources
- [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] — design spec for the per-plugin staleness banner pattern
- [[wiki/sources/2026-05-lattice-release-wiki-sync]] — a workflow-level instance of the same discipline: the `/release` slash command refuses to run when HEAD is not `main` rather than silently rebasing or warning-and-continuing, ensuring downstream steps (wiki sync, scanner `state_gate`) have a known precondition.

## Open questions / gotchas
- v2 may add `auto_update_threshold` config (silently update if fewer than N commits behind). Behind a flag, not default.
- v2 may add background update that kicks off after session start without blocking queries.
- A future global `/lattice:status` command (or `lattice-workflows` SessionStart hook) could aggregate `pending_updates` across all installed plugins — same discipline at a higher level. Enabled by the v0.3.0 API; not built.
