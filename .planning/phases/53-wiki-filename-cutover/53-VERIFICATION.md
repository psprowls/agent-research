---
status: human_needed
phase: 53-wiki-filename-cutover
phase_req_ids: [WIKI-FN-05, WIKI-FN-06]
plan_count: 2
must_haves_total: 20
must_haves_verified: 18
must_haves_human_only: 2
plans_summary: [53-01, 53-02]
verified_at: 2026-05-28
---

# Phase 53: Wiki Filename Cutover — VERIFICATION

## Goal Restatement

Per `.planning/ROADMAP.md` §Phase 53:

> The wiki-io codebase no longer carries dead bidirectional-slug machinery
> (`encode_slug` / `decode_slug`); all consumer call sites read entity
> `frontmatter.uri` directly or call `short_filename` from Phase 52; the
> exploratory `~/Personal/graph-wiki/agent-research` vault is regenerated
> from scratch to reflect Phase 52's short filenames; UAT findings are
> documented in `53-UAT.md`.

## Plan-level must_haves status

### Plan 53-01 (markdown reshape)

| # | Must-have | Source / Evidence | Status |
|---|---|---|---|
| 1.1 | ROADMAP §Phase 53 SC #1 (`migrate-vault` atomic rewrite) REMOVED | `grep -A30 "^### Phase 53" .planning/ROADMAP.md` — only "Scope reshape" historical mention remains, no SC mentioning `migrate-vault` | ✓ |
| 1.2 | ROADMAP §Phase 53 SC #2 (idempotency via manifest marker) REMOVED | same block — `idempotent via manifest marker` absent | ✓ |
| 1.3 | ROADMAP §Phase 53 SC #3 rewritten to verification observation re Phase 52 | same block — SC #3 says "verified observation from Phase 52's `write_entities` correctness" | ✓ |
| 1.4 | ROADMAP §Phase 53 SC #4 rewritten as manual UAT procedure | same block — SC #4 enumerates the delete → cg update → scan → inspect sequence and points at `53-UAT.md` | ✓ |
| 1.5 | ROADMAP §Phase 53 Goal loosened ('single atomic operation' wording removed) | same block — `single atomic operation` absent; goal mentions "regenerated from scratch" + UAT | ✓ |
| 1.6 | REQUIREMENTS.md WIKI-FN-05 rewritten to verification-language | `grep WIKI-FN-05 .planning/REQUIREMENTS.md` — bullet now mentions `encode_slug` / `decode_slug` removal + grep-zero gate + test pass | ✓ |
| 1.7 | REQUIREMENTS.md WIKI-FN-06 rewritten to verification-language | `grep WIKI-FN-06 .planning/REQUIREMENTS.md` — bullet now mentions short filenames + manual vault regen + `53-UAT.md` | ✓ |
| 1.8 | REQUIREMENTS.md traceability table for WIKI-FN-05/06 unchanged | both rows stay `Phase 53 / Pending`; `git diff` of plan 53-01 shows no edits below line 65 of REQUIREMENTS.md | ✓ |
| 1.9 | No source code under `packages/` or `agents/` touched by plan 53-01 | commit `d04cc9a` + `d918873` modify only `.planning/REQUIREMENTS.md` + `.planning/ROADMAP.md` | ✓ |

### Plan 53-02 (source cleanup)

| # | Must-have | Source / Evidence | Status |
|---|---|---|---|
| 2.1 | `encode_slug(uri)` definition REMOVED from `entity_writer.py` | `grep -cE "^def encode_slug" packages/wiki-io/src/wiki_io/entity_writer.py` → 0 | ✓ |
| 2.2 | `decode_slug(slug)` definition REMOVED from `entity_writer.py` | `grep -cE "^def decode_slug" packages/wiki-io/src/wiki_io/entity_writer.py` → 0 | ✓ |
| 2.3 | `_ADMITTED_URI_PREFIXES` REMOVED (orphan branch — D-06 default) | `grep -E "^_ADMITTED_URI_PREFIXES" packages/wiki-io/src/wiki_io/entity_writer.py` → 0 lines (only historical comment remains) | ✓ |
| 2.4 | `link_rewriter.py` no longer imports/calls `encode_slug`/`decode_slug`; uses `short_filename` + `frontmatter.uri` reverse lookups | `grep "encode_slug\|decode_slug" packages/wiki-io/src/wiki_io/link_rewriter.py` → 0; uses `short_filename` 4× | ✓ |
| 2.5 | `index_generator.py` no longer imports/calls `encode_slug`/`decode_slug`; uses `short_filename` | `grep "encode_slug\|decode_slug" packages/wiki-io/src/wiki_io/index_generator.py` → 0; uses `short_filename` 5× | ✓ |
| 2.6 | Scanner-side `agents/graph-wiki-agent/...scan.py` uses `short_filename` instead of `encode_slug` | `grep "encode_slug\|decode_slug" agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` → 0 | ✓ |
| 2.7 | Global symbol-removal grep returns ZERO hits | `grep -rn "encode_slug\|decode_slug" packages/ agents/ --include="*.py"` → 0 | ✓ |
| 2.8 | Legacy tests (`test_encode_slug` / `test_decode_slug` / round-trip property tests) deleted | `grep -rn "encode_slug\|decode_slug" packages/wiki-io/tests/` → 0 | ✓ |
| 2.9 | Round-trip fixture reflects short-form filename scheme | `find packages/wiki-io/tests/fixtures/round-trip-vault/ -name "*__*__*__*.md"` → 0; no long-form wikilinks either (no-op confirmation per D-07) | ✓ |
| 2.10 | wiki-io test suite passes | `uv run --package wiki-io pytest packages/wiki-io/tests/` → 356 passed, 2 skipped, 1 xfailed | ✓ |
| 2.11 | Negative import test passes | `from wiki_io.entity_writer import encode_slug` raises ImportError; same for `decode_slug` | ✓ |

