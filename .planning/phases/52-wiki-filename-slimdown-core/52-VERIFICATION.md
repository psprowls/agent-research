---
phase: 52-wiki-filename-slimdown-core
verified: 2026-05-28T04:35:00Z
mode: initial
status: passed
truths:
  total: 4
  verified: 4
  failed: 0
  uncertain: 0
artifacts:
  total: 5
  verified: 5
  stub: 0
  missing: 0
key_links:
  total: 4
  verified: 4
  partial: 0
  not_wired: 0
requirements:
  total: 4
  satisfied: 4
  blocked: 0
  needs_human: 0
overrides:
  - must_have: "Roadmap SC#3: only the collider receives a hash suffix; the non-colliding entity keeps the plain short name"
    reason: "Locked decision D-04 in 52-CONTEXT.md — symmetric all-colliders-get-suffix is the only way to keep `short_filename(uri, collision_set)` a pure idempotent function. A winner/loser tiebreaker breaks idempotence-across-time: adding a 3rd colliding URI later would shift which existing entity has the plain name, causing a vault-wide file-rename storm. The roadmap SC#3 wording is honored for non-colliding entities (the vast majority); only entities in a collision set deviate, and the deviation is locally symmetric and globally stable. Discussion-log explicitly accepted."
    accepted_by: "Pat (CONTEXT.md D-04)"
    accepted_at: "2026-05-27T20:13:00Z"
human_verification:
  - "SC#1 manual smoke check (optional): running a real `cg scan` of the workspace would produce `wiki/entities/app_graph-wiki-agent.md` because Phase 50 classifies graph-wiki-agent as an app. Verified end-to-end via synthesized fixtures (test_write_entities_short_filenames + test_write_entities_renders_app_pages); the literal cg-scan smoke check is documented in 52-VALIDATION.md as manual and remains optional."
---

# Phase 52: Verification Report

**Verified:** 2026-05-28T04:35:00Z
**Mode:** initial
**Status:** passed

## Summary

Phase 52 delivers all 4 Roadmap Success Criteria and all 4 requirements
(WIKI-FN-01 / WIKI-FN-02 / WIKI-FN-03 / WIKI-FN-04). One documented divergence
from the strict reading of SC#3 (symmetric vs. winner/loser collision-suffix
semantics) is accepted via an override pointing to CONTEXT.md D-04 — the
symmetric semantics are required for `short_filename` to remain a pure
idempotent function.

The Phase 50 → Phase 52 chain now produces SC#1's literal
`app_graph-wiki-agent.md` output for synthesized fixtures (a real `cg scan`
would too, given that Phase 50 admitted the `app` kind into `graph-io` and
Phase 52 admitted it into `wiki-io`).

## Truths

### T-1: `write_entities()` on a fresh vault produces short-form filenames

**Status:** ✓ VERIFIED

**Evidence:**
- `packages/wiki-io/tests/test_entity_writer.py::test_write_entities_short_filenames` exercises one node per admitted kind and asserts the documented 6 short-form filenames on disk (`repo_test-repo.md`, `pkg_widget.md`, `domain_observability.md`, `plugin_demo-plugin.md`, `dep_example-lib.md`, `unit_tests_widget.md`).
- `packages/wiki-io/tests/integration/test_entity_writer_integration.py` builds a synthetic workspace via `graph_io.upsert`, runs `write_entities`, and asserts the 5 expected short-form filenames on disk (`pkg_pkg-a.md`, `pkg_pkg-b.md`, `dep_boto3.md`, `plugin_graph-wiki.md`, `repo_fixture.md`).

### T-2: Test-suite entities use kind-aware short filenames

**Status:** ✓ VERIFIED

**Evidence:**
- `test_short_filename.py::test_suite_kind_dispatch` parametrizes all 5 documented suite_kinds + unknown fallback and asserts the prefix (unit → unit_tests, integration → int_tests, e2e → e2e_tests, contract → contract_tests, None/unknown → tests).
- `test_write_entities_short_filenames` end-to-end produces `unit_tests_widget.md` from a `test_suite:` URI with `suite_kind=unit`.
- `entity_writer.py:286` dispatches via `kind_prefix_by_suite.get(suite_kind, "tests")`.
- `entity_writer.py:737-754` reads `suite_kind` from `node.attrs["suite_kind"]` and `pkg_for_suite` from `Path(attrs["path"]).parent.name` inside `write_entities`.

### T-3: Cross-org collision produces deterministic hash suffix

**Status:** ✓ VERIFIED (with override on the "winner/loser" wording — see frontmatter)

**Evidence:**
- `test_short_filename.py::test_collision_suffix_format` asserts the suffix is exactly `sha256(uri).hexdigest()[:6]` for a known URI.
- `test_entity_writer.py::test_write_entities_cross_org_collision` builds two `pkg:` nodes from different orgs with the same trailing name, runs `write_entities`, and asserts BOTH files exist with the `__<6hex>` suffix; assert `pkg_utils.md` plain stem does NOT exist (D-04 symmetric).
- `test_short_filename.py::test_collision_resistance_within_set` (Hypothesis, 50 examples) asserts distinct URIs in the same collision_set always produce distinct filenames.

**Override:** Locked decision D-04 (CONTEXT.md) — symmetric all-colliders-get-suffix replaces the roadmap SC#3 "only collider gets suffix; non-collider keeps plain name" wording. Required for `short_filename` to remain a pure idempotent function. Non-colliding entities still keep the plain short name (the vast majority).

### T-4: `short_filename(uri, collision_set)` is a pure function with property tests for idempotence + collision-resistance

**Status:** ✓ VERIFIED

