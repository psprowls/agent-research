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

## Milestone: v1.1 — Quality Improvements

**Shipped:** 2026-05-17
**Phases:** 5 (Phases 6-10) | **Plans:** 39 | **Tasks:** ~150 | **Sessions:** dense execution over ~3 calendar days (2026-05-15 → 2026-05-17)
**Git range:** `8aa21d5` → `92e26fd` (230 commits; 49 feat-prefixed; +37,702 / −27,672 lines across 323 files)

### What Was Built

- **Prompt content port** (Phase 6) — librarian, ingestor, linter, scanner system prompts re-grounded in canonical lattice-wiki SKILL.md content via 8 shared fragments under `prompts/_fragments/` with `# Source: / # Anchor: / # Source-commit:` provenance comments. 4 prompt builder functions (`build_X_system`) replace module-level constants. Drift becomes detectable in code review because every rule traces to a source path + anchor.
- **Divergence detection eval** (Phase 6) — 15 programmatic check rules (LIB/ING/LNT/SCN), 4 LLM-judge rubrics, 37 unit tests, plus a `--accept-divergence-baseline` regression gate. All pure-Python, no Bedrock dependency for the check rules themselves. 0 hard-severity divergences against the lattice-wiki baseline.
- **Cost-frontier sweep** (Phase 7) — two-gate scoring (divergence vs. baseline + LLM-judge quality) across 6 in-scope roles, run against the post-port agent. `models.toml` defaults updated to Qwen3-32B fan-out + Qwen3-80B synthesis with provenance comments preserving the previous Claude defaults. Full results doc under `.planning/sweep/`.
- **Host reliability** (Phase 8) — `SubagentPool` cancellation chain (`_run_one` `CancelledError` branch + `_write_batch_terminal` outer terminal record), direct-asyncio cancel test with stubbed LLM (zero Bedrock cost), single sequential E2E integration test exercising all 6 MCP tools (`wiki_init/scan/ingest/query/lint/log`) as stdio subprocess against tmp_path vault. 210-line `docs/cancellation.md` documents the protocol + the v1.2+ aioboto3 path.
- **Trace schema versioning + cost-aware renderer** (Phase 9) — `schema_version: 1` stamped as first key of every JSONL record by all 3 producers; renderer surfaces per-(role, model_id) cost rollup with `(+K unknown)` accounting (sorted desc cost, alphabetical tie-break, fully-null groups last); collapses ≥2 consecutive same-role groups by default into single summary line, `--expand` for full per-record view; lenient consumer warns once per file on v0 (inferred) or unknown future versions.
- **Subagent context completion** (Phase 10) — `render_project_context(wiki_path)` reads `wiki/CLAUDE.md` (or `AGENTS.md`), parses the layout block via `vault_io.layout_io.read_layout`, returns deterministic ~30-line block. Wired through 4 prompt builders and 3 commands (scan, lint, ingest) at SystemMessage construction. +1500 token cap per role enforced via syrupy snapshot tests; ingestor tightest at +751 headroom. Divergence eval re-ran live (us-east-1, 193s, 4/4 PASSED), no regression.

### What Worked

- **Quality before measurement, sequencing held.** Hard constraint: Phase 7 (sweep) must run after Phase 6 (port). Tempting to invert (have sweep data first), but porting first meant the sweep measured the *improved* agent. Cost-optimal picks reflect production behavior, not pre-port behavior.
- **Provenance comments on every prompt rule.** Each rule traces to a lattice-wiki SKILL.md source path + anchor + source-commit. Drift detection now lives in `git diff` rather than memory. Pattern reused across all 8 shared fragments.
- **Snapshot tests + token budget tests as the contract for prompt changes.** syrupy `.ambr` baselines lock 14 prompt shapes; `test_token_budget.py` enforces +1500 tokens per role ceiling. Any future prompt change announces itself loudly in CI rather than silently inflating cost.
- **Two-gate sweep scoring (divergence + LLM-judge).** Cheap models that pass divergence checks but produce subjectively worse output get filtered. Single-gate would have under-rejected; sharper signal at the cost of a small amount of judge runtime.
- **Scope narrowing documented in RESEARCH.md before implementation.** Phase 8 SC#1 (direct-asyncio cancel test vs. real DA-CLI host) and SC#2 (no opt-in gate) were intentional narrowings backed by RESEARCH/PLAN reasoning. VERIFICATION flagged them as `human_needed` for explicit owner sign-off rather than silently passing — exactly the right shape.
- **Single sequential E2E test over six separate per-tool tests.** One stdio subprocess spawn amortized across all 6 tools, matches the DA-CLI runtime shape, gated to opt-in for cost discipline.
- **`render_project_context()` at command entry (not per-subagent invocation).** Render once, pass through; respects the token budget, avoids redundant `wiki/CLAUDE.md` reads on fan-out. Also: no deepagents `SubAgentMiddleware` migration — fragment curation + project_context renderer achieved the same outcome at a fraction of the architectural cost.
- **Gap-closure plans as the response to verification failures.** Phase 6 found 5 UAT gaps (ING-001 fenced frontmatter, page_type routing, etc.) — closed via plans 06-12 through 06-16 rather than re-planning the phase. Phase 9 found 3 CR/WR advisory gaps — closed via plan 09-06. Tight feedback loop kept phases atomic.

