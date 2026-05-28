# Phase 52: Wiki Filename Slimdown — Core - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace URI-fully-qualified entity filenames (`pkg__org__repo__name.md`) with short human-readable forms — `pkg_<name>.md`, `app_<name>.md`, `dep_<name>.md`, `repo_<name>.md`, `domain_<name>.md`, `plugin_<name>.md`, and test-suite kind-aware `unit_tests_<pkg>.md` / `int_tests_<pkg>.md` — with deterministic cross-repo collision handling via a sha256-derived 6-hex suffix applied to all members of any colliding set. Filename derivation becomes a pure, property-tested helper in `wiki_io.entity_writer`.

In scope: new pure helper `short_filename(uri, collision_set, **derived_attrs) → str`; pre-pass that builds `collision_set` once per `write_entities` invocation; switch `write_entities` to call `short_filename` instead of `encode_slug`; CommonMark template references that still use slug names continue to work via frontmatter `uri:`; property tests (idempotence + collision-resistance); dep_ filename-layer alias in `_URI_PREFIX_BY_KIND`.

Out of scope: vault wikilink rewrites (Phase 53); deletion of `decode_slug` (kept until Phase 53 cutover cleanup since the rewriter needs old-long → URI to identify rewrites); graph-io URI prefix changes — graph URIs stay `dependency:`, `package:`, etc.; backward-compat shim that writes both old + new filenames (Phase 53 handles transition atomically); existing exploratory vault migration (Phase 53 owns `~/Personal/graph-wiki/agent-research/` cutover).

</domain>

<decisions>
## Implementation Decisions

### Collision detection — pre-pass at write time

- **D-01: Pre-pass collision detection inside `write_entities`.** Before the per-entity loop, run a single SQL query that enumerates all admitted-kind nodes, compute each one's *plain* short filename via `short_filename(uri, collision_set=frozenset())`, group by filename, and let `collision_set = frozenset(uri for uri in all_uris if plain_filename_of(uri) appears more than once)`. Pass that set into the per-entity `short_filename(uri, collision_set)` call inside the loop. Pre-pass is O(N) and runs once per invocation; dwarfed by per-entity I/O. Pure function semantics preserved — no hidden state, no persistent side-table.
- **D-02: Pre-pass extends to TestSuite kind-aware filenames.** For test suites, the "plain" name is `unit_tests_<pkg>` or `int_tests_<pkg>` derived from the suite's `kind` attribute. The pre-pass must enumerate this same derived form so collisions across `tests` suites in different packages are caught correctly. Suite `kind` is read once per node during the pre-pass; passed alongside `uri` into `short_filename`.

### Hash format — sha256, 6 hex, all-colliders suffix

