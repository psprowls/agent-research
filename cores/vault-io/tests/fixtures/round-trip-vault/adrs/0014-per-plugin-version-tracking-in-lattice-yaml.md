---
title: "ADR-0014: Per-plugin version tracking in `.lattice.yaml`"
category: adr
summary: Bump `.lattice.yaml` to v2 to record `installed_version` and `applied_version` per plugin; expose `warn_if_stale` / `pending_updates` on `lattice-workspace`; require `version=` on `init()`; coerce v1 lazily; accept PyYAML as a runtime dep on the foundational package.
adr_id: "0014"
status: accepted
decision_date: 2026-05-09
deciders: [Patrick Sprowls]
supersedes: []
superseded_by:
tags: [workspace, manifest, versioning, lifecycle, ecosystem]
updated: 2026-05-09
tokens: 1944
---

# ADR-0014: Per-plugin version tracking in `.lattice.yaml`

**Status:** accepted (2026-05-09)

## Context

`.lattice.yaml` v1 records *which* plugins are registered with a workspace (a flat `list[str]`) but not *which version* of each plugin last touched it. When a plugin ships changes the workspace ought to absorb — new template files, restructured page sections, schema changes — it has no way to detect "the workspace is behind." The user must remember to re-run plugin init manually, or the plugin must re-run all setup unconditionally on every invocation. Both options are bad.

A global "all plugins, all pending updates" surface (e.g. a `/lattice:status` command, or a SessionStart hook in `lattice-workflows` that scans every plugin) was considered but explicitly deferred — it requires per-plugin metadata to exist *first*. This ADR provides that metadata and the minimal API plugins need to surface their own staleness, leaving the orchestration layer for a follow-up.

See [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] for the full design spec.

## Decision

Adopt all of the following as a single coherent change to `lattice-workspace` (shipped in v0.3.0):

1. **Manifest schema bumps 1→2.** Top-level `version: 2`. `plugins:` becomes a list of dicts:
   ```yaml
   plugins:
     - name: lattice-wiki
       installed_version: 0.7.0
       applied_version: 0.5.2     # update pending
   ```
2. **Three API surfaces on `lattice-workspace`:**
   - `init(repo_root, *, plugin, version, workspace=None)` — `version=` is **required**; writes both `installed_version` and `applied_version` together. Idempotent.
   - `warn_if_stale(workspace, *, plugin, version) -> bool` — returns `True` only when there is an existing entry whose `applied_version` differs from `version`; on `True` it writes `installed_version=version` (applied_version untouched).
   - `pending_updates(workspace) -> list[PendingUpdate]` — pure read; excludes v1-coerced entries (where `installed_version is None`).
3. **Lazy backward compatibility.** A `_coerce()` step promotes v1 → v2 in memory on read; the file on disk is **never rewritten** by coercion alone. Disk rewrite happens only when a real mutation occurs.
4. **PyYAML replaces the hand-rolled flat-YAML parser.** `manifest.read` uses `yaml.safe_load`; `manifest.write` uses `yaml.safe_dump(sort_keys=False, default_flow_style=False)` to keep diffs stable. `pyyaml >= 6.0` is now a runtime dependency of `lattice-workspace`.
5. **Plugins integrate at two seams:**
   - At command entry — call `warn_if_stale` and print a plugin-owned banner if `True`.
   - Inside the plugin's own init flow — read the manifest, run plugin-specific update logic, then call `init(..., version=__version__)` to record both versions atomically.
6. **Each plugin owns its banner copy and update logic.** `lattice-workspace` only signals; it never auto-applies anything.

`lattice-wiki` (`packages/lattice-wiki-core/_version_check.py`) is the reference integration. Other plugins (`lattice-graph`, `lattice-curator`, `lattice-work`) migrate as follow-ups; until they do, their entries stay v1-coerced and never trigger banners.

## Consequences

**Positive:**

- Each plugin can detect and surface its own staleness without a global orchestrator.
- Untouched workspaces never produce spurious diffs — coercion is in-memory only.
- `warn_if_stale` is a single line at command entry; the integration cost per plugin is trivial.
- The `installed_version` / `applied_version` split lets plugins record "I noticed an update is available" separately from "I successfully applied it" — supports plugin-specific update logic that may need to run between detection and application.
- `init()` is now strictly more informative — old v1 manifests still read, but every new write carries version metadata.

**Negative:**

- `init()` gains a required keyword argument, which is a breaking API change. All in-tree call sites are updated; external consumers (none known today) break loudly with a `TypeError` rather than silently miscount versions.
- `warn_if_stale` writes `installed_version` during what reads as a check — surprising for a read-style name. Documented; the alternative (a separate "record install" call every plugin must remember) is worse.
- `lattice-workspace` is no longer stdlib-only — it now depends on `pyyaml >= 6.0`. The package sits at the bottom of the per-repo plugin dependency graph, so this dep cascades to every consumer in that tier.
- Coercion is lazy, which means v1 reader code must be supported indefinitely. Acceptable: the `_coerce()` function is ~25 lines.
- A workspace nobody runs against stays in v1 on disk forever, then jumps to v2 the first time any plugin runs. The git diff for that first run can look surprising if reviewers don't know the cause.

## Alternatives considered

- **Per-workspace version field instead of per-plugin.** Rejected: different plugins ship updates at different cadences; a workspace can be fresh enough for one plugin and stale for another. Per-plugin tracking matches the actual unit of versioning.
- **Eager v1→v2 rewrite on first read.** Rejected: would cause an unrelated tool's invocation to dirty the working tree with a manifest rewrite. Lazy coercion preserves the principle of least surprise for non-mutating reads.
- **Keep the hand-rolled YAML parser, hand-roll dict-list support too.** Rejected: the v2 shape (nested dicts inside a list, including `null` values) is past the complexity threshold where hand-rolling is cheaper than a real parser. The maintenance burden was the bigger cost.
- **A single `record_install(workspace, plugin, version)` call separate from a pure `is_stale(workspace, plugin, version)` check.** Rejected: plugins would have to remember to call both; missing the record call would silently break staleness detection forever after. `warn_if_stale` collapses the two into one call so the failure mode goes away.
- **Build the global update orchestrator (`/lattice:status`, SessionStart hook in `lattice-workflows`) as part of this change.** Rejected: scope. The metadata and per-plugin API enable it; building it is its own design.

## Impact

- [[wiki/packages/lattice-workspace/lattice-workspace]] — owns the manifest schema, `init`, `warn_if_stale`, `pending_updates`, and `PendingUpdate`.
- [[wiki/packages/lattice-workspace/api]] — public surface fully updated to v0.3.0.
- [[wiki/packages/lattice-workspace/patterns]] — manifest-schema example and dependency posture updated.
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — `_version_check.py` is the reference integration.
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — the first plugin to integrate `warn_if_stale` at command entry.
- [[wiki/concepts/lattice-cross-plugin-contract]] — extended with the per-plugin version-tracking discipline.
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — extended with the banner-not-auto-apply pattern at the per-plugin level.

## Follow-ups

- Migrate `lattice-graph`, `lattice-curator`, `lattice-work` to call `init(..., version=__version__)` and `warn_if_stale` at their own command entries. Until they do, their manifest entries stay v1-coerced.
- A future global `/lattice:status` command that aggregates `pending_updates` across all installed plugins.
- A `lattice-workflows` SessionStart hook surfacing the same aggregate signal at session start (analogue of the `lattice-graph` staleness banner).
- A future enhancement to render per-plugin version info in the auto-rendered `<workspace>/CLAUDE.md` plugins block (currently name-only).
