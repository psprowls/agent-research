# Phase 54 — Debt Clearance — Research

**Researched:** 2026-05-28
**Phase goal:** The test suite is clean and the project documentation accurately describes the current stack.

> This phase is pure cleanup: a test-annotation gate fix (DEBT-01) and a doc-correction (DEBT-02). The CONTEXT.md already did the scouting work (each target file's nature was verified, the marker mechanism is established, and the canonical wording source is identified). This research confirms those findings against the live repo and fixes the planner's facts in place — there are no open technical unknowns.

---

## DEBT-01 — Integration gate

### What the gate actually enforces

`tests/test_integration_gate.py::test_integration_test_files_use_canonical_gate` walks `**/tests/integration/test_*.py` across the monorepo (excluding `.venv`, `site-packages`, and `.claude/worktrees/`) and asserts every file either:

1. matches the canonical skipif regex `pytest.mark.skipif( (not )?os.environ.get("GRAPH_WIKI_RUN_INTEGRATION") ...)`, **or**
2. contains the literal substring `# integration-gate-allow`.

Files satisfying neither are reported as "divergent" and fail the assertion.

### Current failing set (verified by running the gate, 2026-05-28)

The failing assertion lists exactly the 7 files named in CONTEXT.md D-03 — confirmed identical, no drift:

- `agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py`
- `agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py`
- `agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py`
- `packages/graph-io/tests/integration/test_cluster_cli.py`
- `packages/graph-io/tests/integration/test_e2e_apps.py`
- `packages/graph-io/tests/integration/test_e2e_builtins.py`
- `packages/wiki-io/tests/integration/test_link_rewriter_integration.py`

### Why the marker, not the skipif (D-01 confirmation)

The gate is satisfied by **either** mechanism, but they have opposite runtime semantics:

- The `GRAPH_WIKI_RUN_INTEGRATION` skipif **disables** the test in CI (where that env var is unset), preserving the body for opt-in local/network runs.
- The `# integration-gate-allow` marker **keeps the test running** in CI; it is an explicit exemption declaring "this file looks like an integration test but is safe to run by default."

CONTEXT.md's scout verified all 7 are LLM-stubbed or fully self-contained (local sqlite + `tmp_path` + `subprocess` against tmp repos) and are *meant* to run in CI. Applying the skipif would silently drop them from CI coverage. Therefore the marker is correct for every one of the 7. This matches DEBT-01's "or the `# integration-gate-allow` marker where genuinely appropriate" clause; ROADMAP SC #1's "use the canonical skipif" wording is imprecise and is superseded by D-01.

### Marker form (D-02)

Each marker carries a one-line justification so the exemption is self-documenting, e.g. `# integration-gate-allow — LLM stubbed, runs in CI` or `# integration-gate-allow — local sqlite/fs only`. The gate only greps for the literal `# integration-gate-allow` prefix, so any trailing text is free-form and does not affect the match. Module-level placement near the top of each file is fine.

### Contrast set — DO NOT TOUCH

These integration files already pass the gate via the genuine network skipif (they make real Bedrock/network calls): `agents/graph-wiki-agent/tests/integration/test_bedrock_iam.py`, `test_mcp_e2e.py`, `test_query_e2e.py`, `packages/wiki-io/tests/integration/test_count_tokens_live.py`, `packages/subagent-runtime/tests/integration/test_pool_bedrock.py`. Adding the marker to these would wrongly force network tests into the default CI run.

### Do not modify the gate test

D-04: the fix satisfies the existing gate; do not edit `tests/test_integration_gate.py` or its canonical regex. The gate's failure message references a non-existent `docs/testing.md` — that is out of scope (deferred to v1.10) and must not leak into this fix.

---

## DEBT-02 — PROJECT.md stack-description correction

### Stale references located (verified by grep, 2026-05-28)

`grep -n "deepagents\|lattice-wiki\|DeepAgents" .planning/PROJECT.md` returns matches at lines 5, 9, 11, 27, 252, 263, 317, 321, 323, 328, 329, 331, 335, 345, 351, 353, 354, 363, 365, 367, 372, 373, 376, 385.

### In-scope (must correct) vs out-of-scope (must preserve)

**In-scope — current-tense prose describing the live stack:**
- **"What This Is"** (line ~5) — `LangChain/deepagents-based`, `upstream lattice-wiki Claude Code plugin`.
- **Core Value** (lines ~9, ~11) — `upstream lattice-wiki plugin`, `today's upstream lattice-wiki librarian` (D-05 explicitly folds Core Value into scope).
- **Constraints** (lines ~351, ~354) — `langchain` + `langchain-aws` + `deepagents`; `must read existing lattice-wiki vaults`.

**Out-of-scope — historical record, preserve verbatim (D-06):**
- **Context** (~328–345), **Key Decisions** / decision-log tables (~358–385), **Evolution**, and prior-milestone narrative (~252, ~263, ~317, ~321, ~323, ~367, ~372, ~373, ~376). These accurately record decisions made when `deepagents` genuinely *was* the chosen framework (pre stack-departure) and when the source plugin was named `lattice-wiki`. Rewriting them would falsify history and drift from CLAUDE.md's §2 stack-departure note.
- **Line 27** (the v1.10 milestone bullet describing *this very debt task*) accurately quotes the stale state as the thing being fixed — leave it.

### Critical distinction — "DeepAgents CLI" stays (D-07)

"DeepAgents CLI" is the external MCP *host product* the agent is consumed by (lines ~345, ~353, ~365). It is legitimate and must remain — CLAUDE.md still references it. Only the `deepagents` *Python framework/library* references (the rejected agent-framework dependency) and the `lattice-wiki` *naming* get corrected. **Do not blanket-replace the string "DeepAgents".** A naive `sed s/deepagents//` would corrupt the host-product references and the historical sections.

### Canonical wording source (D-08)

`CLAUDE.md` ("## Project" + "### Constraints" + §2 Stack-departure note) is the canonical, already-correct description: in-house `subagent-runtime` + `langchain-aws` + `langchain-core`; `graph-wiki` naming; Bedrock-only; MCP host = DeepAgents CLI; `deepagents`/`langgraph` evaluated and intentionally not adopted. The corrected PROJECT.md sentences must mirror this wording.

### Verification (D-09)

`grep -n "deepagents\|lattice-wiki" .planning/PROJECT.md` returns no matches **inside the "What This Is", "Core Value", and Constraints sections**. Historical sections may legitimately still contain those strings — the grep is scoped to the corrected sections, not the whole file.

---

## Validation Architecture

This phase is verified entirely by deterministic shell/pytest assertions; there is no probabilistic or LLM-graded behavior to sample.

| Dimension | Approach |
|-----------|----------|
| **Primary signal (DEBT-01)** | `uv run pytest tests/test_integration_gate.py` exits 0. Single boolean gate — fully deterministic. |
| **Primary signal (DEBT-02)** | Scoped grep returns no stale strings in the three corrected sections; in-scope sections name `subagent-runtime`/`langchain-aws`/`langchain-core`/`graph-wiki`. Deterministic. |
| **Regression guard** | No runtime code paths are touched (markers are comments; PROJECT.md is a planning doc). The only behavioral risk is over-broad editing — guarded by the contrast-set and out-of-scope lists above and by re-running the full affected test packages is unnecessary (comments don't change collection). A spot `uv run pytest --collect-only` on the 7 files confirms they still collect. |
| **Sampling rate** | After each task: run that task's verify command. After the plan: run both gate + grep. No flakiness surface (no network, no LLM). |
| **Manual-only** | None — both criteria are mechanically checkable. |

**Wave 0:** None required — pytest and the gate test already exist; PROJECT.md and the 7 target files already exist. No new test infrastructure.

---

## Risks & landmines

| Risk | Severity | Mitigation |
|------|----------|------------|
| Blanket string-replace corrupts "DeepAgents CLI" host references or historical sections | HIGH | Edit only the named in-scope lines; preserve "DeepAgents CLI" and all historical/decision-log sections (D-06, D-07). Use targeted edits, never `sed -i` across the file. |
| Applying the skipif instead of the marker silently drops 7 tests from CI | MEDIUM | D-01: use `# integration-gate-allow` for all 7 (they stub the LLM / run locally and are meant to run in CI). |
| Touching a contrast-set file (genuine network test) | MEDIUM | Explicit DO-NOT-TOUCH list above; only the 7 D-03 files get the marker. |
| Editing the gate test itself to force a pass | MEDIUM | D-04: do not modify `tests/test_integration_gate.py` or its regex. |
| `docs/testing.md` reference leaking into the fix | LOW | Out of scope; the marker work has no dependency on it (deferred to v1.10). |

---

## RESEARCH COMPLETE

Phase 54 has zero open technical unknowns. Both requirements are mechanically specified by CONTEXT.md's locked decisions D-01–D-09, all of which are confirmed against the live repo as of 2026-05-28. Ready to plan.
