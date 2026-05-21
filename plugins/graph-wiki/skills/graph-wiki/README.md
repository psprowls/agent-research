# graph-wiki

> **Maintained documentation for a source code repository — single package, monorepo, or hybrid.**
> An adaptation of the [wiki](../wiki) skill, which itself implements [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). Port of upstream `lattice-wiki` targeting the deep-agents `vault-io`/`workspace-io` surface.

Turn any LLM CLI into a disciplined wiki maintainer for your repo. graph-wiki detects the repo's top-level shape — single package, workspace-style monorepo (Turborepo / pnpm / Nx / Bazel / Cargo / Go workspaces), or a hybrid — and adapts the vault layout to match. The chosen layout is pinned to `<workspace>/wiki/CLAUDE.md` and `<workspace>/wiki/AGENTS.md` so the LLM knows what containers exist. The LLM walks your code, produces a page per package (or per module/area in single-package repos), cross-references domains and concepts, ingests specs and articles and PRs, and keeps everything current as the code evolves.

## When to use

- Single-package libraries or services
- Monorepos (Turborepo, pnpm workspaces, Nx, Cargo workspaces, Go workspaces)
- Hybrid repos (a primary app plus loose internal libs, or mixed-language trees)
- Any repo where you want a compounding, cross-referenced wiki maintained alongside the code

## The idea in one paragraph

READMEs go stale. Architecture diagrams drift. Comments rot. This skill turns an LLM into a disciplined wiki maintainer that **reads the code**, **ingests your specs, PRs, and articles**, and **writes a persistent, interlinked Obsidian-compatible vault** alongside the repo. Every package has a summary page. Every domain has an overview. Every decision has an ADR. Every ingested article gets filed and cross-linked. Linting detects **code drift** — packages added/renamed/deleted without the vault noticing. The vault compounds instead of rotting.

## What's in the box

| Piece | What it does |
|---|---|
| **SKILL.md** | Master skill — architecture, workflows, page categories, iron rules |
| **4 sub-agents** | `graph-wiki:scanner`, `graph-wiki:ingestor`, `graph-wiki:librarian`, `graph-wiki:linter` |
| **6 slash commands** | `/graph-wiki:bootstrap`, `/graph-wiki:scan`, `/graph-wiki:ingest`, `/graph-wiki:query`, `/graph-wiki:lint`, `/graph-wiki:log` |
| **7 Python tools** | Via vault_io: `init_vault`, `scan_monorepo`, `ingest_source`, `wiki_search`, `lint_wiki` (+ code-drift), `detect_containers`, plus `_config.py` backend selector |
| **12 reference docs** | Schema, page formats, 4 workflows (scan/ingest/query/lint), Obsidian setup, cross-tool setup, monorepo principles, lifecycle rules, sidecar schema |
| **Wiki templates** | `CLAUDE.md`, `AGENTS.md`, `cursorrules`, `index.md`, `log.md`, plus page templates (app, package, domain, concept, dependency, package-family, work, source, architecture, adr) |

## Quick start

```bash
# 1. Initialize a wiki (workspace and repo resolved automatically via workspace_io)
uv run --project "$DEEP_AGENTS_ROOT" python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/init_vault.py \
    --topic "my-repo"

# 2. Open the workspace in Obsidian (sidebar will show wiki/, raw/, work/ as siblings).
open -a Obsidian ~/my-repo/graph-wiki

# 3. Scan the repo — creates a stub page for every workspace package (or for the single package, if not a monorepo)
cd ~/my-repo
# in Claude Code:
> /graph-wiki:scan

# 4. Stage a source (article, spec, PR summary) under <workspace>/raw/ and ingest
> /graph-wiki:ingest graph-wiki/raw/specs/auth-migration.md

# 5. Ask questions
> /graph-wiki:query "which packages depend on common-context-node-ts?"

# 6. Health check (mechanical + semantic + code drift)
> /graph-wiki:lint
```

## Page categories

| Category | Example |
|---|---|
| `app` | `<workspace>/wiki/apps/web-next-ts/web-next-ts.md` — Next.js app: platform, routes, domains consumed, deployment |
| `package` | `<workspace>/wiki/packages/common-aws-node-ts/common-aws-node-ts.md` — Lambda handlers, middleware, exports |
| `domain` | `<workspace>/wiki/domains/auth/auth.md` — cross-package feature area (auth spans cognito + native + shared) |
| `concept` | `<workspace>/wiki/concepts/global-context.md` — cross-cutting pattern used across packages |
| `dependency` | `<workspace>/wiki/dependencies/react.md` — external lib: versions in use, upgrade notes, gotchas (`kind: package | package-family | service`) |
| `source` | `<workspace>/wiki/sources/2026-04-auth-migration-spec.md` — ingested spec with claims + citations |
| `architecture` | `<workspace>/wiki/architecture/request-flow.md` — high-level synthesis |
| `adr` | `<workspace>/wiki/adrs/0012-move-to-esm.md` — dated decision with context + consequences |