### What Was Inefficient

- **REQUIREMENTS.md traceability table drifted again.** Same pattern as v1.0 — at audit time, 9 REQ-IDs (MCP-09/10/11, DACLI-01/02/03, OBS-04/05/06) were still `[ ]` Pending despite shipping. v1.0 lesson explicitly called this out, but the fix never landed in the per-phase completion gate. Recommend: enforce in `/gsd:execute-phase` completion that all phase REQ-IDs flip in REQUIREMENTS.md before SUMMARY.md commit.
- **SUMMARY.md `requirements_completed` frontmatter is sparse.** Many SUMMARY files have `requirements_completed: []` despite the plan covering specific REQ-IDs. Made the 3-source cross-reference (VERIFICATION + SUMMARY + traceability) rely heavily on VERIFICATION. Fix: tighten the SUMMARY template + add a planner check that derives `requirements_completed` from the plan's `requirements` frontmatter.
- **Nyquist coverage is uneven across v1.1.** 0 phases reached `nyquist_compliant: true`; 3 phases have draft VALIDATION.md, 2 phases have no VALIDATION.md at all. The toggle is configured `true` but the workflow doesn't fail closed. Either: retro-validate v1.1, or disable the toggle to align config with practice. v1.2 should pick one.
- **The CLI `summary-extract --pick one_liner` returned literal strings like `"One-liner:"` or random plan-text first-lines** for ~13 of the 39 v1.1 SUMMARY files. Made the auto-generated MILESTONES.md entry unusable until manually curated. Same root cause as the v1.0 `null` one_liner issue — different failure mode (matches the wrong line) but same fix: tighten the SUMMARY template.
- **Workspace rename `cores/` → `packages/` landed after v1.1 plans were written.** Historical entries throughout PROJECT.md and SUMMARY files reference `cores/`. Not invalidating, but noisy. Future rule: do path renames at milestone boundaries, not mid-flight, or do them atomically with a doc sweep.
- **CTX-05 divergence eval re-run had to defer half of itself.** "Live Bedrock unreachable from the parallel-executor worktree" forced a manual developer-side run rather than CI-side. The eventual re-run (post-Phase 10) passed cleanly, but the deferral pattern is a smell — long-running live evals shouldn't live on the critical path of a parallel worktree.

### Patterns Established

- **Provenance comments on every prompt rule** — `# Source: <path> / # Anchor: <section> / # Source-commit: <sha>`. Reusable for any external-source content drift detection.
- **Two-gate eval scoring** — pair a cheap programmatic check (divergence vs. fixed baseline) with a quality judge (LLM rubric). Either gate alone under-filters.
- **`schema_version` as first key of every record** — JSONL/object schemas with explicit versioning + lenient consumer that warns-but-renders on unknown versions. Generalizable beyond traces.
- **`build_X_system(project_context="") -> str` over module-level constants** — prompt strings as composable functions; backward-compat aliases preserved for incremental migration.
- **Render-once context injection at command entry** — pre-compute shared context (`render_project_context`) at command entry and pass through to all subagent prompt builders. Avoids redundant reads on fan-out.
- **Documented scope narrowing** — when implementation deviates from ROADMAP SC, document in RESEARCH/PLAN and let VERIFICATION emit `human_needed` for explicit sign-off rather than `passed` for silent acceptance.
- **Gap-closure plans rather than re-planning the phase** — when VERIFICATION/UAT surface gaps, add 1-3 targeted plans to the same phase. Preserves atomic phase shape, keeps plan history intact, avoids rewriting working plans.

### Key Lessons

