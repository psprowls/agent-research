# Phase 54: Debt Clearance - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Two independent cleanup tasks, no new capability:

1. **DEBT-01** — Make `tests/test_integration_gate.py::test_integration_test_files_use_canonical_gate` pass by resolving the 7 flagged integration test files.
2. **DEBT-02** — Correct stale `deepagents` / `lattice-wiki` wording in `.planning/PROJECT.md` so it reflects the actual stack (`subagent-runtime` + `langchain-aws` + `langchain-core`, `graph-wiki` naming).

Goal state: the test suite gate is green and PROJECT.md's current-tense prose accurately describes the shipped stack.
</domain>

<decisions>
## Implementation Decisions

### DEBT-01 — Integration gate strategy
- **D-01:** Resolve all 7 flagged files with the `# integration-gate-allow` marker — NOT the `GRAPH_WIKI_RUN_INTEGRATION` skipif. Scout confirmed every one of the 7 is LLM-stubbed or fully self-contained (local sqlite + `tmp_path` + `subprocess` against tmp repos) and is intended to run in CI by default. Applying the skipif would silently disable them in CI, losing coverage. This follows DEBT-01's "or the `# integration-gate-allow` marker where genuinely appropriate" clause; treat ROADMAP SC #1's "use the canonical skipif" wording as imprecise.
- **D-02:** Each `# integration-gate-allow` marker should carry a short inline justification (e.g. `# integration-gate-allow — LLM stubbed, runs in CI` or `# integration-gate-allow — local sqlite/fs only`) so the exemption is self-documenting and a future reader knows why it isn't gated.
- **D-03:** The 7 files to mark (verified against the failing test output):
  - `agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py` (stubbed LLM, runs in CI)
  - `agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py` (real `cg update`, no LLM — local only)
  - `agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py` (stubs narrator LLM + monkeypatches `cg update`)
  - `packages/graph-io/tests/integration/test_cluster_cli.py` (runtime `pytest.skip` when `code.db` missing — local only)
  - `packages/graph-io/tests/integration/test_e2e_apps.py` (subprocess + local, no LLM)
  - `packages/graph-io/tests/integration/test_e2e_builtins.py` (subprocess + local; `boto3` appears only as test-fixture text, not a real call)
  - `packages/wiki-io/tests/integration/test_link_rewriter_integration.py` (pure local fixture vault)
- **D-04:** Verification = `uv run pytest tests/test_integration_gate.py` passes. Do NOT alter the gate test itself or the canonical-pattern regex.

### DEBT-02 — PROJECT.md correction scope
- **D-05:** Fix the SC-targeted sections ("What This Is" line ~5, Constraints lines ~349–356) AND obviously current-tense prose elsewhere — specifically the **Core Value** section (lines ~9, ~11) which still says "upstream lattice-wiki plugin".
- **D-06:** Leave historical decision-log sections intact — **Key Decisions** (~358–385), **Context** (~328–345), **Evolution**, and the **Deferred/Previous-milestone** narrative. These accurately record decisions made when `deepagents` genuinely *was* the chosen framework (pre stack-departure). Rewriting them would falsify history and drift from the stack-departure note in CLAUDE.md.
- **D-07:** **Critical distinction — preserve "DeepAgents CLI":** "DeepAgents CLI" is the external MCP *host product* the agent is consumed by; it is legitimate and stays (CLAUDE.md still references it). Only the `deepagents` *Python framework/library* references (the rejected agent-framework dependency) and the `lattice-wiki` *naming* get corrected. Do not blanket-replace the string "DeepAgents".
- **D-08:** Corrected wording for "What This Is" / Constraints should mirror the already-correct equivalent prose in `CLAUDE.md` ("## Project" + "### Constraints") — that is the canonical source of the corrected description (`subagent-runtime` / `langchain-aws` / `langchain-core`; `graph-wiki` naming; Bedrock-only; MCP host = DeepAgents CLI).
- **D-09:** Verification = `grep -n "deepagents\|lattice-wiki" .planning/PROJECT.md` returns no matches inside the "What This Is", "Core Value", and "Constraints" sections (historical sections may still legitimately contain them).

### Claude's Discretion
- Exact marker comment text and placement (module-level near the top of each file is fine).
- Exact corrected sentences in PROJECT.md, as long as they mirror CLAUDE.md's stack description and honor D-06/D-07.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### DEBT-01 — gate test + pattern
- `tests/test_integration_gate.py` — defines the canonical regex (`pytest.mark.skipif(... GRAPH_WIKI_RUN_INTEGRATION ...)`) and the `# integration-gate-allow` marker; the file walked is `**/tests/integration/test_*.py`. Do not modify; just satisfy it.
- The 7 target files listed in D-03 (full paths above).
- Contrast set (already-passing, genuinely network-gated — do NOT touch): `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py`, `test_mcp_e2e.py`, `test_query_e2e.py`, `packages/wiki-io/tests/integration/test_count_tokens_live.py`, `packages/subagent-runtime/tests/integration/test_pool_bedrock.py`.

### DEBT-02 — PROJECT.md + canonical wording source
- `.planning/PROJECT.md` — the file being corrected. In-scope sections: "What This Is" (~3–11, incl. Core Value), "Constraints" (~349–356). Out-of-scope (preserve): "Context", "Key Decisions", "Evolution".
- `CLAUDE.md` ("## Project" + "### Constraints" + §2 Stack-departure note) — canonical source for the corrected stack description and the `deepagents`-rejected rationale. Mirror this wording.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `# integration-gate-allow` marker: already an established escape hatch recognized by `tests/test_integration_gate.py` (`_ALLOW_MARKER`). No new mechanism needed.

### Established Patterns
- Canonical network gate: `@pytest.mark.skipif(not os.environ.get("GRAPH_WIKI_RUN_INTEGRATION"), ...)` — used by genuine Bedrock/network tests. The 7 target files are explicitly NOT this category (they stub the LLM / run locally), which is exactly why the marker (not the skipif) is the correct fit.
- CLAUDE.md already carries the corrected stack description and a "Stack-departure note" explaining that `deepagents`/`langgraph` were evaluated and intentionally not adopted — reuse this framing in PROJECT.md.

### Integration Points
- None — this is doc + test-annotation cleanup with no runtime code paths touched.

</code_context>

<specifics>
## Specific Ideas

- The test's failure message points readers to `docs/testing.md`, which does not exist (see Deferred Ideas). Don't let this leak into the fix — the marker work doesn't depend on it.
- Self-documenting markers matter to Pat: prefer `# integration-gate-allow — <one-line why>` over a bare marker.

</specifics>

<deferred>
## Deferred Ideas

- **`docs/testing.md` missing** — `tests/test_integration_gate.py`'s failure message references `docs/testing.md`, which doesn't exist in the repo. Out of scope for Phase 54 (not in DEBT-01/02 criteria). Future options: create the doc capturing the gate policy, or repoint the error message at the in-test policy comment. Noted for the v1.10 backlog.
- **Stale `deepagents`/`lattice-wiki` in historical PROJECT.md sections** — intentionally left as accurate historical record per D-06. If a future milestone wants a "historical note" banner on those sections, that's a separate doc task.

</deferred>

---

*Phase: 54-debt-clearance*
*Context gathered: 2026-05-28*
