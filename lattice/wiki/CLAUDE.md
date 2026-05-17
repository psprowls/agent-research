# wiki — Code Wiki

> **Topic:** deep-agents monorepo — LangChain/deepagents wiki agent on AWS Bedrock
> **Repo:** /Users/pat/Personal/deep-agents
> **Initialized:** 2026-05-14
> **Tool:** Claude Code (this file).

You are the maintainer of this wiki. You read from `../raw/` (immutable ingested sources, owned by `lattice-workspace`) and from the repo's source code. You write to pages under this wiki directory. You never edit `../raw/` and you never edit code through this skill.

## Where the wiki sits

This wiki is a sibling of other workspace-level directories. Obsidian opens at the workspace root, so the sidebar shows them all together:

```
<workspace>/                  → e.g. <repo>/lattice/. Obsidian vault opens here.
├── .lattice.yaml             → workspace manifest (owned by lattice-workspace)
├── CLAUDE.md                 → workspace-level schema (owned by lattice-workspace)
├── raw/                      → ingested sources. IMMUTABLE. Owned by lattice-workspace.
├── work/                     → unified bug / tech-debt / feature / initiative / spike tracker. Owned by lattice-workspace.
├── knowledge/                → other plugin-managed knowledge stores
└── wiki/                     → this wiki — you own everything here
    ├── CLAUDE.md             → this file
    └── …                     → curated pages described below
```

When this file says "wiki root" it means the directory containing this `CLAUDE.md` (i.e. `<workspace>/wiki/`). Paths below are written relative to the wiki root unless prefixed with `../`.

## Wiki structure

```
index.md                  → content catalog — update every scan/ingest
log.md                    → append-only timeline
apps/                     → [conditional] one folder per application workspace
└── <app>/
    └── <app>.md          →   the app overview (category: app)
packages/                 → [conditional] cross-domain library/service packages
└── <pkg>/
    └── <pkg>.md          →   the package overview (category: package)
domains/                  → [conditional] feature areas across packages
└── <domain>/
    ├── <domain>.md       →   the domain overview (category: domain)
    └── packages/         →   the domain's workspace packages
        └── <pkg>/
            └── <pkg>.md
concepts/                 → cross-cutting technical concepts
dependencies/             → external libraries (index.md auto-generated)
sources/                  → one summary per ingested source (cites files in ../raw/)
architecture/             → high-level syntheses
adrs/                     → architecture decision records
.templates/               → page templates (reference only)
```

Work items live at `../work/` (sibling of this wiki, owned by `lattice-workspace`). Reference them from wiki pages with wikilinks like `[[work/2026-04-21-flaky-healthkit-tests]]`.

## Page frontmatter (required on every wiki page)

```yaml
---
title: <Title>
category: app | package | domain | concept | dependency | work | source | architecture | adr
summary: <one-line summary>
tags: [tag1, tag2]
updated: YYYY-MM-DD
---
```

Each category has additional required fields — see `<skill>/references/page-formats.md`.

## The four operations

### Scan (`/lattice-wiki:scan`)

1. Run `python <skill>/scripts/scan_monorepo.py --json` (workspace and repo discovered automatically)
2. Present the diff to the user — new / renamed / deleted packages
3. Wait for confirmation on renames and deletions
4. Create stub `packages/<name>/<name>.md` pages for new packages (one folder per package)
5. Update frontmatter (`exports`, `depends_on`, `depended_on_by`) on existing pages
6. Update `index.md` and append a `scan` log entry

### Ingest (`/lattice-wiki:ingest <path>`)

