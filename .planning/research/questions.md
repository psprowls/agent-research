# Open Research Questions

Append-only log of open research questions surfaced during exploration. Resolved questions should be moved out of this file (e.g. into a research SUMMARY.md or a phase's RESEARCH.md) and crossed off here with a link.

---

## Wiki Entity Restructure (2026-05-26)

Context: see `.planning/notes/wiki-entity-restructure-design.md`. These questions need answers before — or as part of — the milestone that scopes the wiki restructure.

### Q1. Entity keying

How does an entity page get a stable identifier that survives renames, moves, and refactors? This reconnects to the original v1.8 URI-keying problem. Options to evaluate:

- URI-as-key (path-based, e.g. `pkg://agent-research/graph-io`) — stable across filename changes but coupled to package/path naming.
- Opaque UUID assigned at first scan, persisted in frontmatter — fully stable but loses human readability.
- Hybrid: human-readable slug + opaque ID, with slug as a display alias.

Which scheme works for both graph-derived entities and the existing curated lanes (concepts/adrs/etc.) that link to them?

### Q2. Reconciliation on graph-node disappearance

When the scanner runs and a graph node that previously had a wiki entity page is no longer present (package deleted, dependency dropped, test-suite removed), what should happen to the page?

- Hard delete?
- Move to an `/archive/` or `/tombstones/` folder?
- Mark with `status: removed` frontmatter and keep in place for backlink integrity?

The choice affects how dangling wikilinks from `/concepts/` and `/adrs/` are handled.

### Q3. Migration of existing inbound wikilinks

Existing `/concepts/` and `/adrs/` pages contain wikilinks pointing at the current package-folder layout (e.g. `[[packages/graph-io/index]]`). When packages collapse to single entity pages (`[[entities/graph-io]]` or similar), these inbound links break. Options:

- One-shot migration pass run at the moment of layout change.
- Compatibility-shim redirect pages at old paths.
- Author-time link rewriter that runs on every scan.

### Q4. Scanner pipeline scope

Where does relation-frontmatter generation slot into the existing scanner architecture? Specifically:

- Which scanner stage currently produces wiki pages?
- Is the new entity-page writer a replacement for that stage, or a new stage that runs after graph construction?
- How does relation frontmatter coexist with any human-authored frontmatter on the same page (e.g. `status:`, `last_reviewed:`)? Whitelist of scanner-owned keys?

### Q5. Index-page generation

The new index has nested domain sections and global by-kind sections — both derived from the graph. Is the index page itself a scanner-generated artifact (regenerated each run), or a human-authored shell with scanner-generated injection blocks?
