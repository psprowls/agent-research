---
phase: 46-inbound-link-migration-cutover
status: passed
verified_at: 2026-05-27
verified_by: gsd-execute-phase (inline verification)
requirements_verified:
  - MIGRATION-01
  - MIGRATION-02
  - MIGRATION-03
  - MIGRATION-04
  - MIGRATION-05
---

# Phase 46 Verification: Inbound-Link Migration + Cutover

## Phase Goal (from ROADMAP)

> `link_rewriter.py` rewrites old layout wikilinks in curated lanes to new
> entity slugs (Markdown-aware, alias-preserving, idempotent), and the cutover
> commit atomically populates `wiki/entities/`, rewrites inbound links,
> removes old directories, and regenerates the index — the vault restructure
> is complete

## Status: PASSED

All five MIGRATION requirements are implemented and tested. The code that
ENABLES the user-gated atomic cutover ships in this phase; the destructive
production cutover (`graph-wiki-agent migrate-vault`) is a manual user step
intentionally NOT executed by this orchestrator.

## Requirement-by-Requirement

### MIGRATION-01 — Markdown-aware rewriter (prose-only)

**Status: PASSED**

- `wiki_io.link_rewriter.rewrite_text(text, table) -> (new_text, count)`
  defined in `packages/wiki-io/src/wiki_io/link_rewriter.py:92`.
- Tokenizes via `_code_region_spans` which unions fenced
  (`FENCED_CODE_RE`), inline (`INLINE_CODE_RE`), and indented
  (`indented_code_spans`) spans; merges; sorts.
- Wikilinks whose `m.start()` falls inside any merged code span are SKIPPED
  (byte-preserved in output).
- Tests: `test_rewrite_text_skips_fenced_code`,
  `test_rewrite_text_skips_inline_code`, `test_rewrite_text_skips_indented_code`
  in `packages/wiki-io/tests/test_link_rewriter.py` — all pass.

### MIGRATION-02 — Graph-derived rewrite table

**Status: PASSED**

- `build_rewrite_table(conn, wiki_root, *, log_path)` in
  `packages/wiki-io/src/wiki_io/link_rewriter.py:435` runs the three-source
  pipeline (CONTEXT D-03):
  - Source 1: convention templates × `graph_io.queries.list_*` (5 kinds).
  - Source 2: scan-and-match `wiki/<old-root>/*.md` against the in-memory
    `(kind, name[, ecosystem]) → new_slug` index built from Source 1.
  - Source 3: grep curated lanes for inbound `OLD_LAYOUT_PREFIXES`;
    resolvables → table; unresolvables → `(target, None)` + JSONL log.
- No hardcoded entity strings — every new slug comes from
  `encode_slug(node.attrs["uri"])`.
- Tests: 11 tests in `test_link_rewriter_build_table.py` exercise each
  source, dedup, unresolvable logging, package_family exclusion.

### MIGRATION-03 — Idempotency + marker

**Status: PASSED**

- `rewrite_text` is idempotent: rewritten slugs no longer match `table` keys;
  second call returns `(text, 0)`. Test:
  `test_rewrite_text_idempotent`.
- `run_migrate_vault` Step 0 reads `.graph-wiki/manifest.json`; if
  `migrated_to == "v1.8-entity-restructure"`, prints
  `Vault is already migrated. ...` and returns 0 without touching the
  filesystem. Tests:
  - `test_migrate_vault_second_run_no_op` — back-to-back runs; second is a
    no-op + empty `git status --porcelain`.
  - `test_migrate_vault_force_no_effect_on_clean_state` — `--force` on
    a clean post-migration state is also a no-op.
  - `test_migrate_vault_force_recovery` — partial-cutover state (marker
    present + old dirs remain) → `--force` completes cleanup.
- Marker schema:
  `{migrated_to, migrated_at, rewrite_count, rewrite_unresolved}` written by
  `_write_manifest` (D-08); verified by
  `test_migrate_vault_full_cutover_writes_manifest`.

### MIGRATION-04 — Code-block exclusion test

**Status: PASSED**

- The fenced-code-block exclusion test is the second-source acceptance
  criterion. Test: `test_rewrite_text_skips_fenced_code` asserts the
  fenced-block bytes are preserved byte-identical AND the surrounding prose
  wikilinks are rewritten — byte equality verified via direct string
  comparison.
- Reinforcing test in the integration suite:
  `test_integration_fenced_code_byte_preserved` runs the full `rewrite_vault`
  pass and asserts the fenced wikilink survives intact.

