# Phase 54: Debt Clearance - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 54-debt-clearance
**Areas discussed:** Integration gate strategy, PROJECT.md correction scope, docs/testing.md handling

---

## Integration gate strategy (DEBT-01)

| Option | Description | Selected |
|--------|-------------|----------|
| Allow-marker | Add `# integration-gate-allow` to all 7; keeps them running in CI (they don't touch Bedrock/network). Matches DEBT-01's "where genuinely appropriate"; treats SC wording as imprecise. | ✓ |
| Canonical skipif | Add `GRAPH_WIKI_RUN_INTEGRATION` skipif to all 7. Literal SC #1 match, but tests then silently skip in CI — losing default coverage. | |
| Case-by-case | Re-examine each file, pick per-file. | |

**User's choice:** Allow-marker
**Notes:** Scout established all 7 files stub the LLM or are fully self-contained and run in CI by default; the skipif would defeat their purpose. Each marker should carry a one-line justification.

---

## PROJECT.md correction scope (DEBT-02)

| Option | Description | Selected |
|--------|-------------|----------|
| In-scope + current prose | Fix "What This Is" + Constraints (SC target) AND current-tense prose like Core Value. Leave historical sections (Key Decisions, Evolution, Context) intact. | ✓ |
| Strictly SC-scoped | Touch only "What This Is" and Constraints. Leaves Core Value stale. | |
| Full sweep | Rewrite every mention including historical entries. Risks falsifying history. | |

**User's choice:** In-scope + current prose
**Notes:** Distinction locked — "DeepAgents CLI" (the MCP host product) stays; only the `deepagents` framework/library refs and `lattice-wiki` naming get corrected. CLAUDE.md is the canonical source for corrected wording.

---

## docs/testing.md handling

| Option | Description | Selected |
|--------|-------------|----------|
| Out of scope | Note as deferred idea; keep phase tightly scoped to DEBT-01/02. | ✓ |
| Fix the reference | Repoint the test's error message at an existing doc. | |
| Create docs/testing.md | Write the missing gate-policy doc. | |

**User's choice:** Out of scope
**Notes:** The gate test's failure message references a non-existent `docs/testing.md`; deferred to the v1.10 backlog.

---

## Claude's Discretion

- Exact marker comment text and placement within each test file.
- Exact corrected sentences in PROJECT.md, provided they mirror CLAUDE.md and honor the keep-history / keep-"DeepAgents CLI" rules.

## Deferred Ideas

- Missing `docs/testing.md` referenced by the gate test's failure message.
- Stale wording in historical PROJECT.md sections — intentionally preserved as accurate record.
