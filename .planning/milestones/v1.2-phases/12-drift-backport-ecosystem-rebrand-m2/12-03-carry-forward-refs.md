# Phase 12 Carry-Forward `lattice` References

Hand-off to plan 04 Task 1 (`.brand-grep-allow` authoring). Each row lists a surviving `lattice` reference left verbatim after the Phase 12 plan 03 rebrand sweep, with a one-line rationale.

The rationale falls into one of these classes:

- **Provenance** — a "Ported from / Extracted from / Ported verbatim from" header documenting the upstream module a downstream file was lifted from. Renaming would lie about history.
- **Parity-behavior** — a comment describing that the downstream code matches upstream behavior bit-for-bit (e.g., BM25 tokenizer parity). The literal upstream name is the calibration target.
- **Upstream-reference** — the prose explicitly names the upstream system (`upstream lattice-wiki-core`, `upstream lattice-workspace`) as the thing being ported, benchmarked against, or replaced. Rebranding would erase the upstream/downstream distinction.
- **Test-data** — recorded baseline answers / fixtures referencing the upstream package name as the subject the eval is measuring (per R-02).
- **Upstream-guard** — a test that asserts the downstream code does NOT import the upstream symbol. Renaming the literal would break the guard.
- **Test-fixture (non-round-trip)** — a fixture file outside `round-trip-vault/` whose content was generated against the upstream tooling and is consumed verbatim by tests (R-01 spirit).
- **Plan-meta** — requirement / phase / decision text that DESCRIBES the rebrand itself (e.g., BRAND-01 reads "all `lattice` references renamed to `graph-wiki`"). Cannot be rewritten without losing meaning.
- **Historic-decision-log** — dated entries in PROJECT.md key-decisions, Validated milestones, or Out-of-Scope context that describe upstream lattice-wiki as it existed at the time (R-03).

## Plan-meta + Upstream-reference (live planning surface)

| Path                                     | Line(s)                                | Class               | One-line rationale                                                                                                       |
| ---------------------------------------- | -------------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| CLAUDE.md                                | 6, 8, 10, 17                           | Upstream-reference  | Project intro / core-value / north-star / format-compatibility — names upstream lattice-wiki as the system being ported. |
| .planning/PROJECT.md                     | 5, 9, 11, 18, 20, 29, 34, 35, 36, 49   | Upstream-reference  | Current-state, current-milestone, M1/M2/M3 goal descriptions referencing upstream packages/plugin.                       |
| .planning/PROJECT.md                     | 62                                     | Historic-decision-log | v1.1 Validated entry: divergence eval baseline against upstream lattice-wiki (dated milestone closeout, R-03).         |
| .planning/PROJECT.md                     | 125, 127                               | Historic-decision-log | Out-of-Scope items describing upstream lattice-wiki behavior matching / transition policy.                            |
| .planning/PROJECT.md                     | 132, 133, 135, 139                     | Historic-decision-log | Context §"Prior work — the thing being reimplemented" — describes upstream paths and Pat's prior work (R-03).         |
| .planning/PROJECT.md                     | 158                                    | Upstream-reference  | Constraint: read existing upstream lattice-wiki vaults — names the compatibility target.                                 |
| .planning/PROJECT.md                     | 171, 176, 180                          | Historic-decision-log | Key Decisions table — validated decisions referencing upstream system at the time of the decision (R-03).             |
| .planning/REQUIREMENTS.md                | 3, 14, 16, 18, 20, 24, 30, 36, 37, 38  | Plan-meta           | Milestone goal + WS-/BACKPORT-/BRAND-/PLUGIN- requirements explicitly describe the rename from upstream → graph-wiki.    |
| .planning/ROADMAP.md                     | 48, 51, 65, 68, 78, 94, 98, 104, 110, 121 | Plan-meta / Upstream-reference | Phase summaries and success criteria for Phases 11–15 describing the port/rebrand work and upstream comparisons.   |
| .planning/STATE.md                       | 28, 32                                 | Upstream-reference  | Core Value / North Star (mirrored from PROJECT.md).                                                                      |
| .planning/STATE.md                       | 103                                    | Plan-meta           | Research Flags note: "internal port/rebrand of known upstream lattice code".                                             |
| .planning/STATE.md                       | 132                                    | Upstream-reference  | Session continuity context: upstream source-code paths for port work.                                                    |

## Provenance / Parity-behavior (packages/ + agents/)