### Phase-level

| # | Goal-level item | Status |
|---|---|---|
| P.1 | Dead bidirectional-slug machinery removed | ✓ (must_haves 2.1, 2.2, 2.3, 2.7) |
| P.2 | All consumer call sites use `frontmatter.uri` or `short_filename` | ✓ (must_haves 2.4, 2.5, 2.6) |
| P.3 | Manual vault regen produces short filenames (D-08) | **Human verification required** — see below |
| P.4 | UAT findings documented in `53-UAT.md` | **Human verification required** — see below |

## Human verification items

Two items require Pat's manual execution before phase ships:

### H.1 — Manual vault regen + spot-check

Run the regen sequence on `~/Personal/graph-wiki/agent-research`:

```bash
cd ~/Personal/graph-wiki/agent-research
rm -rf wiki/packages wiki/dependencies wiki/domain wiki/plugin wiki/test-suites wiki/app
cd ~/Personal/agent-research
uv run cg update --full
uv run graph-wiki-agent scan
```

Expected behavior:
- `cg update --full` completes without error.
- `graph-wiki-agent scan` populates `wiki/entities/` with short-form filenames (e.g. `pkg_graph-io.md`, `dep_boto3.md`, `unit_tests_wiki-io.md`).
- `wiki/index.md` is regenerated; spot-check that entries point at the new short filenames.
- No `pkg__org__repo__name.md` style files remain in `wiki/entities/`.

### H.2 — Record UAT findings in `53-UAT.md`

After H.1 succeeds (or surfaces issues), create `.planning/phases/53-wiki-filename-cutover/53-UAT.md` recording:
- Date / commit hash regen ran against
- Entity counts (created / updated / unchanged) from scan output
- 2-3 spot-checked entity filenames + URIs
- Any anomalies (missing entities, unexpected filenames, broken wikilinks)
- Pass/fail verdict

## Out-of-scope / pre-existing findings

- `tests/test_integration_gate.py::test_integration_test_files_use_canonical_gate` — pre-existing failure unrelated to Phase 53; 7 integration test files don't match the canonical `GRAPH_WIKI_RUN_INTEGRATION` skipif pattern from `docs/testing.md`. None were touched by Phase 53. Recorded in `53-02-SUMMARY.md` ## Issues Encountered.

## Test summary

| Suite | Result |
|---|---|
| `uv run --package wiki-io pytest packages/wiki-io/tests/` | **356 passed, 2 skipped, 1 xfailed** |
| `uv run pytest agents/graph-wiki-agent/tests/test_migrate_vault.py` | **13 passed** |
| `uv run pytest` (workspace) | **1526 passed, 1 failed (pre-existing), 38 skipped, 2 xfailed** |
| Negative import: `encode_slug` | ImportError ✓ |
| Negative import: `decode_slug` | ImportError ✓ |
| Positive import: Phase 52 survivors | ok ✓ |

## Decision

**status: human_needed.** 18/20 must_haves verified automatically. 2 must_haves (H.1 + H.2 — manual vault regen and UAT recording) require Pat's manual execution before the phase can be marked fully complete. All automated gates pass; no source-code work remains.

The HUMAN-UAT contract (per the workflow `verify_phase_goal` step's `human_needed`
branch) is satisfied by surfacing H.1 + H.2 as `53-UAT.md` items that will appear in
`/gsd:progress` and `/gsd:audit-uat` until Pat runs them and flips status to
`passed`.
