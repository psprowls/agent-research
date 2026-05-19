---
phase: 12-drift-backport-ecosystem-rebrand-m2
plan: 03
subsystem: rebrand-sweep
tags: [rebrand, brand-01, brand-02, atomic-commits]
requires: [12-02]
provides:
  - "Live planning surface (CLAUDE.md, ROADMAP, REQUIREMENTS, STATE, PROJECT) rebranded to graph-wiki with explicit `upstream` prefixes on remaining historical/provenance references"
  - "packages/vault-io/src/ rebranded (12 .py + lint/ + assets templates); layout block markers renamed `<!-- graph-wiki:layout:start/end -->`"
  - "agents/code-wiki-agent/ rebranded (commands prose + architecture_overview prompt fragment)"
  - "Empty plugins/ directory placeholder for Phase 14"
  - "BRAND-02 fix landed in .planning/spikes/CONVENTIONS.md (cores/ → packages/)"
  - "12-03-carry-forward-refs.md inventory of 52 surviving lattice references across 10 classes"
affects:
  - packages/vault-io/src/
  - agents/code-wiki-agent/src/
  - .planning/{ROADMAP,REQUIREMENTS,STATE,PROJECT,spikes/CONVENTIONS}.md
  - CLAUDE.md
  - plugins/ (created)
tech-stack:
  added: []
  patterns:
    - "`upstream` / `legacy upstream` prefix to mark allowlist-candidates in live planning prose"
    - "Layout-block sentinel rename requires test-fixture parity in same commit (SQ-03 inline fix)"
key-files:
  created:
    - plugins/.gitkeep
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md
    - .planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-SUMMARY.md
  modified:
    - packages/vault-io/src/vault_io/{__init__,init_vault,update_index,scan_monorepo,ingest_work_item,git_state,layout_io,ingest_source,update_tokens,append_log}.py
    - packages/vault-io/src/vault_io/lint/{container,dependency}.py
    - packages/vault-io/src/vault_io/assets/{AGENTS.md,CLAUDE.md,cursorrules,index.md,log.md}.template
    - packages/vault-io/src/vault_io/assets/page-templates/{app,package,source}.md
    - agents/code-wiki-agent/src/code_wiki_agent/commands/{scan,lint}.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/architecture_overview.py
    - agents/code-wiki-agent/tests/prompts/{test_project_context,test_prompt_snapshots}.py
    - agents/code-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md
    - .planning/STATE.md
    - .planning/PROJECT.md
    - .planning/spikes/CONVENTIONS.md
    - CLAUDE.md
decisions:
  - "Folded commit 5 (CONVENTIONS.md fix) into commit 4 per SQ-02 Claude's Discretion — the BRAND-02 fix is two-line surgery and stays cleanly grouped with the planning-surface rebrand."
  - "Marker rename `<!-- lattice-wiki:layout -->` → `<!-- graph-wiki:layout -->` was bundled with vault-io src rebrand (commit 1); the rename required updating two agents/code-wiki-agent test fixtures (test_project_context.py + test_prompt_snapshots.py) in the same commit to keep SQ-03 green-or-revert satisfied."
  - "Test files in packages/vault-io/tests/ left verbatim: every `lattice` ref is either a provenance docstring or an upstream-guard test (`test_no_lattice_wiki_core_imports` + `assert \"lattice_wiki_core\" not in text`). Renaming the guard literal would break the guard."
  - "eval-harness src (baseline.py, pricing.py) left verbatim: all `lattice-evals` / `lattice-wiki` references describe recorded baseline-data provenance (R-02)."
  - "Live planning surface uses `upstream lattice-...` / `legacy upstream lattice-...` prefixing convention; these references are explicitly upstream-scoped and will be allowlisted by plan 04."
metrics:
  duration: ~75 minutes wall-clock
  commits: 5
  completed: 2026-05-18
---

# Phase 12 Plan 03: Rebrand Sweep Summary

