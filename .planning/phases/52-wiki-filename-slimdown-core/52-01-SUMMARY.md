---
phase: 52-wiki-filename-slimdown-core
plan: 01
subsystem: wiki-io
tags: [helper, pure-function, filename-encoding]
requires: []
provides:
  - short_filename
  - _FILENAME_PREFIX_BY_URI_PREFIX
affects:
  - packages/wiki-io
tech-stack:
  added:
    - hashlib (stdlib — sha256-based collision suffix)
  patterns:
    - "pure function w/ caller-supplied collision_set (D-03/D-04)"
    - "kind-aware test_suite naming dispatch (D-07)"
    - "filename-layer alias dependency -> dep (D-05)"
key-files:
  created:
    - packages/wiki-io/tests/test_short_filename.py
  modified:
    - packages/wiki-io/src/wiki_io/entity_writer.py
key-decisions:
  - "Helper is pure: no I/O, no SQL, no logging from inside the body. Fallback warnings (missing suite_kind on test_suite URIs) are the caller's responsibility, per Phase 50 D-04."
  - "Collision suffix is sha256(uri.encode('utf-8')).hexdigest()[:6] — 24 bits, ~16M-distinct collision space per stem."
  - "All colliders carry the suffix (D-04), not just N-1 of them, so the rule is referentially transparent."
  - "test_suite kind-aware prefix mapping: unit -> unit_tests, integration -> int_tests, e2e -> e2e_tests, contract -> contract_tests, None/unknown -> tests."
  - "dependency -> dep is a filename-layer alias only; the URI prefix 'dependency' is unchanged at the graph layer."
requirements-completed: [WIKI-FN-04, WIKI-FN-02]
duration: 0h 12m
completed: 2026-05-28
---

# Phase 52 Plan 01: short_filename Pure Helper + Property Tests Summary

`short_filename(uri, collision_set, *, suite_kind, pkg_for_suite) -> str` is a
pure helper that maps a graph URI to its slim vault filename stem; covers all
seven admitted URI prefixes (repo, pkg, app, domain, plugin, dependency,
test_suite) with a caller-supplied collision_set, kind-aware test_suite
naming, and a sha256-derived 6-hex suffix on collisions (D-03 / D-04).

## What was built

- `packages/wiki-io/src/wiki_io/entity_writer.py`:
  - New top-of-file import: `import hashlib`.
  - New module-level dict `_FILENAME_PREFIX_BY_URI_PREFIX` mapping each URI
    prefix to its filename prefix; `dependency -> dep` is the alias (D-05),
    `test_suite -> tests` is the suite_kind=None fallback (the test_suite
    branch in `short_filename` overrides for known suite_kinds).
  - New function `short_filename` placed after `decode_slug` and before the
    `# Phase 43 Plan 02:` separator. Body:
    1. Raise `ValueError` on empty uri, missing `:` separator, or unknown
       URI prefix.
    2. For `test_suite:` URIs: dispatch on `suite_kind` to one of
       `unit_tests` / `int_tests` / `e2e_tests` / `contract_tests` / `tests`;
       use `pkg_for_suite` or fall back to URI path[-2] / path[-1].
    3. For other URIs: look up the filename prefix from
       `_FILENAME_PREFIX_BY_URI_PREFIX`; concat with `name = path.split("/")[-1]`.
    4. If `uri in collision_set`, append `__<6hex>` where 6hex =
       `sha256(uri.encode()).hexdigest()[:6]`; otherwise return the plain stem.
- `packages/wiki-io/tests/test_short_filename.py` (new):
  - 9 test functions (20 collected after parametrization).
  - Unit cases for each of the 7 URI shapes, all 5 documented suite_kinds +
    unknown fallback, sha256 suffix format, and the 3 ValueError paths.
  - 4 Hypothesis property tests (max_examples=50, deadline=None):
    idempotence, collision-resistance-within-set, suffix-triggering-in-set,
    suffix-absence-when-not-in-set.

Duration: 12 min. Files modified: 2. Tasks: 2.

Start: 2026-05-28T03:59:00Z
End:   2026-05-28T04:11:00Z

## Verification results

| Check | Command | Result |
|-------|---------|--------|
| New tests pass | `uv run --package wiki-io pytest packages/wiki-io/tests/test_short_filename.py -v` | 20 passed in 0.28s |
| No regression in legacy | `uv run --package wiki-io pytest packages/wiki-io/tests/test_entity_writer.py -x` | 43 passed in 4.77s |
| Importability | `uv run --package wiki-io python -c "from wiki_io.entity_writer import short_filename, encode_slug, decode_slug; print('all importable')"` | `all importable` |
| Source markers (`import hashlib`, `def short_filename`, `_FILENAME_PREFIX_BY_URI_PREFIX`, legacy `encode_slug`/`decode_slug`) | grep | all 5 markers present |
| ValueError on empty | CLI check | raises with "empty uri" |
| ValueError on missing `:` | CLI check | raises with "malformed" |
| ValueError on unknown prefix | CLI check | raises with "unknown uri prefix" |

## Deviations from Plan

None - plan executed exactly as written.

**Total deviations:** 0. **Impact:** none.

## Issues Encountered

None.

## Next Phase Readiness

Ready for Plan 52-02: `_compute_collision_set` + `write_entities` integration
+ `dependency -> dep` URI alias (graph layer) + integration tests. The pure
helper this plan ships is the function 52-02 will wire into the write path,
and the property test surface guards regressions during the write-path
integration.

## Self-Check: PASSED

- All `<acceptance_criteria>` from both tasks: PASS
- All `<verification>` commands from the plan: PASS
- `key-files.created` exist on disk: `packages/wiki-io/tests/test_short_filename.py` ✓
- `git log --oneline --grep="52-01"` returns 2 commits (`feat(52-01)` + `test(52-01)`).
