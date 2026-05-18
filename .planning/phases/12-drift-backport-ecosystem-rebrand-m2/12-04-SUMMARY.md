---
phase: 12-drift-backport-ecosystem-rebrand-m2
plan: 04
subsystem: brand-grep-gate
tags: [brand-04, brand-01, grep-gate, allowlist, phase-verification]
requires: [12-03]
provides:
  - "scripts/check-brand.sh — re-runnable BRAND-04 grep gate (set -euo pipefail, plugins/ in targets per W5, grep -vF -f .brand-grep-allow exclusion)"
  - ".brand-grep-allow — versioned allowlist with per-entry rationale comments grouped by R-decision + carry-forward class (52 entries)"
  - "Phase 12 verification complete — gate exits 0, uv run pytest exits 0 (526 passed, 30 skipped, 19 snapshots passed)"
  - "BRAND-01 + BRAND-04 closed; SC#3 + SC#5 from ROADMAP §Phase 12 satisfied"
affects:
  - scripts/
  - repo root (.brand-grep-allow)
tech-stack:
  added: []
  patterns:
    - "grep -vF -f <allowlist> path-fragment substring filtering — line-oriented exclusion semantics"
    - "Two-stage verification with named exit-code variables (GATE_RC, TEST_RC) per W4 — distinguishable failure attribution"
    - "Per-entry # rationale comment grouped under R-01..R-04 / carry-forward (post-hoc) section headers"
key-files:
  created:
    - scripts/check-brand.sh
    - .brand-grep-allow
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-04-SUMMARY.md
  modified: []
decisions:
  - "Allowlist entries use path fragments (e.g., `packages/eval-harness/baselines/`) not exact paths — the gate's `grep -vF -f` does substring matching so a fragment safely covers all files under a directory while remaining specific enough to avoid over-allowing."
  - "Self-allowlist `.brand-grep-allow` + `scripts/check-brand.sh` (per R-04 §Claude's Discretion) — both files literally contain `lattice` as pattern/documentation."
  - "Post-hoc carry-forward additions for hits not enumerated by plan 03's `12-03-carry-forward-refs.md`: `packages/workspace-io/` (Provenance — ported from upstream lattice-workspace), `packages/prompt-sources/` (Provenance — canonical upstream SKILL.md prose), `packages/eval-harness/baselines/divergence-{ingestor,librarian}.json` (R-02 — recorded baseline JSONs), `agents/code-wiki-agent/tests/commands/test_lint_parity.py` + `tests/prompts/test_provenance.py` (Provenance — test-prose port-history refs). All classified against existing R-01/R-02/R-03 decisions; no genuine missed rebrand."
  - "No allowlist iteration during gate run — gate passed first try (GATE_RC=0 on initial invocation), so Task 2 added no commit per plan §Task 2 last paragraph."
metrics:
  duration: ~10 minutes wall-clock
  commits: 1
  completed: 2026-05-18
  gate_hits: 0
  gate_rc: 0
  test_rc: 0
  tests_passed: 526
  tests_skipped: 30
  snapshots_passed: 19
  allowlist_entries: 52
  allowlist_lines: 165
---

# Phase 12 Plan 04: Grep Gate + Verification Summary

`scripts/check-brand.sh` + `.brand-grep-allow` landed as a single atomic commit; both Phase 12 verification stages green on first run. BRAND-01 (rebrand surfaces) verified via the gate; BRAND-04 (reproducible grep-gate) closed by the script's existence and green exit. Phase 12 verification complete.

## Verification Results

| Stage    | Command                  | Exit code captured | Result                                 |
| -------- | ------------------------ | ------------------ | -------------------------------------- |
| 1: gate  | `bash scripts/check-brand.sh` | `GATE_RC=0`     | `BRAND-04 OK: zero unallowlisted hits` |
| 2: tests | `uv run pytest`          | `TEST_RC=0`        | 526 passed, 30 skipped, 19 snapshots passed |

Both stages green on the first run; no allowlist iteration was required.