Five atomic commits sweep upstream `lattice` / `LATTICE` / `lattice_workspace` / `lattice_wiki_core` references to `graph-wiki` / `graph_wiki` across in-scope surfaces, with `uv run pytest` gated green after each commit (SQ-03). Carry-forward inventory (`12-03-carry-forward-refs.md`) hands 52 intentionally-preserved references to plan 04's `.brand-grep-allow` authoring step.

## Commits

| #   | Subject                                                                                                   | SHA       | Files | Purpose                                                                                  |
| --- | --------------------------------------------------------------------------------------------------------- | --------- | ----- | ---------------------------------------------------------------------------------------- |
| 1   | `refactor: rebrand lattice → graph-wiki in packages/`                                                     | `00d3e6f` | 19    | vault-io src + lint/ + assets templates; layout markers; fixture parity (2 agent tests). |
| 2   | `refactor: rebrand lattice → graph-wiki in agents/code-wiki-agent`                                        | `4291c94` | 4     | scan.py example path, lint.py work-archive comment, architecture_overview prompt + snapshots. |
| 2b  | `refactor: rebrand lattice → graph-wiki in agents/code-wiki-agent (followup)`                             | `ccb5876` | 1     | lint.py port-history comment reworded to satisfy strict zero-`lattice_wiki_core` grep.   |
| 3   | `chore: create empty plugins/ directory placeholder`                                                      | `ed8229c` | 1     | `plugins/.gitkeep` for Phase 14.                                                         |
| 4   | `docs: rebrand live planning surface to graph-wiki (incl. CONVENTIONS.md cores→packages + carry-forward refs)` | `71c125f` | 7     | Folded commits 4 + 5 per Claude's Discretion; includes `12-03-carry-forward-refs.md`.    |

Final pytest after all commits: **526 passed, 30 skipped, 19 snapshots passed.**

## Carry-Forward Hand-off

`.planning/phases/12-drift-backport-ecosystem-rebrand-m2/12-03-carry-forward-refs.md` enumerates **52 surviving lattice references across 10 classes** plus 12 scope-glob allowlists. Plan 04 Task 1 (`.brand-grep-allow` authoring) consumes this file to encode the allowlist.

Top classes by count:
- **Plan-meta** (10 entries) — requirement/phase text that DESCRIBES the rebrand and cannot be rewritten without losing meaning.
- **Upstream-reference** (15 entries) — live prose explicitly naming upstream lattice-wiki / lattice-workspace / lattice-wiki-core as the system being ported.
- **Historic-decision-log** (8 entries) — dated milestone closeouts / key decisions / Out-of-Scope items in PROJECT.md (R-03).
- **Test-data** (24 entries) — recorded eval-baseline answers and test inputs citing `[[packages/lattice-wiki-core]]` as the measurement subject (R-02).
- **Provenance** (10 entries) — "Ported from / Extracted from" headers documenting where a downstream file was lifted from.
- **Parity-behavior** (4 entries) — BM25 tokenizer + stopwords match upstream wiki_search behavior.
- **Upstream-guard** (4 entries) — tests asserting downstream code does NOT import `lattice_wiki_core` — the literal IS the guard subject.
- **Test-fixture (non-round-trip)** (1 entry) — `tests/fixtures/single-package-vault/log.md` generated against upstream tooling.

## Deviations from Plan

### Claude's Discretion exercised

1. **Commits 4 + 5 folded** — CONVENTIONS.md BRAND-02 fix bundled with the live-planning-surface rebrand per SQ-02 §"Claude's Discretion on whether commit 5 folds into commit 4". Two-line surgery on CONVENTIONS.md kept cleanly grouped with the planning-surface diff.

