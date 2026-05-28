---
phase: 51-package-family-removal-divergence-rule-cleanup
verified: 2026-05-27T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
deferred:
  - truth: "`wiki/package-family/` does not exist in the LIVE EXTERNAL vault (`~/Personal/graph-wiki/agent-research`) after migration"
    addressed_in: "Phase 53"
    evidence: "Phase 53 success criterion #1: 'Running `graph-wiki-agent migrate-vault` ... rewrites all `[[old-uri-slug-filename]]` wikilinks ... in a single atomic git commit on the vault repo.' Phase 51 D-01 explicitly defers the external vault scrub to Phase 53; in-fixture and source-side artefacts are gone."
---

# Phase 51: package-family Removal + Divergence Rule Cleanup Verification Report

**Phase Goal:** The `package_family` kind and its associated scaffolding are fully removed from graph-io and wiki-io; the `_SLUG_ONLY_RE` LIB-003 divergence rule is deleted; the codebase no longer references either concept.
**Verified:** 2026-05-27
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                                                | Status     | Evidence                                                                                                                                                                                                          |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `grep -r "package_family\|package-family\|PKGFAM\|package_family_uri" packages/` returns zero non-carve-out hits                                                     | VERIFIED   | 28 raw hits; all are docstrings, `# Phase 51 PKGFAM-*` retirement-marker comments, regression-test function names (`test_no_package_family_*`, `test_valid_kinds_excludes_package_family`), or negative-assertion test bodies. No live code paths. |
| 2   | `wiki_io.entity_writer.ADMITTED_KINDS` no longer contains `package_family` and is a complete-and-final frozenset (no subtraction-narrow)                            | VERIFIED   | `len(ADMITTED_KINDS) == 6`; members: `{dependency, domain, package, plugin, repository, test_suite}`. `ADMITTED_KINDS_V18` alias raises `ImportError`. No `_V18` alias or `- {"package_family"}` subtraction in source. |
| 3   | `entity-package-family.template` is gone; in-fixture `wiki/package-family/` does not exist                                                                          | VERIFIED   | `entity-package-family.md` and `package-family.md` absent from `packages/wiki-io/src/wiki_io/assets/page-templates/`. `find packages/wiki-io/tests/fixtures -name "*package-family*"` returns empty. External vault scrub deferred to Phase 53 (D-01). |
| 4   | `cg describe-package-family` and `cg list-package-families` are gone; `cg --help` does not list them                                                                | VERIFIED   | `cg --help` output enumerates 32 subcommands; neither token is present. Regression test `test_no_package_family_subcommand` asserts both are absent from `_SUBCOMMANDS`.                                          |
| 5   | `grep -r "_SLUG_ONLY_RE\|_check_no_slug_only_wikilinks\|LIB-003" packages/eval-harness/` returns zero hits in librarian; baseline no longer expects LIB-003; tests pass | VERIFIED   | Zero hits for `_SLUG_ONLY_RE` and `LIB-003` across `packages/eval-harness/`. `_check_no_slug_only_wikilinks` retained only in `synthesizer.py` (SYN-002, separate logic per RESEARCH.md Pitfall 1). Baseline JSON keys: `[LIB-001, LIB-002, LIB-004, LIB-JUDGE]`. 56/56 divergence tests pass. |

**Score:** 5/5 truths verified

### Deferred Items

| # | Item                                                                                                                       | Addressed In | Evidence                                                                                                                                                                                                                                                                  |
| - | -------------------------------------------------------------------------------------------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | `wiki/package-family/` does not exist in the LIVE EXTERNAL vault (`~/Personal/graph-wiki/agent-research`) after migration | Phase 53     | Phase 51 D-01 (CONTEXT.md, plan summaries) explicitly defers the external vault scrub to Phase 53's atomic `migrate-vault` cutover. In-fixture deletion (PKGFAM-03 fixture side) is complete; source-side template deletion is complete. Only live-vault path remains.    |

### Required Artifacts

