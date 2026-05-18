# Source: packages/prompt-sources/SKILL.md
# Anchor: ## Architecture (L34-L69)
# Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030

ARCHITECTURE_OVERVIEW = """\
## Vault layout

The wiki lives at `<workspace>/wiki/`. `raw/` (immutable ingested sources) and `work/` (unified work tracker) are siblings of `wiki/`, owned by `graph-wiki workspace` — not by this agent.

```
<repo>/graph-wiki/              # workspace; Obsidian vault opens here
├── raw/                        # IMMUTABLE ingested sources (articles, specs, prs, tickets, transcripts, assets)
├── work/                       # unified bugs / tech debt / features / initiatives / spikes
└── wiki/                       # this agent's curated knowledge base
    ├── index.md                # Content catalog (updated every ingest/scan)
    ├── log.md                  # Append-only timeline
    ├── apps/<app>/             # [conditional] One folder per app workspace; overview at apps/<app>/<app>.md
    ├── packages/<pkg>/         # [conditional] One folder per library/service package; overview at packages/<pkg>/<pkg>.md
    ├── domains/<domain>/       # [conditional] One folder per cross-package feature area; overview at domains/<domain>/<domain>.md
    ├── concepts/               # Cross-cutting technical concepts (auth, testing patterns, comparisons)
    ├── dependencies/           # External libraries — index.md auto-generated; detail pages opt-in
    ├── sources/                # One summary page per ingested source (cites files in <workspace>/raw/)
    ├── architecture/           # High-level architecture syntheses
    ├── adrs/                   # Architecture Decision Records
    ├── .templates/             # Page templates (reference only, not indexed)
    ├── CLAUDE.md               # wiki schema + conventions (Claude Code)
    └── AGENTS.md               # same content for Codex/Cursor/Antigravity/OpenCode
```

`apps/`, `packages/`, and `domains/` are **conditional** — created only when the repo has matching containers. A single-package repo has none; a library-only monorepo has `packages/` but no `apps/`. Pinned containers are recorded in `<workspace>/wiki/CLAUDE.md` and `<workspace>/wiki/AGENTS.md`.

**The code is the source of truth.** The wiki is a compiled layer above it. If the wiki disagrees with the code, the code wins — the wiki gets updated.\
"""
