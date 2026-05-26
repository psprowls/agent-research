# Phase 41: Address v1.7 tech debt — integration_gate + traceability — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 41-address-v1-7-tech-debt-integration-gate-traceability
**Areas discussed:** Skipif fix scope, Skipif pattern, REQUIREMENTS sync, Retroactive UAT/VERIFICATION

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Skipif fix scope | Just Phase 39's test, or also the pre-existing v1.6 sample_monorepo offender? | ✓ |
| Skipif pattern | Canonical INTEGRATION_GATE constant vs inline skipif vs `# integration-gate-allow` marker | ✓ |
| REQUIREMENTS sync | Checkbox flips + traceability table, plus optional format enrichment | ✓ |
| Retro UAT/VERIFICATION | Produce retroactive UAT/VERIFICATION.md for Phases 39 + 40, or accept gap | ✓ |

**User's choice:** All four areas.
**Notes:** Phase scope is well-defined by `.planning/v1.7-MILESTONE-AUDIT.md`; each area maps to a concrete remediation item.

---

## Skipif fix scope

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 39 file only (Recommended) | Fix test_scan_graph_end_to_end.py only; defer sample_monorepo/test_top.py to v1.8 | ✓ |
| Both offenders | Also fix packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py | |
| Both + add gate scan to pre-commit | Above plus wire the canonical-gate grep into pre-commit / CI lint | |

**User's choice:** Phase 39 file only.
**Notes:** Audit explicitly identifies sample_monorepo/test_top.py as a v1.8 candidate (pre-existing v1.6-era offender, fixture inside another package's tree). Minimum-blast-radius approach.

---

## Skipif pattern

| Option | Description | Selected |
|--------|-------------|----------|
| INTEGRATION_GATE constant + apply (Recommended) | Module-level constant mirroring test_bedrock_iam.py / conftest.py:19-22 | ✓ |
| Inline skipif on test | Single decorator on the test function | |
| `# integration-gate-allow` marker | Allowlist comment marker (passes gate but doesn't actually gate the test) | |

**User's choice:** INTEGRATION_GATE constant.
**Notes:** Matches the existing canonical reference in the repo (test_bedrock_iam.py uses the exact same constant name). The allowlist marker was explicitly rejected — semantically wrong here because the test should actually be skipped without the env var, not allowlisted past the gate.

---

## REQUIREMENTS sync

| Option | Description | Selected |
|--------|-------------|----------|
| Checkboxes + table only (Recommended) | 24 [ ]→[x] flips + Pending → Satisfied in traceability table; no format changes | ✓ |
| Above + add phase-link column | Add explicit phase-number link next to each Satisfied row | |
| Above + reconcile Future Requirements section | Also re-examine v1.8 deferred items capture in Future Requirements | |

**User's choice:** Checkboxes + table only.
**Notes:** Future Requirements / v1.8 deferred-items capture belongs in v1.8 milestone scoping, not here. No format restructuring in this phase.

---

## Retroactive UAT/VERIFICATION

| Option | Description | Selected |
|--------|-------------|----------|
| Skip — accept the gap (Recommended) | Audit's 3-source cross-reference establishes evidence; note gap at milestone close | ✓ |
| VERIFICATION.md only (machine-verifiable) | Re-run automated suite for Phases 39 + 40, record pass/fail per requirement | |
| Full UAT walkthroughs for 39 + 40 | Run /gsd-verify-work retroactively for both phases | |

**User's choice:** Skip — accept the gap.
**Notes:** Retro UAT after the fact adds ceremony without adding signal. Gap should be surfaced at `/gsd-complete-milestone` time, not patched in this phase.

---

## Final readiness check

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context (Recommended) | Write CONTEXT.md now | ✓ |
| Explore more gray areas | Commit grouping, milestone-close note wording, v1.8 deferred-items pre-staging | |

**User's choice:** Ready for context.

---

## Claude's Discretion

- Commit grouping strategy (single commit vs one per item)
- Exact wording in REQUIREMENTS.md table cells ("Satisfied" vs "Done")
- Whether to add a final `pytest -m integration` sanity-check step in the phase summary

## Deferred Ideas

- Fix `packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py` (v1.8 candidate)
- Wire canonical-gate grep into pre-commit / CI lint (future hygiene phase)
- Resolve `BUDGET_EXCEEDED_EXIT_CODE` (3) vs `NOT_INITIALIZED` (3) collision (v1.8)
- URI-drift / orphaned-page reconciliation, INGESTOR-03 (already v1.8 by design)
- Retroactive UAT/VERIFICATION.md for Phases 39 and 40 (gap surfaced at milestone close)
- REQUIREMENTS.md "Future Requirements" section update for v1.8 deferred items (v1.8 scoping)
- Phase-link / evidence column for the traceability table (format enrichment, deferred)
