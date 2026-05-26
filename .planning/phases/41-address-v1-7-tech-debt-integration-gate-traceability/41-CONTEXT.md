# Phase 41: Address v1.7 tech debt — integration_gate + traceability — Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Resolve the two named remediation items from `.planning/v1.7-MILESTONE-AUDIT.md` so the v1.7 milestone can close without trailing CI-noise and without a stale traceability matrix:

1. **CI blocker:** restore the canonical `GRAPH_WIKI_RUN_INTEGRATION` gate on `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` so `tests/test_integration_gate.py` passes.
2. **Traceability sync:** flip the 24 stale `[ ]` checkboxes in `.planning/REQUIREMENTS.md` (HYGIENE-01..14, CGFIND-01..03, INGESTOR-01..03) and update the Pending rows in the traceability table to Satisfied.

Everything else flagged in the audit (pre-existing v1.6 `sample_monorepo/test_top.py` offender, exit-code-3 collision, URI-drift reconciliation, retro UAT/VERIFICATION.md for Phases 39/40) is explicitly **out of scope** for this phase.

</domain>

<decisions>
## Implementation Decisions

### Skipif fix scope
- **D-01:** Fix `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` only. The pre-existing `packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py` offender stays deferred to v1.8 (it's a fixture file inside another package's tree and predates v1.7).
- **D-02:** Do **not** add a pre-commit / CI lint hook to enforce the gate at author time in this phase. `tests/test_integration_gate.py` already fails loudly on drift; adding tooling is a separate scope decision.

### Skipif pattern
- **D-03:** Use the canonical `INTEGRATION_GATE` constant pattern that `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py` already uses verbatim. Module-level:
  ```python
  INTEGRATION_GATE = pytest.mark.skipif(
      not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"),
      reason="Set GRAPH_WIKI_RUN_INTEGRATION=1 to run real integration scenarios",
  )
  ```
  Then apply `@INTEGRATION_GATE` to the test function (alongside the existing `pytestmark = pytest.mark.integration`). Matches `conftest.py:19-22` and is what the audit explicitly calls "the canonical pattern."
- **D-04:** Do **not** use `# integration-gate-allow` — the allowlist marker is for files that intentionally bypass the gate; this test should run only when the env var is set, so the real skipif is correct.

### REQUIREMENTS.md sync
- **D-05:** Flip exactly these 24 checkboxes `[ ]` → `[x]`: HYGIENE-01..14, CGFIND-01..03, INGESTOR-01..03. LIBTOOLS-* / GRAPHCMD-* / SCANNER-* are already correctly `[x]` — do not touch.
- **D-06:** In the traceability table, change the Status column from `Pending` to `Satisfied` for the same 24 REQ-IDs. Leave row format (columns, ordering, phase mapping) unchanged.
- **D-07:** Do **not** add a new evidence column, phase-link column, or restructure the table. Do **not** edit the "Future Requirements" section in this phase — v1.8 deferred-items capture is a v1.8-milestone concern.

### Retroactive verification artifacts
- **D-08:** Do **not** produce retroactive UAT or VERIFICATION.md for Phases 39 and 40 in this phase. The audit's 3-source cross-reference (SUMMARY frontmatter + automated suite + integration-checker WIRED verdicts) already establishes evidence; retro UAT after the fact adds ceremony without adding signal. The verification-artifact gap is acknowledged in the milestone audit and should be surfaced explicitly during `/gsd-complete-milestone`, not patched here.

### Claude's Discretion
- Commit grouping (one commit per item vs single commit), exact wording of REQUIREMENTS.md table cell text (e.g., "Satisfied" vs "Done"), and whether to run the full `pytest -m integration` suite as a final sanity check in the phase summary — pick whatever matches existing v1.7 phase conventions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Audit & scope
- `.planning/v1.7-MILESTONE-AUDIT.md` — authoritative source for what tech debt this phase addresses (see "Tech Debt Items (Inventory)" and "Recommendation" sections). Items 1 and 2 in the recommendation list are in scope; items 3 and 4 are out of scope.
- `.planning/STATE.md` — v1.7 status (6/6 phases complete, milestone in `tech_debt` state, blocked from `/gsd-complete-milestone` until this phase ships).

