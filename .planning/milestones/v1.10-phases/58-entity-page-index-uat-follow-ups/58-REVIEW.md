---
phase: 58-entity-page-index-uat-follow-ups
reviewed: 2026-05-28T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - packages/graph-io/src/graph_io/test_suites.py
  - packages/graph-io/tests/test_test_suites.py
  - packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md
  - packages/wiki-io/src/wiki_io/assets/page-templates/entity-package.md
  - packages/wiki-io/src/wiki_io/assets/page-templates/entity-plugin.md
  - packages/wiki-io/src/wiki_io/entity_writer.py
  - packages/wiki-io/src/wiki_io/index_generator.py
  - packages/wiki-io/tests/test_entity_writer.py
  - packages/wiki-io/tests/test_index_generator.py
findings:
  critical: 0
  warning: 2
  info: 3
  total: 5
status: issues_found
---

# Phase 58: Code Review Report

**Reviewed:** 2026-05-28
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 58 reworks TestSuite node naming (basename `tests` → qualified `<owner>-<kind>-tests`), switches three index_generator queries plus their callsite threading from name-keyed to URI-keyed test_suite lookups, replaces the `summary:` placeholder marker, and simplifies the `## Related` template stubs.

The core changes are correct and internally consistent with the tests:

- All three `ts.name = ?` → `ts.uri = ?` switches landed (`_compute_qualifying_domains`, `_consumer_pkgs_in_domain`, `_consumer_pkgs`); no `ts.name`-keyed test_suite lookup remains in production code (only doc comments reference `ts.name`).
- The URI threading at the `_place_entities` callsites (lines 369–386) is correct: `uri = node.attrs.get("uri") or ""` is sourced from `_row_to_node`, which folds the `nodes.uri` column back into `attrs["uri"]` for the 6-column `list_*` projection — so `node.attrs.get("uri")` is populated on this path (the MEMORY footgun about `attrs["uri"]` being None applies only to the `describe_*` projections, not `list_test_suites`). test_suite passes `entity_uri=uri`; dependency passes `entity_name=node.name`.
- The `kind_attr` reorder in `test_suites.emit` introduced no unguarded reference: `kind_attr` is computed before its first use in `suite_name`, and `attrs["suite_kind"]` continues to consume it. No `Path(rel_path).name` basename naming remains.
- Template edits are inert: `## Related` is a static H2 with literal prose, carries no `{{...}}` data token, and sits after `## Narrative`, so `inject_narrative` (which stops at the next H2) will not clobber it.
- The `summary` placeholder change is a genuine quality fix (see IN-01).

Two correctness concerns survive, both rooted in name-keyed lookups that the URI migration did NOT cover, plus dead-code and consistency notes.

## Warnings

### WR-01: Same-package dual test directories produce a name collision the SC#3b guard claims is eliminated

**File:** `packages/graph-io/src/graph_io/test_suites.py:339-342, 210`
**Issue:** A single package containing BOTH `tests/` and `__tests__/` (the loop at line 210 iterates `("tests", "__tests__")` and adds a `_TestRoot` for each that exists) yields two suites for the same owner. If both classify to the same `suite_kind` (e.g. both `unit`), `suite_name = f"{r.owner_name}-{kind_attr}-tests"` produces the IDENTICAL name `<pkg>-unit-tests` for both. The same collision is reachable via config-driven `testpaths` (e.g. a `spec/` dir that also classifies `unit` alongside `tests/` for the same owner).

This directly violates the SC#3b invariant the phase advertises — `test_test_suites.py::test_suite_names_unique_after_multi_package_emit` asserts `GROUP BY name HAVING COUNT(*) > 1` returns `[]`, but that fixture only builds ONE test dir per package, so it never exercises the dual-dir case. The nodes themselves stay distinct (keyed by `(kind, name, path)` and unique `uri`), and the URI-keyed index lookups are safe, but the documented uniqueness guarantee is false for this input.

**Fix:** Either incorporate the path discriminator into the name when a collision is possible, or assert/dedupe at emit time. Minimal disambiguation:
```python
# after computing suite_name for package-owned suites, ensure uniqueness
if r.owner_kind != "repository":
    base = f"{r.owner_name}-{kind_attr}-tests"
    # disambiguate when the same (owner, kind) recurs across multiple dirs
    suite_name = base if base not in _seen_suite_names else f"{base}-{Path(r.rel_path).name}"
    _seen_suite_names.add(suite_name)
```
Alternatively, add a regression test that seeds both `tests/` and `__tests__/` for one package and asserts unique names, then fix to make it pass.

