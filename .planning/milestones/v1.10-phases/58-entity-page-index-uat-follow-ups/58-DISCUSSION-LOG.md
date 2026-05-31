# Phase 58: Entity Page & Index UAT Follow-Ups - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 58-entity-page-index-uat-follow-ups
**Areas discussed:** Related from edges (#1), Test-suite fix approach (#3), summary placeholder format (#2), Golden-fixture rebaseline

---

## Related section (#1) — ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Scanner-owned (re-derive each scan) | Rewrite Related from graph edges every scan | |
| Fill-when-empty (human-editable) | Populate only when empty; preserve edits | |
| Hybrid (derived block + human zone) | Scanner block + human zone below | |

**User's choice (free text):** Related should reflect concepts/ADRs/architecture pages that reference the entity, with an empty message when there are none. Those do not come from graph edges today; they may later if non-entity wiki pages get added to the graph.

## Related section (#1) — what to build in Phase 58

| Option | Description | Selected |
|--------|-------------|----------|
| Clean empty marker now, defer population | Replace `<...>` with a clean fill-me-in message; defer real population | ✓ |
| Build the backlink scan now | Scan curated pages for inbound `[[entities/...]]` wikilinks | |
| Roadmap-literal: graph-edge links now | Populate from `depends_on`/domains/dependencies | |

**User's choice:** Clean empty marker now, defer population.
**Notes:** Reinterprets roadmap success criterion #1. Real population deferred until non-entity wiki pages are in the graph.

---

## Test-suite fix approach (#3)

| Option | Description | Selected |
|--------|-------------|----------|
| Renderer-side: resolve by node uri/id | Thread `PlacedEntity.uri` into `_consumer_pkgs`; fix in-domain too | |
| Scan-side: unique suite names | Rename test_suite nodes to package-qualified names | |
| Both renderer + scan-side rename | Both fixes | ✓ |

**User's choice:** Both.
**Notes:** Wants suites named for their package, e.g. `wiki-io-unit-tests`, `graph-wiki-agent-int-tests`.

---

## Summary placeholder format (#2)

| Option | Description | Selected |
|--------|-------------|----------|
| Plain text, entity summary only | `TODO add a one-line summary for {name}`, narrow scope | ✓ (with note) |
| Plain text + sweep sibling templates | Also update source.md / AGENTS / CLAUDE templates | |
| Backtick-escape the placeholder | Keep `<...>` wrapped in backticks | |

**User's choice (free text):** "You decide" — but flagged that anything containing `:` may also cause rendering problems; unsure if backticks help.
**Notes:** Resolved to a plain-text marker with no leading `>`, no angle brackets, and no `:`. Scope kept narrow to the entity `summary:` placeholder.

---

## Golden-fixture rebaseline

| Option | Description | Selected |
|--------|-------------|----------|
| Regenerate affected goldens in-phase | Rebaseline from the fixed generator | ✓ |
| Targeted hand-edits to fixtures | Manually edit changed lines | |
| You decide per fixture | Defer to planner/executor | |

**User's choice:** Regenerate affected goldens in-phase.

---

## Claude's Discretion

- Exact final marker strings for Related (#1) and summary (#2), within the no-`>`/no-`<>`/no-`:` constraint.
- Whether suite kind renders as `integration` or abbreviated `int` in node names.
- Regenerate-vs-edit per individual fixture where wholesale regeneration is awkward.

## Deferred Ideas

- Dynamic `## Related` population from curated concept/ADR/architecture backlinks (via graph nodes for non-entity pages, or a filesystem wikilink-backlink index) — future phase.
- Graph-edge relations (`depends_on`/domains/dependencies) in Related — judged redundant with frontmatter + index nesting; not pursued.
