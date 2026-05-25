---
title: Plugin versioning and update mechanism
category: concept
summary: Per-plugin `installed_version` / `applied_version` tracking inside `.lattice.yaml` (v2 schema), backed by a three-call `lattice-workspace` API (`init`, `warn_if_stale`, `pending_updates`) — banner-only, plugin-owned upgrade logic, lazy v1→v2 coercion.
tags: [versioning, manifest, lifecycle, plugins, lattice-workspace, banner]
updated: 2026-05-09
tokens: 2389
---

# Plugin versioning and update mechanism

## Definition

`lattice-workspace` records, per workspace and per plugin, two version strings: `installed_version` (what the plugin most recently reported about itself) and `applied_version` (the version whose update logic has been run successfully against this workspace). When the two diverge, the plugin owes the workspace an upgrade; surfacing that fact and running the upgrade are both **plugin-owned**. `lattice-workspace` only stores the numbers and exposes a tiny query API.

Introduced in `lattice-workspace` v0.3.0 (2026-05-09). Reference integration: `lattice-wiki`.

## Manifest schema — v1 → v2

The `.lattice.yaml` top-level `version` field bumps **1 → 2** to mark the format change. The `plugins` entry changes from a bare string list to a list of objects.

**v1 (legacy):**

```yaml
version: 1
initialized_at: 2026-05-09
plugins:
  - lattice-workflows
  - lattice-wiki
```

**v2 (current):**

```yaml
version: 2
initialized_at: 2026-05-09
plugins:
  - name: lattice-workflows
    installed_version: 0.6.0
    applied_version: 0.6.0
  - name: lattice-wiki
    installed_version: 0.7.0
    applied_version: 0.5.2     # update pending
```

| Field | Meaning |
|---|---|
| `name` | Plugin slug — matches `plugin.json` `name`. |
| `installed_version` | What the plugin reported about itself the last time any of its commands ran here. May be `null` for v1-coerced entries until the plugin runs. |
| `applied_version` | The last version whose update path completed successfully against this workspace. May be `null` for v1-coerced entries. |

**Update-pending predicate:** `installed_version is not None and installed_version != applied_version`.

Source authority: `packages/lattice-workspace/src/lattice_workspace/manifest.py`.

## Public API surface

Three functions on `lattice_workspace`. Two are new in v0.3.0; the third (`init`) gains a **required** `version=` keyword argument.

```python
def init(
    repo_root: Path,
    *,
    plugin: str,
    version: str,             # required
    workspace: Path | None = None,
) -> None: ...

def warn_if_stale(workspace: Path, *, plugin: str, version: str) -> bool: ...

def pending_updates(workspace: Path) -> list[PendingUpdate]: ...
```

`PendingUpdate` is a small frozen dataclass:

```python
@dataclass(frozen=True)
class PendingUpdate:
    plugin: str
    applied_version: str | None
    installed_version: str
```

| Call | Writes? | Returns | Used by |
|---|---|---|---|
| `init(..., version=v)` | Yes — sets both `installed_version=v` and `applied_version=v`. Idempotent: file unchanged if values match. | `None` | A plugin's own init/upgrade command, after its update logic has run. |
| `warn_if_stale(workspace, plugin, version)` | Yes — only when `applied_version != version` and not None: writes `installed_version=version`, leaves `applied_version` untouched. | `True` on mismatch, `False` otherwise. | Top of every user-facing plugin command. |
| `pending_updates(workspace)` | Never. Pure read. | List of `PendingUpdate` for plugins where `installed_version != applied_version` and `installed_version` is not None. | A future `/lattice:status` command (not built; see Open questions). |

Source authority: `packages/lattice-workspace/src/lattice_workspace/versions.py`, `init.py`.

## Lazy v1 → v2 coercion

`manifest.read` runs an in-memory `_coerce()` step on every read:

- Top-level `version: 1` (or missing): each bare-string plugin entry becomes `{"name": <s>, "installed_version": None, "applied_version": None}`. The in-memory `version` is promoted to `2`.
- Top-level `version: 2`: pass-through unchanged.

**The disk file is not rewritten by coercion.** Disk rewrite happens only when a real mutation occurs — a plugin runs `init` and bumps its versions, or `warn_if_stale` writes a new `installed_version`. At that point the file is rewritten in v2 form.

A workspace nobody touches stays on disk in v1 indefinitely. No spurious diffs for untouched repos; v1 readers stay supported indefinitely (the coercion logic is small).

A v1-coerced entry presents as `(plugin, applied_version=None, installed_version=None)`. Both `pending_updates` and `warn_if_stale` treat `applied_version=None` as "no signal yet" and short-circuit — first-time semantics, no banner, no write.

