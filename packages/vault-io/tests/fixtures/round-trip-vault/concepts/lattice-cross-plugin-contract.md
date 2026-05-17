---
title: Lattice cross-plugin contract
category: concept
summary: How lattice plugins find each other, invoke each other, and degrade gracefully — `${LATTICE_<NAME>_ROOT}` env-var discovery, subprocess-not-import, JSON-to-stdout, idempotent scripts, exit-code conventions, optionality matrix.
tags: [architecture, contracts, ecosystem, env-vars, subprocess, install, gitignore]
sources: 1
updated: 2026-05-09
tokens: 2394
---

# Lattice cross-plugin contract

## Definition
The conventions that govern how plugins in the `lattice-*` ecosystem discover each other, invoke each other's scripts, and compose at install/upgrade time. The contract is **discoverable through env vars, executed through subprocess, and silent when peers are absent** (with one explicit hard-dep exception).

## Workspace resolution via subprocess

A second discovery channel sits beside the env-var convention: any consumer can resolve the lattice workspace by shelling out to `python -m lattice_workspace.config`, which prints the resolved workspace path and exits 0 (see [[wiki/packages/lattice-workspace/lattice-workspace]]). [[wiki/plugins/lattice-workflows/lattice-workflows]]'s `brainstorming` and `writing-plans` skills use this entry point — falling back to `Path("lattice").resolve()` when the call fails — and then assert `<workspace>/.lattice.yaml` exists before writing into `<workspace>/{specs,plans}/` (per [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]]). This honors the "subprocess, not import" rule while keeping the resolution logic single-sourced inside `lattice-workspace`.

## Discovery — `${LATTICE_<NAME>_ROOT}` env vars

Each plugin's manifest sets its own lattice-named env var on activation (layered on top of `${CLAUDE_PLUGIN_ROOT}`):

| Plugin | Env var |
|---|---|
| lattice-wiki | `${LATTICE_WIKI_ROOT}` |
| lattice-graph | `${LATTICE_GRAPH_ROOT}` |
| lattice-work | `${LATTICE_WORK_ROOT}` |
| lattice-workflows | `${LATTICE_WORKFLOWS_ROOT}` |
| lattice-experts | `${LATTICE_EXPERTS_ROOT}` |

Consumer plugins detect peers by checking var presence:

```python
if (graph_root := os.environ.get("LATTICE_GRAPH_ROOT")):
    use_graph(graph_root)
else:
    fall_back_to_filesystem()
```

Why named env vars instead of filesystem walking: explicit, debuggable, no plugin-discovery code to maintain. The marketplace tells Claude Code about installed plugins; the plugin tells the ecosystem about its root.

## Predictable per-plugin layout

Plugins ship with a stable directory structure so consumers can address entry points:

```
<plugin>/
├── .claude-plugin/plugin.json    # manifest; sets the env var
├── lib/                          # library boundary (per §3.1)
├── cli/                          # CLI entry points
├── scripts/                      # invokable, cross-plugin-callable
├── skills/                       # skill content
├── agents/                       # subagent definitions
└── commands/                     # slash command definitions
```

A consumer invokes:

```python
subprocess.run(
    ["python3",
     f"{work_tracker_root}/scripts/regenerate_work_index.py",
     "--vault", vault_path],
    check=True,
)
```

## Invocation conventions

| Convention | Rule |
|---|---|
| **Subprocess, not import** | Plugins evolve independently; Python imports couple them implicitly. |
| **JSON to stdout** | Caller parses; no shared serialization library. |
| **Exit codes** | `0` success · `2` invalid args · `3` runtime error · `4` missing dependency |
| **No assumed cwd** | Scripts accept absolute paths via `--vault` / `--repo`; never `os.getcwd()`. |
| **Idempotent** | Same args → same result. Sidecar regen, lint, etc. all idempotent. **Migrations are the explicit exception** — named `migrate_<from>_to_<to>.py` to signal one-shot. |

## Optionality matrix

Exactly one hard dep in the ecosystem. Everything else is graceful degradation, with a one-line banner at first invocation when a soft-dep peer is missing.

| Plugin | Hard deps | Soft deps |
|---|---|---|
| `lattice-wiki` | none | graph (citation lint); work-tracker (sidecar regen on ingest) |
| `lattice-graph` | none | wiki (consumer lights up when present) |
| **`lattice-work`** | **wiki** (vault must exist) | graph (richer `affects:` resolution); workflow |
| `lattice-workflows` | none | wiki, graph, work-tracker |
| `lattice-experts` | none | workflow, graph |

The hard dep: work data lives inside the wiki vault; without the vault directory there's nothing to lint against. Runtime check at startup; error points at `/lattice-wiki:init`. There is no `dependencies:` field in `marketplace.json` to enforce it (confirmed against `.claude-plugin/marketplace.json` which carries only `name`, `source`, `description`).

## Install / upgrade choreography

### Logical install order

Not enforced; documented in each plugin's README:

