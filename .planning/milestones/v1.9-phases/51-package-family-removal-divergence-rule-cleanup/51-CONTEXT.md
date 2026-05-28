# Phase 51: package-family Removal + Divergence Rule Cleanup - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Surgical removal of the `package_family` kind and its scaffolding from `graph-io` and `wiki-io`, plus deletion of the `_SLUG_ONLY_RE` / LIB-003 divergence rule from the `eval-harness`. After this phase, `ADMITTED_KINDS` is a single complete-and-final frozenset (no subtraction-narrow), `package_family_uri` no longer exists, the divergence registry no longer registers LIB-003, and there are zero `package_family` / `PKGFAM` references in `packages/` (excluding planning docs and migration-log comments).

In scope: code-only deletions in `graph-io`, `wiki-io`, `eval-harness`; CLI subcommand removal (if `cg describe-package-family` / `cg list-package-families` exist); test fixture surgical edits; divergence baseline regeneration; `ADMITTED_KINDS_V18` alias deletion.

Out of scope: vault directory deletion (`wiki/package-family/` in the existing exploratory vault) — deferred to Phase 53 cutover migration alongside wikilink rewrites; any schema-version bump or pre-flight migration check (user regenerates graph manually via `cg update --full`); domain layer changes (PKGFAM-05 orthogonality).

</domain>

<decisions>
## Implementation Decisions

### Cut line: code-only this phase

- **D-01: Vault directory deletion deferred to Phase 53.** `wiki/package-family/` in the existing exploratory vault is removed during Phase 53's atomic `migrate-vault` operation (alongside wikilink rewrites), not in this phase. Mirrors Phase 50 D-08 ("wiki-io untouched in Phase 50; vault writes belong to Phase 53"). PKGFAM-03's "removed from the existing vault during migration" wording is satisfied by Phase 53's migration command — Phase 51 ships only the code changes (delete `entity-package-family.md` template + remove `package_family` from `ADMITTED_KINDS`).

### Pre-v1.9 graph compatibility — manual regeneration

- **D-02: No SCHEMA_VERSION bump, no pre-flight scan, no migration command.** PKGFAM-01's literal "SCHEMA_MISMATCH" wording is reinterpreted: the user (sole developer) regenerates graphs manually via `cg update --full` after this phase ships. Whatever cryptic error fires when `_VALID_KINDS` encounters a stale `package_family` row is acceptable — the workflow is "delete the graph, regenerate". Schema version stays at 2 (consistent with Phases 49 D-10 and 50 D-12). The planner should NOT add a pre-flight check at connect time, and should NOT bump `SCHEMA_VERSION`.

### Test fixtures + V18 alias

- **D-03: Surgical fixture edits.** `packages/wiki-io/tests/fixtures/round-trip-vault/` is a golden snapshot — keep its non-package-family coverage intact. Surgically delete: (a) `.templates/package-family.md` and any `wiki/package-family/` directory inside the fixture, (b) lines mentioning `package_family` in concept/source/overview markdowns, (c) the `package-family` template in `.graph-wiki/`. Rebuild `vocab.index.json` and `vocab.tokenizer.json` via existing test tooling (bm25 regeneration path) rather than hand-editing the JSON.
- **D-04: Delete `ADMITTED_KINDS_V18` alias outright.** `packages/wiki-io/src/wiki_io/entity_writer.py:195-196` defines `ADMITTED_KINDS_V18 = ADMITTED_KINDS - frozenset({"package_family"})` as a v1.8 caller compat shim. Per success criterion #2, the frozenset must be "complete and final" with no subtraction-narrow. Delete the alias outright, update both call sites to plain `ADMITTED_KINDS`. No deprecation grace period — single-developer project, no external consumers.

### Divergence baseline regeneration

- **D-05: Regenerate `baselines/divergence-librarian.json` via existing eval-harness tooling, not hand-edit.** Hand-editing the JSON creates drift risk between the registered checks and the baseline. The planner should identify the existing baseline-regeneration path (likely a `pytest --record-baseline` or `eval-harness baseline regen` flag — researcher to surface) and use it after LIB-003 is removed from the registry. Hand-edit is the fallback only if no regen tooling exists.

### Claude's Discretion (left to planner)

