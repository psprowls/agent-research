---
title: Wiki Entity Restructure — Design Decisions
date: 2026-05-26
context: explore session, post-v1.8-abort
status: design-direction
---

# Wiki Entity Restructure — Design Decisions

Captured from `/gsd-explore` session on 2026-05-26, immediately after aborting the original v1.8 scope (URI-Keyed Wiki & Reconciliation). This document captures the design direction for what may become the next v1.8 milestone: a wiki schema overhaul that collapses the current page-type-per-directory model into a unified entity model driven by the graph.

## Motivation

The current wiki has separate page types — `dependencies`, `packages`, `domain`, `plugin`, `package-family` — each with its own directory layout and template. With the v1.6 ontology and v1.7 graph integration in place, the wiki is now **modeling the same structural reality twice**: once as a directory/file hierarchy, once as graph nodes and edges. The user wants to collapse the two models so the wiki becomes the curated, human-readable projection of the graph rather than a parallel structure.

## Architecture

### Two-lane wiki layout

The wiki is organized into two top-level lanes:

1. **`/entities/`** — flat folder, graph-derived structural entities. One file per entity, `kind` discriminator in frontmatter, per-kind templates.
2. **Existing curated lanes** — `/concepts/`, `/adrs/`, `/architecture/`, `/work/`, `/sources/` retain their current homes. These are synthesized from source code and human-curated; they are not direct graph projections.

The index page interleaves both lanes (see "Index structure" below).

### Entity boundary

Entities in `/entities/` are **major structural code entities only**. Concretely:

- **Admitted kinds:** `repository`, `domain`, `package`, `package-family`, `plugin`, `dependency`, `test-suite`
- **Excluded:** `sub-package`, and in-file graph nodes — `class`, `function`, `method`, `module-inside-file`. The wiki stops at the `package` boundary; sub-packages do not get their own entity pages (they remain graph nodes and can be referenced from their parent `package` entity, but are not promoted to wiki entities).
- **Policy for new kinds:** when a new graph node kind is added, an explicit decision must be made on whether it warrants a wiki entity page. This is not automatic.

### Per-kind templates replace directory templates

Today, some entity types (notably `package`) are represented as a directory with multiple sub-pages and a directory-template that governs the layout. In the new model:

- Each entity is a single page.
- A per-kind template (e.g. `entity-package.template`) governs the layout for that kind.
- The package-as-folder pattern collapses: all sub-content rolls into the single `entity-package` page, or is broken out as separate linked entities (e.g. a package's test-suite is its own `kind: test-suite` page).
- Directory templates as a concept go away.

### Edges as frontmatter relations

Graph edges are surfaced on entity pages via **structured frontmatter relations**, not layout blocks and not inline prose wikilinks.

- The scanner reads the graph and populates relation frontmatter on each entity page (e.g. a `package` page's `covered_by` field points to its `test-suite` entity).
- Frontmatter is the source of truth for relationship state. Prose is reserved for narrative.
- The render layer can present relations however it wants (collapsed lists, grouped sections, etc.) — that's a separate concern.
- This makes the entity-page relation set **deterministic and regenerable**: re-running the scanner brings the page in sync with the graph without prose edits.

### Index structure

The main index page is organized hierarchically:

1. **Domains section (first).** Each domain expanded inline, with its contained packages, test-suites, dependencies, etc. listed nested under it.
2. **Global by-kind sections** (after domains). Cross-cutting flat lists: all packages, all plugins, all dependencies, all test-suites, etc. — for browsing by kind regardless of domain.

Entities therefore appear in **two places** in the index: once nested under their domain, once in the global by-kind list. (Both are index views; the entity page itself is the single canonical home.)

## Open questions (see also `.planning/research/questions.md`)

- **Keying.** How does an entity page get a stable identifier? This reconnects to the original v1.8 URI-keying problem — entities still need stable IDs, especially when graph nodes are renamed or moved.
- **Reconciliation.** When a graph node disappears (package deleted, dependency dropped), what happens to its entity page? Delete, archive, tombstone?
- **Migration.** Existing `/concepts/` and `/adrs/` pages contain wikilinks to old package-folder pages. These need fix-up when packages collapse to single entity pages.
- **Scanner scope.** Which existing scanner stages produce wiki pages today, and how does relation-frontmatter generation slot in? Is this a new pipeline stage or a rewrite of existing wiki-writer code?

## Relation to v1.8

The original v1.8 (URI-Keyed Wiki & Reconciliation) was aborted before research synthesis landed. The user's direction is that **this restructure may become the new v1.8 scope**, with URI-keying folded in as one sub-problem inside the larger overhaul rather than the headline goal. To be decided in `/gsd-new-milestone`.
