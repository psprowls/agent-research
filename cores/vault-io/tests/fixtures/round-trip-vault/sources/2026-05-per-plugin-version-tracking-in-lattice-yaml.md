---
title: "Per-plugin version tracking in `.lattice.yaml`"
category: source
summary: Spec proposing per-plugin `installed_version`/`applied_version` tracking in `.lattice.yaml`, a v1→v2 manifest schema bump with lazy in-memory coercion, a PyYAML swap, and a `warn_if_stale` / `pending_updates` API on `lattice-workspace` so each plugin can detect and surface its own staleness without forcing a global update orchestrator.
source_path: lattice/specs/2026-05-09-lattice-workspace-plugin-versions-design.md
source_type: spec
source_date: 2026-05-09
authors: [Patrick Sprowls]
ingested: 2026-05-09
updated: 2026-05-09
tokens: 2293
---

# Per-plugin version tracking in `.lattice.yaml`

## TL;DR

This spec adds **per-plugin version tracking** to `.lattice.yaml` so each plugin can detect when its own installed version has drifted from the version that last applied changes to the workspace. It bumps the manifest schema 1→2 (plugins go from `list[str]` to `list[{name, installed_version, applied_version}]`), introduces `warn_if_stale` and `pending_updates` helpers on [[wiki/packages/lattice-workspace/lattice-workspace]], makes `version=` a required keyword on `init()`, and swaps the hand-rolled YAML parser for PyYAML.

## Key claims

1. **Manifest schema bumps 1→2.** Plugins entries become dicts: `{name, installed_version, applied_version}`. Top-level `version: 2` marks the format. (`spec §1`)
2. **Update-pending predicate.** `installed_version is not None and installed_version != applied_version`. v1-coerced entries (both `None`) never produce a pending signal until a plugin first runs against them. (`spec §1`)
3. **Three API functions.** `init()` (existing, gains required `version=` kwarg) writes both versions together; `warn_if_stale(workspace, *, plugin, version) -> bool` is a check that *also writes* `installed_version` on mismatch; `pending_updates(workspace) -> list[PendingUpdate]` is pure read. (`spec §2`)
4. **Required `version=` on `init()` is a breaking API change.** All in-tree call sites are migrated in this spec; external callers fail loudly with `TypeError`. (`spec §2`, `§6`)
5. **Parser switches to PyYAML.** `manifest.read` → `yaml.safe_load`; `manifest.write` → `yaml.safe_dump(sort_keys=False, default_flow_style=False)`. Adds `pyyaml >= 6.0` to runtime deps — explicitly trades away the package's prior "stdlib-only" posture. (`spec §3`, `§Risks`)
6. **Lazy backward compatibility.** A `_coerce()` step promotes v1 → v2 in memory on every read but **never rewrites the file on disk** until a real mutation occurs (a plugin runs `init` or `warn_if_stale` writes a new `installed_version`). Untouched workspaces stay v1 indefinitely. (`spec §5`)
7. **Plugin integrates at two seams.** (a) `warn_if_stale` at command entry to surface a banner; (b) inside the plugin's own init flow: read manifest → run plugin-specific update logic → call `init(..., version=__version__)`. The plugin owns banner copy and update semantics; `lattice-workspace` only signals. (`spec §4`)

## Implementation status

**Already shipped in `lattice-workspace` v0.3.0** — even though the spec frontmatter still reads `status: draft`. Concrete evidence in code:

- `packages/lattice-workspace/pyproject.toml:9` — `dependencies = ["pyyaml>=6.0"]`
- `packages/lattice-workspace/src/lattice_workspace/manifest.py` — uses `yaml.safe_load` / `yaml.safe_dump`; `_coerce()` promotes v1→v2 in memory at lines 9-31
- `packages/lattice-workspace/src/lattice_workspace/init.py:22-28` — `init()` now takes a required `version=` kwarg and writes both `installed_version` and `applied_version` (lines 50-65)
- `packages/lattice-workspace/src/lattice_workspace/versions.py` — `warn_if_stale` and `pending_updates` plus the `PendingUpdate` frozen dataclass
- `packages/lattice-wiki-core/src/lattice_wiki_core/_version_check.py` — reference plugin integration; called from `scan_monorepo`, `lint_wiki`, `ingest_source`, `wiki_search`, `append_log` entry points
- Tests: `test_manifest_v1_read.py`, `test_manifest_v2_roundtrip.py`, `test_init_records_version.py`, `test_init_bumps_version.py`, `test_warn_if_stale.py`, `test_pending_updates.py` all present in `packages/lattice-workspace/tests/`

## Proposed changes

