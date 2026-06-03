# Source: plugins/graph-wiki/skills/graph-wiki/SKILL.md §Architecture

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
    ├── concepts/               # Cross-cutting technical concepts (auth, testing patterns, comparisons)
    ├── entities/               # One page per graph-derived entity (repositories, domains, packages, apps, dependencies, test suites) as <prefix>_<name>.md
    ├── sources/                # One summary page per ingested source (cites files in <workspace>/raw/)
    ├── architecture/           # High-level architecture syntheses
    ├── adrs/                   # Architecture Decision Records
    ├── .templates/             # Page templates (reference only, not indexed)
    ├── CLAUDE.md               # wiki schema + conventions (Claude Code)
    └── AGENTS.md               # same content for Codex/Cursor/Antigravity/OpenCode
```

**The code is the source of truth.** The wiki is a compiled layer above it. If the wiki disagrees with the code, the code wins — the wiki gets updated.\
"""