**Evidence:**
- `packages/wiki-io/src/wiki_io/entity_writer.py:209-305` defines `short_filename` with no I/O, no SQL, no logging from inside the body. Fallback warnings live at the call site in `write_entities`.
- `test_short_filename.py::test_idempotence` (Hypothesis, 50 examples) asserts `short_filename(u, S, **k) == short_filename(u, S, **k)`.
- `test_short_filename.py::test_collision_resistance_within_set` (Hypothesis, 50 examples) asserts distinct URIs in a shared collision_set produce distinct outputs.
- `test_short_filename.py::test_suffix_triggering_in_set` and `test_suffix_absence_when_not_in_set` (Hypothesis, 50 examples each) round out the property surface.

## Artifacts

### A-1: `short_filename` pure helper + `_FILENAME_PREFIX_BY_URI_PREFIX` dict

**Path:** `packages/wiki-io/src/wiki_io/entity_writer.py:194-305`
**Status:** ✓ VERIFIED (exists, substantive, wired, data flows)
**Evidence:** Imported by `test_short_filename.py` and (after Plan 02) by `write_entities` at the same module.

### A-2: `_compute_collision_set` internal pre-pass helper

**Path:** `packages/wiki-io/src/wiki_io/entity_writer.py:646-705`
**Status:** ✓ VERIFIED (exists, substantive, wired)
**Evidence:** Called once by `write_entities` (line 711) before the lock-held write block. Returns `frozenset[str]` of colliding URIs; threaded into every `short_filename` call site inside the per-entity loop.

### A-3: `write_entities` integration (encode_slug call site replaced)

**Path:** `packages/wiki-io/src/wiki_io/entity_writer.py:708-816`
**Status:** ✓ VERIFIED
**Evidence:** `grep -n "slug = encode_slug" packages/wiki-io/src/wiki_io/entity_writer.py` returns zero matches inside `write_entities`. `grep -n "slug = short_filename" packages/wiki-io/src/wiki_io/entity_writer.py` returns exactly 1 match (line 747).

### A-4: `entity-app.md` template

**Path:** `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md`
**Status:** ✓ VERIFIED (exists, substantive, wired)
**Evidence:** `_template_path_for_kind("app").exists()` is True (verified by `test_entity_app_template_exists`). Frontmatter `kind: app`; body has `## Narrative` at column 0 (Phase 42 D-16).

### A-5: `app` admission in ADMITTED_KINDS + URI prefix dict + list_fn dispatch + scanner_frontmatter branch

**Path:** `packages/wiki-io/src/wiki_io/entity_writer.py:66-101, 561, 604-617`
**Status:** ✓ VERIFIED
**Evidence:** `'app' in ADMITTED_KINDS` is True; `_URI_PREFIX_BY_KIND['app'] == 'app'`; `_kind_list_fns()['app']` dispatches to `_queries.list_apps`; `scanner_frontmatter_for_node` has an `elif kind == 'app':` branch calling `_queries.describe_app` and surfacing all AppDescription fields including `app_kind` + `app_signals`.

## Key Links

### KL-1: `tests/test_short_filename.py → wiki_io.entity_writer.short_filename`

**Status:** ✓ WIRED
**Pattern:** `from wiki_io.entity_writer import short_filename` (verified by grep).

### KL-2: `write_entities → short_filename`

**Status:** ✓ WIRED
**Evidence:** Per-entity loop body in `write_entities` (line 747) calls `short_filename(uri, collision_set, suite_kind=..., pkg_for_suite=...)`.

### KL-3: `write_entities → _compute_collision_set`

**Status:** ✓ WIRED
**Evidence:** Line 711 of `entity_writer.py` — `collision_set = _compute_collision_set(conn, admitted_kinds, list_fns)` called once before the lock-held write block.

### KL-4: `_template_path_for_kind("app") → packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md`

**Status:** ✓ WIRED
**Evidence:** `importlib.resources` lookup pattern verified by `test_entity_app_template_exists`.

## Requirements Coverage

| ID | Description | Status | Evidence |
|----|-------------|--------|----------|
| WIKI-FN-01 | Short, human-readable entity filenames | ✓ SATISFIED | T-1 (write_entities short-form test) + cross-org collision test + dep alias test all pass |
| WIKI-FN-02 | Test-suite kind-aware naming | ✓ SATISFIED | T-2 (5 suite_kinds + unknown fallback all asserted at function + integration levels) |
| WIKI-FN-03 | Deterministic collision suffix on disk | ✓ SATISFIED | T-3 (cross-org collision test + Hypothesis property test) |
| WIKI-FN-04 | `short_filename` pure function + property tests | ✓ SATISFIED | T-4 (4 Hypothesis properties + signature + purity) |

## Test Suite Results

| Suite | Command | Result |
|-------|---------|--------|
| Plan 52-01 property tests | `pytest packages/wiki-io/tests/test_short_filename.py -v` | 20 passed |
| wiki-io full suite | `pytest packages/wiki-io/tests/` | 366 passed, 2 skipped, 1 xfailed |
| Full repo suite (regression gate) | `pytest packages/` | 1187 passed, 28 skipped, 2 xfailed |

## Code Review Cross-Reference

See `52-REVIEW.md`. One Warning (WR-01) and two Info findings; no Critical
issues. WR-01 describes the known transition-period inconsistency
(`link_rewriter.py` + `index_generator.py` still call `encode_slug` per
CONTEXT.md D-09 / Phase 53 deferral) and is explicitly out of Phase 52 scope.

## Issues

None.

## Verdict

**PASSED.** All 4 Success Criteria verified. All 4 requirements satisfied.
SC#3's strict wording is overridden by locked decision D-04 in CONTEXT.md
(symmetric all-colliders-get-suffix is required for `short_filename` to
remain pure and time-stable).
