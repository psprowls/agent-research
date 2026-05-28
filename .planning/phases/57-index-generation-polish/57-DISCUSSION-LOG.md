# Phase 57: Index Generation Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 57-index-generation-polish
**Areas discussed:** Cross-cutting packages' nested items, App section placement & nesting, Summary source (page vs graph), Nested Dependencies composition

---

## Cross-cutting packages' nested items

| Option | Description | Selected |
|--------|-------------|----------|
| Nest under package in By-Kind too | Mirror domain nesting inside By-Kind entries; every package shows its items | ✓ |
| Domain-placed packages only | Only domain-section packages nest; cross-cutting packages show none | |
| Flat fallback for orphans only | Minimal flat section for cross-cutting packages' items | |

**User's choice:** Nest under package in By-Kind too
**Notes:** Makes flat-section removal (IDX-04/05) safe — no orphaned test-suites/deps for multi-domain packages.

---

## App section placement & nesting

| Option | Description | Selected |
|--------|-------------|----------|
| app first, nests like packages | Order: app, package, plugin; apps nest test-suites/deps | ✓ |
| app after packages, nests like packages | Order: package, app, plugin | |
| app section, no nesting | App section but apps don't nest | |

**User's choice:** app first, nests like packages

### App domain placement sub-decision
| Option | Description | Selected |
|--------|-------------|----------|
| Same placement rule as packages | Single-domain app → domain section; multi-domain → By-Kind app section | ✓ |
| Always in By-Kind app section only | Apps never nest under a domain | |
| You decide during planning | Defer | |

**Notes:** Apps route through `_place_entities()` identically to packages.

---

## Summary source (page vs graph)

| Option | Description | Selected |
|--------|-------------|----------|
| Entity .md frontmatter | Read `summary:` from the entity page; captures human edits; mirrors curated-lane pattern | ✓ |
| Graph attrs['description'] | Read from graph node; no I/O but misses human edits | |
| Graph attr + page override | Hybrid | |

**User's choice:** Entity .md frontmatter
**Notes:** Phase 56 D-07 makes summary fill-when-empty (human-editable), so the page is authoritative. Reuses `_scan_curated_lane()` file-frontmatter pattern.

---

## Nested Dependencies composition

| Option | Description | Selected |
|--------|-------------|----------|
| Both, separate sub-lists | "Dependencies" (external used_by) + "Internal dependencies" (depends_on_package) | ✓ |
| Both, merged into one list | Single mixed Dependencies list | |
| External only | Only external deps nested; internal via describe-package | |

**User's choice:** Both, separate sub-lists
**Notes:** Internal deps link to real package entities; distinct heading surfaces the Phase 55 depends_on_package data IDX-05 relies on. Duplication across packages expected (IDX-04/05).

---

## Claude's Discretion

- Ordering within nested sub-lists (alphabetical default).
- Sub-list heading text/indentation, matching existing domain-nesting style.
- How `summary` is threaded into PlacedEntity (file-read pass vs folded into placement read).

## Deferred Ideas

- Dependency-family clustering — already in Future Requirements.
- Usage counts/weights on nested entries — no SC requires it.
