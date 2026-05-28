---
phase: 56-entity-templates-scan-time-population
plan: 02
subsystem: wiki-io
tags: [entity-templates, migration, two-token-rule]
requires: []
provides:
  - "{{var}} token contract for Plan 01 substitution"
  - "filled entity-<kind>.md templates with migrated prose"
affects:
  - packages/wiki-io/src/wiki_io/assets/page-templates/
tech-stack:
  added: []
  patterns:
    - "D-01 two-token rule: {{var}} = scanner-substituted data; <...> = retained authoring instruction"
    - "D-12 TODO convention: visible `> TODO: <instructions>` blockquote"
key-files:
  created: []
  modified:
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-domain.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-dependency.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-repository.md
    - packages/wiki-io/src/wiki_io/assets/page-templates/entity-test-suite.md
    - packages/wiki-io/tests/test_entity_templates.py
key-decisions:
  - "Per-kind H1 token chosen: {{package_name}}, {{app_name}}, {{domain_name}}, {{plugin_name}}, {{dependency_name}}, {{repository_name}}, {{test_suite_name}}"
  - "Token contract for Plan 01 = those 7 per-kind name tokens + pre-existing {{PACKAGE_SLUG}} (entity-test-suite)"
  - "Honored precise <done> D-09 criterion (no testing *section* in package/app) over the plan's overly-broad `! grep -q test` <verify>, which matched the structural `test_suites:` frontmatter field"
requirements-completed: [ENTITY-01, ENTITY-02]
duration: 12 min
completed: 2026-05-28
---

# Phase 56 Plan 02: Fill Entity Templates Summary

Filled the 7 existing `entity-<kind>.md` templates with curated prose migrated from the
legacy `{package,domain,plugin,app}/overview.md` (+ `app/testing.md`), converted each
data-bearing body H1 from an angle placeholder to a `{{..._name}}` data token (D-01), and
extended `test_entity_templates.py` with H1-token / migrated-section / D-09 assertions.

**Duration:** ~12 min | **Tasks:** 3 | **Files:** 8 modified

## What was built

- **Task 1** — Converted the body H1 in all 7 templates: `# <Package Name>` → `# {{package_name}}`,
  and the analogous per-kind tokens for app/domain/plugin/dependency/repository/test-suite.
  Instruction-style `<...>` angles (links, flow names, `<command>`, `<file>`) were left intact
  per D-01. `entity-test-suite.md`'s pre-existing `{{PACKAGE_SLUG}}` preserved.
- **Task 2** — Migrated curated sections (D-08): package Purpose/Public API/Key patterns/Conventions
  → entity-package; app Purpose/Platform & runtime/Entry points/Routes/Provider chain → entity-app;
  domain Scope/Contained packages/Key flows → entity-domain; a single coherent Purpose/usage →
  entity-plugin. The `plugin/overview.md` Purpose+testing duplication was dropped (D-08). ALL
  testing prose routed to `entity-test-suite.md` only (D-09). Authoring-needed sections render as
  `> TODO: <instructions>` blockquotes (D-11/D-12). entity-dependency/entity-repository got only
  the Task-1 H1 conversion (no legacy source to migrate).
- **Task 3** — Added 4 test groups: each body H1 is a `# {{..._name}}` token with no surviving
  `# <...>` H1; entity-package has migrated Purpose/Conventions; entity-app has Platform & runtime;
  entity-test-suite owns the testing sections; no testing section leaked into package/app.

## Token contract (consumed by Plan 01)

Plan 01's substitution variable-builder MUST cover every one:
`{{package_name}}`, `{{app_name}}`, `{{domain_name}}`, `{{plugin_name}}`, `{{dependency_name}}`,
`{{repository_name}}`, `{{test_suite_name}}` — plus the pre-existing `{{PACKAGE_SLUG}}` token in
entity-test-suite.md. Any `{{var}}` without a node value must get a D-03 `> TODO:` fallback.

## Deviations from Plan

- **[Rule 1 - Spec ambiguity] D-09 verify-check breadth** — Found during: Task 2 acceptance gate.
  The plan's Task 2 `<verify>` block included `! grep -q 'test' entity-package.md`, which matches
  the structural `test_suites: []` frontmatter field (a graph relationship key, not testing prose),
  while Task 2 explicitly forbids touching template frontmatter. Resolved by honoring the precise
  `<done>` criterion — "no testing *section*" via `grep -i 'how to run\|test conventions'` returns
  nothing — which passes. The intent (no testing-derived section leaks into package/app, D-09) is
  fully satisfied; only the over-broad literal substring check was reinterpreted.
  Verification: `grep -i 'how to run|test conventions' entity-package.md entity-app.md` → empty.

**Total deviations:** 1 reinterpreted (spec ambiguity, no behavior change). **Impact:** none — D-09
intent satisfied; frontmatter untouched as the plan required.

## Issues Encountered

None.

## Next Phase Readiness

Ready for 56-01 (scanner `{{...}}` substitution) — the token contract above is the input it must
satisfy. Phase complete after Wave 2 (56-01 substitution, 56-03 legacy deletion).

## Self-Check: PASSED

- `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_templates.py -q` → 28 passed
- `grep -l '^# <' entity-*.md` → none (no data-bearing angle H1 survives)
- All 7 templates have a `# {{..._name}}` H1
- entity-plugin.md has a single Purpose section, no testing prose
- Commits present: `git log --grep="56-02"` → 3 task commits (feat/feat/test)
