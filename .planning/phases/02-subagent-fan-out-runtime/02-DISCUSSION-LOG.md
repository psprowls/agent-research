# Phase 2: Subagent Fan-Out Runtime - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 02-subagent-fan-out-runtime
**Areas discussed:** SubAgentMiddleware fate, SubagentPool API shape, Cost rate source for traces

---

## SubAgentMiddleware Fate

| Option | Description | Selected |
|--------|-------------|----------|
| Skip to asyncio — bugs already confirmed | STATE.md records bug #694/#1698 as confirmed; skip trial, go straight to asyncio pool | |
| Run the trial for real | Write an integration test against SubAgentMiddleware; record failure evidence | |
| Researcher reads 0.6.1 source first, then decides | Inspect source before code; choose based on bug status | |

**User's choice:** Researcher reads #694 PR first, then recommends — with full discretion

**Notes:** User provided new information mid-discussion that changed the landscape:
- Bug #1698 (recursion limit / GraphRecursionError) was fixed in deepagents 0.5.4 via PR #2194. It is already shipped in 0.6.1. No workaround needed.
- Bug #694 (cancellation cascade) was closed/merged on 2026-05-13 but is NOT yet in a released version.
- User suggested: "Could we potentially just create our own implementation of this new middleware and use it until everything is live?" — This is captured as the "vendor path" option in D-01.
- Final tiebreaker: researcher has full discretion based on PR complexity. No hardcoded rule beyond "read the PR."

---

## SubagentPool API Shape

**Q1: Calling convention**

| Option | Description | Selected |
|--------|-------------|----------|
| Items + async callable + role name | `pool.run_all(items, task, role)` — plain Python callables | ✓ |
| Pre-built LangChain runnables + role name | `pool.run_all(runnables, role)` — callers construct one chain per item | |
| Prompt template + items + role name | Pool constructs prompts internally | |

**Q2: Return type on partial failure**

| Option | Description | Selected |
|--------|-------------|----------|
| FanOutResult(successes, errors) | Structured dataclass; caller can correlate errors back to items | ✓ |
| list[result \| Exception] | Parallel-indexed list; simpler but requires zip to correlate | |

**Q3: Model injection**

| Option | Description | Selected |
|--------|-------------|----------|
| Task captures model in a closure | Caller calls `make_llm(role)` before constructing task; pool owns only throttle + trace | ✓ |
| Pool injects model: `task(item, llm=resolved_llm)` | Centralized model injection; couples pool to task signature | |

**User's choice:** Items + async callable + role, FanOutResult return, closure-owns-model

**Notes:** Consistent with Phase 1's `make_llm()` pattern. Pool's role parameter serves two purposes only: semaphore cap (from models.toml max_concurrency) and trace metadata emission.

---

## Cost Rate Source for Traces

**Q1: Where does cost_usd come from?**

| Option | Description | Selected |
|--------|-------------|----------|
| Store rates in models.toml | Each role gets cost_per_1k_input/output fields | |
| Null in Phase 2, populate in Phase 4 | Write cost_usd: null now; Phase 4 eval harness adds it | ✓ |
| Hardcoded Python lookup table | Dict mapping model_id prefix → rate; gets stale | |

**Q2: Tokens in/out — capture or defer?**

| Option | Description | Selected |
|--------|-------------|----------|
| Capture tokens from response metadata in Phase 2 | usage_metadata available from ChatBedrockConverse response | ✓ |
| Defer everything — null for tokens too | Minimal trace in Phase 2; accounting added in Phase 4 | |

**User's choice:** cost_usd=null deferred to Phase 4; tokens_in/tokens_out captured from response in Phase 2

**Notes:** Phase 4 (eval harness) has full model ARN context and pricing infrastructure. Having token counts in Phase 2 traces is useful for debugging even without cost. Pragmatic split.

---

## Claude's Discretion

- **SubAgentMiddleware vs asyncio pool:** Researcher's call after reading #694 PR
- **7-role model ARN selection** for models.toml expansion: researcher confirms from current Bedrock lineup
- **models.toml schema** for max_tokens + max_concurrency fields: planner designs
- **Trace file naming** within `.code-wiki/traces/`: planner picks convention
- **OBS-02 trace viewer format** for `code-wiki-agent trace <file>`: planner designs

## Deferred Ideas

- **Cost rates in models.toml** (cost_per_1k_input/output fields) — surfaced as an option but deferred to Phase 4 when cost accounting infrastructure is built
- **Throttle backoff on ThrottlingException** — the semaphore cap approach avoids throttling proactively; reactive backoff is a future optimization if the cap approach proves insufficient