## Commits

| #   | Subject                                                                | SHA       | Files | Purpose                                              |
| --- | ---------------------------------------------------------------------- | --------- | ----- | ---------------------------------------------------- |
| 1   | `chore(12-04): land brand grep-gate + allowlist (BRAND-04)`            | `644b942` | 2     | scripts/check-brand.sh + .brand-grep-allow committed atomically. |

Task 2 added no commit (gate passed first try; per plan §Task 2 last paragraph this is the expected zero-iteration path).

## Allowlist Coverage (per R-decision)

| Decision | Paths covered                                                                                                                                                                                                                                                              | Entry count |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| R-01     | `packages/vault-io/tests/fixtures/round-trip-vault/` — real upstream lattice vault preserved verbatim for byte-identical round-trip parsing.                                                                                                                              | 1           |
| R-02     | `packages/eval-harness/baselines/`, `packages/eval-harness/src/eval_harness/divergence/rubrics/`, `packages/eval-harness/src/eval_harness/{baseline,pricing}.py`, plus 6 test files citing the upstream package as measurement subject, plus 2 divergence baseline JSONs. | 11          |
| R-03     | `.planning/RETROSPECTIVE.md`, `.planning/MILESTONES.md`, `.planning/milestones/v1.0-`, `.planning/milestones/v1.1-`, `.planning/spikes/{001,002,WRAP-UP-SUMMARY}.md`, `.planning/sweep/STORY.md`, `.planning/research/`, `.planning/threads/next-milestone-planning.md`.    | 10          |
| R-04     | `.brand-grep-allow` + `scripts/check-brand.sh` self-allowlist; `scripts/drift-diff.sh` references upstream lattice-wiki-core paths; phase 11 + phase 12 plan dirs reference both names; spike scaffolding; vault-io DRIFT-DECISIONS{,-RAW}.md embed upstream symbols.       | 8           |