### WR-02: `describe_test_suite` is still name-keyed and is now ambiguous under the new naming

**File:** `packages/wiki-io/src/wiki_io/entity_writer.py:619` (callsite); `packages/graph-io/src/graph_io/queries.py:727-738` (lookup)
**Issue:** `scanner_frontmatter_for_node` calls `describe_test_suite(conn, suite_name=node.name)`, which executes `SELECT ... WHERE kind='test_suite' AND name = ?` with no `LIMIT` discriminator on path/uri. The phase migrated the index_generator queries to URI keying precisely because `name` is not a stable key, but this lookup was left name-keyed. In the WR-01 collision scenario (two suites sharing `<pkg>-unit-tests`), this query returns whichever row SQLite emits first and silently attaches the wrong `suite_kind`/`file_count` to one of the two entity pages. Even absent a collision, this is the same class of fragility the rest of the phase eliminated.

**Fix:** Thread the suite URI to a URI-keyed describe, mirroring the index_generator pattern:
```python
elif kind == "test_suite":
    suite_uri = node.attrs.get("uri") if isinstance(node.attrs, dict) else None
    d = _queries.describe_test_suite(conn, suite_uri=suite_uri)  # add uri-keyed param
```
and add a `WHERE kind='test_suite' AND uri = ?` branch to `describe_test_suite`. If a same-package-name collision is impossible by construction, document that invariant at the callsite; otherwise this is a latent wrong-data bug.

## Info

### IN-01: `summary` placeholder change is correct — note the latent YAML/inline-render hazard it removes

**File:** `packages/wiki-io/src/wiki_io/entity_writer.py:587`
**Issue:** The change from `> TODO: <add a one-line summary for {node.name}>` to `TODO add a one-line summary for {node.name}` is a real fix, not cosmetic. The old value flowed into the YAML `summary:` scalar and then into the index inline suffix ` — {summary}` via `index_generator._read_entity_summary` → `_parse_frontmatter`. The index's regex parser splits on the FIRST `:` (`k, _, v = line.partition(":")`), so a value containing `> TODO: <...>` rendered as a stray blockquote-with-angle-brackets fragment in the index bullet. The new value contains no `:` and no markdown control prefix, so it round-trips cleanly. No action required; flagged so the rationale is recorded.

### IN-02: `_consumer_pkgs_in_domain` is production-dead but still maintained/exported

**File:** `packages/wiki-io/src/wiki_io/index_generator.py:225-266, 915`
**Issue:** `_consumer_pkgs_in_domain` has no production caller — `_place_entities` uses only `_consumer_pkgs` (lines 380/384). It is exercised solely by `test_index_generator.py::test_consumer_pkgs_fanout_regression_guard`. Phase 58 still spent signature-change effort on it (adding `entity_uri`, reordering params so `domain_name` follows defaulted ones). This is pre-existing dead code (not introduced this phase), so per project convention it should be mentioned, not deleted, but the dual-maintenance cost is real: the domain-scoped fan-out path is only proven by a synthetic test, never by `_render`.
**Fix:** Either wire it into the domain-section render path (if intra-domain nesting was meant to use it) or drop it and fold its coverage into the `_consumer_pkgs` guard, in a future cleanup.

### IN-03: Keyword-only signature reorder places a required arg after defaulted args

**File:** `packages/wiki-io/src/wiki_io/index_generator.py:225-232`
**Issue:** `_consumer_pkgs_in_domain(conn, *, kind, entity_uri="", entity_name="", domain_name)` declares the required `domain_name` AFTER two defaulted keyword params. This is legal only because all are keyword-only (`*`), but it reads as a footgun — a reader skimming the signature may assume `domain_name` is optional. Callers must always pass `domain_name`; there is no positional protection.
**Fix:** Order keyword-only params required-first for readability: `(conn, *, kind, domain_name, entity_uri="", entity_name="")`. Behavior-neutral.

---

_Reviewed: 2026-05-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
