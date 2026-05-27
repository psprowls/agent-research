---
phase: 42
plan: 02
subsystem: graph-io, wiki-io
tags: [uri-builders, page-templates, mechanical]
requires: []
provides:
  - graph_io.uri.package_family_uri
  - graph_io.uri.plugin_uri
  - graph_io.uri.dependency_uri
  - 7 entity-*.md templates
affects:
  - packages/graph-io/src/graph_io/uri.py
  - packages/graph-io/tests/test_uri.py
  - packages/wiki-io/src/wiki_io/assets/page-templates/entity-*.md
tech-stack: {}
key-files:
  created:
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-repository.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-domain.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-package-family.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-dependency.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-test-suite.md
  modified:
    - packages/graph-io/src/graph_io/uri.py
    - packages/graph-io/tests/test_uri.py
key-decisions:
  - test_uri.py already existed; 4 new-builder tests appended (no duplicate coverage of the 7 existing builders).
  - Template body sections kept minimal per kind — single-bullet placeholders rather than tabular skeletons. Phase 43+ may extend during real-page authoring.
requirements-completed:
  - URI-03
duration: ~10 min
completed: 2026-05-27
---

# Phase 42 Plan 02: URI Builders + 7 Entity Templates

Provisioned the three new v1.8 URI builders in `graph_io.uri` and authored seven `entity-*.md` page templates under `packages/wiki-io/src/wiki_io/assets/page-templates/`, one per admitted kind. Mechanical authoring — no design departures.

## What was built

- `packages/graph-io/src/graph_io/uri.py`: 3 functions appended (`package_family_uri`, `plugin_uri`, `dependency_uri`). Each is a single-line f-string per D-04; no `RepoContext` parameter (concept-level kinds are not repo-scoped).
- `packages/graph-io/tests/test_uri.py`: 4 new tests appended (existing file). Total file count: 23 tests passing.
- 7 new templates under `packages/wiki-io/src/wiki_io/assets/page-templates/`. Each carries:
  - YAML frontmatter with `kind:` in underscore-form (D-02 / D-18)
  - All scanner-owned keys for that kind, populated as empty placeholders
  - H1 title
  - `## Narrative` H2 placeholder per D-16
  - Per-kind canonical H2 sections per the D-17 table

## Path reconciliation

REQUIREMENTS.md URI-03 and ROADMAP.md success criterion #3 reference `wiki_io/templates/entities/`; this plan honors CONTEXT.md D-17 (locked decisions are source of truth) and writes to `packages/wiki-io/src/wiki_io/assets/page-templates/`. Plan 03 propagates the corrected paths back to REQUIREMENTS.md and ROADMAP.md.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- [x] 3 new URI builders return the expected strings (test_uri.py green).
- [x] 7 entity-*.md templates exist; inline frontmatter validator returns `OK 7 templates, all kinds covered, all have ## Narrative`.
- [x] Every template's `kind:` value is in ADMITTED_KINDS.
- [x] Every template has a `## Narrative` H2 section (no HTML-comment sentinels).
- [x] No regressions: `uv run pytest -x` in graph-io exits 0 (330 passed, 1 skipped, 1 xfailed).

## Next

Ready for **42-03** (Wave 2 — depends on both 42-01 and 42-02).
