# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — code-wiki-agent parity

**Shipped:** 2026-05-15
**Phases:** 5 | **Plans:** 25 | **Sessions:** ~12 working sessions over 3 calendar days (2026-05-13 → 2026-05-15)

### What Was Built

- **End-to-end `code-wiki-agent`** on AWS Bedrock with full lattice-wiki command parity: `init`, `scan`, `ingest`, `query`, `lint`, `log` — all six surfaced through both a FastMCP stdio server (`code-wiki-mcp`) and a Typer-based headless CLI sharing a single command-implementation module.
- **`cores/subagent-runtime`** — `SubagentPool.run_all()` with per-role semaphore throttling, partial-failure isolation (one failure ≠ sibling cancellation), explicit recursion-limit propagation, and structured JSONL trace output (`.code-wiki/traces/`) wired in from day one. Powers fan-out for the librarian (Phase 3), scanner (Phase 5), and linter (Phase 5).
- **`cores/vault-io`** — 11 modules ported verbatim from `lattice-wiki-core` with import surgery only (no logic changes), gated by a round-trip golden test that asserts byte-identical write-back on a 148-page real-vault fixture.
- **`cores/model-adapter`** — `ModelRegistry` keyed by logical role (`librarian`, `scanner`, `linter`, `ingestor`, `synthesizer`, `judge_a`, `judge_b`, etc.) sourced from a single `models.toml`. Bedrock-only via `ChatBedrockConverse`; `BedrockAccessDenied` raised with the attempted ARN + IAM verb on permission failure.
- **`cores/eval-harness`** — fixture corpus (3 repos), headless `claude -p` baseline recorder (EVAL-08 schema, 8 reproducibility fields), `deepeval` 4.0 integration with `AmazonBedrockModel`, heterogeneous two-judge GEval panel (`claude-sonnet-4-6` + `nova-pro-v1:0`) with position-bias check, cost-frontier sweep runner via `pytest-evals`, and a regression-check `AssertionError` gate.
- **Hybrid search**: BM25 via `bm25s` 0.3.8 + Titan Embeddings v2 in SQLite (WAL mode), sha256-keyed incremental rebuild, RRF fusion with configurable weights; raw + fused scores exposed in `--json` for debugging.
- **MCP stdout discipline** locked at infrastructure level — `_StdoutGuard` sentinel + subprocess JSON-RPC integrity test that asserts every stdout byte is valid framing.
- **CI hygiene** — ruff lint+format clean across the workspace; per-member pytest isolation; `uv` single shared `uv.lock`.

### What Worked

- **"Port verbatim" was the right call for vault-io.** All 11 modules ported with import surgery only — no re-implementation bugs, no schema drift, golden test green on the first real-vault fixture run. The temptation to "improve" PyYAML round-tripping during the port would have cost days; preserving the hand-rolled emitter from `layout_io.py` paid for itself in Phase 1.
- **Phase ordering held under pressure.** Building `SubagentPool` (Phase 2) before any command that needed fan-out (Phases 3-5) meant fan-out semantics — partial failure, throttle, trace — were designed once, not retrofitted three times. Same pattern with the eval harness (Phase 4) before the bulk of the commands (Phase 5) — having a working `query` to baseline against gave the harness real signal instead of toy data.
- **Structured trace output from day one** turned out to be the cheapest observability investment of the milestone. JSONL records with `(role, model, prompt hash, item_id, status, latency_ms, tokens_in, tokens_out, cost_usd)` mean v1.1 cost analysis has the data already — no instrumentation pass needed.
- **Bedrock-only single-provider focus.** Adding a second provider would have at least doubled the eval-harness combinatorics. Sticking to Bedrock kept `ModelRegistry` simple (`role → ChatBedrockConverse`) and the `deepeval` setup uniform.
- **Stop-and-port discipline at Phase 3 G1 (citation resolver) regression.** Catching the `.md`-suffixed-wikilink bug in UAT and rolling back rather than papering over it gave Phase 5's lint command a correct foundation.

### What Was Inefficient