- Whether to delete `package-family.md` (non-`entity-` prefix) template at `packages/wiki-io/src/wiki_io/assets/page-templates/package-family.md` in the same plan as `entity-package-family.md` or separately. Both files clearly belong to the same removal; default to deleting in one plan.
- Whether `dependency.py:_check_*` and `link_rewriter.py` references to `package_family` are real code paths or comment-only. Researcher to confirm; if comment-only and inside a "migration log" or "historical" docstring, success criterion #1 permits them to stay. Default: delete the references unless they are clearly historical-comment markers.
- Order of CLI removal (PKGFAM-04: `cg describe-package-family` / `cg list-package-families`) — researcher first verifies whether these subcommands exist; if so, removal slots into the same plan as `package_family_uri` deletion (both touch the same CLI module family).
- Whether the divergence baseline regen runs before or after the LIB-003 code deletion. Logical order is: delete code → regen baseline → assert no LIB-003 row in JSON. Planner picks the exact plan ordering.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — PKGFAM-01 through PKGFAM-05 and CLEANUP-01 (Milestone v1.9).
- `.planning/ROADMAP.md` §Phase 51 — goal, 5 success criteria, dependency on Phase 50.

### Prior phase context (precedent — must be honored)
- `.planning/phases/50-app-reclassification-graph-io/50-CONTEXT.md` — D-08 (wiki-io scope boundary; vault writes deferred to Phase 53), D-12 (no SCHEMA_VERSION bump policy).
- `.planning/phases/49-builtin-kind-graph-io/49-CONTEXT.md` — D-10 (kinds are text strings; no SQL gate; same rationale applies to retraction).

### graph-io deletions
- `packages/graph-io/src/graph_io/uri.py:49-50` — `package_family_uri(name)` to delete (PKGFAM-02).
- `packages/graph-io/src/graph_io/queries.py:9` — remove `"package_family"` from `_VALID_KINDS` (PKGFAM-01).
- `packages/graph-io/tests/test_uri.py` — drop any `package_family_uri` tests.

### wiki-io deletions
- `packages/wiki-io/src/wiki_io/entity_writer.py:9` — docstring mention; clean up.
- `packages/wiki-io/src/wiki_io/entity_writer.py:22` — docstring example; clean up.
- `packages/wiki-io/src/wiki_io/entity_writer.py:66` — `package_family` in URI-prefix list; remove.
- `packages/wiki-io/src/wiki_io/entity_writer.py:82` — `"package_family": "package_family"` mapping; remove.
- `packages/wiki-io/src/wiki_io/entity_writer.py:125` — "Edge-derived (package_family)" comment block; remove the block.
- `packages/wiki-io/src/wiki_io/entity_writer.py:195-196` — delete `ADMITTED_KINDS_V18` alias entirely (D-04).
- `packages/wiki-io/src/wiki_io/entity_writer.py:530` — unknown-admitted-kind fallback comment ("e.g. package_family v1.9"); remove or rewrite.
- `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package-family.md` — delete (PKGFAM-03).
- `packages/wiki-io/src/wiki_io/assets/page-templates/package-family.md` — delete.
- `packages/wiki-io/src/wiki_io/lint/dependency.py` — review/clean references.
- `packages/wiki-io/src/wiki_io/link_rewriter.py` — review/clean references.
- `packages/wiki-io/tests/test_link_rewriter_build_table.py` and `packages/wiki-io/tests/test_entity_writer.py` — drop package_family branches.

### eval-harness deletions (CLEANUP-01)
- `packages/eval-harness/src/eval_harness/divergence/librarian.py:53` — `_SLUG_ONLY_RE` regex; delete.
- `packages/eval-harness/src/eval_harness/divergence/librarian.py:85-91` — `_check_no_slug_only_wikilinks` function; delete.
- `packages/eval-harness/src/eval_harness/divergence/librarian.py:118-121` — `LIB-003-no-slug-only-wikilinks` registry entry; delete.
- `packages/eval-harness/src/eval_harness/divergence/synthesizer.py:46, 116` — appears to also reference `_check_no_slug_only_wikilinks`; researcher to confirm and remove.
- `packages/eval-harness/baselines/divergence-librarian.json` — regenerate via existing tooling to drop the `LIB-003-no-slug-only-wikilinks` row (D-05).
- `packages/eval-harness/tests/test_divergence_checks.py:98-110` — delete LIB-003 test cases.
- `packages/eval-harness/tests/test_divergence_baseline.py:35` — update fixture (or regen).
- `packages/eval-harness/tests/test_two_gate_scorer.py:98, 144` — update fixtures (or regen).

