---
phase: 46-inbound-link-migration-cutover
plan: 02
type: execute
status: complete
completed_at: 2026-05-27
requirements:
  - MIGRATION-01
  - MIGRATION-02
  - MIGRATION-05
key-files:
  created:
    - packages/wiki-io/tests/test_link_rewriter_build_table.py
    - packages/wiki-io/tests/integration/test_link_rewriter_integration.py
  modified:
    - packages/wiki-io/src/wiki_io/link_rewriter.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md
commits:
  - 069a831 feat(46-02): add build_rewrite_table + rewrite_vault + migration log + docs
note: |
  ROADMAP.md SC#1 expansion (add /sources/ and /work/) was authored as part of this plan
  but landed in commit 429f43c (docs(48): create phase plan) which executed in parallel.
  The substantive change is present on main.
---

# Plan 46-02 Summary: build_rewrite_table + rewrite_vault + ROADMAP/REQUIREMENTS edits

## What Shipped

1. **`build_rewrite_table(conn, wiki_root, *, log_path)`** — three-source pipeline
   (CONTEXT D-03):
   - **Source 1** Convention templates: 5 admitted kinds (`package`, `dependency`,
     `domain`, `plugin`, `test_suite`). For each entity, BOTH bare
     (`packages/foo/index`) AND `wiki/`-prefixed (`wiki/packages/foo/index`) forms
     map to `entities/<encode_slug(uri)>`. `package_family` deferred per D-04 —
     not in `CONVENTION_TEMPLATES`.
   - **Source 2** Scan-and-match: walks `wiki/{packages,dependencies,domain,
     plugin,package-family}/` and adds any old-layout files matchable to a graph
     entity. `wiki/package-family/` is intentionally skipped (D-04).
   - **Source 3** Grep curated lanes: walks the 5 curated lanes for inbound
     wikilinks starting with any `OLD_LAYOUT_PREFIXES` entry. Resolvable targets
     are added; unresolvables become `(target, None)` AND emit one JSONL
     `{phase: unresolved, file, target, timestamp}` line to `.graph-wiki/migration.log`.

2. **`rewrite_vault(wiki_root, table, *, log_path, lanes)`** — walks the 5
   curated lanes (`wiki/concepts`, `wiki/adrs`, `wiki/architecture`,
   `wiki/sources`, workspace-rooted `work/`) per D-13. For each `.md` file:
   read text, call `rewrite_text(text, table)`, atomically write back (temp +
   `os.replace`) if count > 0. Emits one JSONL `{phase: rewrite, file, from,
   to, timestamp}` per actual rewrite. `wiki/` root files are excluded by
   default per D-14. Returns `RewriteResult` (frozen dataclass: scanned/
   modified/totals + per-file map).

3. **`_append_migration` + `_utc_iso_z`** — private JSONL log helpers; 10-line
   copy of Phase 43's `_append_deletion` shape, WITHOUT rotation
   (migration.log is one-shot per Research §8 — do NOT refactor
   `entity_writer` to share).

4. **Module constants:** `CONVENTION_TEMPLATES`, `OLD_LAYOUT_ROOTS`,
   `OLD_LAYOUT_PREFIXES`, `CURATED_LANES_REL`, `RewriteResult`.

5. **REQUIREMENTS.md MIGRATION-05** rewritten to spell out the 6-step cutover
   composition (write_entities -> rewrite_vault -> rm old dirs ->
   generate_index -> update_index -> manifest.json marker; abort-before-commit
   on failure).

6. **ROADMAP.md Phase 46 SC#1** expanded to include `/sources/` and `/work/`
   (CONTEXT D-13). This edit landed in commit `429f43c` (Phase 48 planner ran
   in parallel and absorbed the change); the substantive content is on main.

## Tests Green

```
packages/wiki-io/tests/test_link_rewriter_build_table.py:      11 passed
packages/wiki-io/tests/integration/test_link_rewriter_integration.py: 12 passed
Full wiki-io suite:                                            343 passed, 2 skipped, 1 xfailed
```

Plan 01 surfaces still green (no regression).

## Decisions Honored

- **D-03:** All three sources implemented in order; merged into a single
  table; unresolvables → `None` + JSONL log (not silent drop).
- **D-04:** `package_family` excluded from `CONVENTION_TEMPLATES`; Source 2
  skips `wiki/package-family/`; Source 3 logs `[[package-family/...]]`
  inbound references as unresolvable.
- **D-13:** All 5 curated lanes covered, including workspace-rooted `work/`.
- **D-14:** `wiki_root` itself is not in the default lane list — `wiki/index.md`
  and `wiki/log.md` are never visited (verified by
  `test_integration_wiki_root_files_not_rewritten`).
- **D-16:** `_append_migration` is private to `link_rewriter.py`; no shared
  helper hoist.
- **CONTEXT §deferred (wikilink target normalization):** Source 1 emits both
  bare and `wiki/`-prefixed forms for every entity.

## Deviations

None substantive. Two minor adjustments from the verbatim plan:

- The plan suggested optionally simplifying the `OLD_LAYOUT_PREFIXES`
  construction; I chose a clear two-tuple union over `_PREFIX_ROOTS = roots +
  ("test-suites",)` instead of the inline `tuple("test-suites" for _ in
  [None])` idiom in the plan.
- The ROADMAP SC#1 line is not on line `header+1`, so the literal
  `grep -A 1 "### Phase 46:..." | grep -q "/sources/"` acceptance check
  doesn't match. Substantively, the SC#1 line contains both `/sources/` and
  `/work/`, verified by `grep -A 20`.

## Next Wave Enables

Plan 03 (CLI + 7-step cutover orchestration) can now:
1. Build the rewrite table via `build_rewrite_table(conn, wiki_root, log_path)`
2. Apply rewrites across all curated lanes via `rewrite_vault(...)`
3. Use `RewriteResult` for the cutover summary
4. Honor the same `.graph-wiki/migration.log` JSONL shape

## Self-Check: PASSED

- [x] Task 1 acceptance — imports succeed; `build_rewrite_table`,
      `CONVENTION_TEMPLATES`, `OLD_LAYOUT_ROOTS`, `OLD_LAYOUT_PREFIXES`,
      `_append_migration` all grep-resolvable; `package_family` absent.
- [x] Task 2 acceptance — `rewrite_vault`, `RewriteResult`, `CURATED_LANES_REL`
      all defined; integration suite passes; full wiki-io regression passes.
- [x] Task 3 acceptance — SC#1 line contains `/sources/` and `/work/`;
      change landed in commit 429f43c (parallel Phase 48 planner pickup).
- [x] Task 4 acceptance — MIGRATION-05 bullet contains `all 5 curated lanes`,
      `update_index.update_index`, and the manifest.json marker; status table
      row preserved (count of "MIGRATION-05" = 2).
- [x] Plan-level verification — both new test files pass; full wiki-io suite
      green (343 passed, 2 skipped, 1 xfailed); proof-of-life one-liner imports
      succeed.
