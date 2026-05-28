---
title: lattice vault terminology
category: concept
summary: Canonical glossary for load-bearing terms used across the lattice-wiki plugin (scripts, references, page templates) and the vaults it produces. Pending renames flagged but not decided. Drift is a bug, not a term.
tags: [terminology, glossary, schema, lattice, conventions]
sources: 2
updated: 2026-05-09
tokens: 2109
---

# lattice vault terminology

## Summary
Single source of truth for what each load-bearing term means across the [[wiki/plugins/lattice-wiki/lattice-wiki]] plugin and the vaults it produces. When usage is in question, this page is authoritative; when terminology drifts, the drift is the bug, not the term.

Captured in 2026-05-lattice-ecosystem-schema-refinements Terminology section.

## Glossary — current canonical terms

### Structural

| Term | Meaning |
|---|---|
| **workspace** | The per-repo root that Obsidian opens (e.g. `<repo>/lattice/`). Resolved by [[wiki/packages/lattice-workspace/lattice-workspace]]; defaults to `<repo>/lattice/`, override via `.lattice.local.yaml`'s `lattice-directory:`. Contains `wiki/`, `raw/`, `work/`, `knowledge/`, `.lattice.yaml`, and `CLAUDE.md` as direct children. |
| **vault** | The Obsidian vault. Opens at `<workspace>/`, so `wiki/`, `raw/`, `work/` are vault-root-level siblings. Wikilinks are workspace-root-relative — see [[wiki/adrs/0015-workspace-root-wikilink-form]]. *Vault* and *workspace* are co-extensive on disk; the distinction is which tool's perspective applies (Obsidian vs. lattice-workspace). |
| **wiki** | `<workspace>/wiki/` — the directory of LLM-curated pages (overview, package, concept, ADR, source-summary, architecture). Owned by [[wiki/plugins/lattice-wiki/lattice-wiki]]. Sibling of `raw/` and `work/`. Was previously a top-level container holding `raw/` + a sub-vault; consolidated to a single workspace root in [[wiki/adrs/0011-single-workspace-root]]. |
| **raw** | `<workspace>/raw/` — immutable ingested sources (specs, articles, PRs, transcripts). Owned by [[wiki/packages/lattice-workspace/lattice-workspace]]. The LLM never edits files here; the wiki ingestor reads from here and writes summaries to `<workspace>/wiki/sources/`. |
| **work** | `<workspace>/work/` — unified bug / tech-debt / feature / initiative / spike tracker. Owned by [[wiki/packages/lattice-workspace/lattice-workspace]] (schema) and [[wiki/plugins/lattice-work/lattice-work]] (lifecycle lint + sidecar). Sibling of `wiki/`; cited from wiki pages as `[[work/<slug>]]`. |
| **container** | Umbrella term for the four detected structural shapes: `app`, `package`, `domain`, `docs`. Used by `detect_containers.py`, `pinned_containers`. *(See pending rename below.)* |
| **app** | A deployable application (web, mobile, CLI). One of the four container shapes. |
| **package** | A shared library, used by apps and other packages. One of the four container shapes. |
| **domain** | A bounded area of business logic spanning multiple packages (e.g. HealthKit, location). One of the four container shapes. *(See pending rename below.)* |
| **docs** | A documentation location detected as a container. |
| **page** | Any markdown file in the vault. Specific shapes are referred to as "work page," "dependency page," etc. |

### Schema

| Term | Meaning |
|---|---|
| **frontmatter** | YAML block at the top of every vault page. |
| **category** | Frontmatter field — the kind-of-page (`work`, `package`, `dependency`, `concept`, `endpoint`, `data-model`, `source`, `architecture`, `adr`). One per page; identifies which schema applies. |
| **kind** | Frontmatter field — sub-discriminator within a category. `category: work` has `kind: bug | tech-debt | feature | …`; `category: dependency` has `kind: package | service`. Not every category uses `kind`. |
| **status** | Frontmatter field — lifecycle state. Currently work-specific (7-state set per [[wiki/concepts/lattice-work-namespace-schema]]). |
| **plan** | The committed direction for a work item. Lives in the body as a `## Plan` markdown table (not a frontmatter field). |
| **affects** | Frontmatter field — packages or files a work item touches. |
| **defined_in** | Frontmatter field — code path that's the source of truth for a wiki page (data-model, endpoint, etc.). Lint walks it for drift. |