### Test fixtures — surgical edits (D-03)
- `packages/wiki-io/tests/fixtures/round-trip-vault/.templates/package-family.md` — delete.
- `packages/wiki-io/tests/fixtures/round-trip-vault/plugins/lattice-wiki/patterns.md` and `context.md` — remove `package_family` lines.
- `packages/wiki-io/tests/fixtures/round-trip-vault/packages/lattice-wiki-core/overview.md` — remove `package_family` references.
- `packages/wiki-io/tests/fixtures/round-trip-vault/concepts/*.md` — remove `package_family` mentions.
- `packages/wiki-io/tests/fixtures/round-trip-vault/sources/2026-05-lattice-wiki-core-tokens-frontmatter-field.md` — review and clean.
- `packages/wiki-io/tests/fixtures/round-trip-vault/.graph-wiki/bm25/vocab.index.json` and `vocab.tokenizer.json` — regenerate via existing fixture-build tooling, not hand-edit.

### CLI commands (PKGFAM-04)
- Researcher first verifies presence of `cg describe-package-family` / `cg list-package-families` in `packages/graph-io/src/graph_io/cli/`. If present, remove both handlers and any registrations in `main._SUBCOMMANDS`.

</canonical_refs>

<code_context>
## Codebase Context

### Reusable patterns
- **Phase 49/50 deletion-of-kind precedent**: although those phases *added* kinds, they established the convention that kind admission lives in `_VALID_KINDS` (queries.py:9), URI builders live in `uri.py`, and edge handling is FK-stable. Removal is the mirror image — drop from `_VALID_KINDS`, delete the URI builder, leave inbound edges alone (any pre-existing `package_family` edges in stale graphs are user-rebuild territory per D-02).
- **`ADMITTED_KINDS` as the gate** (entity_writer.py:60-90): the existing pattern is a single frozenset with per-kind URI prefix mapping in a dict. Removal is local: drop the entry from the prefix dict, drop from the frozenset, delete the template file.
- **Divergence rule registry** (librarian.py:115-130): rules are registered as `DivergenceRule(id=..., check=..., ...)` instances; deletion is a single-row removal from the list.

### Integration points
- The `_VALID_KINDS` frozenset is referenced by both write-time (upsert) and read-time (query) paths in graph-io. Removal is single-source-of-truth — no other location duplicates the set.
- `ADMITTED_KINDS` in wiki-io is the dispatch table for entity-writer; the V18 alias was introduced to defer package_family to v1.9 — that deferral now resolves to "drop".

</code_context>

<deferred>
## Deferred Ideas

- **Vault `wiki/package-family/` directory deletion** — Phase 53 cutover (D-01).
- **Pre-flight schema check / migration command** — out of scope per D-02; if Pat ever publishes graph-io for external consumers, revisit a `cg migrate v1.8→v1.9` command with explicit `SCHEMA_MISMATCH` errors.
- **`SCHEMA_VERSION` bump policy revisit** — currently held flat across 49/50/51. When schema gains a *structural* change (new column, edge-table reshape), bump it then. Kind admission/retraction alone doesn't warrant a bump under the current policy.
- **`ADMITTED_KINDS_V18` deprecation grace** — explicitly skipped per D-04. If a future kind ever needs a multi-release deferral pattern, build it with a documented `__deprecated__` shim rather than reusing this ad-hoc alias.

</deferred>

<next_steps>
## Next Steps

1. `/gsd:plan-phase 51` — research + planning. Researcher should confirm:
   - Presence/absence of `cg describe-package-family` / `cg list-package-families` CLI handlers.
   - The exact baseline-regeneration path for `baselines/divergence-librarian.json`.
   - Whether `dependency.py` / `link_rewriter.py` `package_family` references are code or comment-only.
   - Full list of fixture files needing surgical edits (the canonical_refs list is from grep, may have gaps).
2. Plan should aim for 3–4 atomic plans:
   - **51-01**: graph-io removal (`_VALID_KINDS`, `package_family_uri`, tests).
   - **51-02**: wiki-io removal (`ADMITTED_KINDS_V18` alias, prefix dict, edge-derived block, templates, CLI handlers if present).
   - **51-03**: eval-harness CLEANUP-01 (`_SLUG_ONLY_RE`, `_check_no_slug_only_wikilinks`, registry row, baseline regen, test updates).
   - **51-04** (optional): test-fixture surgical edits + bm25 regen.
3. Verification gate: `grep -r "package_family\|package-family\|PKGFAM\|package_family_uri" packages/` returns zero hits outside migration-log comments + `grep -r "_SLUG_ONLY_RE\|_check_no_slug_only_wikilinks\|LIB-003" packages/eval-harness/` returns zero hits.

</next_steps>