## Cross-tool compatibility

Only the schema loader file changes per tool. The scripts run identically everywhere.

| Tool | Loader file |
|---|---|
| Claude Code | `<workspace>/wiki/CLAUDE.md` |
| Codex CLI (OpenAI) | `<workspace>/wiki/AGENTS.md` |
| Cursor (modern) | `<workspace>/wiki/AGENTS.md` |
| Cursor (legacy) | `<workspace>/wiki/.cursorrules` |
| Antigravity (Google) | `<workspace>/wiki/AGENTS.md` |
| OpenCode / Pi | `<workspace>/wiki/AGENTS.md` |
| Gemini CLI | `<workspace>/wiki/AGENTS.md` |

`init_vault.py --tool all` installs all three. Your repo's root `CLAUDE.md` (build/lint conventions) and the wiki's `CLAUDE.md` (vault conventions) are independent.

## Architecture

```
<repo>/graph-wiki/             # workspace; Obsidian vault opens here
├── .graph-wiki.yaml           # workspace manifest
├── CLAUDE.md                  # workspace-level schema (owned by workspace_io)
├── raw/                       # IMMUTABLE ingested sources (owned by workspace_io)
│   ├── articles/              # clipped web articles
│   ├── specs/                 # design docs, RFCs
│   ├── prs/                   # PR summaries
│   ├── tickets/               # issue exports
│   └── transcripts/           # meeting notes
├── work/                      # unified bugs / tech debt / features / initiatives / spikes (owned by workspace_io)
├── knowledge/                 # other plugin-managed knowledge stores
└── wiki/                      # this plugin's curated knowledge base
    ├── index.md               # content catalog
    ├── log.md                 # append-only timeline
    ├── apps/<app>/            # one folder per application workspace; overview at apps/<app>/<app>.md
    ├── packages/<pkg>/        # one folder per library/service workspace; overview at packages/<pkg>/<pkg>.md
    ├── domains/<domain>/      # one folder per cross-package feature area; overview at domains/<domain>/<domain>.md
    ├── concepts/              # cross-cutting technical concepts (and `<a>-vs-<b>.md` comparisons)
    ├── dependencies/          # external libraries — index.md auto-generated; detail pages opt-in
    ├── sources/               # one summary per ingested source
    ├── architecture/          # high-level syntheses
    ├── adrs/                  # decision records
    ├── CLAUDE.md              # wiki-local schema (Claude Code)
    └── AGENTS.md              # wiki-local schema (others)
```

**Iron rule:** the code is the source of truth. The LLM never edits `<workspace>/raw/`; all wiki writes go under `<workspace>/wiki/`. Work items live at `<workspace>/work/` and are referenced from wiki pages via wikilinks (e.g. `[[../work/2026-04-21-flaky-healthkit-tests]]`).

## Four operations

- **Scan** — walk the repo (`package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, `Cargo.toml`, `go.mod`), propose/update stub `packages/*.md` pages, flag renames/deletions for human review
- **Ingest** — read a source, discuss with user, write summary, update 5-15 cross-referenced pages, update index, log
- **Query** — index-first read, drill into 3-10 pages, synthesize with inline citations, offer to re-file the answer
- **Lint** — mechanical checks (orphans, broken links, stale pages, missing frontmatter) + semantic checks (contradictions, cross-reference gaps) + **code-drift** (packages on disk vs. in vault)

## Why not just maintain READMEs?

| READMEs | Code Wiki |
|---|---|
| One per package, manually written | One per package, LLM-maintained and cross-linked |
| Go stale silently | `lint` detects drift mechanically |
| No cross-references | Every package links to domains, sources, ADRs |
| No history of why decisions were made | ADRs capture decisions; log tracks every ingest/scan |
| Specs and articles live elsewhere | Ingested into `raw/` and summarized in `sources/` |

## Status

**v0.1.0** — port of upstream `lattice-wiki` v0.5.x targeting deep-agents vault-io/workspace-io surface. Claude Code host path; `graph-wiki-agent` is the parallel Bedrock CLI companion.

## License

MIT.

## Related

- [`wiki`](../wiki) — generic personal-knowledge-base version of this pattern
- [Karpathy's original gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- Vannevar Bush, "As We May Think" (1945) — the Memex