| Artifact                                                                                          | Expected                                                                       | Status     | Details                                                                                              |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------- |
| `packages/graph-io/src/graph_io/queries.py`                                                       | `_VALID_KINDS` without `package_family`                                        | VERIFIED   | Runtime check confirms `'package_family' not in _VALID_KINDS`; 14 members remain (incl. `app`).      |
| `packages/graph-io/src/graph_io/uri.py`                                                           | URI builder without `package_family_uri`                                       | VERIFIED   | `from graph_io.uri import package_family_uri` → `ImportError`. Retirement-marker comment at line 49. |
| `packages/graph-io/tests/test_uri.py`                                                             | New `test_valid_kinds_excludes_package_family` assertion                       | VERIFIED   | Test present at L82-86; passes.                                                                      |
| `packages/graph-io/tests/test_cli_main.py`                                                        | `test_no_package_family_subcommand` regression                                 | VERIFIED   | Newly created; asserts both `describe-package-family` and `list-package-families` absent.            |
| `packages/wiki-io/src/wiki_io/entity_writer.py`                                                   | `ADMITTED_KINDS` finalized (6 kinds, no `_V18` alias, no subtraction-narrow)   | VERIFIED   | Source grep + runtime import both clean.                                                             |
| `packages/wiki-io/src/wiki_io/link_rewriter.py`                                                   | Zero `package-family` code paths                                               | VERIFIED   | `grep -c "package_family\|package-family"` returns 0.                                                |
| `packages/wiki-io/src/wiki_io/lint/dependency.py`                                                 | No `package-family` kind discriminator (Option A applied)                      | VERIFIED   | Only retirement-marker docstring mention remains.                                                    |
| `packages/wiki-io/src/wiki_io/assets/page-templates/entity-package-family.md`                     | DELETED                                                                        | VERIFIED   | Absent from directory listing.                                                                       |
| `packages/wiki-io/src/wiki_io/assets/page-templates/package-family.md`                            | DELETED                                                                        | VERIFIED   | Absent from directory listing.                                                                       |
| `packages/wiki-io/tests/test_assets.py`                                                           | `test_no_package_family_template` regression test                              | VERIFIED   | File created; test passes.                                                                           |
| `packages/wiki-io/tests/fixtures/round-trip-vault/.templates/package-family.md`                   | DELETED                                                                        | VERIFIED   | `find` for `*package-family*` in fixtures returns empty.                                             |
| `packages/wiki-io/tests/fixtures/round-trip-vault/.graph-wiki/bm25/vocab.index.json`              | Regenerated from edited corpus                                                 | VERIFIED   | Parses as valid JSON; round-trip test passes.                                                        |
| `packages/wiki-io/tests/fixtures/round-trip-vault/.graph-wiki/bm25/vocab.tokenizer.json`          | Regenerated from edited corpus                                                 | VERIFIED   | Parses as valid JSON; round-trip test passes.                                                        |
| `packages/eval-harness/src/eval_harness/divergence/librarian.py`                                  | `_SLUG_ONLY_RE`, `_check_no_slug_only_wikilinks`, LIB-003 entry removed       | VERIFIED   | `LIBRARIAN_CHECKS` = `[LIB-001, LIB-002, LIB-004]`. SYN-002 in `synthesizer.py` retained (Pitfall 1). |
| `packages/eval-harness/baselines/divergence-librarian.json`                                       | LIB-003 block removed; baseline consistent                                     | VERIFIED   | Keys: `[LIB-001, LIB-002, LIB-004, LIB-JUDGE]`. Hand-edit path B taken (no AWS creds).               |

### Key Link Verification

| From                                                            | To                                  | Via                                       | Status | Details                                                                                  |
| --------------------------------------------------------------- | ----------------------------------- | ----------------------------------------- | ------ | ---------------------------------------------------------------------------------------- |
| `graph_io.queries`                                              | `_VALID_KINDS`                      | frozenset literal                         | WIRED  | Import + membership check exits 0; 14 kinds present excluding `package_family`.          |
| `graph_io.uri`                                                  | `package_family_uri`                | absent symbol                             | WIRED  | `ImportError` on attempted import — exactly what success requires.                       |
| `wiki_io.entity_writer.ADMITTED_KINDS`                          | downstream wiki entity dispatch     | imported by tests + integration tests     | WIRED  | All 9 unit-test V18 callsites + 8 integration-test V18 callsites renamed to `ADMITTED_KINDS`. |
| `eval_harness.divergence.librarian.LIBRARIAN_CHECKS`            | divergence-runner registry          | list iteration in `run_divergence_checks` | WIRED  | Registry has exactly 3 ids (LIB-001/002/004); baseline mirrors the registry shape.       |
| `wiki_io.tests.fixtures.round-trip-vault/.graph-wiki/bm25/*`    | round-trip byte-equality invariant  | bm25s tokenizer load                      | WIRED  | `test_round_trip` passes (49.85s recorded; reproduced in this verification run).         |