### Skipif fix
- `agents/graph-wiki-agent/tests/integration/test_scan_graph_end_to_end.py` — the file to edit (currently fails the canonical-gate check).
- `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py` — reference implementation of the canonical `INTEGRATION_GATE` constant pattern; copy verbatim.
- `agents/graph-wiki-agent/tests/integration/conftest.py` §lines 19–22 — defines the same canonical pattern; D-10 anchor referenced from Phase 16.
- `tests/test_integration_gate.py` — the meta-test that enforces the gate (regex pattern + `# integration-gate-allow` marker logic). Will turn green once D-03 lands on the file in D-01.

### Traceability sync
- `.planning/REQUIREMENTS.md` — file containing the 24 stale checkboxes and the traceability table. Both edits land here.
- `.planning/v1.7-MILESTONE-AUDIT.md` §"Requirements Coverage (3-Source Cross-Reference)" — definitive list of which REQ-IDs map to which phase and Final Status, used to verify the sync was correct.

### Project conventions
- `.planning/PROJECT.md` — project value statement (Bedrock-only, subagent fan-out, format compatibility constraint); no implementation changes required, included for downstream-agent grounding.
- `CLAUDE.md` (project root) — stack rules; relevant only insofar as the test edit must not introduce non-Bedrock imports.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `INTEGRATION_GATE` constant in `test_bedrock_iam.py` — exact pattern to mirror; the canonical regex in `tests/test_integration_gate.py` tolerates whitespace/newlines, so a clean multi-line declaration is fine.
- `pytestmark = pytest.mark.integration` already at top of `test_scan_graph_end_to_end.py` — keep it; D-03 adds the per-test gate alongside it (not a replacement).

### Established Patterns
- Two-layer integration gating across the agent's test tree: package-level `pytest.mark.integration` (skipped by default in CI), plus per-test `INTEGRATION_GATE = pytest.mark.skipif(not GRAPH_WIKI_RUN_INTEGRATION, ...)` so even `pytest -m integration` is a no-op without the env var.
- v1.7 phases land plan-then-execute with atomic per-task commits; a tech-debt phase this small (two files) likely fits one plan with two tasks (test edit + REQUIREMENTS edit).

### Integration Points
- `tests/test_integration_gate.py` is the success oracle for D-01..D-04 — running it before and after must show the failure → pass transition.
- No other code touches; no module imports change; no test fixtures affected.

</code_context>

<specifics>
## Specific Ideas

- The user explicitly opted for minimum-scope remediation across all four gray areas (D-01, D-03, D-05, D-08 all chose the smallest option). Downstream planning should resist the temptation to bundle in adjacent cleanups.
- Audit-recommendation item ordering (skipif first, then traceability sync) maps cleanly to plan task ordering; CI flips from red→green after task 1, so task 2 can rely on a green suite as its baseline.

</specifics>

<deferred>
## Deferred Ideas

- **Fix `packages/graph-io/tests/fixtures/sample_monorepo/tests/integration/test_top.py`** — pre-existing v1.6-era offender; v1.8 cleanup candidate per audit.
- **Wire canonical-gate grep into pre-commit / CI lint** — defense-in-depth that prevents recurrence; out of scope here, candidate for a future hygiene phase.
- **Resolve `BUDGET_EXCEEDED_EXIT_CODE` (3) vs `NOT_INITIALIZED` (3) collision** — audit-flagged warning; documented as intentional in Phase 37 D-04; v1.8 candidate.
- **URI-drift / orphaned-page reconciliation (INGESTOR-03)** — already deferred to v1.8 by design.
- **Retroactive UAT/VERIFICATION.md for Phases 39 and 40** — gap acknowledged; surface in `/gsd-complete-milestone` notes, do not patch retroactively.
- **REQUIREMENTS.md "Future Requirements" section update for v1.8 deferred items** — belongs in v1.8 milestone scoping, not here.
- **Add a phase-link / evidence column to the traceability table** — format enrichment; deferred unless explicitly requested.

</deferred>

---

*Phase: 41-address-v1-7-tech-debt-integration-gate-traceability*
*Context gathered: 2026-05-26*
