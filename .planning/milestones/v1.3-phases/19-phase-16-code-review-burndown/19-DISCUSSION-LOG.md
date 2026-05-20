# Phase 19: Phase 16 Code Review Burndown - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-20
**Phase:** 19-phase-16-code-review-burndown
**Areas discussed:** Triage timing & ownership, Plan granularity, Disposition recording surface, Test policy & judgment calls

---

## Triage timing & ownership

| Option | Description | Selected |
|--------|-------------|----------|
| Lock all dispositions now | Walk all 15 findings here, classify each as fix / dismiss / defer-to-todo. | ✓ |
| Lock only the judgment calls now | Default the obvious calls; only the 3 ambiguous findings decided here. | |
| Defer all triage to planner | CONTEXT.md just locks the rubric; planner proposes per-finding. | |

**User's choice:** Lock all dispositions now.
**Notes:** Triage walked through 15 individually-answered prompts (WR-01..06, IN-01..09 grouped in 4 batches). Outcome: 13 fixes + 2 no-actions (IN-02, IN-05 self-corrected by review).

---

## Per-finding dispositions

| Finding | Severity | Disposition |
|---------|----------|-------------|
| WR-01 (synthesizer slug-only regex too narrow) | Warning | Fix as proposed |
| WR-02 (.graph-wiki/ regex misses inline path refs) | Warning | Fix as proposed |
| WR-03 (path:line regex requires '/') | Warning | Fix as proposed |
| WR-04 (integration trace-coverage fragile against empty/empty) | Warning | Fix as proposed |
| WR-05 (inspect.signature per-item, fragile) | Warning | Fix as proposed |
| WR-06 (hardcoded '/' separator in ingest containment) | Warning | Fix as proposed (locked: Path.is_relative_to convergence) |
| IN-01 (stale docstring line-range in query.py) | Info | Fix as proposed |
| IN-02 (typing.Any "unused" — review self-corrected) | Info | No-action |
| IN-03 (unused typing.Union import in metric.py) | Info | Fix as proposed |
| IN-04 (test promises caplog WARNING but doesn't assert) | Info | Fix — add caplog assertion |
| IN-05 (pytest "unused" — review self-corrected) | Info | No-action |
| IN-06 (synth trace filename shared across branches) | Info | Fix as proposed (locked: cheap insurance vs future retry-fallback) |
| IN-07 (stale docstring "3 vault-thin cases" vs 6) | Info | Fix as proposed |
| IN-08 (docs/cancellation.md missing schema_version) | Info | Fix as proposed |
| IN-09 (G1 resolution duplicated in query.py) | Info | Fix as proposed (locked: drift bait removal) |

---

## Plan granularity

| Option | Description | Selected |
|--------|-------------|----------|
| Grouped by code area | ~4 plans split by file/area (divergence-eval / runtime / tests / query+docs). | ✓ |
| One plan per finding | 13 atomic plans. | |
| One consolidated burndown plan | Single plan executing all 13 fixes. | |
| Split by severity | Two plans: all warnings then all info. | |

**User's choice:** Grouped by code area.
**Notes:** Planner expected to split close to: (1) divergence-eval regex fixes, (2) core runtime fixes, (3) test + integration fixes, (4) query trace + docs cleanup. Planner can adjust within ~3–5 plan range.

---

## Disposition recording surface

| Option | Description | Selected |
|--------|-------------|----------|
| New 19-REVIEW-BURNDOWN.md | Phase-local disposition table; 16-REVIEW.md untouched as historical record. | ✓ |
| Append "Triage" section to original 16-REVIEW.md | Edit the archived 16-REVIEW.md in place with outcomes. | |
| Both | Phase-local table + back-pointer in 16-REVIEW.md. | |

**User's choice:** New 19-REVIEW-BURNDOWN.md.
**Notes:** 16-REVIEW.md stays as historical record. Phase SUMMARY.md will link to 19-REVIEW-BURNDOWN.md so future review passes find it.

---

## Test policy & judgment calls

| Option | Description | Selected |
|--------|-------------|----------|
| Require regression tests for WR-01..04 | Add a test per logic-bug warning exercising the closed failure mode. | |
| Fix-only — existing suite catches it | No new regression tests authored solely for these fixes. | ✓ |
| Tests only for divergence-eval fixes | WR-01/02/03 get tests; WR-04 fix-only. | |

**User's choice:** Fix-only — existing suite catches it.
**Notes:** Per-commit gate scoped to `pytest packages/eval-harness/tests/ packages/subagent-runtime/tests/ agents/graph-wiki-agent/tests/ -m "not integration"`. Planner may add a single targeted assertion if a regex change discovers a true silent-pass gap; no new test files.

Judgment-call answers (folded into Triage):
- WR-06: Fix as proposed (Path.is_relative_to convergence)
- IN-06: Fix as proposed (filename qualifier)
- IN-09: Fix as proposed (dedup G1)

---

## Claude's Discretion

- Plan filenames, exact ordering within each plan, commit-message phrasing — planner per existing GSD conventions.
- 19-REVIEW-BURNDOWN.md table column order and markdown styling — executor.
- Whether to add one targeted assertion in existing test files if a regex change discovers a true silent-pass — planner judgment per D-18 exception path.

## Deferred Ideas

None — every finding in 16-REVIEW.md is dispositioned in this phase.