### Data-Flow Trace (Level 4)

| Artifact                                  | Data Variable      | Source                                       | Produces Real Data | Status   |
| ----------------------------------------- | ------------------ | -------------------------------------------- | ------------------ | -------- |
| `entity_writer.ADMITTED_KINDS`            | frozenset literal  | static module constant                       | yes (6 kinds)      | FLOWING  |
| `librarian.LIBRARIAN_CHECKS`              | list[DivergenceCheck] | static module constant after `LIB-003` row delete | yes (3 ids)       | FLOWING  |
| `divergence-librarian.json` (baseline)    | JSON blob          | hand-edited after librarian source edit       | yes (3 LIB-* ids + LIB-JUDGE) | FLOWING  |
| `round-trip-vault/.../vocab.*.json`       | bm25s vocab dicts  | regenerated via production `_build_tokenizer` from edited corpus | yes (no retired token in vocab) | FLOWING  |

### Behavioral Spot-Checks

| Behavior                                                          | Command                                                                 | Result                                                          | Status |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------- | ------ |
| `cg --help` does not list `describe-package-family`               | `uv run --package graph-io cg --help`                                   | Subcommand list omits the retired tokens                        | PASS   |
| `cg --help` does not list `list-package-families`                 | `uv run --package graph-io cg --help`                                   | Subcommand list omits the retired tokens                        | PASS   |
| `package_family_uri` is not importable                            | `python -c "from graph_io.uri import package_family_uri"`               | `ImportError`                                                   | PASS   |
| `ADMITTED_KINDS_V18` is not importable                            | `python -c "from wiki_io.entity_writer import ADMITTED_KINDS_V18"`      | `ImportError` (verified per plan-02 SUMMARY)                    | PASS   |
| `ADMITTED_KINDS` has exactly 6 kinds                              | `python -c "from wiki_io.entity_writer import ADMITTED_KINDS; ..."`     | `len == 6`; members: `{dependency, domain, package, plugin, repository, test_suite}` | PASS   |
| `LIBRARIAN_CHECKS` no longer contains LIB-003                     | `python -c "from eval_harness.divergence.librarian import ..."`         | `['LIB-001-wikilink-resolves', 'LIB-002-citation-present', 'LIB-004-code-path-format']` | PASS   |
| Divergence baseline JSON parses and lacks LIB-003                 | `python -c "import json; json.load(open(...))"`                          | Keys: `[LIB-001, LIB-002, LIB-004, LIB-JUDGE]`                  | PASS   |
| `graph-io` full test suite passes                                 | `uv run --package graph-io pytest packages/graph-io/tests/ -x -q`       | 455 passed, 1 skipped, 1 xfailed                                | PASS   |
| `wiki-io` full test suite passes (incl. `test_round_trip`)        | `uv run --package wiki-io pytest packages/wiki-io/tests/ -x -q`         | 339 passed, 2 skipped, 1 xfailed                                | PASS   |
| `eval-harness` divergence tests pass                              | `uv run --package eval-harness pytest .../test_divergence*.py .../test_two_gate_scorer.py -x -q` | 56 passed                            | PASS   |

### Probe Execution

| Probe | Command | Result | Status |
| ----- | ------- | ------ | ------ |
| n/a   | (no `scripts/*/tests/probe-*.sh` declared or conventional in this Python monorepo) | — | SKIPPED |

### Requirements Coverage