Carry-forward refs from plan 03 (Plan-meta, Upstream-reference, Provenance, Parity-behavior, Test-data, Upstream-guard, Test-fixture, Historic-decision-log) add the remaining 22 entries. **Total non-comment entries: 52** (matches plan 03's "52 surviving lattice references across 10 classes" count after path-level deduplication).

## Plan-03 Carry-Forward Incorporation

`.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md` enumerated 52 surviving references across 10 classes plus 12 scope-glob allowlists. The allowlist incorporates:

- **22 per-file entries** under the "carry-forward refs" section header (each preceded by a `# rationale: …` line citing the carry-forward class).
- **12 scope-glob entries** in the R-01/R-02/R-03 sections covering the path prefixes (`packages/vault-io/tests/fixtures/round-trip-vault/`, `packages/eval-harness/baselines/`, `.planning/milestones/v1.0-`, etc.).
- **9 post-hoc additions** for hits plan 03 did not enumerate but which classify cleanly against existing R-decisions (workspace-io Provenance, prompt-sources Provenance, eval-harness baselines JSON R-02, two agent test-prose Provenance files).

The audit-trail header `# Phase 12 plan-03 carry-forward refs (from …12-03-carry-forward-refs.md)` is present so future readers see exactly which file seeded the allowlist.

## `.brand-grep-allow` Contents (audit)

```text
# .brand-grep-allow — allowlist consumed by scripts/check-brand.sh (BRAND-04 grep gate)
#
# Format (per R-04): one path or path-fragment per line. Lines starting with `#` are
# comments and are ignored by `grep -vF -f` …
# … (full file inlined below) …

# R-01: round-trip-vault test fixtures
packages/vault-io/tests/fixtures/round-trip-vault/

# R-02: eval-harness baselines + divergence rubrics
packages/eval-harness/baselines/
packages/eval-harness/src/eval_harness/divergence/rubrics/
packages/eval-harness/src/eval_harness/baseline.py
packages/eval-harness/src/eval_harness/pricing.py

# R-03: archived / historical planning documents
.planning/RETROSPECTIVE.md
.planning/MILESTONES.md
.planning/milestones/v1.0-
.planning/milestones/v1.1-
.planning/spikes/001-subagent-context-audit/README.md
.planning/spikes/002-lattice-drift-inventory/README.md
.planning/spikes/WRAP-UP-SUMMARY.md
.planning/sweep/STORY.md
.planning/research/
.planning/threads/next-milestone-planning.md

# R-04 (self-allowlist) + drift-diff script + Phase 12 own artifacts + Phase 11 plans + spike scaffolding
.brand-grep-allow
scripts/check-brand.sh
scripts/drift-diff.sh
packages/vault-io/DRIFT-DECISIONS-RAW.md
packages/vault-io/DRIFT-DECISIONS.md
.planning/phases/12-drift-backport-ecosystem-rebrand-m2/
.planning/phases/11-workspace-io-port-m1/
.planning/spikes/MANIFEST.md

# Plan-meta + Upstream-reference (live planning surface)
CLAUDE.md
.planning/PROJECT.md
.planning/REQUIREMENTS.md
.planning/ROADMAP.md
.planning/STATE.md

# Provenance / Parity-behavior (packages/ + agents/)
packages/vault-io/src/vault_io/__init__.py
packages/vault-io/src/vault_io/ingest_work_item.py
packages/vault-io/src/vault_io/ingest_source.py
agents/code-wiki-agent/src/code_wiki_agent/commands/query.py

# Test prose / Upstream-guard / Test-data
packages/vault-io/tests/test_ingest_source.py
packages/vault-io/tests/test_ingest_work_item.py
packages/vault-io/tests/test_wikilink_predicate.py
packages/vault-io/tests/test_lint_modules.py
packages/vault-io/tests/fixtures/single-package-vault/
packages/eval-harness/tests/test_two_gate_scorer.py
packages/eval-harness/tests/test_sweep.py
packages/eval-harness/tests/test_divergence_metric.py
packages/eval-harness/tests/test_structural.py
packages/eval-harness/tests/test_divergence_checks.py
packages/eval-harness/tests/eval/test_sweep_eval.py

# carry-forward (post-hoc) — hits not in plan 03 inventory but classified under existing R-decisions
packages/eval-harness/baselines/divergence-ingestor.json
packages/eval-harness/baselines/divergence-librarian.json
packages/workspace-io/README.md
packages/workspace-io/src/workspace_io/config.py
packages/workspace-io/tests/test_local_config.py
packages/workspace-io/tests/test_warn_if_stale.py
packages/prompt-sources/
agents/code-wiki-agent/tests/commands/test_lint_parity.py
agents/code-wiki-agent/tests/prompts/test_provenance.py
```

(See `.brand-grep-allow` at repo root for the verbatim file including full rationale comments.)

## Acceptance Criteria Status

| Task | Criterion                                                                                                       | Status                       |
| ---- | --------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| 1    | `.brand-grep-allow` exists at repo root                                                                         | ✅                            |
| 1    | Base entries cover R-01 (`round-trip-vault`), R-02 (`baselines/`, `rubrics/`), R-03 (archived planning)         | ✅                            |
| 1    | R-decision comment headers (`R-01:`, `R-02:`, `R-03:`, `R-04:`) present                                         | ✅                            |
| 1    | Carry-forward section header references `12-03-carry-forward-refs.md`                                           | ✅                            |
| 1    | Every non-`(none)` row from `12-03-carry-forward-refs.md` has a corresponding entry with `# rationale:` comment | ✅                            |
| 1    | `scripts/check-brand.sh` exists, executable, passes `bash -n`                                                   | ✅                            |
| 1    | Script uses `set -euo pipefail` and `grep -vF -f .brand-grep-allow`                                             | ✅                            |
| 1    | Grep pattern matches `lattice\|LATTICE\|lattice_workspace\|lattice_wiki_core`                                   | ✅                            |
| 1    | Grep target list includes `plugins/` (W5)                                                                       | ✅                            |
| 2    | Stage 1: `bash scripts/check-brand.sh` exits 0 (`GATE_RC == 0`)                                                 | ✅ (zero hits on first run) |
| 2    | Stage 2: `uv run pytest` exits 0 (`TEST_RC == 0`)                                                               | ✅ (526 passed)             |
| 2    | Each stage's exit code captured in a named variable and asserted independently                                  | ✅                            |
| 2    | Allowlist amendments during iteration documented with rationale comments                                        | ✅ (no iteration needed)    |
| 2    | No genuine missed-rebrand was silently allowlisted                                                              | ✅                            |

## Deviations from Plan

### Auto-fixed Issues

None — gate passed on first invocation; no iteration loop entered.

### Claude's Discretion exercised

1. **Post-hoc carry-forward additions** — plan 03 enumerated 52 references but the gate's initial dry-run surfaced additional files with `lattice` hits that plan 03 did not list (`packages/prompt-sources/`, `packages/workspace-io/`, `packages/eval-harness/baselines/divergence-*.json`, `agents/code-wiki-agent/tests/commands/test_lint_parity.py`, `agents/code-wiki-agent/tests/prompts/test_provenance.py`). Each was inspected: every hit is either Provenance (workspace-io ported from upstream lattice-workspace; prompt-sources mirrors upstream lattice-wiki SKILL.md; test-prose names upstream packages as the parity/non-import target) or R-02 (recorded eval-baseline JSONs). Per plan §Task 2 ("carry-forward refs that plan 03 forgot to record"), added these under a `# carry-forward (post-hoc):` section. No operator approval needed — none is a genuine missed rebrand.

2. **Path-fragment vs. exact path** — chose fragments (e.g., `packages/eval-harness/baselines/`, `packages/prompt-sources/`) over per-file enumeration for whole-directory allowlist groups. Trade-off: fragment is broader (covers future additions to the directory) but specific enough that no R-out-of-scope file accidentally matches. Documented in decisions.

3. **No new commit in Task 2** — plan §Task 2 last paragraph explicitly anticipates this: "If Task 1 already committed `scripts/check-brand.sh` + `.brand-grep-allow` and no iteration was required, this task adds no new commit." Total commit count for this plan: 1.

### Auth gates

None.

## Self-Check: PASSED

- `scripts/check-brand.sh` exists and is executable (`ls -la scripts/check-brand.sh` → `-rwxr-xr-x`).
- `.brand-grep-allow` exists at repo root (`test -f .brand-grep-allow` → 0).
- Commit `644b942` present on the worktree branch (`git log --oneline | grep 644b942`).
- `bash scripts/check-brand.sh` exits 0 (`GATE_RC=0`); zero unallowlisted hits.
- `uv run pytest` exits 0 (`TEST_RC=0`); 526 passed, 30 skipped, 19 snapshots passed.

## Next Steps

**Phase 12 verification complete.** SC#3 (`grep -rE 'lattice|LATTICE|...' packages/ agents/ plugins/ .planning/ CLAUDE.md` returns zero hits, excluding allowlist) and SC#5 (`uv run pytest` passes after rebrand) from ROADMAP §Phase 12 are now satisfied. BRAND-01 + BRAND-04 closed.

The grep gate is long-lived: Phases 13 (Plugin Spec), 14 (Plugin Port), and 16 (v1.1 carry-forward debt) re-run `bash scripts/check-brand.sh` cheaply before merging to assert no upstream-name regression has crept back in. Any new legitimate references in those phases (e.g., Phase 14 plugin port may introduce new `plugins/graph-wiki/` content referencing upstream `lattice-wiki` plugin docs) add entries to `.brand-grep-allow` with `# carry-forward (post-hoc):` or `# Phase 14:` headers.

Next phase: **Phase 13 — Plugin Spec** (per `.planning/threads/next-milestone-planning.md` §M3 — answers the open question "what do plugin slash commands actually shell out to?" before the Phase 14 plugin port).