- **D-03: sha256 of the full URI, first 6 hex chars.** `suffix = hashlib.sha256(uri.encode()).hexdigest()[:6]`. 24 bits = ~16M space; second-order collision probability is negligible at personal-vault scale. Format: `<plain_stem>__<6hex>.md` — matches roadmap example `pkg_utils__a3f7c1.md` exactly. Double-underscore is the separator (visually distinguishes the hash from the stem; doesn't conflict with the new short-form scheme since plain stems contain at most single underscores between kind-prefix and name).
- **D-04: Suffix attaches to ALL members of the colliding set, not just one.** **Diverges from roadmap §52 SC#3 strict reading** ("only the collider receives a hash suffix; the non-colliding entity keeps the plain short name"). Rationale: a pure function over `(uri, collision_set)` cannot have a winner/loser semantics without a tiebreaker (lex-smallest URI?), and a tiebreaker breaks idempotence-across-time — adding a 3rd colliding URI later would shift which existing entity has the plain name, causing a file-rename storm in the vault. Symmetric all-colliders-get-suffix is deterministic, time-stable, and trivially property-testable. The "non-colliding entity keeps the plain short name" wording is still honored for entities that aren't in any collision set (the vast majority).

### Dependency naming — filename-layer alias only

- **D-05: `_URI_PREFIX_BY_KIND["dependency"] = "dep"`.** Add the alias to the existing dict in `entity_writer.py:78-86`. Mirrors the existing `repository → repo` and `package → pkg` aliases. Graph URIs stay `dependency:langchain-aws` — no changes to `graph_io/uri.py`, queries, or any graph-side test. The mapping is one-way at write time; reverse direction is irrelevant under D-08.
- **D-06: Apply the same alias pattern to App + Builtin** (kinds added in Phases 49/50). Confirm the `_URI_PREFIX_BY_KIND` dict already maps them or add entries: `app → app`, `builtin → builtin`. No abbreviation — those prefixes are already short. (Researcher to confirm current state of the dict after Phase 51 cleanup of `package_family`.)

### Test-suite kind-aware naming

- **D-07: `short_filename` accepts an optional `kind_attr` parameter** to handle test suites' framework-aware naming. Signature: `short_filename(uri: str, collision_set: frozenset[str], *, suite_kind: str | None = None) → str`. For `test_suite:org/repo/pkg`, the writer reads `suite_kind` from the TestSuite node's attrs (likely `attrs_json.kind` ∈ {`unit`, `integration`}; researcher to confirm exact shape) and passes it in. Derived stem: `unit_tests_<pkg>` if `suite_kind == "unit"`, `int_tests_<pkg>` if `suite_kind == "integration"`. If `suite_kind` is missing/None for a `test_suite` URI, the function falls back to `tests_<pkg>` and logs a warning (graph data quality issue, not a fatal write error).

### `decode_slug` fate

- **D-08: Drop `decode_slug` from the new write path; reverse lookups go through `frontmatter.uri`.** The bidirectional `encode_slug`/`decode_slug` contract is fundamentally broken by short filenames (multiple URIs can map to the same plain stem; collisions resolved via D-04 suffix make the forward direction injective, but the reverse is still N→1 in the absence of the URI). Every existing consumer that today calls `decode_slug` is already walking .md files — read `uri:` from frontmatter instead. Phase 52 updates these call sites.
- **D-09: `decode_slug` function itself stays until Phase 53 cutover cleanup.** Phase 53's wikilink rewriter needs the old-long-filename → URI mapping to identify which `[[pkg__org__repo__name]]` references to rewrite. After Phase 53 ships, a follow-up plan in Phase 53 (or carried-forward debt) deletes `decode_slug` + `encode_slug` entirely.

### Claude's Discretion (left to planner)

- **Pre-pass SQL shape**: single `SELECT uri, kind, attrs_json FROM nodes WHERE kind IN (...)` then in-Python filename grouping, vs. SQL window function. Default: plain Python grouping — readable, no SQL gymnastics, runs once per write_entities call.
- **Property test framework**: `hypothesis` is the standard Python property-test library and may already be a dev dep. If absent, planner picks: add `hypothesis` (recommended; small dep, big payoff for the idempotence + collision-resistance proofs) or roll deterministic parametrized cases. Default: add `hypothesis` if not already present.
- **Where the pre-pass query lives**: inline in `write_entities` vs. extracted helper `_compute_collision_set(conn) -> frozenset[str]`. Default: extracted helper — testable in isolation, mirrors Phase 50's `classification.py` pattern.
- **Behavior on writing into a vault with stale old-long filenames present**: Phase 52 writes new short filenames; old long ones remain orphaned until Phase 53 cutover deletes them. Phase 52 does NOT proactively delete old files (avoids cross-phase coupling; keeps Phase 52 → Phase 53 transition atomic at the vault level via Phase 53's commit). Default: leave the existing stale-file cleanup at the end of `write_entities` (the `for page_path in entities_dir.glob("*.md")` loop at line 577) untouched — that loop already handles "old entity file no longer in graph" semantics generically.
- **`hashlib.sha256` import**: top-of-file vs. function-local. Default: top-of-file alongside existing imports (entity_writer.py:174-188).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — WIKI-FN-01 through WIKI-FN-04 (Phase 52); WIKI-FN-05, WIKI-FN-06 (Phase 53; informational, not implemented here).
- `.planning/ROADMAP.md` §Phase 52 — goal, 4 success criteria, dependency on Phase 51.

### Prior phase context (precedent — must be honored)
- `.planning/phases/42-uri-slug-scheme-per-kind-templates/42-CONTEXT.md` — D-01..D-05 introduce `encode_slug`/`decode_slug`, `_URI_PREFIX_BY_KIND` dict, and ADMITTED_KINDS. Phase 52 changes the encode side and stops using decode.
- `.planning/phases/43-entity-writer/43-CONTEXT.md` — `write_entities` orchestration patterns; D-12..D-14 frontmatter merge semantics; D-21 per-page error bucketing. Phase 52 plugs into this orchestration.
- `.planning/phases/46-inbound-link-migration-cutover/46-CONTEXT.md` — link rewriter + CommonMark-aware tokenizer pattern that Phase 53 will reuse for the vault cutover.
- `.planning/phases/50-app-reclassification-graph-io/50-CONTEXT.md` — D-04 classification module pattern (pure function with passthrough args, no SQL); template for `short_filename`'s purity guarantees.
- `.planning/phases/51-package-family-removal-divergence-rule-cleanup/51-CONTEXT.md` — D-04 removes `ADMITTED_KINDS_V18` alias; D-01 confirms vault writes belong to Phase 53.

### Core code surface (this phase touches)
- `packages/wiki-io/src/wiki_io/entity_writer.py:61-71` — `ADMITTED_KINDS` frozenset (post-Phase-51: 7 kinds — `repository`, `domain`, `package`, `app`, `plugin`, `dependency`, `test_suite`, and possibly `builtin` if rendered).
- `packages/wiki-io/src/wiki_io/entity_writer.py:78-86` — `_URI_PREFIX_BY_KIND` dict; add `dependency → dep` alias here (D-05).
- `packages/wiki-io/src/wiki_io/entity_writer.py:133-142` — `encode_slug(uri)`; reference only. New helper replaces calls to this in the write path.
- `packages/wiki-io/src/wiki_io/entity_writer.py:145-167` — `decode_slug(slug)`; stays for Phase 53 transient use (D-09); no calls from new code.
- `packages/wiki-io/src/wiki_io/entity_writer.py:496-630` — `write_entities` orchestrator; inject pre-pass collision computation before the per-entity loop (~line 530); replace `encode_slug(uri)` call at line 544 with `short_filename(uri, collision_set, suite_kind=...)`.
- `packages/wiki-io/src/wiki_io/entity_writer.py:577-610` — stale-file cleanup glob loop; leave untouched (D-discretion note).

### Test surface
- `packages/wiki-io/tests/test_entity_writer.py` — existing assertions on filenames produced by `write_entities`; update expected filenames to short forms.
- `packages/wiki-io/tests/test_link_rewriter_build_table.py` — link rewriter tests; should NOT need changes in Phase 52 (rewriter still consumes existing wikilinks; Phase 53 owns the cutover).
- New file: `packages/wiki-io/tests/test_short_filename.py` — property tests for `short_filename`:
  - Idempotence: same `(uri, collision_set, suite_kind)` always yields same filename.
  - Collision-resistance: distinct URIs never yield equal filenames within the same `collision_set`.
  - Suffix triggering: URIs in `collision_set` get 6-hex suffix; URIs outside do not.
  - Kind-aware test-suite naming: `suite_kind` flows through correctly.

### Graph-io read surface (read-only)
- `packages/graph-io/src/graph_io/queries.py` — read path for enumerating admitted-kind nodes during the pre-pass. Researcher to confirm whether an existing helper (`list_admitted_entities()`-style) already exists or needs to be added.
- `packages/graph-io/src/graph_io/uri.py` — URI builders are NOT modified by Phase 52 (D-05).

</canonical_refs>

<code_context>
## Codebase Context

### Reusable patterns
- **Pure function with explicit set parameter** (mirrors Phase 50 `classify(manifest_dict, pkg_dir)`): `short_filename(uri, collision_set, suite_kind=None)` is a leaf-level pure function with no SQL connection, no I/O. Testable in isolation.
- **Pre-pass O(N) scan once per write_entities call** (mirrors the existing `_kind_list_fns()` dispatch at entity_writer.py:425): the scan is already part of `write_entities`' standard cost; adding a collision pre-pass slots into the same pattern.
- **Filename alias via `_URI_PREFIX_BY_KIND` dict** (existing pattern at entity_writer.py:78-86): D-05 just adds one entry. No new mechanism.
- **Per-entity error bucketing** (Phase 43 D-09 + entity_writer.py:565-575): when `short_filename` raises (e.g., malformed URI), bucket into `EntityWriteError` like every other write-path exception.

### Integration points
- `write_entities` calls `encode_slug(uri)` once per entity at line 544. Single replacement site.
- Stale-file cleanup at line 577-610 globs `*.md` and deletes orphans — this loop will naturally clean up old-long-filename files in Phase 53 once the new short-filename path is the live write path (provided the graph's URI set hasn't changed). No special phase-52 work needed for that loop.
- The `_template_path_for_kind(kind)` function at line 436-438 maps kind → template filename via `entity-<kind>.md` convention. Unrelated to filename slimdown; templates remain `entity-<kind>.md` regardless of the per-entity filename scheme.

### Known sharp edges
- Collision set must be re-derived inside any test that exercises `write_entities`, not memoized at module scope (otherwise tests that vary the URI population would share stale state). Test fixtures should compute it per-test.
- `suite_kind` may be `None` for malformed TestSuite nodes — D-07 specifies fallback to `tests_<pkg>` + warning. Property test should cover the `None` case.

</code_context>

<deferred>
## Deferred Ideas

- **Vault wikilink rewrites + atomic cutover commit** — Phase 53 (WIKI-FN-05, WIKI-FN-06).
- **Deletion of `encode_slug` / `decode_slug` functions** — Phase 53 cleanup plan (D-09).
- **Cross-vault collision policy** — if Pat ever runs multiple parallel vaults that share an index, the collision_set scope might need to widen beyond a single workspace. Out of scope; defer until use case emerges.
- **Hash length tuning** — 6 hex chars is the locked default. If a real-world collision-of-collisions ever fires, bump to 8 hex (32 bits, ~4B space). Probability is astronomically low at personal-vault scale; no provision needed now.
- **`hashlib.blake2b` vs sha256** — blake2b is faster and produces shorter hashes natively, but sha256 is the universally-available default and the speed differential is irrelevant for ≤thousands of entities. Stick with sha256.

</deferred>

<next_steps>
## Next Steps

1. `/gsd:plan-phase 52` — research + planning. Researcher should confirm:
   - Exact `test_suite` node attrs shape — where `suite_kind` lives (attrs_json key name, possible values).
   - Whether `_URI_PREFIX_BY_KIND` already contains `app` and `builtin` after Phase 51 lands (likely yes, but verify).
   - Whether `hypothesis` is already a dev dep in `packages/wiki-io/`.
   - Whether any non-test consumer of `decode_slug` exists outside `wiki-io` (grep across `packages/`).
   - Whether `graph_io.queries` exposes a helper to enumerate admitted-kind nodes, or one needs to be added.
2. Plan should aim for 3–4 atomic plans:
   - **52-01**: `short_filename` pure helper + property tests (`test_short_filename.py`). No `write_entities` changes yet. WIKI-FN-04.
   - **52-02**: Pre-pass collision computation + integration into `write_entities` write path; switch from `encode_slug` to `short_filename`; update `_URI_PREFIX_BY_KIND` with `dep` alias. WIKI-FN-01, WIKI-FN-03.
   - **52-03**: Test-suite kind-aware naming (`unit_tests_<pkg>` / `int_tests_<pkg>`); fallback + warning for missing `suite_kind`. WIKI-FN-02.
   - **52-04** (optional): Updates to `test_entity_writer.py` to reflect new short filenames; verify link-rewriter tests still pass unchanged.
3. Verification gates:
   - Property tests pass: idempotence + collision-resistance + suffix-triggering.
   - `write_entities` on a fresh vault produces `pkg_eval-harness.md`, `app_graph-wiki-agent.md`, `dep_langchain-aws.md`, `repo_agent-research.md`, `domain_observability.md` (per SC #1).
   - Two synthesized colliding entities both produce `<stem>__<6hex>.md` files; a non-colliding `<stem>.md` exists alongside.
   - `decode_slug` function untouched and still importable (Phase 53 dependency).

</next_steps>