1. lattice-wiki — creates `<repo>/lattice/wiki/`, pins `CLAUDE.md`/`AGENTS.md`, generates the schema reference.
2. lattice-graph — creates `<repo>/lattice/.graph/`, runs initial full build.
3. lattice-work — no per-repo init; runs lint and regen against the vault.
4. lattice-workflows — global install; reads peers when present.
5. lattice-experts — global install; consumed by workflow.

A user can install in any order; plugins check peer state at runtime and emit warnings (never errors, except the work-tracker hard dep).

### Init commands

| Plugin | First-time command |
|---|---|
| lattice-wiki | `/lattice-wiki:init` (idempotent; won't overwrite existing vault) |
| lattice-graph | `/lattice-graph:update --full` (creates `<repo>/lattice/.graph/code.db`) |
| lattice-work | `/lattice-work:lint` (emits `sidecar-missing` first time, prompting `regen-index`) |
| lattice-workflows | none — global activation |
| lattice-experts | none — global activation |

### Schema upgrades

- Migrators at `<plugin>/scripts/migrate_<from>_to_<to>.py`. One-shot transformations from `schema_version` N to N+1.
- Plugin's startup checks the existing data's `schema_version` and prompts the user to run the migrator if behind.
- Migrators are explicit user actions. Same reasoning as [[wiki/concepts/explicit-not-magic-update-lifecycle]] — surprise factor.

### Compatibility matrix per README

```
# lattice-work README
## Compatibility
- Requires: lattice-wiki >= 2.0.0 (work/ namespace)
- Optional: lattice-graph >= 1.0.0 (richer affects: resolution)
```

Versioning:
- **Major** — schema-breaking; requires migrator.
- **Minor** — additive (new fields, slash commands, lint rules). Backwards-compatible.
- **Patch** — bugfixes only.

Per-plugin `installed_version` and `applied_version` are tracked in `.lattice.yaml` (manifest schema v2) so each plugin can detect "the workspace is behind this plugin code" at command entry. See [[wiki/concepts/plugin-versioning-and-update-mechanism]] — the `warn_if_stale` / `pending_updates` / `init(version=)` API in `lattice-workspace` is the recommended top-of-command call alongside the env-var discovery above.

## `.gitignore` conventions

`lattice-wiki:init` adds these to the repo's `.gitignore` if absent:

```
# Lattice ecosystem
lattice/.graph/code.db
lattice/.graph/code.db-wal
lattice/.graph/code.db-shm
lattice/*/transient/
```

**Committed** (NOT gitignored):
- `<vault>/` and everything in it — committed (markdown vault is human-visible source-of-truth).
- `<vault>/work-index.json` — sidecar lives with the data it summarizes.
- `<vault>/log.md` — committed.
- `lattice/.lattice.yaml` — committed (when it lands; per-repo config the team shares).

The graph DB itself is gitignored at v1; v2's CI-built-graph option may flip this with explicit configuration.

## Used in
- [[wiki/plugins/lattice-wiki/lattice-wiki]]
- [[wiki/plugins/lattice-graph/lattice-graph]]
- [[wiki/plugins/lattice-work/lattice-work]]
- [[wiki/plugins/lattice-workflows/lattice-workflows]]

## Related patterns
- [[wiki/concepts/per-repo-layout]] — the single `<repo>/lattice/` workspace root this contract sits on top of
- [[wiki/concepts/lattice-workflows-observability-gate]] — sibling env-var convention: `LATTICE_<PLUGIN_UPPER>_OBSERVABILITY` gates a hook category instead of identifying a plugin's install root. First adopter is `plugins/lattice-workflows/hooks/log-skill-invocation`.
- [[wiki/concepts/plugin-versioning-and-update-mechanism]] — per-plugin version tracking in `.lattice.yaml` v2 + the `warn_if_stale` / `pending_updates` / `init(version=)` API in `lattice-workspace` (v0.3.0).

## Decisions
- [[wiki/adrs/0011-single-workspace-root]] — the single `<repo>/lattice/` workspace root
- [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]] — adds `python -m lattice_workspace.config` as a workflow-side adopter of subprocess-based resolution

## Sources
- [[wiki/sources/2026-05-plans-specs-path-redesign]] — concrete adopter: brainstorming + writing-plans skills resolve via subprocess CLI, hard-fail on missing `.lattice.yaml`
- [[wiki/sources/2026-05-per-plugin-version-tracking-in-lattice-yaml]] — adds per-plugin `installed_version` / `applied_version` to the install/upgrade choreography section. `warn_if_stale` is the recommended top-of-command call alongside the env-var discovery convention; `lattice-wiki` is the reference adopter, `lattice-graph` / `lattice-curator` / `lattice-work` are follow-ups.

## Open questions / deferred to v2
- Hard plugin dependencies in `marketplace.json` (today: runtime check + helpful error).
- Auto-discovery of peers via marketplace API (today: env vars).
- CI-built graph snapshot per [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]] — flips graph DB from gitignored to committed.
- `<repo>/.lattice/config.yaml` for ecosystem-wide settings.
- Multi-repo aggregation across workspaces.
- `/lattice:status` cross-plugin telemetry command.