### Actions / scripts

| Term | Meaning |
|---|---|
| **scan** | Walk the monorepo, detect containers, propose/update stub pages. `scan_monorepo.py`, `/lattice-wiki:scan`. |
| **ingest** | Bring a raw source into the vault as structured content across multiple pages. `ingest_source.py`, `/lattice-wiki:ingest`. |
| **lint** | Validate the vault for drift, malformed pages, broken links, missing frontmatter. `lint_wiki.py`, `/lattice-wiki:lint`. |
| **query** | Answer a question by reading and synthesizing across vault pages. `wiki_search.py`, `/lattice-wiki:query`. |
| **init** | Bootstrap a new wiki + vault for a repo. `init_vault.py`, `/lattice-wiki:init`. |
| **log** | Append-only history at `<workspace>/wiki/log.md` of every ingest/scan/edit. `append_log.py`, `/lattice-wiki:log`. |

### Schema-introduced in §2 (net-new vocabulary)

| Term | Meaning | Where defined |
|---|---|---|
| **work** | Unified namespace replacing `issues/` + `roadmap/`. `category: work`. | [[wiki/concepts/lattice-work-namespace-schema]] |
| **work-index** | The auto-generated `<workspace>/work-index.json` sidecar listing all work items for planner consumption. | [[wiki/concepts/lattice-work-namespace-schema]] |
| **data-model** | A first-class category for documented type/schema definitions, with bidirectional drift detection against code. | _(ADR-0009, deleted — category removed as overkill)_ |
| **endpoint group** | An endpoint cluster (one resource, 3-6 routes) — the unit a single endpoint page describes. | _(ADR-0009, deleted — category removed as overkill)_ |
| **exposure** | Endpoint frontmatter axis: `external | internal | partner | dev-only`. | _(ADR-0009, deleted — category removed as overkill)_ |
| **migration audit** | The `migration-audit.md` report each migrator emits listing weak-pattern matches and family/cluster candidates for human review (rather than auto-applying). | 2026-05-lattice-ecosystem-schema-refinements §4.7 |

## Pending renames (deferred)

### `domain` — rename candidate

The term carries DDD baggage heavier than the wiki's actual usage. Candidates:

| Candidate | Pro | Con |
|---|---|---|
| `area` | neutral, no collision | slightly less specific |
| `collection` | neutral | collides with MongoDB collections (live vault has Mongo issues) |
| `container` | already in use | conflicts with the umbrella term |
| `bounded-context` | DDD canon | verbose |
| keep `domain` | descriptive, zero migration | DDD baggage |

**Status: deferred.** `area` is the cleanest non-collision rename. Migration cost (if we move): `domains/` folder rename in vaults, `detect_containers.py`, schema reference, all `[[wiki/domains/<x>]]` wikilinks across live vaults, `domain-placement` lint check, fixture trees, `init_vault.py` directory creation.

### `container` (umbrella) — rename only if needed

Only requires renaming if the `domain` rename adopts `container`. Status: blocked on the `domain` decision.

## Rule

- When new terms are coined or renamed, **add an entry here** *before* changing scripts, references, or templates. Order matters — design first, mechanical sweep second.
- When the doc and live state disagree, this page wins. Live drift is filed as a `terminology-drift` lint flag for repair.
- Future lint check `terminology-violation` (info) will scan templates/references/script docstrings for usage of deprecated terms (post-§2-landing audit).

## Related
- [[wiki/concepts/lattice-naming-convention]] — plugin-name-level terminology
- [[wiki/concepts/lattice-work-namespace-schema]]
- [[wiki/concepts/lattice-dependencies-tiering]]
- [[wiki/concepts/lattice-page-body-table-conventions]]
- [[wiki/concepts/per-repo-layout]] — current workspace shape
- [[wiki/adrs/0015-workspace-root-wikilink-form]] — canonical wikilink forms
- [[wiki/sources/2026-05-workspace-relative-wikilinks-linter-and-content-rewrite]]
- 2026-05-lattice-ecosystem-schema-refinements
