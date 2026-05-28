# Phase 52 Research: Wiki Filename Slimdown — Core

**Researched:** 2026-05-28
**Phase:** 52 — Wiki Filename Slimdown — Core
**Requirements:** WIKI-FN-01, WIKI-FN-02, WIKI-FN-03, WIKI-FN-04

---

## Open Questions from CONTEXT.md — Resolved

### Q1. Exact `test_suite` node attrs shape — where `suite_kind` lives

**Answer (confirmed in code):** `attrs_json.suite_kind` on the `nodes` row. Set during scan at
`packages/graph-io/src/graph_io/test_suites.py:344` via `_classify_suite_kind` (line 112).

**Possible values** (verified at `test_suites.py:112-150`):
- `"unit"` — default fallback when no other classifier matches
- `"integration"` — directory name contains "integration"
- `"e2e"` — directory name is `e2e` or `system`
- `"contract"` — directory name contains "contract", or filename matches `_SPEC_FILENAME_GLOBS`

**Plan implication for D-07:** CONTEXT.md D-07 names only `unit` and `integration`. For `e2e` and
`contract`, fall back to `tests_<pkg>` (current planned default), or extend the naming map to
`e2e_tests_<pkg>` / `contract_tests_<pkg>`. **Recommendation:** extend the map. It costs nothing
and produces readable filenames for the existing classifier outputs. The fallback path is then
reserved for genuinely-missing `suite_kind` (legacy/malformed nodes).

### Q2. State of `_URI_PREFIX_BY_KIND` and `ADMITTED_KINDS` after Phase 51

**Answer (read at `packages/wiki-io/src/wiki_io/entity_writer.py:66-89`):**

```python
ADMITTED_KINDS = frozenset({
    "repository", "domain", "package", "plugin", "dependency", "test_suite",
})  # 6 kinds — NOT 7. No `app`, no `builtin`.

_URI_PREFIX_BY_KIND = {
    "repository": "repo",
    "domain":     "domain",
    "package":    "pkg",
    "plugin":     "plugin",
    "dependency": "dependency",   # ← long form; D-05 changes this to "dep"
    "test_suite": "test_suite",
}
```

**Falsifies a CONTEXT.md drafting assumption:** CONTEXT.md says "post-Phase-51: 7 kinds — …
`app`, …". Phase 50 added the `app` classification in `graph-io` and `list_apps` in
`graph_io/queries.py:833`, BUT neither the wiki-io `ADMITTED_KINDS` set, the
`_URI_PREFIX_BY_KIND` dict, nor `_kind_list_fns` were updated to render app entity pages.

**Plan implication for SC#1:** SC#1 example output includes `app_graph-wiki-agent.md`. To satisfy
SC#1, Phase 52 MUST also:

1. Add `"app"` to `ADMITTED_KINDS`.
2. Add `"app": "app"` to `_URI_PREFIX_BY_KIND` (matches D-06).
3. Add `"app": lambda conn: _queries.list_apps(conn)` to `_kind_list_fns()`.
4. Add `kind == "app"` branch to `scanner_frontmatter_for_node` mirroring `kind == "package"`
   (calls `_queries.describe_app`, populates the same frontmatter keys; `describe_app` already
   exists at `queries.py:443`).
5. Create the `entity-app.md` template under
   `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` (mirror `entity-package.md`
   with `kind: app`).

This is a small extension — 5 atomic edits — and is the smallest change that delivers SC#1's
literal `app_graph-wiki-agent.md` example.

**`builtin` is explicitly NOT to be added** (Phase 49 D-16 + entity_writer.py:62-65 lock that
decision; stdlib pages dilute the entity surface). The CONTEXT.md D-06 mention of "builtin → builtin"
alias entry is moot since `builtin` will never appear in `ADMITTED_KINDS`. Skip it.

### Q3. Is `hypothesis` already a dev dep?

**Answer:** Yes. `/Users/pat/Personal/agent-research/pyproject.toml:11` declares
`hypothesis>=6.153.2` in the workspace `[dependency-groups].dev`. Already used in
`packages/wiki-io/tests/test_entity_writer.py:20-21`. No new dependency action required.

