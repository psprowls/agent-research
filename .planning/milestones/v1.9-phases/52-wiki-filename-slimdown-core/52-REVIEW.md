---
phase: 52-wiki-filename-slimdown-core
reviewed: 2026-05-28T04:30:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md
  - packages/wiki-io/src/wiki_io/entity_writer.py
  - packages/wiki-io/tests/conftest.py
  - packages/wiki-io/tests/integration/test_entity_writer_integration.py
  - packages/wiki-io/tests/test_entity_templates.py
  - packages/wiki-io/tests/test_entity_writer.py
  - packages/wiki-io/tests/test_short_filename.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 52: Code Review Report

**Reviewed:** 2026-05-28T04:30:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 52 wires `short_filename` into `wiki_io.entity_writer`'s write path, adds
the `app` kind admission, and flips the `dependency → dep` filename-layer alias.
The implementation is tight: the pure helper is well-documented, has
property-based tests, and the integration follows the same pattern as Phase
50's classification pre-pass.

One transition-period concern crosses the phase boundary: `index_generator.py`
and `link_rewriter.py` still call `encode_slug` (legacy long-form), so their
emitted links now point at filenames the writer no longer produces. The plan
explicitly defers this to Phase 53; flagged here as a Warning so the gap is
tracked.

Two minor info items: an asymmetric `_ADMITTED_URI_PREFIXES` derivation after
the dep alias flip, and a stylistic redundant-None-check in
`_compute_collision_set`.

## Warnings

### WR-01: Index + link rewriter emit stale long-form references to non-existent files

**File:** `packages/wiki-io/src/wiki_io/index_generator.py:417,425,430,499`
and `packages/wiki-io/src/wiki_io/link_rewriter.py:246`

**Issue:** After Phase 52, `write_entities` writes entity pages at short-form
filenames (`pkg_widget.md`, `dep_boto3.md`, `app_demo-app.md`). However,
`index_generator.py` and `link_rewriter.py` still call `encode_slug(uri)` to
build wikilinks:

- `index_generator.py:417`: `pkg_link = f"[[wiki/entities/{encode_slug(pkg.uri)}]]"`
- `link_rewriter.py:246`: `return f"entities/{_encode_slug(uri)}"`

These will produce broken wikilinks pointing at long-form filenames that no
longer exist on disk (e.g. `wiki/entities/pkg__org__repo__widget` instead of
`wiki/entities/pkg_widget`). The vault will be left in a state where the
top-level index and rewritten links don't resolve to actual entity files.

The phase planning explicitly defers this to Phase 53 (CONTEXT.md D-09:
"encode_slug + decode_slug function bodies are not deleted; Phase 53 transient
use"), and the orphaned long-form files from prior scans aren't deleted in
Phase 52 either. The vault is therefore in a known-inconsistent transitional
state between Phase 52 ship and Phase 53 ship.

**Fix:** No source change in Phase 52 scope. Phase 53 plan should:

1. Update `link_rewriter.py:246` and the four `index_generator.py` call sites
   to take a `collision_set` and call `short_filename` instead of
   `encode_slug`. This requires passing `collision_set` from the orchestrator
   (already computed in `write_entities`) into both modules.
2. Add a one-shot vault sweep that removes orphan long-form files
   (`*__*.md` patterns matching `_ADMITTED_URI_PREFIXES` followed by `__`).
3. Optionally rewrite existing vault wikilinks via the link_rewriter pipeline
   so prior human-authored content keeps working.

Track this as a hard prerequisite before Phase 53 ships.

## Info

### IN-01: `_FILENAME_PREFIX_BY_URI_PREFIX` and `_URI_PREFIX_BY_KIND` use different alias semantics

**File:** `packages/wiki-io/src/wiki_io/entity_writer.py:82-101,194-206`

**Issue:** `_URI_PREFIX_BY_KIND` (used by `decode_slug`) maps
`"dependency" -> "dep"` (alias). `_FILENAME_PREFIX_BY_URI_PREFIX` (used by
`short_filename`) also maps `"dependency" -> "dep"`. These are two
independent dicts that happen to encode the same alias, but they're not
linked — a future change that updates one without the other (e.g. introduces
a new kind with an alias) would create a silent divergence.

`_ADMITTED_URI_PREFIXES = frozenset(_URI_PREFIX_BY_KIND.values())` is
derived from the first dict, so `decode_slug` validates against `dep` but
not against `dependency`. Legacy `dependency__*` slugs from pre-Phase-52
vaults can no longer be decoded — already noted in 52-02-SUMMARY deviations
and exercised in the narrowed `test_slug_round_trip` hypothesis strategy.

**Fix:** Phase 53 can consolidate these into a single source-of-truth by
deriving `_URI_PREFIX_BY_KIND` from `_FILENAME_PREFIX_BY_URI_PREFIX` (or
vice versa) after the cutover sweep. For Phase 52, the duplication is
acceptable because the two dicts serve distinct call sites (legacy
`decode_slug` vs. new `short_filename`) and consolidating them now would
either break decode_slug for existing vaults or require a behavior change
in encode_slug — both out of scope.

### IN-02: Redundant `or None` guard in `_compute_collision_set`

**File:** `packages/wiki-io/src/wiki_io/entity_writer.py:686-690`

**Issue:** The guard reads:

```python
pkg_for_suite: str | None = None
if suite_path:
    pkg_for_suite = Path(suite_path).parent.name or None
if not pkg_for_suite:
    pkg_for_suite = None
```

The first `or None` on line 688 already converts empty-string to `None`, so
the `if not pkg_for_suite: pkg_for_suite = None` on lines 689-690 is a
no-op for the empty-string case. It would only trigger if
`Path(suite_path).parent.name` returned a falsy non-None value other than
`""` (impossible — pathlib's `.name` always returns a string), or if the
initial `None` somehow flipped to a different falsy value (also impossible).

The corresponding block in `write_entities` (lines ~742-748) doesn't
include the second guard, so this is also a minor style inconsistency
between the two call sites.

**Fix:** Remove the redundant guard:

```python
pkg_for_suite: str | None = None
if suite_path:
    pkg_for_suite = Path(suite_path).parent.name or None
stem = short_filename(uri, frozenset(), suite_kind=suite_kind, pkg_for_suite=pkg_for_suite)
```

Non-blocking; the redundant check is harmless and slightly defensive.

---

_Reviewed: 2026-05-28T04:30:00Z_
_Reviewer: Claude Opus 4.7 (inline gsd-code-reviewer, runtime lacked Agent dispatch)_
_Depth: standard_
