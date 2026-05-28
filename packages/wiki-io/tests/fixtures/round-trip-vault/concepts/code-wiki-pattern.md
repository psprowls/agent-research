---
title: Code wiki pattern
category: concept
summary: A markdown wiki maintained alongside source code, structured as three layers (immutable raw sources, curated vault, code-as-source-of-truth) and governed by a small set of iron rules. The pattern lattice-wiki implements.
tags: [wiki, pattern, lattice, knowledge-management, obsidian, monorepo]
sources: 1
updated: 2026-05-09
tokens: 1424
---

# Code wiki pattern

## Definition

A **code wiki** is a markdown knowledge base that lives next to a source-code project, evolves with it, and obeys a small set of structural and behavioral rules: source code is the only source of truth, ingested raw material is immutable, and all curated knowledge accretes in a single vault directory. Pages cite — they don't duplicate — facts that the code or other vault pages already carry.

The pattern is the structural shape (three layers, frontmatter-on-every-page, append-only log, content-oriented index) plus the iron rules (code-truth, raw-immutable, every-write-goes-to-vault, every-claim-cites). Any tool that follows the shape and the rules implements the pattern; [[wiki/plugins/lattice-wiki/lattice-wiki]] is one such implementation.

## Motivation

Documentation drifts the moment the code moves. The pattern fights drift through three structural choices:

1. **Code-as-truth** — the wiki may describe the code, but it never overrides it. When the wiki and the code disagree, the wiki is wrong.
2. **Raw is immutable** — clipped articles, PRs, specs, transcripts get captured once and never edited. Curated knowledge happens in the vault on top of them.
3. **Every claim cites** — vault pages carry inline `[[wiki/wikilinks]]` to other pages and `` `code-paths:line` `` to source. Claims that don't cite are flagged.

This shape lets a code wiki accrete value over many small contributions (ingest one source, file one query answer, fix one drift) without requiring any single page to be authoritative.

## Shape

The canonical layout has three layers, sitting at a configurable wiki root:

```
<repo-root>/              → source code. Read-only from the wiki's perspective.
<wiki>/raw/               → ingested sources (specs, PRs, articles). Immutable.
<wiki>/<vault>/           → the curated knowledge base. The only place the wiki writes.
<wiki>/CLAUDE.md          → schema + iron rules + container layout (co-evolved).
```

Inside the vault, fixed top-level folders carry category-specific page schemas: `apps/`, `packages/`, `domains/`, `concepts/`, `dependencies/`, `endpoints/`, `data-models/`, `work/`, `sources/`, `architecture/`, `adrs/`. Every page declares its category in YAML frontmatter; lint enforces category-specific required fields (see `wiki/CLAUDE.md` and the page-format references).

Four maintenance operations close the loop:

- **Scan** — walk the repo, detect workspaces, create stub package/app pages and update derived frontmatter (`exports`, `depends_on`, `depended_on_by`).
- **Ingest** — read a source from `raw/` (or an in-repo `.md` design doc), write a `sources/<YYYY-MM>-<slug>.md` summary, update every package/domain/concept page it touches, propose ADRs when decisions are captured.
- **Query** — read `index.md` first, drill into 3–10 relevant pages, synthesize an answer with citations, offer to file the answer back.
- **Lint** — mechanical checks (orphans, broken links, frontmatter, log gap, code drift, sync drift) plus semantic checks (contradictions, stale claims, concept gaps, ADR chain health).

Each operation touches at minimum the changed page(s), `index.md`, and `log.md` — three files per write keeps the index and timeline accurate.

## Iron rules

The pattern is defined as much by what it forbids as what it does:

1. The code is the source of truth.
2. `raw/` is immutable.
3. All writes go to `<vault>/`.
4. Every vault page has YAML frontmatter (`title`, `category`, `summary`, `updated`).
5. Every scan/ingest touches ≥3 files (the page, the index, the log).
6. Every claim cites — a vault page or a code path.
7. Contradictions get flagged inline (callouts on the vault page, noting the code path).
8. Good query answers get filed back. Explorations compound.

Drop any of these and the pattern stops being self-correcting.

## Used in

- [[wiki/plugins/lattice-wiki/lattice-wiki]] — the canonical implementation; ships scripts (`scan_monorepo.py`, `ingest_source.py`, `lint_wiki.py`, `update_index.py`, `wiki_search.py`, `graph_analyzer.py`) and the agent dispatch (`ingestor`, `librarian`, `linter`, `scanner`).
- [[wiki/plugins/lattice-work/lattice-work]] — consumer plugin; reads `<vault>/work/*.md` for lifecycle tracking. Schema and migrator stay in the wiki per adrs/0004-work-tracker-as-consumer-plugin.

## Related patterns

- wiki-cites-graph-not-duplicates — the wiki↔graph integration principle; mechanically derivable facts get queried from `lattice-graph` rather than duplicated into vault frontmatter.
- [[wiki/concepts/per-repo-layout]] — `<repo>/wiki/` (committed, human-visible) plus `<repo>/.lattice/` (machine state, gitignored) as the two ecosystem roots.
- [[wiki/concepts/lattice-page-body-table-conventions]] — the body-table grammar (`## Plan`, `## Endpoints`, `## Fields`) the schema relies on.
- [[wiki/concepts/lattice-vault-terminology]] — canonical glossary for the load-bearing terms (`raw`, `vault`, `container`, `domain`).

## Sources

- 2026-05-lattice-ecosystem-review — foundational architecture review; diagnoses live-vault asymmetry and prescribes the schema/topology direction.

## Open questions / gotchas

- **Bootstrap problem** — does a code wiki self-host its own graph-derived summaries once `lattice-graph` is wired up? Same shape as the wiki↔graph integration question for `lattice-wiki` itself.
- **Single-package vs monorepo** — the same pattern produces different vault shapes (no `apps/`, `domains/` for single-package). Container detection is interactive when classifications are ambiguous.