- `packages/lattice-workspace/pyproject.toml` — add `pyyaml >= 6.0` to runtime deps. ✅ shipped
- `packages/lattice-workspace/src/lattice_workspace/manifest.py` — PyYAML, `_coerce()`, v2 read/write. ✅ shipped
- `packages/lattice-workspace/src/lattice_workspace/init.py` — `version=` kwarg; record both versions. ✅ shipped
- `packages/lattice-workspace/src/lattice_workspace/versions.py` — new module with `warn_if_stale`, `pending_updates`, `PendingUpdate`. ✅ shipped
- `packages/lattice-workspace/src/lattice_workspace/render.py` — iterate plugin entries as dicts. ✅ shipped
- `packages/lattice-wiki-core/src/lattice_wiki_core/_version_check.py` — reference integration. ✅ shipped

## Evidence / rationale

- **Why per-plugin, not per-workspace.** Different plugins ship updates at different cadences; a workspace can be "fresh enough" for one plugin and stale for another. Per-plugin tracking lets each plugin's own command entry surface its own banner without needing a global orchestrator.
- **Why lazy coercion (not eager rewrite).** A workspace nobody touches shouldn't show up in `git diff` after an unrelated tool runs. Coercion happens on read; rewrite happens only when a real mutation needs to land. Cost: v1 reader code lives forever — accepted because it's small (~25 lines).
- **Why `warn_if_stale` writes during a check.** Naming is mildly surprising, but the alternative (a separate "record install" call every plugin must remember to make) is worse — it's the kind of thing that goes wrong silently. The function records `installed_version` so `pending_updates` has something to compare against on the next read.
- **Why PyYAML on a foundational package.** v2's nested dict-inside-list shape pushes past what the hand-rolled flat parser can do without becoming a maintenance liability. The "stdlib-only" constraint was a defensive default, not a goal — accepted trade-off given parser correctness on the bottom-tier shared package.

## Surprises / contradictions

> [!warning] Wiki↔code drift discovered while ingesting
> Two `lattice-workspace` sub-pages were stale and have been updated as part of this ingest:
>
> - [[wiki/packages/lattice-workspace/api]] — described `init(repo_root, *, plugin, workspace=None)` and a hand-rolled YAML parser; both contradicted `packages/lattice-workspace/src/lattice_workspace/init.py:22` and `manifest.py`. Now updated to describe the v0.3.0 surface (required `version=`, PyYAML, `warn_if_stale`, `pending_updates`, `PendingUpdate`).
> - [[wiki/packages/lattice-workspace/patterns]] — claimed `dependencies = []` in `pyproject.toml` and showed a v1 manifest example. Both contradicted `packages/lattice-workspace/pyproject.toml:9` and the v2 schema. Now updated.
>
> The package overview ([[wiki/packages/lattice-workspace/lattice-workspace]]) was already accurate.

- Spec frontmatter says `status: draft` but the design is shipped. The spec doc is being treated as a historical design record, not a forward-looking proposal.
- Spec §5 says "v1-coerced entries present as `(plugin, applied_version=None, installed_version=None)`" and `pending_updates` excludes them — this matches the `versions.py:51-53` implementation. `warn_if_stale` short-circuits when `applied_version is None` (`versions.py:34`), which is consistent with spec §5's "first-time semantics, returns False, does not write."
- Spec §8 says the renderer change is name-only; `<workspace>/CLAUDE.md` continues to render just plugin names. The rendered block at `lattice/CLAUDE.md` confirms this — only `name` is surfaced, no version info.

## Touches

- [[wiki/packages/lattice-workspace/lattice-workspace]] — added to `## Sources`
- [[wiki/packages/lattice-workspace/api]] — major rewrite: v2 manifest, `version=` kwarg, `warn_if_stale`, `pending_updates`
- [[wiki/packages/lattice-workspace/patterns]] — v2 manifest example, PyYAML dep, version-aware idempotent init
- [[wiki/packages/lattice-workspace/context]] — sources section, ADR reference
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]] — sources reference (reference integration via `_version_check.py`)
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — sources reference (consumer of `warn_if_stale` at command entry)
- [[wiki/concepts/lattice-cross-plugin-contract]] — new section on per-plugin version tracking
- [[wiki/concepts/explicit-not-magic-update-lifecycle]] — new section on the per-plugin staleness banner pattern

## Decisions triggered

- [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]]

## Where it's cited in this wiki

- [[wiki/packages/lattice-workspace/lattice-workspace]]
- [[wiki/packages/lattice-workspace/api]]
- [[wiki/packages/lattice-workspace/patterns]]
- [[wiki/packages/lattice-workspace/context]]
- [[wiki/packages/lattice-wiki-core/lattice-wiki-core]]
- [[wiki/plugins/lattice-wiki/lattice-wiki]]
- [[wiki/concepts/lattice-cross-plugin-contract]]
- [[wiki/concepts/explicit-not-magic-update-lifecycle]]
- [[wiki/adrs/0014-per-plugin-version-tracking-in-lattice-yaml]]
