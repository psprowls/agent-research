---
title: Per-repo directory layout
category: concept
summary: Each consumer repo gets a single `<repo>/lattice/` workspace root containing the vault, work items, and (gitignored) machine state. The Obsidian vault opens at the workspace root, so wikilinks are workspace-root-relative.
tags: [layout, ecosystem, conventions]
sources: 1
updated: 2026-05-09
tokens: 1583
---

# Per-repo directory layout

## Definition
The `lattice-*` ecosystem occupies a single configurable workspace root inside any consumer repo. The default workspace name is `lattice` (`DEFAULT_WORKSPACE_NAME` in `packages/lattice-workspace/src/lattice_workspace/config.py`). All per-repo data lives under this root:

- `<workspace>/wiki/` — the [[wiki/plugins/lattice-wiki/lattice-wiki]] vault. Human-visible. Committed to git.
- `<workspace>/work/` — work items (bugs, features, spikes). Committed to git.
- `<workspace>/.graph/` — machine state for [[wiki/plugins/lattice-graph/lattice-graph]]. Gitignored.

The workspace path is resolved by `lattice_workspace.config.resolve()`: it walks up from cwd to find `.git`, then checks `.lattice.local.yaml` for a `lattice-directory` override; if absent it defaults to `<repo>/lattice`. The resolved workspace is then passed to path accessors in `packages/lattice-workspace/src/lattice_workspace/paths.py`.

> [!note] ADR-0011 records the consolidation to a single workspace root
> An earlier decision proposed two distinct roots (`<repo>/wiki/` + `<repo>/.lattice/`). The implementation consolidated to a single workspace root. [[wiki/adrs/0011-single-workspace-root]] documents this decision.

## Motivation
- All per-repo lattice data lives under one named root, making it easy to find, move, or exclude from non-lattice tooling.
- Human-visible content (`wiki/`, `work/`) is committed alongside code; machine state (`.graph/code.db`) is gitignored.
- The workspace root is configurable via `.lattice.local.yaml`; the default `lattice/` is short and unambiguous.

## Shape

```
<repo>/
└── lattice/                    # workspace root (configurable; default "lattice"); Obsidian opens here
    ├── CLAUDE.md               #   workspace-level schema (owned by lattice-workspace)
    ├── .lattice.yaml           #   workspace manifest
    ├── raw/                    #   immutable ingested sources (sibling of wiki/)
    ├── work/                   #   work items — committed (sibling of wiki/)
    ├── knowledge/              #   other plugin-managed knowledge stores
    ├── wiki/                   #   lattice-wiki curated pages — committed
    │   ├── CLAUDE.md           #     wiki-specific schema (Claude Code)
    │   └── AGENTS.md           #     wiki-specific schema (Codex/Cursor/etc.)
    └── .graph/                 #   lattice-graph machine state — gitignored
        └── code.db             #     SQLite store
```

Source authority: `packages/lattice-workspace/src/lattice_workspace/paths.py` and `config.py`.

## Wikilink form follows from this layout

Because the Obsidian vault opens at `<workspace>/`, wikilinks resolve **workspace-root-relative**:

| Target | Wikilink |
|---|---|
| Wiki page | `[[wiki/<category>/...]]` — e.g. `[[wiki/packages/foo/foo]]`, `[[wiki/concepts/bar]]` |
| Work item | `[[work/<slug>]]` |
| Sibling resource | `[[raw/...]]`, `[[knowledge/...]]` (resolvable but not structurally linted) |

==Forbidden:== `[[../work/...]]` (the `../` escapes the vault), bare `[[packages/...]]` / `[[concepts/...]]` (only resolves if the vault opened one level deeper).

See [[wiki/adrs/0015-workspace-root-wikilink-form]] and [[wiki/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]] for the linter alignment that enforces these forms.

## Used in
- [[wiki/plugins/lattice-wiki/lattice-wiki]] — owns `<workspace>/wiki/`
- [[wiki/plugins/lattice-graph/lattice-graph]] — owns `<workspace>/.graph/code.db`
- [[wiki/plugins/lattice-work/lattice-work]] — work items live at `<workspace>/work/`

## Related patterns
- [[wiki/concepts/lattice-naming-convention]] — naming applies to plugins, not directories.

## Path ownership across the ecosystem

| Path | Owner | Other plugins' access |
|---|---|---|
| `<workspace>/wiki/` | lattice-wiki | read-only by all peers |
| `<workspace>/work/*.md` | lattice-workspace (schema) | lattice-work reads (lifecycle lint, sidecar regen); humans + ingestor write |
| `<workspace>/work-index.json` | lattice-work | read by lattice-workflows, lattice-experts |
| `<workspace>/wiki/log.md`, `<workspace>/wiki/index.md` | lattice-wiki | read by all |
| `<workspace>/.graph/code.db` | lattice-graph | read-only by all peers via MCP / CLI |

### Why graph DB lives at `<workspace>/.graph/`, NOT inside `<workspace>/wiki/`

Graph machine state is separated from the human-visible vault. Reasons:

1. **Path-ownership cleanliness.** lattice-wiki owns `<workspace>/wiki/`; another plugin's data inside crosses the boundary.
2. **Graph independence.** A user might run lattice-graph against an undocumented codebase (no wiki). Forcing a wiki subdirectory would make wiki a hard dep where it shouldn't be.
3. **Gitignore simplicity.** The `.graph/` subtree is gitignored wholesale; the `wiki/` subtree is committed wholesale. Mixing them inside one directory complicates both.

The exception: `work-index.json` lives at `<workspace>/work-index.json` (alongside the `work/` items it summarizes), even though it's machine-generated — same logic as `wiki/index.md`. Sidecars humans want to see live with the data they describe; pure machine state lives at `<workspace>/.graph/`.

## `.gitignore` conventions

`lattice-graph` adds these to `<workspace>/.graph/.gitignore` on first `cg update`:

```
code.db
code.db-wal
code.db-shm
```

NOT gitignored: `<workspace>/wiki/` (everything in it), `<workspace>/work/`, `<workspace>/work-index.json`, `<workspace>/wiki/log.md`, `<workspace>/.lattice.yaml`.

## Decisions
- [[wiki/adrs/0011-single-workspace-root]] — consolidation to single root
- [[wiki/adrs/0015-workspace-root-wikilink-form]] — canonical wikilink forms that follow from this layout

## Related concepts
- [[wiki/concepts/lattice-cross-plugin-contract]] — env-var discovery, subprocess invocation, idempotency

## Open questions / gotchas
- `<workspace>/.graph/` is gitignored at v1; v2 deployment option per [[wiki/adrs/0001-sqlite-primary-store-for-code-graph]] commits a CI-built graph as a release artifact.