2. **Auto-fix Rule 3 inline (Task 1, blocking-issue)** — Renaming `LAYOUT_START` / `LAYOUT_END` constants in `vault_io/layout_io.py` from `<!-- lattice-wiki:layout:* -->` to `<!-- graph-wiki:layout:* -->` immediately broke 7 fixture-based tests under `agents/code-wiki-agent/tests/prompts/` that materialize a CLAUDE.md fixture containing the old markers. Per SQ-03 (green-or-revert), the only options were (a) bundle fixture rename with the marker rename in commit 1, or (b) leave markers as `lattice-wiki:layout`. Chose (a) so the rebrand isn't half-done; documented the cross-task file (`agents/code-wiki-agent/tests/prompts/{test_project_context,test_prompt_snapshots}.py`) in the commit message.

3. **Followup commit for stricter acceptance criterion** — Task 2's first commit left `Import swaps: lattice_wiki_core.* → vault_io.*` as a port-history docstring in `commands/lint.py`. The acceptance criterion `grep -rE 'lattice_workspace|lattice_wiki_core' agents/code-wiki-agent/src/` returns zero matches required tightening — reworded to "Imports swap upstream package -> vault_io for the linter's internals." Created a small followup commit rather than amending.

4. **Asset templates rebranded** — `packages/vault-io/src/vault_io/assets/{AGENTS,CLAUDE,cursorrules,index,log}.md.template` and `page-templates/{app,package,source}.md` were not in the plan's `<files>` list but contain `/lattice-wiki:*` slash-command references that get baked into new vaults. Rebranded to keep new-vault prose consistent with the renamed slash-command namespace; documented in commit 1.

5. **`lint/container.py` + `lint/dependency.py` rebranded** — plan's `<files>` list didn't enumerate `lint/`, but the action text says "All `packages/vault-io/src/vault_io/*.py` files (12 modules per CONTEXT.md)". Both files had functional lattice references (`/lattice-wiki:init` error message and `lattice-graph` forward-looking ref); rebranded for consistency.

### Auth gates

None.

### No-op deviations

- `git_state.py` was "byte-identical to upstream" per spike 002. The only lattice reference was a docstring; rebranded in commit 1.

## Acceptance Criteria Status

| Task | Criterion                                                                                          | Status |
| ---- | -------------------------------------------------------------------------------------------------- | ------ |
| 1    | `uv run pytest` exits 0 after commit 1                                                             | ✅ 526 passed |
| 1    | HEAD subject = `refactor: rebrand lattice → graph-wiki in packages/`                               | ✅      |
| 1    | No file under round-trip-vault/baselines/rubrics touched                                           | ✅      |
| 1    | `grep -rE 'lattice_workspace\|lattice_wiki_core' packages/vault-io/src/ ...baseline.py ...pricing.py` is empty | ✅ |
| 2    | `uv run pytest` exits 0 after commit 2 (and followup)                                              | ✅      |
| 2    | HEAD subject = `refactor: rebrand lattice → graph-wiki in agents/code-wiki-agent`                  | ✅      |
| 2    | `grep -rE 'lattice_workspace\|lattice_wiki_core' agents/code-wiki-agent/src/` is empty             | ✅ (after followup) |
| 3    | `plugins/` exists                                                                                  | ✅      |
| 3    | HEAD or recent subject = `chore: create empty plugins/ directory placeholder`                      | ✅      |
| 4    | `uv run pytest` exits 0 after commit 4                                                             | ✅      |
| 4    | Commit subject matches one of the two SQ-02 wordings (folded)                                      | ✅      |
| 4    | `grep -E 'cores/' .planning/spikes/CONVENTIONS.md` is empty (BRAND-02)                             | ✅      |
| 4    | `12-03-carry-forward-refs.md` exists                                                               | ✅      |
| 4    | No R-03 allowlisted path touched                                                                   | ✅      |

## Self-Check: PASSED

- All 5 commits exist on the worktree branch (`git log --oneline e03a687..HEAD` shows them).
- All listed key-files exist (verified post-commit).
- `uv run pytest`: 526 passed, 30 skipped after the final commit.
- `12-03-carry-forward-refs.md` written; references hand-off path in plan 04.
- BRAND-02 satisfied (`cores/` gone from CONVENTIONS.md).
- No R-01/R-02/R-03 allowlisted paths modified.
