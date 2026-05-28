---
phase: 56-entity-templates-scan-time-population
plan: 01
subsystem: wiki-io
tags: [scan, substitution, summary, entity-writer]
requires:
  - "Plan 02 token contract (per-kind {{<kind>_name}} + {{PACKAGE_SLUG}})"
  - "Plan 04 graph-io attrs[description] source"
provides:
  - "SCAN-01: {{...}} body substitution in _render_entity_page"
  - "SCAN-02: fill-when-empty summary derived from node description"
affects:
  - packages/wiki-io/src/wiki_io/entity_writer.py
tech-stack:
  added: []
  patterns:
    - "literal str.replace substitution (no Jinja); residual-token -> TODO marker"
    - "fill-when-empty merge category (third category beyond scanner-owned/human-owned)"
key-files:
  created: []
  modified:
    - packages/wiki-io/src/wiki_io/entity_writer.py
    - packages/wiki-io/tests/test_entity_writer.py
    - packages/wiki-io/tests/integration/test_entity_writer_integration.py
key-decisions:
  - "_render_entity_page signature: added variables: dict[str,str] 3rd arg; updated 2 existing render tests to pass {} (byte-stable, no token)"
  - "Variable map built at write_entities call site: {kind}_name <- node.name, package_slug/PACKAGE_SLUG <- slug"
  - "D-03 residual-token fallback uses a module-level regex; the marker STRIPS braces so the marker itself carries no {{ (a bug the new test surfaced)"
  - "summary placed in merge_frontmatter step 2b (right after kind) as fill-when-empty; NOT in SCANNER_OWNED_KEYS (D-07)"
  - "summary read defensively from node.attrs.get('description') so it works (TODO fallback) even independent of Plan 04"
requirements-completed: [SCAN-01, SCAN-02]
duration: 22 min
completed: 2026-05-28
---

# Phase 56 Plan 01: Scanner Token Substitution & Summary Summary

Wired `{{...}}` data-token substitution into entity-page rendering (SCAN-01) and a fill-when-empty
`summary:` derived from the graph node's description (SCAN-02), reusing the existing literal
`str.replace` mechanism — no Jinja, no new dependency.

**Duration:** ~22 min | **Tasks:** 3 | **Files:** 3 modified

## What was built

- **Task 1 — substitution (`_render_entity_page`)** — Added a `variables: dict[str,str]` argument;
  after loading the template body, each `{{key}}` is replaced via `body.replace("{{"+k+"}}", v)`
  (mirroring `init_vault.render_template`). Only `{{...}}` data tokens are substituted; `<...>`
  instruction placeholders are never touched (D-01 two-token rule, commented at the site). A
  module-level `_RESIDUAL_TOKEN_RE` rewrites any unmapped `{{...}}` to a visible
  `> TODO: <add value for ...>` marker (D-03/D-12) so no raw `{{...}}` survives. The variable map
  is built at the `write_entities` call site from `node.name` (per-kind `{{<kind>_name}}`) and the
  `slug` (`{{package_slug}}` / `{{PACKAGE_SLUG}}`). Two existing render tests were updated to the
  new 3-arg signature with `variables={}` (their fixtures have no tokens — byte-identical, intent
  unchanged).
- **Task 2 — summary derivation + merge (`entity_writer.py`)** — `scanner_frontmatter_for_node`
  now emits `summary` for every kind, read uniformly from `node.attrs.get("description")` with a
  TODO-marker fallback when empty/absent (D-05/D-03). `merge_frontmatter` gained a step-2b
  fill-when-empty special-case (right after `kind`): a non-empty existing summary is preserved
  verbatim (human edit survives re-scan), otherwise the scanner value fills it (D-07). `summary`
  is intentionally NOT in `SCANNER_OWNED_KEYS`; both behaviors are commented to prevent a future
  reader collapsing it into the scanner-owned set.
- **Task 3 — tests** — Unit: substitution + `<...>` retention; D-03 TODO-fallback (no `{{`
  survives); merge preserve-human / fill-empty / TODO-marker; `summary` not scanner-owned.
  Integration (gated): end-to-end real-workspace assertion that no page body contains `{{` (SCAN-01)
  and every page has a non-empty `summary:` (SCAN-02), with pkg-a's real `[project].description`
  exercising the description-derived path.

## Deviations from Plan

- **[Rule 1 - Bug] D-03 residual-token marker re-emitted `{{`** — Found during: Task 3
  (`test_render_unmapped_token_becomes_todo_marker`). The first implementation built the marker as
  `> TODO: <add value for {{version}}>`, echoing the raw token (braces included) back into the body
  — which itself contains `{{`, defeating SCAN-01's "no `{{` survives" guarantee. Fixed by stripping
  the braces (`m.group(0).strip('{}')`) so the marker carries the bare token name only. Files:
  entity_writer.py. Verification: `assert "{{" not in out` now passes; integration asserts zero
  `{{` across all generated pages. Commit: 155038f.
- **[Rule 1 - Required signature adaptation] two existing render tests** — Found during: Task 1.
  The mandated `_render_entity_page` signature change broke two pre-existing render tests
  (`test_render_entity_page_deterministic_key_order`, `test_render_entity_page_byte_stable_across_runs`)
  that called the old 2-arg form. Updated them to pass `variables={}`; their fixtures contain no
  tokens, so output is byte-identical and the tests' intent (key order / byte-stability) is
  unchanged. Committed with Task 1 (0a956bb).

**Total deviations:** 2 auto-fixed (1 real bug, 1 required signature adaptation). **Impact:** the
bug fix is load-bearing for SCAN-01; the test adaptation is mechanical with no behavior change.

## Issues Encountered

None beyond the deviations above.

## Next Phase Readiness

SCAN-01 and SCAN-02 are satisfied end-to-end. Phase 57 (IDX-03 inline summaries) can now rely on a
populated `summary:` on every entity page. Wave 2 sibling 56-03 (legacy template deletion) remains.

## Self-Check: PASSED

- `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -q` → 44 passed
- Integration SCAN-01+02 test → 1 passed (no `{{` survives, every page has non-empty summary)
- `summary` not in `SCANNER_OWNED_KEYS`
- Commits present: `git log --grep="56-01"` → 3 task commits (feat/feat/test)