| Path                                                           | Line(s)            | Class            | One-line rationale                                                                |
| -------------------------------------------------------------- | ------------------ | ---------------- | --------------------------------------------------------------------------------- |
| packages/wiki-io/src/wiki_io/__init__.py                     | 1                  | Provenance       | Package docstring: "(ported from lattice-wiki-core)" — accurate port history.     |
| packages/wiki-io/src/wiki_io/ingest_work_item.py             | 4, 7, 129          | Provenance       | Module + function docstrings: "Extracted from lattice-wiki-core's …"              |
| packages/wiki-io/src/wiki_io/ingest_source.py                | 4                  | Provenance       | Module docstring: "Extracted from lattice-wiki-core's ingest_source.py".          |
| packages/eval-harness/src/eval_harness/baseline.py             | 5, 6, 43           | Provenance       | "Ported from lattice-evals/runner_headless.py" + dropped-sections note + verbatim eval-prompt provenance. R-02. |
| packages/eval-harness/src/eval_harness/pricing.py              | 4, 17              | Provenance       | "Ported from lattice-evals/pricing.py" + cache-key inline note. R-02.             |
| agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py   | 8, 59, 176, 192    | Parity-behavior  | BM25 tokenizer + stopword-set parity with upstream lattice-wiki-core wiki_search. |

## Test prose / Upstream-guard / Test-data (test files)

| Path                                                                | Line(s)                                   | Class               | One-line rationale                                                                                                                 |
| ------------------------------------------------------------------- | ----------------------------------------- | ------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| packages/wiki-io/tests/test_ingest_source.py                       | 3, 5, 239, 243, 251                       | Provenance + Upstream-guard | Module docstring + comment + function name `test_no_lattice_wiki_core_imports` + `assert "lattice_wiki_core" not in text` guard. Renaming breaks the guard. |
| packages/wiki-io/tests/test_ingest_work_item.py                    | 3, 5, 273, 277, 286                       | Provenance + Upstream-guard | Same shape as above for ingest_work_item: docstring + comment + guard test + assertion literal.                                 |
| packages/wiki-io/tests/test_wikilink_predicate.py                  | 3                                         | Provenance          | "Ported from lattice_wiki_core/tests/test_lint_wikilink_placeholders.py".                                                          |
| packages/wiki-io/tests/test_lint_modules.py                        | 4                                         | Provenance          | "Finding-count parity with lattice-wiki-core" — describes the test's parity goal.                                                  |
| packages/wiki-io/tests/fixtures/single-package-vault/log.md        | 12                                        | Test-fixture        | Fixture log file generated against upstream tooling; consumed verbatim. R-01 spirit applies outside `round-trip-vault/` too.       |
| packages/eval-harness/tests/test_two_gate_scorer.py                 | 49                                        | Test-data           | Recorded answer cites `[[packages/lattice-wiki-core]]` — measures behavior against upstream subject (R-02).                       |
| packages/eval-harness/tests/test_sweep.py                           | 72                                        | Test-data           | Query subject ("What does lattice-wiki-core do?") — recorded baseline (R-02).                                                      |
| packages/eval-harness/tests/test_divergence_metric.py               | 76, 103, 104, 105, 152, 195               | Test-data           | Recorded answer payloads citing `[[packages/lattice-wiki-core]]` (R-02).                                                           |
| packages/eval-harness/tests/test_structural.py                      | 36, 37, 112                               | Test-data           | Recorded structural-test inputs citing the upstream package (R-02).                                                                |
| packages/eval-harness/tests/test_divergence_checks.py               | 42, 43, 70, 95, 371, 377                  | Test-data           | Divergence-check inputs + a synthetic source-page citing the upstream package (R-02).                                              |
| packages/eval-harness/tests/eval/test_sweep_eval.py                 | 224, 225, 226, 227                        | Test-data           | Sweep-eval query + answers + expected substring — the entire test subject is "what does lattice-wiki-core do?" (R-02).             |

## Out-of-scope allowlists (already covered by R-01..R-03, NOT re-listed individually)

These scopes are already known carry-forward and should remain on the .brand-grep-allow allowlist without per-file enumeration:

- `packages/wiki-io/tests/fixtures/round-trip-vault/**` (R-01)
- `packages/eval-harness/baselines/divergence-*.json` (R-02)
- `packages/eval-harness/src/eval_harness/divergence/rubrics/*.md` (R-02)
- `.planning/RETROSPECTIVE.md`, `.planning/MILESTONES.md`, `.planning/milestones/v1.0-*.md`, `.planning/milestones/v1.1-*.md` (R-03)
- `.planning/spikes/00*/README.md` (R-03)
- `.planning/spikes/WRAP-UP-SUMMARY.md` (R-03)
- `.planning/sweep/STORY.md` (R-03)
- `.planning/research/*.md` (R-03)
- `.planning/threads/next-milestone-planning.md` (R-03)
- `.planning/phases/12-*/12-CONTEXT.md` and `.planning/phases/12-*/12-03-*-PLAN.md` (this phase's own context describes the rebrand)
- `.brand-grep-allow` (self-allowlist per R-04 §Claude's Discretion)
- `scripts/check-brand.sh` (the grep-gate script literal contains `lattice` as a pattern fragment)

Plan 04 should encode the file-specific carry-forwards above as literal path entries in `.brand-grep-allow`, and the scope-globs above as `path-glob` entries. Both classes give a self-documenting allowlist where every entry has a `# rationale: …` comment.