### Q4. Are there non-test consumers of `decode_slug` outside `wiki-io`?

**Answer:** No — `decode_slug` is only imported in:
- `packages/wiki-io/tests/test_entity_writer.py` (3 import/usage sites, all in tests for the
  legacy encode/decode contract).

There are no production callers of `decode_slug` anywhere. D-09 ("kept until Phase 53 cutover
cleanup since the rewriter needs old-long → URI mapping") is forward-looking — Phase 53's
upcoming wikilink rewriter will need it. Phase 52 leaves `decode_slug` untouched (no test changes
required, no production call site exists to migrate).

### Q5. Non-test consumers of `encode_slug` outside `entity_writer.write_entities`

**Answer (grep result):**

| File | Usage | Phase 52 action |
|------|-------|----------------|
| `packages/wiki-io/src/wiki_io/entity_writer.py:542` | inside `write_entities` | **Replace with `short_filename`** |
| `packages/wiki-io/src/wiki_io/link_rewriter.py:32, 246` | `_new_slug(uri)` generates target rewrite URLs for Phase 46's link rewriter | **Leave untouched** — Phase 53 owns vault wikilink rewrites; the rewriter currently produces long slugs and will be rewired in WIKI-FN-05 |
| `packages/wiki-io/src/wiki_io/index_generator.py:51, 417, 425, 430, 499` | generates `[[wiki/entities/<long_slug>]]` wikilinks in `wiki/index.md` | **Leave untouched** — WIKI-FN-06 (Phase 53) explicitly owns this |
| `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:31, 735` | builds `entity_page_path` to read existing entity files | **Leave untouched** — Phase 53 vault cutover concern |

**Critical caveat:** during Phase 52 → Phase 53 transition, `index_generator` and `link_rewriter`
will still produce **long-form** filename references (the old paths) while `write_entities`
produces **short-form** files. This means the generated index will contain dead wikilinks for
the duration between Phase 52 ship and Phase 53 ship. CONTEXT.md acknowledges this is intentional
("Out of scope: vault wikilink rewrites (Phase 53)") — the vault is a single-user workspace,
the gap is transient, and Phase 53's atomic cutover commit resolves it all at once.

This is an explicit, documented temporary regression. The plan-checker should accept it.

### Q6. Does `graph_io.queries` already expose a way to enumerate admitted-kind nodes?

**Answer (read at `queries.py:798-845`):** Yes — one `list_<kind>` function per kind already
exists and is already used by `_kind_list_fns()` in entity_writer (line 423-431). No new
helper is needed in graph-io.

The pre-pass (D-01) can simply iterate the same `_kind_list_fns` map, collect
`(uri, kind, attrs)` per node, compute plain filenames, group, and return the colliding set.
No SQL changes; reuse the existing per-kind list functions.

---

## Code Surface Map (verified line numbers, post-Phase-51)

| Surface | Location | Phase 52 action |
|---------|----------|-----------------|
| `ADMITTED_KINDS` | `packages/wiki-io/src/wiki_io/entity_writer.py:66-75` | Add `"app"` |
| `_URI_PREFIX_BY_KIND` | `entity_writer.py:82-89` | Change `"dependency": "dependency"` → `"dependency": "dep"`; add `"app": "app"` |
| `_ADMITTED_URI_PREFIXES` | `entity_writer.py:90` | Auto-derived from dict; no manual edit |
| `encode_slug` | `entity_writer.py:134-143` | **Leave** (still used by link_rewriter/index_generator; Phase 53 cleanup) |
| `decode_slug` | `entity_writer.py:146-168` | **Leave** (used only in tests; Phase 53 cleanup) |
| `short_filename` (new) | `entity_writer.py` after `decode_slug` (~line 170) | **Create** — pure function |
| `_compute_collision_set` (new) | `entity_writer.py` near `_kind_list_fns` | **Create** — pre-pass helper |
| `_kind_list_fns` | `entity_writer.py:423-431` | Add `"app"` entry |
| `scanner_frontmatter_for_node` | `entity_writer.py:440-486` | Add `kind == "app"` branch |
| `write_entities` per-entity loop | `entity_writer.py:537-572` | Replace `encode_slug(uri)` at line 542 with `short_filename(uri, collision_set, suite_kind=…, pkg_for_suite=…)`; pass collision set computed once before the kind loop |
| Stale-file cleanup glob | `entity_writer.py:574-604` | **Leave untouched** (D-discretion default) |
| `entity-app.md` template (new) | `packages/wiki-io/src/wiki_io/assets/page-templates/entity-app.md` | **Create** — mirror `entity-package.md` with `kind: app` |
| `test_short_filename.py` (new) | `packages/wiki-io/tests/test_short_filename.py` | **Create** — property tests |
| `test_entity_writer.py` | `packages/wiki-io/tests/test_entity_writer.py` | Add cases asserting new short-filename output; existing `encode_slug` round-trip tests stay (still valid for the legacy function) |

---

## `short_filename` Design Contract

```python
def short_filename(
    uri: str,
    collision_set: frozenset[str],
    *,
    suite_kind: str | None = None,
    pkg_for_suite: str | None = None,
) -> str:
    """Derive the short, human-readable filename stem for a graph entity URI.

    Pure function. Deterministic. Idempotent.

    Args:
        uri: Full graph URI (e.g. `pkg:agent-research/agent-research/graph-io`).
        collision_set: Set of URIs whose *plain* short stem collides with at
            least one other URI in the current write batch. Members of the set
            receive a sha256-derived 6-hex suffix; non-members keep the plain
            stem.
        suite_kind: Only consulted for `test_suite:` URIs. One of `"unit"`,
            `"integration"`, `"e2e"`, `"contract"`, or None.
        pkg_for_suite: For `test_suite:` URIs, the owning package name. If
            None, falls back to the suite's last path segment.

    Returns:
        Filename stem (no `.md` extension). Examples:
            "pkg_eval-harness"
            "pkg_utils__a3f7c1"        # collider
            "unit_tests_wiki-io"
            "int_tests_graph-io"
            "app_graph-wiki-agent"
            "dep_langchain-aws"
            "repo_agent-research"
            "domain_observability"
            "plugin_graph-wiki"

    Raises:
        ValueError: if `uri` is empty or has no `:` separator.
    """
```

### Derivation rules

| URI shape | Prefix | Stem | Filename (plain) |
|-----------|--------|------|------------------|
| `repo:org/repo` | `repo` | `<repo>` (last segment) | `repo_<repo>` |
| `pkg:org/repo/name` | `pkg` | `<name>` (last segment) | `pkg_<name>` |
| `app:org/repo/name` | `app` | `<name>` (last segment) | `app_<name>` |
| `domain:org/repo/name` | `domain` | `<name>` (last segment) | `domain_<name>` |
| `plugin:name` | `plugin` | `<name>` (last segment) | `plugin_<name>` |
| `dependency:ecosystem/name` | `dep` | `<name>` (last segment) | `dep_<name>` |
| `test_suite:org/repo/<path>` | depends on `suite_kind` | derived `<pkg>` | see below |

### Test-suite naming (D-02, D-07)

For `test_suite:` URIs, the filename is `<kind_prefix>_<pkg>` where:

- `<kind_prefix>` is derived from `suite_kind`:
  - `"unit"` → `unit_tests`
  - `"integration"` → `int_tests`
  - `"e2e"` → `e2e_tests`
  - `"contract"` → `contract_tests`
  - `None` or any other value → `tests` (fallback; logs warning at write site, NOT inside the
    pure helper — purity guarantee precludes side effects)
- `<pkg>` is:
  - `pkg_for_suite` if provided (the owning package name from the suite's parent edge)
  - else the second-to-last segment of the URI path (e.g. `wiki-io` from
    `test_suite:agent-research/agent-research/wiki-io/tests`)
  - else the last segment if only one is available

### Collision suffix (D-03, D-04)

After computing the plain stem, if `uri in collision_set`:

```python
suffix = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:6]
return f"{plain_stem}__{suffix}"
```

`hashlib.sha256` is stdlib — no new dependency. Import top-of-file alongside existing imports.

---

## Validation Architecture (for Phase 52)

Phase 52 validation is straightforward — pure function + a small integration surface.

### Validation dimensions

1. **Forward correctness** (Dim 1 — does it produce the right output?)
   - Unit tests on `short_filename` covering each URI shape.
   - Integration test on `write_entities` asserting expected files appear on disk for a
     synthesized graph fixture (already a pattern in `test_entity_writer.py`).

2. **Property: Idempotence** (Dim 2 — same input → same output across time)
   - Hypothesis property: `short_filename(uri, S, **kwargs) == short_filename(uri, S, **kwargs)`
     for arbitrary `(uri, S, suite_kind, pkg_for_suite)` tuples.

3. **Property: Collision-resistance within a write batch** (Dim 3 — distinct URIs → distinct
   filenames given the collision set)
   - Hypothesis property: for any pair of distinct URIs `(u1, u2)` with `u1 ≠ u2`, when both
     are in `collision_set`, their filenames differ. (Probabilistic, sha256-grounded; 24-bit
     space; collision probability astronomically low at personal-vault scale per D-03.)

4. **Property: Suffix triggering** (Dim 4 — collision membership determines suffix)
   - URIs in `collision_set` → filename ends with `__<6hex>`.
   - URIs NOT in `collision_set` → filename has no `__<6hex>` tail.

5. **Pre-pass correctness** (Dim 5 — collision set actually catches duplicates)
   - Unit test: synthesize 2 packages from different orgs sharing the same package name
     (`pkg:org-a/repo/utils` + `pkg:org-b/repo/utils`); assert both URIs appear in
     `_compute_collision_set(conn)`'s output; assert both files end up on disk with
     `__<6hex>` suffix.

6. **Test-suite kind-aware naming** (Dim 6 — `suite_kind` flows through correctly)
   - Parametrized cases: `("unit" → unit_tests_X)`, `("integration" → int_tests_X)`,
     `("e2e" → e2e_tests_X)`, `("contract" → contract_tests_X)`, `(None → tests_X)`.

7. **No regression in existing tests** (Dim 7 — `decode_slug`, `encode_slug` round-trip stays)
   - `test_entity_writer.py` existing tests must still pass (the legacy functions are
     untouched and still importable).

8. **End-to-end integration on a real fixture** (Dim 8 — SC#1 verification)
   - `pytest packages/wiki-io/tests/test_entity_writer.py::test_write_entities_short_filenames`
     (new) builds a small in-memory graph with one representative of each admitted kind plus a
     test_suite with `suite_kind="unit"`; asserts the resulting `wiki/entities/` contains
     `pkg_X.md`, `app_X.md`, `dep_X.md`, `repo_X.md`, `domain_X.md`, `plugin_X.md`,
     `unit_tests_X.md`.

## Validation Architecture

This section is the explicit Nyquist gate input required by step 5.5. It restates the dimensions
above in the canonical structure plan-checker expects.

- **Dim 1 (Forward correctness):** unit tests cover each URI shape; integration test on
  `write_entities` for SC#1 fixture.
- **Dim 2 (Idempotence):** Hypothesis property `short_filename(u,S,**k) == short_filename(u,S,**k)`.
- **Dim 3 (Collision-resistance):** Hypothesis property: distinct URIs in same collision_set
  produce distinct stems.
- **Dim 4 (Suffix triggering):** Parametrized: in-set ⇒ `__<6hex>` suffix; out-of-set ⇒ no
  suffix.
- **Dim 5 (Pre-pass correctness):** Synthesized cross-org `pkg:` collision — both URIs end up
  in `_compute_collision_set` output; both files on disk get suffix.
- **Dim 6 (Suite-kind dispatch):** Parametrized over `suite_kind ∈ {unit, integration, e2e,
  contract, None}`.
- **Dim 7 (Legacy regression):** existing `encode_slug`/`decode_slug` tests stay green.
- **Dim 8 (End-to-end):** SC#1 fixture — `pkg_*`, `app_*`, `dep_*`, `repo_*`, `domain_*`,
  `plugin_*`, `unit_tests_*` files exist on disk after `write_entities`.

---

## Risk Inventory

| Risk | Severity | Mitigation |
|------|----------|------------|
| `_compute_collision_set` runs N+1 queries (1 per kind) per `write_entities` call | LOW | Existing `_kind_list_fns` already does this. The pre-pass adds one full traversal *before* the write loop; total cost is 2× existing scan — dwarfed by per-entity I/O at any realistic vault size (≤thousands of entities). |
| `app` kind addition leaks scope | LOW | SC#1 literally requires `app_graph-wiki-agent.md`. The five small edits (admit + alias + list_fn + frontmatter branch + template) are the minimum required. Tracked as a discrete plan (52-04) so plan-checker can audit boundary. |
| Stale long-form filenames remain in vault after Phase 52 ships | EXPECTED | Documented in CONTEXT.md as transitional state; the existing stale-file glob cleanup at `entity_writer.py:574-604` does NOT delete them automatically because the long-form URI no longer matches what `write_entities` produces. The long-form files sit as orphans (URI in their frontmatter, but URI not in `admitted_uris` set after Phase 53 — wait, no: the URI IS still in `admitted_uris` because `admitted_uris` is built from graph traversal, not filename inspection). Let me re-check: the cleanup loop iterates `entities_dir.glob("*.md")`, reads each file's `uri:` frontmatter, and deletes if `uri NOT IN admitted_uris`. So old long-form files for currently-admitted URIs will be RETAINED until something else deletes them (the URI is admitted, so the file is not orphaned). Phase 53's atomic cutover handles deletion. **Phase 52 should NOT proactively delete long-form files** — CONTEXT.md confirms this default. |
| `link_rewriter` and `index_generator` continue to produce long-form references | DOCUMENTED | Phase 53 owns the cutover. Phase 52 ships a transient broken state. |
| Property test for collision-resistance hits a sha256 collision in 24-bit space | NEGLIGIBLE | Birthday-bound at 24 bits is √(2^24) ≈ 4096 — Hypothesis's example budget is 100 by default; effectively impossible to hit a real collision in test runs. If it ever fires, the test correctly reports the (cosmic-ray) collision. D-03 acknowledges this. |
| `suite_kind` missing on legacy test_suite nodes | MEDIUM | Fallback path (`tests_<pkg>`) plus a warning logged at the write site. Property test must cover the `None` case. |
| `pkg_for_suite` derivation from URI is fragile for repo-owned suites | MEDIUM | For `owner_kind == "repository"` suites the URI path may not contain an obvious package segment. Fallback: if the second-to-last segment looks like a package name (no slashes inside it, alphanumeric-with-dashes), use it; otherwise use the URI's last segment. Document this in `short_filename`'s docstring. |
| `entity-app.md` template missing breaks rendering | HIGH | Plan 52-04 includes template creation. Plan-checker should verify the template path matches `_template_path_for_kind("app")` returns a file that exists. |

---

## Plan Decomposition (recommended)

Per CONTEXT.md `next_steps`, 3–4 atomic plans. Recommended:

- **52-01 — `short_filename` pure helper + property tests.** Adds the function and
  `test_short_filename.py`. No `write_entities` integration yet. Closes WIKI-FN-04.
  **Wave 1** (no deps inside the phase).

- **52-02 — Pre-pass collision computation + integration into `write_entities`; dep alias.**
  Adds `_compute_collision_set` helper, swaps `encode_slug` → `short_filename` at the write
  site, flips `_URI_PREFIX_BY_KIND["dependency"]` from `"dependency"` to `"dep"`, updates
  `test_entity_writer.py` assertions for new short-form filenames. Closes WIKI-FN-01,
  WIKI-FN-03. **Wave 2** (depends on 52-01: needs `short_filename` to exist).

- **52-03 — Test-suite kind-aware naming + fallback path.** Extends `short_filename`'s
  test-suite branch (parametrized for unit/integration/e2e/contract/None); wires
  `scanner_frontmatter_for_node`'s test_suite branch to surface `pkg_for_suite` (derived from
  the suite's `path` attr); adds property tests for kind-aware naming. Closes WIKI-FN-02.
  **Wave 2** (parallel to 52-02 if 52-01 is staged as a pure-function addition with the test-suite
  branch already in place from 52-01 — recommend folding the test-suite handling INTO 52-01 since
  the function is pure and indivisible; then 52-03 becomes the integration into
  `scanner_frontmatter_for_node` + write-site call). **Wave 2** depends on 52-01 + 52-02.

- **52-04 — App kind admission + entity-app.md template + frontmatter branch.** Adds
  `"app"` to `ADMITTED_KINDS`, `_URI_PREFIX_BY_KIND`, `_kind_list_fns`, the
  `scanner_frontmatter_for_node` branch, and creates the `entity-app.md` template.
  Re-verifies SC#1's `app_graph-wiki-agent.md` line. **Wave 2** (depends on 52-02's write
  path; the template + `ADMITTED_KINDS` change are orthogonal to filename slimdown but required
  to satisfy SC#1's literal example).

**Revised recommendation:** keep `short_filename`'s body whole (including the test-suite branch)
in 52-01. Split the per-task work as:

- **52-01 (Wave 1):** `short_filename` (all branches incl. test-suite) + `test_short_filename.py`
  property tests covering all derivation rules + collision behavior. WIKI-FN-04 + the
  function-level part of WIKI-FN-02 (test-suite kind-aware derivation in the pure helper).
- **52-02 (Wave 2):** `_compute_collision_set` helper + `write_entities` integration; flip
  `_URI_PREFIX_BY_KIND["dependency"] → "dep"`; update `test_entity_writer.py` for the new
  short-form expectations + add an integration test asserting cross-org collision triggers the
  suffix. WIKI-FN-01 + WIKI-FN-03 + integration part of WIKI-FN-02 (pass `suite_kind` /
  `pkg_for_suite` into `short_filename` at the call site).
- **52-03 (Wave 2):** Admit `app` kind — `ADMITTED_KINDS`, `_URI_PREFIX_BY_KIND["app"] = "app"`,
  `_kind_list_fns["app"]`, `scanner_frontmatter_for_node` app branch, `entity-app.md` template.
  Re-verify SC#1 in the integration fixture. (Satisfies SC#1's `app_graph-wiki-agent.md`
  example; WIKI-FN-01 nominally already covers this but only by way of app pages being rendered.)

This is the layout used in the plan files.

---

## Outstanding Discretion Items (planner choices)

CONTEXT.md leaves these to the planner:

- **Pre-pass shape:** plain Python grouping. Adopt: iterate `_kind_list_fns` once before the
  per-kind write loop, accumulate `{filename_stem: [uris]}`, return
  `frozenset(uri for stems with len(uris) > 1 for uri in uris)`. Extracted as
  `_compute_collision_set(conn, admitted_kinds) -> frozenset[str]`.
- **Property test framework:** `hypothesis` (already a workspace dev dep — Q3 above).
- **Helper extraction:** YES — `_compute_collision_set` extracted, mirrors Phase 50's
  `classification.py` pattern.
- **Stale-file cleanup glob:** untouched (default).
- **`hashlib` import:** top-of-file.

---

## Sources

- `packages/wiki-io/src/wiki_io/entity_writer.py` — current `ADMITTED_KINDS`, `_URI_PREFIX_BY_KIND`,
  `encode_slug`, `decode_slug`, `write_entities`, `_kind_list_fns`,
  `scanner_frontmatter_for_node`.
- `packages/graph-io/src/graph_io/queries.py` — `list_apps`, `describe_app`,
  `_load_suite_description`, `list_test_suites`.
- `packages/graph-io/src/graph_io/test_suites.py:112-150` — `_classify_suite_kind` value space.
- `packages/graph-io/src/graph_io/uri.py` — URI builder shapes for all admitted kinds.
- `packages/wiki-io/tests/test_entity_writer.py` — existing test patterns + Hypothesis usage.
- `pyproject.toml:11` — `hypothesis>=6.153.2` workspace dev dep.
- `.planning/phases/52-wiki-filename-slimdown-core/52-CONTEXT.md` — locked decisions D-01..D-09.
- `.planning/phases/52-wiki-filename-slimdown-core/52-DISCUSSION-LOG.md` — gray areas + user
  acceptance of D-04's divergence from roadmap §52 SC#3 strict wording.
- `.planning/REQUIREMENTS.md:30-34` — WIKI-FN-01..WIKI-FN-04.
- `.planning/ROADMAP.md` §Phase 52 — 4 success criteria.

## RESEARCH COMPLETE