Sources may live under `../raw/<...>` (clipped articles, specs, PRs, transcripts you've staged) **or** in the repo itself as `.md` design docs (e.g. `docs/architecture.md`). Surfaced by `/lattice-wiki:scan` for any pinned `docs` container; pass the repo-relative path straight to `/lattice-wiki:ingest`. PDF/DOCX support is deferred — md only for now.

1. Run `ingest_source.py --source <path>` (wiki and repo discovered automatically)
2. Read the source directly
3. **Discuss with the user first** — TL;DR, key claims, which packages/domains/concepts will be touched, any contradictions with code
4. Wait for confirmation
5. Create/merge the summary page at `sources/<YYYY-MM>-<slug>.md`. For in-repo docs, record `last_sync_commit` and `last_sync_at` in frontmatter so lint can flag staleness later
6. Update every relevant package/domain/concept page (typically 5-15 pages)
7. If the source represents a decision, propose an ADR
8. Flag contradictions with `> ⚠️ Contradiction:` callouts (on wiki pages and/or noting code paths)
9. Update `index.md` and append an `ingest` log entry
10. Report touched pages as wikilinks

### Query (`/lattice-wiki:query <question>`)

1. Read `index.md` first
2. Pick 3-10 relevant pages across categories (architecture + packages + concepts + sources + adrs)
3. Read them in full
4. Follow wikilinks opportunistically
5. Fall back to `wiki_search.py --query <terms>` or read code directly if the wiki doesn't cover it
6. Synthesize: direct answer → supporting detail → inline `[[wikilinks]]` + `` `code-paths:line` `` → "Related pages" section
7. **Offer to file the answer back** as a new page (concept/architecture/adr — comparisons live as `concepts/<a>-vs-<b>.md`)

### Lint (`/lattice-wiki:lint`)

1. Run `python <skill>/scripts/lint_wiki.py` for mechanical checks **including code drift** (workspace and repo discovered automatically)
2. Run `graph_analyzer.py` for structural stats
3. Semantic checks: contradictions (wiki↔wiki and wiki↔code), stale claims, concept gaps, stale work items (`../work/` items past their target date), ADR chain health
4. Present findings as a markdown report with suggested actions
5. Append a `lint` entry to `log.md`

## Iron rules

1. **The code is the source of truth.** If the wiki and the code disagree, update the wiki — never the other way around.
2. **`../raw/` is immutable.** You read from it; you never write to it.
3. **All wiki writes go under this wiki directory.** Work items go to `../work/` (owned by `lattice-workspace`). No exceptions.
4. **Every wiki page has YAML frontmatter** with `title`, `category`, `summary`, `updated`.
5. **Every scan/ingest touches ≥3 files:** the changed/new page(s), `index.md`, `log.md`.
6. **Every claim cites** — either a wiki page (`[[sources/xxx]]`) or a code path (`` `packages/foo/src/bar.ts:42` ``).
7. **Contradictions get flagged inline** — on both the wiki page and noting the code path.
8. **Good query answers get filed back.** Explorations compound.

## Log format

```
## [YYYY-MM-DD] <op> | <title>
<optional detail — which pages touched, what changed>
```

Valid ops: `scan`, `ingest`, `query`, `lint`, `create`, `update`, `delete`, `note`.

Grep the log: `grep "^## \[" log.md | tail -10`

## Tools

All scripts live at `${CLAUDE_PLUGIN_ROOT}/skills/lattice-wiki/scripts/` (or wherever the plugin is installed). Standard library only.

- `init_vault.py` — bootstrap a wiki
- `scan_monorepo.py` — detect packages, emit diff
- `ingest_source.py` — prep a source for ingest (metadata + preview)
- `update_index.py` — regenerate `index.md`
- `append_log.py` — append a standardized log entry
- `wiki_search.py` — BM25 search fallback
- `lint_wiki.py` — mechanical health check + code-drift
- `graph_analyzer.py` — link graph stats
- `export_marp.py` — render a page as a Marp slide deck

## Obsidian

Open `<workspace>/` (one level up from this wiki) in Obsidian — the sidebar will show `wiki/`, `raw/`, `work/`, etc. as siblings. Useful plugins: Graph view, Backlinks, Dataview, Marp, Templates, Git.

## Style

- Be concise. Wiki pages are read, not generated.
- Prefer short paragraphs. Bulleted lists where appropriate.
- Cite aggressively with `[[wikilinks]]` and `` `code-paths:line` ``.
- When you're not sure, say so in the page. Don't invent content.
- Update `updated:` frontmatter whenever you touch a page.

<!-- lattice-wiki:layout:start -->
```yaml
version: 1
detected_at: 2026-05-14
repo_root: ..
containers:
  - source: agents
    vault_dir: agents
    classification: package
    children_count: 1
  - source: packages
    vault_dir: packages
    classification: package
    children_count: 4
  - source: eval
    vault_dir: null
    classification: skip
    children_count: 2
  - source: lattice
    vault_dir: null
    classification: skip
    children_count: 3
  - source: scripts
    vault_dir: null
    classification: skip
    children_count: 0
  - source: test-out
    vault_dir: null
    classification: skip
    children_count: 0
```
<!-- lattice-wiki:layout:end -->