## Banner-not-auto-apply discipline

`warn_if_stale` returns `True`. That is the entire signal. **Each plugin owns its own banner copy and its own upgrade command.**

```python
from lattice_workspace import warn_if_stale
from lattice_wiki_core import __version__

if warn_if_stale(workspace, plugin="lattice-wiki", version=__version__):
    print("⚠ lattice-wiki updates available — run /wiki:init to apply")
```

This is the same surprise-avoidance principle that governs [[wiki/concepts/explicit-not-magic-update-lifecycle]]: surface staleness as a banner; never auto-apply at session start. Reasons carry over — surprise factor, ambiguity at the moment of invocation, and clean failure handling when the user can see what went wrong.

Inside the plugin's own init/upgrade command, the plugin runs its update logic *before* calling `workspace_init` so the version bump only happens on success:

```python
data = manifest.read(paths.manifest_path(workspace))
entry = next((p for p in data["plugins"] if p["name"] == "lattice-wiki"), None)
applied = entry.get("applied_version") if entry else None

if applied != __version__:
    run_plugin_update(workspace, from_version=applied, to_version=__version__)

workspace_init(repo_root, plugin="lattice-wiki", version=__version__)
```

## `installed_version` vs `applied_version`

Two fields, two writers, two meanings.

| Field | Set by | Set when | Means |
|---|---|---|---|
| `installed_version` | `warn_if_stale` (on mismatch) **and** `init` | Any user-facing command runs, or update completes | "Plugin code at this version was last seen here." |
| `applied_version` | `init` only | The plugin's update logic ran end-to-end against this workspace | "Workspace state matches what this version expects." |

The asymmetry is deliberate. `warn_if_stale` is allowed to bump `installed_version` because *running the plugin* is itself proof a particular version touched the workspace. `applied_version` only moves when the plugin explicitly says "I just finished migrating you" — i.e. when its init/upgrade command calls `workspace_init(..., version=...)`. The pending state — `installed != applied` — is the gap between "I saw this version" and "I migrated for it."

## PyYAML dependency

v0.3.0 swaps `manifest.py`'s hand-rolled YAML-subset reader for `pyyaml` (`>= 6.0`), exclusively `yaml.safe_load` and `yaml.safe_dump(..., sort_keys=False, default_flow_style=False)` — preserves key order, block style, no `!!python/...` tags.

> [!info] Trade-off accepted in v0.3.0
> The hand-rolled reader was sufficient for flat scalars and a flat string list. The v2 shape (nested dicts inside a list) pushes past what it can do without becoming a maintenance liability. PyYAML adds ~5 MB and a transitive dep to a previously dependency-free package; the parser-correctness win on a foundational shared package outweighs the install cost. lattice already pulls heavier deps elsewhere (`lattice-curator`, `lattice-wiki-agent`).

One small consequence: PyYAML parses bare ISO dates (e.g. `2026-05-09`) as `datetime.date`. `manifest.read` normalizes `initialized_at` back to `str` so callers see a stable type.

## Used in
- [[wiki/packages/lattice-workspace/lattice-workspace]] — owner of the manifest, the API, and the coercion step
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — reference integration: calls `warn_if_stale` at command entry; calls `init(..., version=__version__)` from its own init flow

## Related patterns
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — the parent principle: surface staleness, never auto-apply. This concept is the per-workspace analog for plugin code (vs. lattice-graph's per-repo analog for graph data).
- [[wiki/concepts/lattice-cross-plugin-contract]] — adds version tracking to the install/upgrade choreography section. `warn_if_stale` becomes the recommended top-of-command call alongside the existing env-var discovery and subprocess invocation conventions.
- [[wiki/concepts/per-repo-layout]] — `.lattice.yaml` lives at the workspace root this concept reads and writes.

## Decisions
- [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]]

## Sources
- `lattice/specs/2026-05-09-lattice-workspace-plugin-versions-design.md` — the design spec for v0.3.0

## Open questions / deferred
- A global `/lattice:status` command surfacing all plugins' pending updates across the workspace. The `pending_updates` API enables it; the command is not built.
- A `lattice-workflows` SessionStart hook that scans every installed plugin and prints aggregated banners. Same: enabled, not built.
- Migrating `lattice-graph`, `lattice-curator`, and `lattice-work` to use the new API. Until they do, their entries remain v1-coerced (versions `null`) and never trigger update banners — silent no-op, by design.
- Whether the auto-rendered plugin block in `<workspace>/CLAUDE.md` should surface version info (today: just names).