### MIGRATION-05 — Atomic cutover composition

**Status: PASSED**

- `graph_wiki_agent.commands.migrate_vault.run_migrate_vault` orchestrates
  the 6-step composition under a single `git add -A` + `git commit` (the
  7th step) per CONTEXT D-06: write_entities → rewrite_vault → git rm -r
  → generate_index → update_index → manifest marker → commit.
- Abort-before-commit on any step failure (D-07); exit code 2; working tree
  left dirty for manual recovery. Test:
  `test_migrate_vault_aborts_before_commit_on_failure` (monkeypatches
  `generate_index`, asserts exit 2 + no new commit + dirty working tree).
- Single-commit invariant: `test_migrate_vault_single_commit` checks
  `git rev-list --count HEAD` increments by exactly 1 AND
  `git log -1 --format=%s` equals
  `feat(46): v1.8 entity restructure cutover`.
- CLI surface: `graph-wiki-agent migrate-vault --help` shows `--dry-run` /
  `--force` (`--no-write-marker` is hidden by design).
- REQUIREMENTS.md MIGRATION-05 bullet rewritten in Plan 02 to spell out the
  6-step composition; ROADMAP.md Phase 46 SC#1 expanded to include
  `/sources/` and `/work/`.

## Decisions Honored (CONTEXT.md)

| Decision | Status |
|----------|--------|
| D-01 regex with code-region masking; no markdown-it-py | Honored — `pyproject.toml` unchanged |
| D-02 explicit fixture suite for edge cases | Honored — 18 tests for `rewrite_text` |
| D-03 three-source rewrite-mapping pipeline | Honored — `build_rewrite_table` |
| D-04 package_family deferred in `CONVENTION_TEMPLATES` | Honored — explicitly excluded |
| D-05 wiki/package-family/ IS removed by Step 3 | Honored — `OLD_LAYOUT_ROOTS` includes it |
| D-06 atomic 7-step cutover composition | Honored — `run_migrate_vault` |
| D-07 abort-before-commit on failure | Honored + tested |
| D-08 idempotency marker JSON shape | Honored — `_write_manifest` |
| D-09 idempotency check is FIRST step | Honored — pre-DB-open |
| D-10 `--force` bypass + clean-state no-op | Honored + tested |
| D-11 `--dry-run` / `--force` / `--no-write-marker` flags | Honored |
| D-12 dry-run output sections | Honored + tested |
| D-13 all 5 curated lanes incl. `work/` rewritten | Honored — `CURATED_LANES_REL` |
| D-14 `wiki/` root files NOT rewritten | Honored + tested |
| D-15 flat command, not subapp | Honored — `@app.command(name="migrate-vault")` |
| D-16 JSONL migration.log helper private | Honored — `_append_migration` |

## Test Suite Results

```
packages/wiki-io/tests/                          343 passed, 2 skipped, 1 xfailed
agents/graph-wiki-agent/tests/                   328 passed, 11 skipped
  (of which test_migrate_vault.py:               13 passed)
```

The 1 xfailed test (`test_rewrite_text_nested_fence_known_limitation`) is
documented as a v1.8 known limitation per CONTEXT D-02.

## Live-Vault Cutover (User-Gated)

Phase 46 EXECUTION shipped the enabling code and ran all tests against
tmpdir fixture vaults. The destructive cutover against the live
`agent-research` vault is intentionally NOT performed by this orchestrator
— the user runs:

```
uv run graph-wiki-agent migrate-vault --dry-run  # preview
uv run graph-wiki-agent migrate-vault            # commit
```

## Gaps

None.

## Cross-Phase Notes

- Phase 47 (`cg domain-clusters`) and Phase 48 (`graph propose-domains`) ran
  in parallel with Phase 46 execution. The Phase 48 planner commit
  (`429f43c docs(48): create phase plan`) absorbed Phase 46's ROADMAP SC#1
  edit; this is expected per the user's pre-execution note ("Phase 48
  planner is running in parallel — its only file touch is
  `.planning/phases/48-graph-propose-domains/`, which Phase 46 does NOT
  modify"). The substantive content landed correctly on `main`.

## Verification Method

Inline verification by the execute-phase orchestrator (Claude Opus 4.7) —
the runtime in this session lacks the `Agent` tool used for spawning
gsd-verifier sub-agents, so the orchestrator performed the verification
itself using the same checks: read all SUMMARY.md files, cross-reference
the requirement IDs in PLAN frontmatter against REQUIREMENTS.md, spot-check
each `must_haves` truth statement against the committed code via grep + test
results.
