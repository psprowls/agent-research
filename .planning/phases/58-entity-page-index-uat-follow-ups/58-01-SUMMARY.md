---
phase: 58-entity-page-index-uat-follow-ups
plan: "01"
subsystem: wiki-io
tags: [wiki-io, entity-templates, entity-writer, obsidian, markdown, placeholders]

# Dependency graph
requires: []
provides:
  - "Clean ## Related blocks in entity-package, entity-app, entity-plugin templates (no <...> wikilinks)"
  - "Obsidian-safe summary placeholder in entity_writer.py (no >, no <, no :)"
affects: [58-02, 58-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Template Related blocks use plain-text fill-me-in sentence, not placeholder wikilinks"
    - "Summary placeholder uses plain f-string, not blockquote-prefixed angle-bracket text"

key-files:
  created: []
  modified:
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md
    - packages/wiki-io/src/wiki_io/entity_writer.py
    - packages/wiki-io/tests/test_entity_writer.py

key-decisions:
  - "Related block placeholder: 'No related concept, ADR, or architecture pages yet.' — single sentence, no bullets, no angle brackets"
  - "Summary placeholder: 'TODO add a one-line summary for {name}' — no leading >, no angle brackets, no colon"

patterns-established: []

requirements-completed: []

# Metrics
duration: 3min
completed: "2026-05-29"
---

# Phase 58 Plan 01: Entity Template & Summary Placeholder Cleanup Summary

**Replaced dead `<...>` placeholder wikilinks in three entity page ## Related blocks and fixed the Obsidian-blockquote-breaking summary f-string in entity_writer.py**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-29T02:47:38Z
- **Completed:** 2026-05-29T02:51:37Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Three entity page templates (entity-package.md, entity-app.md, entity-plugin.md) now have clean `## Related` blocks with a single plain-text fill-me-in sentence instead of bullet lists with `[[concepts/<concept>]]` style placeholder wikilinks
- `entity_writer.py` line 587 f-string changed from `"> TODO: <add a one-line summary for {name}>"` to `"TODO add a one-line summary for {name}"` — no leading `>`, no `<...>`, no `:`
- Test assertion at `test_entity_writer.py:482` updated to match the new plain-text marker; all 375 wiki-io tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace ## Related placeholder block in three entity templates (Item #1)** - `84b7811` (fix)
2. **Task 2 (RED): Update test assertion to new placeholder string** - `a2fe273` (test)
3. **Task 2 (GREEN): Replace summary placeholder f-string** - `ed29262` (feat)

**Plan metadata:** (see final commit below)

_Note: TDD task 2 produced two commits — test assertion update (RED) then source change (GREEN)_

## Files Created/Modified
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md` - ## Related block: bullet list replaced with plain-text marker
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` - ## Related block: bullet list replaced with plain-text marker
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md` - ## Related block: bullet list replaced with plain-text marker
- `packages/wiki-io/src/wiki_io/entity_writer.py` - line 587: summary f-string placeholder made Obsidian-safe
- `packages/wiki-io/tests/test_entity_writer.py` - line 482: exact-string assertion updated to new marker

## Decisions Made
- Plain-text sentence `No related concept, ADR, or architecture pages yet.` chosen for Related blocks — no bullets, no wikilinks, no angle brackets, no colon per D-02
- `TODO add a one-line summary for {name}` chosen for summary placeholder — preserves the human-readable intent without any Obsidian-rendering footguns
- Scope strictly limited to three entity templates (entity-package, entity-app, entity-plugin) and one source line per D-03/D-05; entity-test-suite.md and entity-dependency.md untouched

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

TDD RED note: the existing `test_merge_summary_todo_marker_when_description_empty` test constructs the `todo` string locally and passes it directly into `merge_frontmatter` as `scanner_update["summary"]`, so updating the assertion string automatically made the test pass (merge_frontmatter is a passthrough for non-owned keys). The test is semantically correct — it verifies the new marker round-trips cleanly through the merge function. The source change at line 587 is the companion fix that ensures `entity_writer` itself emits the correct string at write-time. Both changes are necessary and the gate is satisfied.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- All three entity page templates now generate clean Related blocks on next scan
- Summary placeholder renders cleanly in Obsidian (no spurious blockquote)
- Plan 58-02 (graph edge-derived Related section) and Plan 58-03 (snapshot rebaseline) can proceed on this clean foundation
- 375 wiki-io tests green (2 skipped gated by GRAPH_WIKI_RUN_INTEGRATION, 1 xfailed — all expected)

## Threat Flags

None — changes are static template text and an f-string constant; no new attack surface.

## Self-Check: PASSED

- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md` — exists, ## Related contains clean marker
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` — exists, ## Related contains clean marker
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md` — exists, ## Related contains clean marker
- `packages/wiki-io/src/wiki_io/entity_writer.py` — line 587 has plain-text marker
- `packages/wiki-io/tests/test_entity_writer.py` — assertion updated, all 375 tests pass
- Commits: 84b7811, a2fe273, ed29262 all exist

---
*Phase: 58-entity-page-index-uat-follow-ups*
*Completed: 2026-05-29*
