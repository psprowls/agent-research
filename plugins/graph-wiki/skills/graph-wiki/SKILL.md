---
name: graph-wiki
description: Use when building or maintaining a persistent wiki alongside any source-code project — single packages, monorepos, or hybrid shapes. Adapts to the repo's folder structure: detects app, package, domain, package-family, and docs containers and pins the layout in CLAUDE.md/AGENTS.md. Triggers include "wiki this repo", "document this codebase", "graph-wiki", "ingest this spec/PR/article into the wiki", or whenever the user wants a compounding, cross-referenced knowledge base alongside source code.
context: fork
version: 0.1.0
author: psprowls
license: MIT
tags: [monorepo, documentation, knowledge-management, obsidian, wiki, turborepo, pnpm, nx]
compatible_tools: [claude-code, codex-cli, cursor, antigravity, opencode, gemini-cli]
---

# Code Wiki — Maintained Documentation Alongside Any Source-Code Project

Adapts the LLM Wiki pattern ([graph-wiki](../graph-wiki/SKILL.md); Karpathy's [gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)) to a source code monorepo. The LLM incrementally builds and maintains a persistent, interlinked markdown vault that documents every package, app, domain, and cross-cutting concept in the repo — plus ingested specs, PR summaries, articles, and design notes.

## Core principle

Code comments go stale. README files rot. Architecture diagrams drift from reality. The wiki is **compounding, cross-referenced, and kept current** — sources (code, specs, PRs, articles) are read once and integrated into package summaries, domain overviews, ADRs, and architecture syntheses. Every claim links to a source; contradictions with newer code get flagged; the index stays in sync with what the repo actually looks like.

> Obsidian is the reading room. The LLM is the maintainer. Your repo is the source of truth.

## When to use

- **Single-package repos** — libraries, services, or apps where a README isn't enough and you want per-module/area pages
- **Monorepos** — Turborepo, pnpm workspaces, Nx, Bazel, Rush, Lerna, Go workspaces, Cargo workspaces
- **Hybrid repos** — a primary package at the root with nested apps/packages/domains
- **Onboarding** — a wiki that an LLM keeps up to date reduces the cost of new contributors (human or agent)
- **Agent-assisted development** — coding agents read the vault before making edits; they edit the vault as they go
- **Architecture bookkeeping** — ADRs, cross-package conventions, deprecation notices, migration plans
- **Spec/PR/article ingestion** — you clip an article, write a spec, review a PR — all feed into the vault

**Do NOT use when:** the team has a documentation CMS they prefer, or nobody will curate ingestion (vault quality = source quality).

## Architecture

The wiki lives inside the graph-wiki workspace at `<workspace>/wiki/`. The workspace defaults to `<repo>/graph-wiki/` and is discovered automatically via `workspace_io` (override with `.graph-wiki.yaml`'s workspace path key). The Obsidian vault opens at `<workspace>/`, so `raw/` (immutable ingested sources) and `work/` (unified work tracker) are siblings of `wiki/` — both owned by `workspace_io`, not by this plugin.

```
<repo>/graph-wiki/              # workspace; Obsidian vault opens here
├── .graph-wiki.yaml            # workspace manifest
├── CLAUDE.md                   # workspace-level schema (owned by workspace_io)
├── raw/                        # IMMUTABLE source of truth (owned by workspace_io)
│   ├── articles/               # clipped articles, blog posts
│   ├── specs/                  # design docs, specs, RFCs
│   ├── prs/                    # PR summaries, review notes
│   ├── tickets/                # Linear / Jira / GitHub issue exports
│   ├── transcripts/            # meeting / design-session notes
│   └── assets/                 # images, diagrams referenced by sources
├── work/                       # unified bugs / tech debt / features / initiatives / spikes (owned by workspace_io)
├── knowledge/                  # other plugin-managed knowledge stores
└── wiki/                       # this plugin's curated knowledge base
    ├── index.md                # Content catalog (LLM updates every ingest/scan)
    ├── log.md                  # Append-only timeline
    ├── apps/<app>/             # [conditional] One folder per application workspace (web, mobile, CLI); overview lives at apps/<app>/<app>.md
    ├── packages/<pkg>/         # [conditional] One folder per library/service workspace package; overview at packages/<pkg>/<pkg>.md
    ├── domains/<domain>/       # [conditional] One folder per cross-package feature area; overview at domains/<domain>/<domain>.md (domain-scoped packages live under domains/<domain>/packages/<pkg>/<pkg>.md)
    ├── concepts/               # Cross-cutting technical concepts (auth, testing patterns, comparisons)
    ├── dependencies/           # External libraries — index.md auto-generated; detail pages opt-in
    ├── sources/                # One summary page per ingested source (cites files in <workspace>/raw/)
    ├── architecture/           # High-level architecture syntheses
    ├── adrs/                   # Architecture Decision Records
    ├── .templates/             # Page templates (reference only, not indexed)
    ├── CLAUDE.md               # wiki schema + conventions (Claude Code)
    └── AGENTS.md               # same content for Codex/Cursor/Antigravity/OpenCode
```

`apps/`, `packages/`, and `domains/` are **conditional** — the detector creates them only when the repo has matching containers. A single-package repo has none of these; its workspace pages live at the wiki root (or under `concepts/` / `architecture/` for cross-cutting topics). A library-only monorepo has `packages/` but no `apps/`. Pinned containers are recorded in `<workspace>/wiki/CLAUDE.md` and `<workspace>/wiki/AGENTS.md`.

**Source of truth is the code itself.** The wiki is a compiled layer above it. If the wiki disagrees with the code, the code wins — the wiki gets updated.

## Four core operations

1. **Scan** — walk the repo, detect packages/apps/workspaces, propose stub `packages/*.md` pages, and surface in-repo `.md` docs as ingest candidates. See `references/scan-workflow.md`.
2. **Ingest** — read a source (article, spec, PR, transcript, or in-repo doc), discuss takeaways, write a source summary, update 5-15 relevant pages, update index, append to log. In-repo docs (under a `docs` container) are ingested in place — the summary records `source_path` + `last_sync_commit` (when ingested with a clean working tree on main) so /graph-wiki:lint flags staleness when the file changes. PDF/DOCX support is deferred — see `references/ingest-workflow.md` "Future formats". See `references/ingest-workflow.md`.
3. **Query** — read `index.md`, drill into 3-10 pages, synthesize with inline `[[wikilinks]]`, offer to file the answer back. See `references/query-workflow.md`.
4. **Lint** — health check including **code-drift detection**: packages on disk missing from the vault, vault pages referencing deleted/renamed packages, stale package summaries whose exports have changed. See `references/lint-workflow.md`.

## Quick start

```bash
# 1. Initialize a wiki in the resolved graph-wiki workspace.
#    Workspace and repo root are discovered via workspace_io (walks up from cwd
#    for .git, reads .graph-wiki.yaml, defaults to <repo>/graph-wiki).
#    Wiki is created at <workspace>/wiki/ (e.g. graph-wiki/wiki/).
python ${CLAUDE_PLUGIN_ROOT}/skills/graph-wiki/scripts/init_vault.py \
    --topic "my-repo"

# 2. Scan the repo to create stub pages for every package
/graph-wiki:scan

# 3. Drop a source (article, spec, PR) into raw/ and ingest
/graph-wiki:ingest raw/specs/auth-migration.md

# 4. Ask questions
/graph-wiki:query "which packages depend on common-context-node-ts?"

# 5. Health check (surfaces code-drift too)
/graph-wiki:lint
```

## Slash commands

| Command | Purpose |
|---|---|
| `/graph-wiki:init` | Bootstrap a fresh wiki at `<workspace>/wiki/` (workspace resolved via `workspace_io`, defaults to `<repo>/graph-wiki/`) |
| `/graph-wiki:scan` | Walk the repo, detect packages/apps/workspaces, create/update stub package pages |
| `/graph-wiki:ingest <path>` | Read a source from `raw/`, discuss, update vault, log it |
| `/graph-wiki:query <question>` | Search vault, synthesize answer with citations, offer to file back |
| `/graph-wiki:lint` | Health check — orphans, broken links, stale claims, **code drift** |
| `/graph-wiki:log` | Show recent log entries (uses unix tools on `log.md`) |

## Sub-agents

| Agent | When dispatched |
|---|---|
| `graph-wiki:scanner` | Walk the repo, detect packages, propose or update stub package pages |
| `graph-wiki:ingestor` | Delegated ingest flow — reads source, proposes updates, applies after approval |
| `graph-wiki:linter` | Runs the health-check workflow (mechanical + semantic + code drift) |
| `graph-wiki:librarian` | Answers queries using index-first search with citations |

## Python tools (`scripts/`)

Standard library only (via vault_io). Run with `python scripts/<tool>.py --help`.

| Script | Purpose |
|---|---|
| `init_vault.py` | Create folder structure + seed schema files. Wiki path resolved automatically via `workspace_io`. |
| `scan_monorepo.py` | Walk the repo, detect `package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod` workspaces; emit a diff of missing/renamed/deleted package pages |
| `ingest_source.py` | Extract text + metadata from a source file — prepares a brief for the LLM |
| `wiki_search.py` | BM25 search over vault pages (fallback when index alone isn't enough) |
| `lint_wiki.py` | Orphans, broken links, stale pages, missing frontmatter, log gap, **+ code-drift** (packages on disk vs. in vault) |
| `detect_containers.py` | Classify top-level dirs as apps, packages, domains, or docs containers |

## Cross-tool compatibility

Schema lives in `<workspace>/wiki/CLAUDE.md` (Claude Code) or `<workspace>/wiki/AGENTS.md` (Codex/Cursor/Antigravity/OpenCode). The plugin ships both. The scripts run identically everywhere. See `references/cross-tool-setup.md`.

**Note:** your repo's root `CLAUDE.md` is separate from the wiki's `CLAUDE.md`. The root file defines the repo's build/style conventions; the wiki file defines how the vault is structured. Both are active simultaneously when working from the repo root.

## Page categories

| Category | What it documents | Directory |
|---|---|---|
| `app` | One application workspace (web, mobile, CLI) — platform, entry points, domains consumed, deployment | `<workspace>/wiki/apps/<app>/<app>.md` |
| `package` | One library/service workspace — what it exports, who depends on it, key patterns | `<workspace>/wiki/packages/<pkg>/<pkg>.md` |
| `domain` | A feature area spanning multiple packages (e.g. "auth", "healthkit", "billing") | `<workspace>/wiki/domains/<domain>/<domain>.md` |
| `concept` | Cross-cutting technical idea (e.g. "GlobalContext pattern", "integration test setup"). Comparisons (`<a>-vs-<b>.md`) live here too. | `<workspace>/wiki/concepts/` |
| `dependency` | An external package, package family, or service the monorepo depends on — `kind:` discriminates | `<workspace>/wiki/dependencies/` |
| `source` | Summary of an ingested spec, PR, article, transcript, etc. | `<workspace>/wiki/sources/` |
| `architecture` | High-level synthesis — build system, module graph, request flow, deployment topology | `<workspace>/wiki/architecture/` |
| `adr` | Architecture Decision Record — a dated, citable decision with context + consequences | `<workspace>/wiki/adrs/` |

## Why this works (vs. just READMEs or generic docs)

| READMEs / generic docs | Code Wiki |
|---|---|
| Written once, go stale | Incrementally updated on every ingest/scan |
| One-directional (README describes package) | Bidirectional — packages link to domains link to ADRs link to sources |
| Updates are manual chores | LLM does the cross-reference maintenance |
| Drift is invisible until you read | Lint surfaces drift mechanically |
| Searchable only by file | Indexed by category + frontmatter + BM25 |
| Specs/PRs/articles live in separate systems | Ingested and linked alongside code documentation |

## Related skills

- **`obsidian-markdown`** — bundled with this plugin. Covers Obsidian-specific syntax (wikilinks, embeds, callouts, properties, comments, highlights). The four sub-agents (`graph-wiki:scanner`, `graph-wiki:ingestor`, `graph-wiki:linter`, `graph-wiki:librarian`) invoke it whenever they create, edit, or verify a vault page so the output renders correctly in Obsidian.
- **`wiki`** — the generic personal-knowledge-base version of this skill. Same pattern, different page categories. Use `wiki` for non-code topics (research, books, journaling).
- **`para-memory-files`** — PARA memory; useful if you have personal memory feeding into a repo wiki.

## Reference docs

- `references/wiki-schema.md` — full vault layout, page frontmatter, taxonomies, body-table conventions
- `references/page-formats.md` — annotated examples for app, package, domain, concept, dependency, work, source, architecture, ADR
- `references/detection-workflow.md` — how containers are classified and pinned
- `references/scan-workflow.md` — how the scanner detects packages and proposes pages
- `references/ingest-workflow.md` — detailed ingest flow
- `references/query-workflow.md` — query patterns, citation format, re-filing answers
- `references/lint-workflow.md` — health-check heuristics including code-drift detection
- `references/obsidian-setup.md` — Obsidian plugins, hotkeys, vault config
- `references/cross-tool-setup.md` — per-tool setup (Codex, Cursor, Antigravity, etc.)
- `references/monorepo-principles.md` — why this pattern works for code, how it differs from the generic LLM Wiki
- `references/lifecycle-rules.md` — the 19 work-layer lint rules with severities and remediation (upstream reference; work-layer not ported in v1.2)
- `references/sidecar-schema.md` — `work-index.json` schema and stability guarantees (upstream reference)

## Templates (`assets/`)

- `CLAUDE.md.template`, `AGENTS.md.template`, `cursorrules.template` — schema loaders per tool
- `index.md.template`, `log.md.template` — starter index and log
- `page-templates/` — app, package, domain, concept, dependency, package-family, work, source, architecture, adr

## Iron rules

1. **The code is the source of truth.** If the vault contradicts the code, the code wins — update the vault.
2. **The LLM never edits files in `raw/`.** Sources are immutable.
3. **All LLM writes for the wiki go under `<workspace>/wiki/`.** Work items go to `<workspace>/work/` (owned by `workspace_io`); ingested sources stay in `<workspace>/raw/` (immutable). No exceptions.
4. **Every vault page has YAML frontmatter** with `title`, `category`, `summary`, `updated`.
5. **Every ingest or scan touches ≥3 files:** the changed/new page(s), `index.md`, `log.md`.
6. **Every claim on a package/domain page cites** either a source page (`[[sources/xxx]]`) or a code path (`packages/foo/src/bar.ts`).
7. **Good query answers get filed back** — explorations compound.