1. **The REQUIREMENTS.md drift problem from v1.0 was not fixed.** Same gap recurred in v1.1 — 9 REQ-IDs unchecked at audit time despite shipping. The lesson "keep REQUIREMENTS.md in the per-phase gate" is correct; it needs to actually land in the workflow before v1.2.
2. **Architectural restraint pays.** Phase 10 explicitly declined to migrate to `deepagents.SubAgentMiddleware` and instead used the existing `SubagentPool` + a render function. The simpler solution shipped in days; the migration would have cost weeks. Default to the smallest delta that closes the gap.
3. **Document scope narrowing in writing, before the implementation lands.** The 2 Phase 8 SC deviations were captured in RESEARCH.md and PLAN.md *first*; VERIFICATION flagged them automatically. Trying to retroactively justify scope narrowings at verification time is much harder.
4. **Token budgets need automated enforcement, not just measurement.** `test_token_budget.py` flips a fail when any role exceeds +1500 tokens. Without that gate, prompt growth would be invisible until a Bedrock bill spike.
5. **Provenance comments turn drift detection into a `git diff` problem.** Code-side rules referencing external sources should always carry source + anchor + source-commit. Drift becomes diffable rather than memory-dependent.
6. **One-liner schema enforcement matters at scale.** The MILESTONES.md auto-population at archive time depends on the `one_liner:` field being parseable and meaningful. Sparseness compounds — at 39 plans, manually fixing 13 wrong entries costs real time.
7. **Live evals don't belong on parallel-worktree critical paths.** When the executor can't reach Bedrock from a worktree, the eval gets deferred. Move live eval calls behind explicit `--run-live-evals` gates that the operator runs from a privileged shell.

### Cost Observations

- **Model mix during development:** primarily Opus 4.7 for planning + Sonnet 4.6 for execution per GSD profile. Heavy parallelization via worktrees (Phases 6/7/8/9/10 partially overlapped — Phase 8 explicitly parallel to 6/7; Phase 10 depends only on 6's baseline).
- **Sessions:** dense execution over ~3 calendar days. 230 commits in range. Pattern: short focused execution sessions per plan, gap-closure rounds via dedicated plans.
- **Notable production cost outcome:** `models.toml` swap to Qwen3-32B fan-out + Qwen3-80B synthesis is the headline cost win. Concrete per-run delta vs. Claude defaults captured in `.planning/sweep/STORY.md`.
- **Eval bill discipline:** Phase 7 explicitly skipped a duplicate `test_full_matrix_live` pytest run to avoid $6 of duplicate Bedrock spend — the test exists and is gated, just wasn't re-executed inside the plan session. Cost-aware verification is the right call.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~12 | 5 | Established `cores/` + `agents/` workspace pattern; SubagentPool as shared infra; eval harness with two-judge Bedrock panel |
| v1.1 | dense ~3 days | 5 | Prompt-as-Python-module with provenance comments; two-gate sweep scoring; schema-versioned trace JSONL with lenient consumer; render-once context injection; gap-closure plan pattern |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 359 pytest files across workspace | per-member (each member's own testpaths) | `bm25s`, `python-frontmatter`, `deepeval`, `typer`, `langchain-aws`, `mcp` |
| v1.1 | +divergence eval (37 tests), prompt snapshots (14 baselines, 26 tests), token budget (6 tests), trace renderer (~20 tests across 09-01..09-06), MCP cancel (1 stub-LLM test), DA-CLI E2E (1 subprocess test covering 6 tools) | per-member | (none — v1.1 was content-and-quality work, no new top-level deps) |

### Top Lessons (Verified Across Milestones)

1. **Schema files (REQUIREMENTS.md, traceability tables) need per-phase gate enforcement, not milestone-close cleanup.** v1.0 flagged it as a one-off; v1.1 hit the same drift again. Now classified as systemic — fix lives in `/gsd:execute-phase` completion, not in human discipline.
2. **`one_liner:` belongs in every SUMMARY.md as a required, parseable field.** v1.0: nulls. v1.1: wrong-line matches. Both shapes break MILESTONES.md auto-population. Tighten the template before v1.2.
3. **Phase ordering with hard constraints holds under pressure.** v1.0: `SubagentPool` before fan-out commands. v1.1: prompt port before cost-frontier sweep. In both cases the sequencing felt slow at the time but produced the correct measurement substrate.
4. **Structured trace output from day 1 keeps compounding.** v1.0 shipped the JSONL format; v1.1's cost-frontier sweep + trace renderer + schema versioning all sit on top of that single decision. Worth front-loading observability schema decisions.
5. **Cap phase plan count at ~6 (and split when it grows).** v1.0 Phase 3 hit 9 plans and snarled the dependency graph. v1.1 Phase 6 hit 16 plans (including 5 gap-closure) — the gap-closure pattern made it workable, but a cleaner phase split would have been simpler.
6. **Bedrock-only single-provider focus was correct.** Both milestones validated it — eval-harness combinatorics stayed manageable; v1.1 cost-frontier sweep was tractable because all candidates lived on one provider.
