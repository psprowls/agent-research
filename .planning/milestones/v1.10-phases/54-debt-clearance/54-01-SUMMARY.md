---
phase: 54-debt-clearance
plan: 01
subsystem: testing + planning-docs
tags: [debt, integration-gate, project-docs]
requires: []
provides:
  - "green tests/test_integration_gate.py"
  - "PROJECT.md current-tense prose matching the shipped stack"
affects:
  - agents/graph-wiki-agent/tests/integration
  - packages/graph-io/tests/integration
  - packages/wiki-io/tests/integration
  - .planning/PROJECT.md
tech-stack:
  added: []
  patterns:
    - "integration-gate-allow marker for LLM-stubbed / local-only integration tests"
key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/tests/integration/test_propose_domains_e2e.py
    - agents/graph-wiki-agent/tests/integration/test_propose_domains_isolation.py
    - agents/graph-wiki-agent/tests/integration/test_scan_entity_integration.py
    - packages/graph-io/tests/integration/test_cluster_cli.py
    - packages/graph-io/tests/integration/test_e2e_apps.py
    - packages/graph-io/tests/integration/test_e2e_builtins.py
    - packages/wiki-io/tests/integration/test_link_rewriter_integration.py
    - .planning/PROJECT.md
key-decisions:
  - "Used the `# integration-gate-allow` marker (not the GRAPH_WIKI_RUN_INTEGRATION skipif) for all 7 files because they are LLM-stubbed or fully local and must keep running in CI by default (D-01)."
  - "Mirrored CLAUDE.md §2 stack-departure meaning in PROJECT.md Constraints without the literal `deepagents`/`langgraph` tokens, resolving the D-08↔D-09 conflict in favor of D-09's mechanical grep gate."
requirements-completed: [DEBT-01, DEBT-02]
duration: 8 min
completed: 2026-05-28
---

# Phase 54 Plan 01: Debt Clearance Summary

Cleared two independent pieces of debt: added self-documenting `# integration-gate-allow` markers to 7 LLM-stubbed/local integration test files so `tests/test_integration_gate.py` passes in CI, and corrected PROJECT.md's "What This Is" / "Core Value" / "Constraints" sections to name the actual `subagent-runtime` + `langchain-aws` + `langchain-core` stack and the `graph-wiki` naming.

- **Duration:** ~8 min
- **Tasks:** 3 (Task 2 was verification-only)
- **Files changed:** 8 (7 test files + PROJECT.md)

## DEBT-01 — integration gate (Task 1 + Task 2)

Inserted one `# integration-gate-allow — <why>` comment line near the top of each of the 7 flagged files (after the module docstring, before the first `import`/`from __future__`):

| File | Justification |
|------|---------------|
| test_propose_domains_e2e.py | LLM stubbed, runs in CI |
| test_propose_domains_isolation.py | local cg update, no LLM |
| test_scan_entity_integration.py | narrator LLM stubbed + cg update monkeypatched |
| test_cluster_cli.py | local only; runtime pytest.skip when code.db missing |
| test_e2e_apps.py | subprocess + local, no LLM |
| test_e2e_builtins.py | subprocess + local, no LLM |
| test_link_rewriter_integration.py | pure local fixture vault |

- `uv run pytest tests/test_integration_gate.py` exits 0.
- `tests/test_integration_gate.py` was NOT modified (`git diff HEAD~2 HEAD -- tests/test_integration_gate.py` empty).
- The 5 network-gated contrast-set files (test_bedrock_iam, test_mcp_e2e, test_query_e2e, test_count_tokens_live, test_pool_bedrock) were NOT touched.
- `pytest --collect-only` over the three edited directories exits 0; all 7 edited files appear in the collected set (no ImportError/SyntaxError) — markers did not break any docstring or `__future__` import.

## DEBT-02 — PROJECT.md drift (Task 3)

Three scoped string edits to `.planning/PROJECT.md` (git diff hunks confined to L5, L9, L11, L351, L354):

- **What This Is (L5):** `…of LangChain/deepagents-based AI tooling.` → `…of LangChain-primitives-based AI tooling running on AWS Bedrock, with a hand-rolled subagent runtime (\`SubagentPool\`) instead of a heavier orchestration framework.`; `reimplementation of the upstream \`lattice-wiki\` Claude Code plugin (being ported in this repo as \`graph-wiki\`)` → `reimplementation of the \`graph-wiki\` Claude Code plugin (in this repo)`. `consumed by the DeepAgents CLI` preserved.
- **Core Value (L9, L11):** `upstream lattice-wiki plugin's … (now ported as \`graph-wiki\`)` → `the \`graph-wiki\` plugin's …`; `today's upstream lattice-wiki librarian` → `the current graph-wiki librarian`.
- **Constraints (L351):** `\`langchain\` + \`langchain-aws\` + \`deepagents\` — chosen … to leverage deepagents' subagent primitives without rebuilding them` → `\`langchain-aws\` + \`langchain-core\` + in-house \`subagent-runtime\` (asyncio.Semaphore-based fan-out) — chosen to match Pat's stack; a heavier orchestration framework was evaluated and intentionally not adopted, see CLAUDE.md §2 stack-departure note`.
- **Constraints (L354):** `existing lattice-wiki vaults` → `existing graph-wiki vaults`.

- Scoped grep over the three sections: no `deepagents`/`lattice-wiki` matches; `subagent-runtime` + `langchain-core` + `graph-wiki` all present (D-09 passes).
- Historical sections preserved: `git diff -U0` shows hunks only at L5/L9/L11/L351/L354 — no Context, Key Decisions, or Evolution hunks (D-06). The L27 v1.10-debt bullet was not touched.
- `grep -c "DeepAgents CLI" .planning/PROJECT.md` = 6 (host-product references preserved, D-07).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Notable Implementation Notes

The plan's normal routing (3 tasks > inline_plan_threshold of 2) would dispatch a worktree subagent, but no `Agent`/`Task` subagent tool was available in this runtime. Per the execute-phase runtime-compatibility fallback, the plan was executed inline on the main working tree as the sole executor; this handler owns the STATE.md/ROADMAP.md tracking writes. Pre-commit hooks ran normally on both task commits (no `--no-verify`).

## Next Phase Readiness

Phase complete (single plan). Ready for `/gsd:verify-work 54`. Next: Phase 55 (dependency classification fix).

## Self-Check: PASSED

- key-files.modified all exist on disk and carry the intended changes (verified via git).
- `git log --oneline --all --grep="54-01"` returns the two task commits (fix + docs).
- All `<verification>` commands re-run: gate test exit 0; exactly 7 test files modified; gate test unchanged; collect-only exit 0; scoped grep clean + contains required tokens; DeepAgents CLI count = 6; no contrast-set file modified.