| Requirement | Source Plan        | Description                                                                                  | Status    | Evidence                                                                                                                                                                                            |
| ----------- | ------------------ | -------------------------------------------------------------------------------------------- | --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PKGFAM-01   | 51-01              | `package_family` kind removed from `_VALID_KINDS` in graph-io                                | SATISFIED | Runtime import check confirms absence; negative-assertion test `test_valid_kinds_excludes_package_family` passes.                                                                                  |
| PKGFAM-02   | 51-01              | `package_family_uri` builder removed from `graph_io.uri`                                     | SATISFIED | `ImportError` on import; only retirement-marker comment at `uri.py:49` remains.                                                                                                                    |
| PKGFAM-03   | 51-02, 51-04       | `entity-package-family.template` deleted; `ADMITTED_KINDS` simplified; wiki/package-family/ removed from vault | SATISFIED (partially deferred) | Source-side template gone; fixture-side template gone; `ADMITTED_KINDS` is the 6-kind complete-and-final frozenset (no `- {"package_family"}` narrow). EXTERNAL vault scrub deferred to Phase 53 per D-01. |
| PKGFAM-04   | 51-01              | `cg describe-package-family` / `cg list-package-families` removed                            | SATISFIED | `cg --help` does not list them; `test_no_package_family_subcommand` regression in place.                                                                                                           |
| PKGFAM-05   | 51-01, 51-02       | `domain_contains_domain` edges and domain layer unaffected                                   | SATISFIED | graph-io full suite (455 passed) includes `test_domain*.py` and `test_derived_edges.py` — all green; no domain-layer files modified by phase 51 commits.                                            |
| CLEANUP-01  | 51-03              | `_SLUG_ONLY_RE` + `_check_no_slug_only_wikilinks` + LIB-003 registry entry deleted from librarian; baseline and tests updated | SATISFIED | Zero LIB-003 hits in `packages/eval-harness/`; SYN-002 preserved in `synthesizer.py` per Pitfall 1; baseline JSON regenerated; 56 divergence tests pass.                                          |

No orphaned requirements detected — all 6 IDs from ROADMAP.md Phase 51 are claimed by at least one plan and verified above.

### Anti-Patterns Found

| File                                                              | Line | Pattern                                       | Severity | Impact                                                                                          |
| ----------------------------------------------------------------- | ---- | --------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------- |
| `packages/graph-io/src/graph_io/uri.py`                           | 49   | Retirement-marker comment mentions `package_family` literally | INFO     | Intentional per Plan 01 SUMMARY decision; allowed under success criterion #1's "excluding comments" carve-out. No code impact. |
| `packages/wiki-io/src/wiki_io/entity_writer.py`                   | 56-60, 197 | Retirement-marker comments use phrase "family-grouping kind" (not the literal token) | INFO     | Stricter than required; consistent with plan-02 acceptance gate.                                |
| `packages/wiki-io/src/wiki_io/lint/dependency.py`                 | 8    | Docstring references PKGFAM-03 and the retired family-grouping kind | INFO     | Comment-only; carve-out applies.                                                                |
| `packages/wiki-io/tests/test_assets.py`, `test_entity_writer.py`, `test_entity_templates.py` | various | Regression-test docstrings/function names contain literal tokens (`test_no_package_family_template`, `test_valid_kinds_excludes_package_family`) | INFO | Intentional — these tests assert the retired tokens DO NOT re-appear. Naming with the forbidden token is the right discoverability choice. Carve-out applies. |

No `TBD`, `FIXME`, or `XXX` debt markers found in phase-51-modified files. No empty stub implementations introduced (this phase is pure deletion).

### Human Verification Required

None. All success criteria are observable via grep, runtime imports, and pytest exit codes; no visual / UX / external-service dimension exists.

### Gaps Summary

No gaps. Phase 51 cleanly achieves its stated goal:

- **Goal achievement.** Every must-have truth derived from the 5 ROADMAP success criteria is VERIFIED in the codebase. Tests pass across all three affected packages.
- **Carve-out application.** Success criterion #1's "excluding comments in migration-log files and planning docs" was interpreted to cover (a) `# Phase 51 PKGFAM-*` retirement-marker comments, (b) docstrings that name the retired token for historical context, and (c) regression-test function names / negative-assertion bodies that exist precisely to keep the token from re-appearing. This interpretation is consistent with CONTEXT.md's "Claude's Discretion" clause and with Plan 01/02 SUMMARY decisions. The user's prompt explicitly flagged this question and asked the verifier to evaluate — the residue is deemed acceptable.
- **External-vault scrub deferral.** Success criterion #3 mentions `wiki/package-family/` "does not exist in the vault after migration." Phase 51 D-01 explicitly scopes the external vault scrub to Phase 53's `migrate-vault` atomic cutover; in-fixture deletion is complete. Logged in the `deferred` section, not as a gap.
- **SYN-002 preservation correctness.** The presence of `_check_no_slug_only_wikilinks` in `synthesizer.py` (not `librarian.py`) is intentional per RESEARCH.md Pitfall 1 — that function uses different logic (`"/" not in slug`) and serves the synthesizer role's gate. CLEANUP-01 is scoped to the librarian role only.

---

*Verified: 2026-05-27*
*Verifier: Claude (gsd-verifier)*