- **REQUIREMENTS.md drift.** The file's checkbox state and traceability table fell badly out of sync with reality — at milestone close, 60 of 67 requirements were unchecked despite all phases shipping. The actual shipped state lived in phase VERIFICATION.md / SUMMARY.md files; reconciling at close required a sweep. Future fix: bump REQUIREMENTS.md as part of the phase-completion gate, not at milestone close.
- **A few SUMMARY.md files lacked a parseable `one_liner:` field** (Phase 3-01, Phase 5-01/02 returned `null` to the extractor). Cost a few minutes per file to recover during the milestone-archive accomplishments pull. Fix: make the `one_liner:` field a required schema field in the SUMMARY template.
- **Phase 1 BED-01 live gate stayed open through the entire milestone.** The code-side acceptance passed (correct error type with ARN + IAM verb), but the live `make_llm("haiku").invoke("ping")` call against real Bedrock remained blocked on an out-of-band AWS account onboarding form. Worked around it, but it would have been better to surface this as a v0 blocker on day 1 instead of carrying it as a quiet caveat across 5 phases.
- **Phase 03 had 9 numbered plans (03-01 … 03-09) — most other phases had 4-6.** Sign that Phase 3's "query vertical slice + hybrid search" probably should have been two phases (hybrid search + query command). Plan dependency chains got tangled around 03-08 / 03-09 (model selection + post-hoc additions). Future fix: cap phase plan count at ~6, split if research surfaces more.

### Patterns Established

- **`cores/` (shared) + `agents/` (consumers)** with `uv` workspaces. `cores/` packages are leaf nodes (no workspace deps); agents pull cores as workspace deps. Will be reused for every future agent in the monorepo.
- **`models.toml` as the single source of truth for role → model binding.** No hardcoded model IDs anywhere in application code. `--config <path>` overrides for dev/eval. `ModelRegistry` is the only resolver.
- **`role` is a first-class concept across the stack** — eval harness, subagent pool, model registry, and `models.toml` all key on the same string. New commands declare their role(s); fan-out picks up role-bound semaphore + max_tokens + cost-tracking automatically.
- **MCP tools register *after* `mcp = FastMCP(...)` to preserve `_StdoutGuard`.** Non-obvious; documented as an iron rule in PROJECT.md → Constraints (going forward).
- **Vault writes route through ported `layout_io.py`; vault reads can use `python-frontmatter`.** Read/write asymmetry is intentional and load-bearing — preserving exact whitespace/ordering on write-back is what makes the tool side-by-side compatible with Obsidian.
- **Single MCP tool with a discriminator** (`wiki_ingest` with `type: Literal['source','work-item']`) beats two near-identical tools — better discoverability, cleaner schema, type-narrowing server-side.

### Key Lessons

1. **Keep schema files (REQUIREMENTS.md, traceability tables) inside the per-phase completion gate.** Anything updated only at milestone-close drifts; anything updated as part of "phase complete" stays accurate.
2. **Cap phase plan count at ~6.** When a phase needs 9+ plans, that's the signal to split — the dependency graph becomes too tangled to manage atomically.
3. **Surface external blockers (BED-01-style "wait on AWS form") on Day 1 as a build-or-break gate, not a quiet TODO.** The cost of pausing is low; the cost of a forgotten side-channel dependency is real.
4. **Eval infrastructure first, eval results second.** Shipping the harness without running the sweep is the *correct* milestone shape — the sweep is its own deliverable with its own variance, and running it under a fixed harness is what makes the results meaningful. (Don't conflate "harness works" with "sweep complete".)
5. **`one_liner:` belongs in every SUMMARY.md.** It's the only field used at milestone-archive time; making it optional pays a tax later.

### Cost Observations

- **Model mix during development:** primarily Opus 4.7 for planning + Sonnet 4.6 for execution per GSD profile (`planner_model: opus`, `executor_model: sonnet`). No haiku in the dev loop; haiku reserved for production-time roles in `models.toml`.
- **Sessions:** ~12 working sessions over 3 calendar days (heavy parallelization via worktrees — phases 4 + 5 ran in parallel worktree branches).
- **Notable:** the SubagentPool fan-out pattern means runtime cost of `code-wiki-agent` itself scales with task count, not with conversation length. Once the v1.1 cost-frontier sweep runs and pushes scanner/linter/librarian onto cheaper non-Claude Bedrock models (Nova, Llama), per-run cost should drop sharply vs. the existing lattice-wiki plugin running on Claude Sonnet via Claude Code.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~12 | 5 | Established `cores/` + `agents/` workspace pattern; SubagentPool as shared infra; eval harness with two-judge Bedrock panel |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 359 pytest files across workspace | per-member (each member's own testpaths) | `bm25s`, `python-frontmatter`, `deepeval`, `typer`, `langchain-aws`, `mcp` |

### Top Lessons (Verified Across Milestones)

1. *(Awaiting v1.1 to cross-validate v1.0 lessons.)*
