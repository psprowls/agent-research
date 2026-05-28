# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — graph-wiki-agent parity

**Shipped:** 2026-05-15
**Phases:** 5 | **Plans:** 25 | **Sessions:** ~12 working sessions over 3 calendar days (2026-05-13 → 2026-05-15)

### What Was Built

- **End-to-end `graph-wiki-agent`** on AWS Bedrock with full lattice-wiki command parity: `init`, `scan`, `ingest`, `query`, `lint`, `log` — all six surfaced through both a FastMCP stdio server (`graph-wiki-mcp`) and a Typer-based headless CLI sharing a single command-implementation module.
- **`cores/subagent-runtime`** — `SubagentPool.run_all()` with per-role semaphore throttling, partial-failure isolation (one failure ≠ sibling cancellation), explicit recursion-limit propagation, and structured JSONL trace output (`.graph-wiki/traces/`) wired in from day one. Powers fan-out for the librarian (Phase 3), scanner (Phase 5), and linter (Phase 5).
- **`cores/wiki-io`** — 11 modules ported verbatim from `lattice-wiki-core` with import surgery only (no logic changes), gated by a round-trip golden test that asserts byte-identical write-back on a 148-page real-vault fixture.
- **`cores/model-adapter`** — `ModelRegistry` keyed by logical role (`librarian`, `scanner`, `linter`, `ingestor`, `synthesizer`, `judge_a`, `judge_b`, etc.) sourced from a single `models.toml`. Bedrock-only via `ChatBedrockConverse`; `BedrockAccessDenied` raised with the attempted ARN + IAM verb on permission failure.
- **`cores/eval-harness`** — fixture corpus (3 repos), headless `claude -p` baseline recorder (EVAL-08 schema, 8 reproducibility fields), `deepeval` 4.0 integration with `AmazonBedrockModel`, heterogeneous two-judge GEval panel (`claude-sonnet-4-6` + `nova-pro-v1:0`) with position-bias check, cost-frontier sweep runner via `pytest-evals`, and a regression-check `AssertionError` gate.
- **Hybrid search**: BM25 via `bm25s` 0.3.8 + Titan Embeddings v2 in SQLite (WAL mode), sha256-keyed incremental rebuild, RRF fusion with configurable weights; raw + fused scores exposed in `--json` for debugging.
- **MCP stdout discipline** locked at infrastructure level — `_StdoutGuard` sentinel + subprocess JSON-RPC integrity test that asserts every stdout byte is valid framing.
- **CI hygiene** — ruff lint+format clean across the workspace; per-member pytest isolation; `uv` single shared `uv.lock`.

### What Worked

- **"Port verbatim" was the right call for wiki-io.** All 11 modules ported with import surgery only — no re-implementation bugs, no schema drift, golden test green on the first real-vault fixture run. The temptation to "improve" PyYAML round-tripping during the port would have cost days; preserving the hand-rolled emitter from `layout_io.py` paid for itself in Phase 1.
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
- **Notable:** the SubagentPool fan-out pattern means runtime cost of `graph-wiki-agent` itself scales with task count, not with conversation length. Once the v1.1 cost-frontier sweep runs and pushes scanner/linter/librarian onto cheaper non-Claude Bedrock models (Nova, Llama), per-run cost should drop sharply vs. the existing lattice-wiki plugin running on Claude Sonnet via Claude Code.

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
- **Subagent context completion** (Phase 10) — `render_project_context(wiki_path)` reads `wiki/CLAUDE.md` (or `AGENTS.md`), parses the layout block via `wiki_io.layout_io.read_layout`, returns deterministic ~30-line block. Wired through 4 prompt builders and 3 commands (scan, lint, ingest) at SystemMessage construction. +1500 token cap per role enforced via syrupy snapshot tests; ingestor tightest at +751 headroom. Divergence eval re-ran live (us-east-1, 193s, 4/4 PASSED), no regression.

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

## Milestone: v1.2 — Graph-Wiki Port & Debt Cleanup

**Shipped:** 2026-05-19
**Phases:** 6 (Phases 11-16) | **Plans:** 21 | **Sessions:** dense execution over ~3 calendar days (2026-05-17 → 2026-05-19)
**Git range:** `92e26fd` → `HEAD` (205 commits; +33,296 / −2,412 lines across 715 files)

### What Was Built

- **`packages/workspace-io/` ported from upstream `lattice-workspace`** (Phase 11) — 8 source modules + 11 test files (~67 tests) under the new `workspace_io` namespace; `.graph-wiki.yaml` is the per-workspace manifest filename (replacing legacy `.lattice.yaml`); `GRAPH_WIKI_WORKSPACE` is the env override; `GraphWikiConfig` dataclass; `workspace_io.config.resolve()` walks upward from cwd. 4 deliberate behavioral divergences locked: D-03 strict resolve, D-06 schema drop (work-layer out of v1.2), D-14 v1-raises, D-16 file/key rename. `wiki_io._workspace.resolve_wiki_and_repo` rewritten as a 2-line delegation shim over `workspace_io.config.resolve()` with the explicit-vault_path MCP boundary preserved. `graph-wiki-agent init` performs a two-phase bootstrap (workspace_io.init first, then init_wiki). 18 `GRAPH_WIKI_REAL_VAULT_PATH` references swept to `GRAPH_WIKI_WORKSPACE`.
- **Drift inventory + selective backport** (Phase 12 P-A/P-B) — Body-diff dump across 11 overlapping modules between `wiki-io` and upstream `lattice-wiki-core` at a pinned SHA, captured in `DRIFT-DECISIONS-RAW.md` (2038 lines). Zero PORT verdicts after analysis: every drift hunk is an intentional wiki-io divergence (lib-ification / MCP error handling / no-tiktoken) or out-of-v1.2 subsystem (package-family / CLI `main()`). Canonical `packages/wiki-io/DRIFT-DECISIONS.md` published with rationale per row.
- **Ecosystem rebrand `lattice` → `graph-wiki`** (Phase 12 P-C/P-D) — 5 atomic commits sweep `lattice` / `LATTICE` / `lattice_workspace` / `lattice_wiki_core` across `packages/`, `agents/`, `plugins/`, `.planning/`, `CLAUDE.md` with `uv run pytest` gated green after each. `scripts/check-brand.sh` + `.brand-grep-allow` (52 intentionally-preserved historical refs) enforces ongoing brand discipline. `.planning/spikes/CONVENTIONS.md` `cores/` → `packages/` corrected.
- **Plugin contract locked** (Phase 13) — 6 per-command port specs + 2 cross-cutting docs under `.planning/spec/13-plugin-contract/`. CONTRACT-INDEX.md is a 9-row verdict table (6 commands rename/reshape, 3 dropped per C-01 work-layer scope-out). SHELL-OUT-PATTERN.md locks SO-01..04: plugin scripts shell out via `uv run --project "$AGENT_RESEARCH_ROOT" python3 -m ...` (SO-01); backend selection per-command via `[plugin]` block in `.graph-wiki.yaml` (SO-03); defaults to `claude`, `bedrock` is documented per-command opt-in. **Foundational reframe:** the ported `plugins/graph-wiki/` plugin runs on **Claude Code inference** (P-01) — NOT a wrapper around `graph-wiki-agent`. The Bedrock-backed `graph-wiki-agent` stays as the parallel cost-frontier surface; the two coexist over the same Python helpers in `wiki-io` / `workspace-io`.
- **Plugin port `plugins/graph-wiki/`** (Phase 14) — Plugin scaffold (`plugin.json`, CLAUDE.md, README, 6 command files) under renamed `/graph-wiki:*` namespace; agent/skill renames per SHELL-OUT-PATTERN.md; shims wired through `wiki-io` (which itself uses `workspace-io`). `workspace_io` manifest extended with `[plugin]` backend-selector block. Phase 14 prerequisite ports landed in `wiki-io`: `wiki_io.lint_wiki` (~509 LOC) + `wiki_io.wiki_search` (~194 LOC) verbatim-ported from upstream `lattice_wiki_core` with brand rename and `_version_check` removal.
- **Wiki self-update** (Phase 15) — `~/Personal/graph-wiki/agent-research` re-scanned + OTel re-ingested + librarian query run via `graph-wiki-agent` using a one-off Claude role-override profile (`models-claude.toml` + `wiki-config-claude.toml`) on Haiku 4.5 fan-out + Sonnet 4.6 reasoning to bring the wiki into alignment with the post-rebrand codebase. 3 operational deviations encountered and auto-fixed inline: `--config` doesn't propagate `vault_path` to subcommands (always pass `--vault` explicitly); wiki CLAUDE.md layout block carried stale `cores/` container name (fixed to `packages/`); BM25 index requires manual rebuild after scan. Documented in `15-VERIFICATION.md`.
- **v1.1 carry-forward debt closed** (Phase 16) — Plan 16-01 in 9 atomic step-commits: `trace_io` module extraction from `pool.py`; ingest/query refactor to use `write_trace_record`; code_reader/synthesizer DivergenceMetric rubrics; `code_reader_cases.json` expanded to 6 cases against post-rebrand surfaces; fixture-vault scanner regression; MCP cancel spike + `docs/cancellation.md` refresh (re-anchored to event-driven trigger: langchain-aws#663 merged OR aioboto3 GA/1.0); `docs/testing.md` codifying `GRAPH_WIKI_RUN_INTEGRATION` semantics + grep gate; synthesizer model_id assertion locked to Qwen reality; live-vault re-sweep + `16-VERIFICATION.md`. Plan 16-02 closed G-01 by threading `response.usage_metadata` through `TaskResult` contract on `SubagentPool.run_all`; all 4 production fan-out callsites (scanner, linter, librarian, code_reader) now emit non-None tokens/cost on per-item trace records; gated TRACE-FU-01 regression passes against real Bedrock.

### What Worked

- **Spec phase before plugin port (M3a → M3b).** Splitting Phase 13 (spec-only) from Phase 14 (port) forced the "what does this thing actually shell out to?" question to get answered in writing before any plugin code moved. The foundational reframe — plugin runs on Claude Code inference, not a `graph-wiki-agent` wrapper — surfaced during spec authoring, not during port debugging. Would have been a much more expensive surprise if it had landed during M3b.
- **Body-diff dump → verdict assignment as separate plans.** Phase 12 P-A produced the raw 2038-line diff; P-B assigned verdicts row-by-row. Splitting the mechanical dump from the judgment work made the verdict phase reviewable in isolation. Zero PORT verdicts was a real outcome, not a "we didn't bother to check" outcome.
- **`uv run pytest` gated after each rebrand commit.** Phase 12 P-C was 5 atomic commits with the test suite green after each. Any single rebrand surface (packages/ / agents/ / plugins/ / .planning/ / CLAUDE.md) could be reverted independently. None had to be.
- **`scripts/check-brand.sh` + `.brand-grep-allow` as a normal pytest gate.** Brand discipline now lives in CI rather than memory. 52 intentionally-preserved historical references stay readable; any unallowlisted hit fails the gate. The pattern generalizes: any "must not contain X" rule should ship as a grep-gate, not as a code-review checklist.
- **WS-10 question forced to written answer.** "Is `wiki-config.toml` the same surface as `.graph-wiki.yaml`?" — the answer (different surfaces, no migration script) got recorded in PROJECT.md Key Decisions during Phase 11 plan 06. Future readers don't have to re-derive it.
- **Render-once project context still pays.** v1.1 Phase 10's `render_project_context()` pattern caught the stale `cores/` reference in `~/Personal/graph-wiki/agent-researchCLAUDE.md` during Phase 15 self-update — the agent's prompt rendering surfaced the drift immediately. Drift detection by execution rather than memory.
- **Phase 16 bundling carry-forward debt was the right move.** All 7 carry-forward items (TRACE-FU-01, SWEEP-FU-02/03/04, MCP-CAN-01/02, MODEL-FU-01) shipped as a single coherent phase rather than fragmenting across the milestone. Most items were independent; bundling kept context cost low and let the live-vault re-sweep (SWEEP-FU-04) reuse the fresh-package vault from Phase 12.
- **G-01 (librarian trace usage_metadata missing) caught by the first gated Bedrock run.** Plan 16-01's regression test landed the test infrastructure; the first real Bedrock run immediately surfaced that librarian callsites weren't returning the LangChain response object. Plan 16-02 added the `TaskResult` contract to fix it. Bug-find-by-running rather than bug-find-by-staring.
- **`TaskResult` contract is backward-compatible.** Wrapping the LangChain `AIMessage` instead of returning the raw scalar response means scalar-returning callbacks (existing tests) still work; new callbacks that need usage_metadata get it. Migration was atomic per-callsite, not big-bang.
- **MCP cancel deferral re-anchored to event trigger (Phase 16 D-09).** The original calendar-based "re-evaluate by X date" generated noise without changing the gate outcome. Switching to "re-evaluate when langchain-aws#663 merges OR aioboto3 GA/1.0 lands" turns the deferral into a real signal — the next re-evaluation will actually have new information.

### What Was Inefficient

- **Phase 14 SC#4 plugin smoke transcript not captured at close.** SC#4 wording was "Pat runs `/graph-wiki:query` and pastes transcript" — the structural evidence (plugin loads, brand-gate clean, manifest validates) was accepted as a substitute, but the actual transcript from a Claude Code session against `~/Personal/graph-wiki/agent-research` did not get recorded. Means there's no regression artifact for the plugin's end-to-end happy path. Fix: smoke transcripts should be a required artifact at phase close, captured by the operator and committed under the phase directory, not implied by structural checks.
- **Scanner re-sweep against fresh-package vault accepted at 65% deterministic pass-rate.** SWEEP-FU-04's "no regression vs. v1.1 baseline" was satisfied by 65% deterministic SCANNER_CHECKS pass-rate with 7 SCN-002/SCN-003 failures excused as structural mismatch (rules target raw LLM stub output; on-disk pages carry pipeline-appended `## File map`). The operator-acknowledged risk is real: an LLM-level scanner regression in v1.2 that the deterministic checks miss. Should have either tightened the deterministic rule set to match real on-disk output, or run `run_role_sweep` live to get actual numeric scores.
- **REQUIREMENTS.md drift recurred for a third milestone.** v1.0 flagged it. v1.1 hit it again. v1.2 hit it again — 28/30 boxes unchecked at close despite all phases shipping. The "per-phase REQ-ID gate in `/gsd:execute-phase`" lesson from v1.1 still hasn't landed in the workflow. v1.3 candidate: ship the fix as part of GSD tooling work, not as discipline.
- **No formal `/gsd:audit-milestone` run for v1.2.** Decision was made to proceed without it (Phase 16 VERIFICATION + UAT closed cleanly, no critical review findings), but skipping the audit means there's no cross-phase integration check committed to the archive. v1.0 and v1.1 had audits; v1.2 doesn't. If a regression turns up across the Phase 11 → 12 → 14 chain later, the recovery path is harder.
- **`gsd-sdk query milestone.complete` auto-accomplishments unusable.** Same root cause as v1.1: `summary-extract --pick one_liner` returns literal `"One-liner:"` strings or random plan-text first lines for SUMMARY files that don't have a clean `one_liner:` field at the top. 9/13 of the auto-generated v1.2 entries had to be discarded and rewritten manually. Fix is still pending from v1.1: tighten the SUMMARY template + add a planner check.
- **Phase 16 code review found 6 warnings + 9 info but no fix plan.** The review ran (`16-REVIEW.md` status: `issues_found`), but the findings rolled into v1.3 carry-forward rather than getting addressed in-phase. A code review that produces issues without a fix plan is review-as-documentation, not review-as-gate. Either: review at the end of a phase produces a follow-up plan in the same phase, or review happens at milestone close as part of audit.
- **Plugin port (Phase 14) was an 800+ LOC change.** Three plans, but plan 14-03 alone bundled "manifest `[plugin]` block + plugins/graph-wiki/ scaffold + 6 shims + SC#4 smoke transcript". The bundled scope made the plan reviewable in isolation, but if any one shim had broken, the rollback granularity would have been the whole plan. Cap at ~300 LOC or split.

### Patterns Established

- **Spec-only phase before code-moving phase** when the contract surface has open questions. M3a → M3b in v1.2; would have been useful (in retrospect) for Phase 06 prompt port in v1.1.
- **Body-diff dump → verdict assignment as separate plans** for any "merge two divergent codebases" surface. Mechanical work separated from judgment work.
- **Grep-gate enforcement for brand/style rules** via `.brand-grep-allow` pattern. Any "must not contain X" rule ships as `scripts/check-X.sh` + an allowlist file, runs in CI as a normal pytest gate.
- **Two-line delegation shim for cross-package boundary preservation.** `wiki_io._workspace.resolve_wiki_and_repo` is now 2 lines: forward to `workspace_io.config.resolve()`. MCP boundary contract (explicit-path override) preserved at the shim layer, not duplicated.
- **`TaskResult` over raw scalars** for any subagent callback that needs to surface LangChain response metadata (usage, model_id, tokens, cost). Backward-compatible per-callsite migration.
- **Event-driven deferrals** over calendar-driven deferrals. Anchor a deferral to a checkable signal (PR merged, dependency GA'd, blocker resolved); avoid scheduled re-evaluation toil.

### Key Lessons

1. **Spec phases pay off when the contract surface has open questions.** Phase 13 was tiny but caught the "plugin runs on Claude Code inference, NOT a graph-wiki-agent wrapper" reframe before any plugin code moved. The cost of a spec-only phase is ~5 plans of documentation; the cost of catching the same reframe mid-port is rewriting everything.
2. **Foundational reframes happen during spec authoring, not during planning.** Phase 13 spec captured the realization that `graph-wiki-agent` and the ported `plugins/graph-wiki/` plugin are parallel surfaces over the same wiki-io helpers, not a wrapper relationship. Spec phases create the space for these realizations.
3. **Grep-gates are how "must not contain X" rules actually live in CI.** Before BRAND-04, brand discipline depended on developer memory. After it, any unallowlisted `lattice` hit fails the test suite. The pattern generalizes to any rule that's verifiable by `grep -rE`.
4. **REQUIREMENTS.md drift is now classified as a tooling problem, not a discipline problem.** Three milestones with the same drift pattern. The fix has to ship as GSD tooling — a per-phase completion gate that flips REQ-IDs in the traceability table — not as another "remember to check the boxes" reminder.
5. **One-liner auto-extraction needs schema enforcement at write-time.** The `summary-extract --pick one_liner` heuristic has now failed across v1.0, v1.1, and v1.2. SUMMARY.md needs `one_liner: "..."` as a required top-level frontmatter field, validated at SUMMARY commit time. Heuristic extraction at archive time is too late.
6. **Bundle carry-forward debt; don't fragment it.** All 7 v1.1 carry-forward items shipped as Phase 16. Fragmenting them across the milestone would have created phantom dependencies and stretched the calendar; bundling kept context cost manageable and let live-vault re-sweep reuse the fresh-package vault from Phase 12.
7. **The fact-check at archive time matters.** v1.2 close caught: stale Phase 14 checkboxes in ROADMAP.md (all plans actually had SUMMARYs), 28/30 unchecked REQ-IDs (everything had shipped), `gsd-sdk milestone.complete` auto-accomplishments unusable. Without the fact-check, the archive would have been wrong. Lesson: don't trust the SDK to know what shipped; verify against SUMMARY.md presence.

### Cost Observations

- **Model mix during development:** primarily Opus 4.7 for planning + Sonnet 4.6 for execution per GSD profile. Phase 15 wiki self-update used a one-off Claude role-override profile (Haiku 4.5 fan-out + Sonnet 4.6 reasoning) to validate the brand on a separate model lineup from the Qwen production defaults.
- **Sessions:** dense execution over ~3 calendar days. 205 commits in range. The port + rebrand surface was much wider (715 files) but most changes were mechanical text edits (rename sweep) rather than logic changes.
- **Notable production cost outcome:** v1.2 closed the trace `usage_metadata` gap, which means future cost analysis can actually be done from JSONL traces. Until 16-02, production traces emitted `tokens_in: null` for librarian fan-out — cost rollups in the renderer were lying by omission. Now they're accurate.
- **Eval bill discipline held:** Phase 16 scanner re-sweep accepted 65% deterministic pass-rate on the live vault rather than re-running `run_role_sweep` against Bedrock at $X cost. Operator-acknowledged risk; cost discipline preserved.
- **Plugin port cost:** zero Bedrock cost during Phase 14. Plugin scaffold + 6 shims is all file-IO work; the integration check (SC#4 smoke transcript) was deferred and didn't happen, so no actual Claude Code session cost landed either.

---

## Milestone: v1.7 — graph-io Integration & Wiki Hygiene

**Shipped:** 2026-05-26
**Phases:** 7 (35-41) | **Plans:** 10 | **Tasks:** 25

> Note: v1.3-v1.6 retrospective entries are not present in this file (rapid-fire shipping pace from v1.3 onward outpaced retrospective backfill); cross-milestone trends below also skip those rows. Each shipped milestone has its own archived ROADMAP/REQUIREMENTS/AUDIT under `milestones/` as the authoritative record. Add v1.3-v1.6 entries here later if the cross-milestone view is needed.

### What Was Built
- **Librarian Grounding Tools** — 5 closure-bound `@tool` callables wrap `graph_io.queries`; one read-only conn shared via factory, closed in `finally`; CountTokens budget gate; vault-thin graceful degradation when graph missing.
- **`graph-wiki-agent graph` subcommand** — first-class `build`/`describe`/`query` on agent CLI + 3 parallel MCP tools registered alongside `wiki_*`.
- **Scanner ↔ graph-io** — `run_scan` dispatches `cg update` before fan-out; workspaces decorated with `pkg["uri"]` + `pkg["domain"]`; strict NOT_INITIALIZED error with filesystem fallback.
- **Ingestor ↔ graph-io** — entity URIs from graph drive routing decisions; missing graph hard-fails with exit code 3 (no silent drift).
- **`cg find` named-flag UX** — `--name`/`--kind`/`--in-package` replace positional form, with anti-regression guard.
- **Wiki & Bootstrap Hygiene** — 10 deferred quick-tasks + 2 bootstrap todos closed; self-healing `uv` re-exec; `--interactive` flag; testing.md scaffold.
- **Tech debt closeout (Phase 41)** — canonical `INTEGRATION_GATE` restored on scan-e2e test; 20 REQUIREMENTS.md checkboxes + 20 traceability rows synced; v1.6-era `sample_monorepo` fixture allowlisted.

### What Worked
- **Pattern-mapper agent** (introduced in plan-phase pipeline) caught the "24-vs-20" CONTEXT.md count discrepancy during Phase 41 planning by trusting explicit ID enumeration over narrative count labels — saved a wrong-output execution.
- **Worktree isolation** for executor agents held up cleanly on a 2-file tech-debt phase (Phase 41) — atomic per-task commits, clean merge, no `.git/config.lock` contention.
- **Integration checker WIRED verdicts as evidence** — Phase 41 D-08 formalized that the 3-source cross-reference (SUMMARY frontmatter + automated suite + integration-checker output) is sufficient for code-only phases; this freed Phases 39/40 from retro-UAT churn.
- **Audit-first close-out cadence** — milestone audit ran BEFORE complete-milestone, surfaced the integration-gate blocker and traceability-sync gap, → Phase 41 was scoped to close both, → re-audit confirmed `passed`. Clean two-step rather than ad-hoc.

### What Was Inefficient
- **SDK audit-open / CJS audit-open divergence** — SDK looks for bare `SUMMARY.md`; the project uses `{quick-id}-SUMMARY.md`. Required 10 symlinks to make the pre-flight audit pass for milestone close. Should be reconciled in the SDK (or the CJS implementation merged into the dist).
- **CONTEXT.md count-label vs ID-list contradictions** — Phase 41 CONTEXT.md said "24 checkboxes" but listed 20 IDs (HYGIENE-14 + CGFIND-3 + INGESTOR-3). The planner caught it, but a tighter discuss-phase validation could catch count/list mismatches up front.
- **Plan-checker "24" warnings landed in two passes** — the first revision fixed three "24"s, then a second pass found four more elsewhere. Plan-checker should sweep the entire plan for the flagged literal, not just the cited locations.

### Patterns Established
- **D-NN citation in plan frontmatter `decisions_addressed:` block** — Phase 41 introduced this for decision-coverage-gate. Cleaner than scattered prose D-NN mentions; verifiable; future plans should adopt.
- **Scope-expansion-with-rationale commits** — Phase 41's `c02f8e6` documented why crossing CONTEXT.md D-01 scope was correct (fixture file ≠ real integration test → D-04's marker prohibition doesn't apply). Good template for future user-approved scope expansions during execution.
- **Two-step milestone close** — `/gsd-audit-milestone` then a remediation phase if needed (Phase 41 pattern) then `/gsd-complete-milestone`. Avoids closing on known tech debt.

### Key Lessons
- **Trust explicit enumerations over count labels.** When CONTEXT.md says "N" and lists items, the list is ground truth — pin acceptance criteria to grep-counts of the list, not narrative N.
- **Worktree mode shields shared files.** Executor agents in worktrees can't accidentally clobber STATE.md/ROADMAP.md — those writes happen in the orchestrator after merge.
- **Audit-tool drift compounds silently.** The audit-open SDK regression went unnoticed for several quick-tasks because each individual task was fine; only at milestone close did the false-positive count add up. A simple `gsd-tools audit-open` sanity check after each quick task would catch it earlier.

### Cost Observations
- **Model mix:** Opus 4.7 for orchestrator + planner; Sonnet 4.6 for researcher / executor / verifier / plan-checker / integration-checker.
- **Sessions:** intense single-day execution — v1.7 (35→41) shipped 2026-05-26, building on v1.6 which also shipped 2026-05-26. Two complete milestones in one calendar day.
- **Notable:** Pattern-mapper agent on Phase 41 ran in ~70s and produced a tight 2-file PATTERNS.md — the analog (`test_bedrock_iam.py`) was already named in CONTEXT.md, so the mapper mostly confirmed and provided code excerpts. Low-cost but added measurable value (the verbatim INTEGRATION_GATE block landed in the executor's read-path without ambiguity).

---

## Milestone: v1.8 — Wiki Entity Restructure

**Shipped:** 2026-05-27
**Phases:** 7 (42-48) | **Plans:** 20 | **Tasks:** 14

### What Was Built
- **URI-keyed `/entities/` lane.** Flat folder, one page per admitted graph node, URI-derived slug (`pkg:agent-research/graph-io` → `pkg__agent-research__graph-io.md`). Seven per-kind templates (repository / domain / package / package-family / plugin / dependency / test-suite) with a reserved `## Narrative` H2. `ADMITTED_KINDS` + `SCANNER_OWNED_KEYS` frozensets in `entity_writer.py` are the single contract surface. `package_family` admitted in source but narrowed to `ADMITTED_KINDS - {"package_family"}` for v1.8 (no real package family to render yet).
- **`write_entities()` — single deterministic create / merge / hard-delete pipeline.** Acquires `.graph-wiki/scan.lock` (non-blocking `flock`), per-kind sweep, byte-stable write-if-changed, partial-failure isolation. Returns `EntityWriteResult(created, updated, deleted, needs_narrative)`. Hard-deletes append-logged to `.graph-wiki/deletions.log` (JSONL with `body_was_empty` flag, 10MB two-file rotation).
- **`generate_index()` — domain-first scanner-generated index.** `wiki/index.md` produced from graph queries directly. Single-placement rule (entities under their qualifying domain iff exactly one, else by-kind). Consolidated curated-lane sections (architecture, ADRs, concepts, sources, work). Determinism verified by permuted-insertion test; write-if-changed via `os.replace`.
- **`run_scan` integration end-to-end.** Steps 9a (entity writer) → 9b (LLM narrator over `needs_narrative` only) → 10 (`inject_narrative` writes prose into `## Narrative` only) → 11 (hard-delete) → 12 (index regen). Eight integration tests verify the call graph, gating, and frontmatter integrity. Plugin smoke test untouched.
- **`migrate-vault` — one-shot atomic cutover.** Markdown-aware tokenizer (CommonMark fenced + indented code blocks excluded, inline-code excluded, alias-preserving). Built rewrite table from graph; live cutover produced a single commit on the external vault repo: 47 entity pages populated, 122 wikilinks rewritten, legacy `wiki/packages/` + `wiki/dependencies/` removed, `wiki/index.md` regenerated, `.graph-wiki/manifest.json#migrated_to` set. Second run no-op via the manifest marker.
- **Domain inference layer.** `cg domain-clusters` produces deterministic connected-component clusters with hub-node exclusion (>50% reverse-deps elided then re-attached) and degenerate-cluster warnings. `graph-wiki-agent graph propose-domains` consumes clusters, fans out to a Bedrock LLM via the new `domain-proposer` role, validates every proposed package name against `graph_io.queries.list_packages`, strips cycle-introducing `domain_contains_domain` edges, writes `domains.proposed.yaml` — never `domains.yaml`. Per-call cost in `.graph-wiki/traces/` per v1.7 schema.

### What Worked
- **Design-lock Phase 42 before any entity code ran.** Slug encoding + scanner-owned frontmatter whitelist locked as `frozenset` constants in `entity_writer.py` with property-tested injectivity (1,000 URIs across all 7 kinds, zero collisions) BEFORE any caller existed. Every downstream phase imported the same constants; no drift.
- **Pitfall guards encoded in plan acceptance criteria, not narrative.** Each of the 10 pre-identified pitfalls (slug collision, frontmatter merge, hard-delete losing edits, migration regex over-match, index churn, degenerate clusters, LLM hallucination, auto-apply leak, concurrent scan race, migration re-run artifact) landed as a specific test in a specific plan. Pitfall 1's property test, Pitfall 4's code-block exclusion test, and Pitfall 9's `LOCK_NB` fast-fail timing assertion all caught real bugs that would have shipped otherwise.
- **Cutover as a single git commit on the vault repo, not the source repo.** Fix `9e803fe` ("run git ops against vault workspace, not source code repo") landed mid-Phase-46 — the bug was that the migrator was opening the agent-research git repo by accident. Catching this before the live cutover meant the actual cutover commit (`35e88af` in the vault) was clean, atomic, and reversible by a single `git revert` in the vault. Operator could review the diff cold.
- **`needs_narrative` as the LLM gate.** `EntityWriteResult.needs_narrative` is the only thing the scanner fan-out reads to decide whether to spend LLM tokens. New entity pages and structurally-changed pages get narrative; everything else skips the LLM call entirely. Cost discipline is structural, not a per-call check.
- **Parallel tracks 47+48 against the wiki-restructure 42-46 chain.** `cg domain-clusters` (Phase 47) and `graph propose-domains` (Phase 48) touched only `graph-io/` and `commands/graph.py` — designed to be cancelable from v1.8 with zero rework. Worked: they shipped in the same milestone with no integration friction against the 42-46 cutover.

### What Was Inefficient
- **Three Phase 48 SUMMARY one-liners are deviation reports, not accomplishments.** "[Rule 1 — missing critical] make_llm did not accept model_override", "[Rule 2 — claude-discretion] Used 13 tests instead of exactly 10.", "[Rule 1 — missing critical] propose_domains_cmd path resolution was wrong." Useful per-plan postmortem signal, but they pollute `gsd-sdk query summary-extract` output at milestone close — the CLI hands them straight into MILESTONES.md as "Key accomplishments". Either the executor should emit two fields (`deviations:` and `accomplishment:`) or `summary-extract --fields one_liner` should prefer the latter.
- **Phase 46 UAT.md untracked at close.** UAT testing for Phase 46 was done live during the session but the `46-UAT.md` file stayed `status: testing` and untracked in git until the milestone close itself flushed it. Per-phase UAT files should commit on session end, not roll up.
- **No `/gsd:audit-milestone` for v1.8.** Acknowledged at close — same pattern as v1.6. Pattern is now established: rapid-ship milestones skip formal audit. Either institutionalize "no audit for ≤8-phase milestones" or invest in a lighter audit shape. Same applies to per-phase security review (`workflow.security_enforcement=true` but 7/7 phases shipped without `*-SECURITY.md`).
- **`44-01-SUMMARY.md` and `44-02-SUMMARY.md` return `null` from `summary-extract --fields one_liner`** — same schema-enforcement gap flagged in v1.0/v1.1/v1.2. Six milestones running. The one_liner schema enforcement at write-time is overdue.

### Patterns Established
- **`frozenset` constants in the consumer module as the design-lock surface.** `ADMITTED_KINDS` + `SCANNER_OWNED_KEYS` in `entity_writer.py` are imported by every downstream module that touches entity identity. Property test guards injectivity. The two constants ARE the contract; renaming or expanding them is a deliberate code change with a code-review-visible diff.
- **`EntityWriteResult.needs_narrative` as a structural LLM gate.** Returning a set of "things that need an LLM call" from the cheap pipeline and consuming it in the expensive pipeline is cleaner than a per-item "should I LLM?" predicate scattered across the scanner. Reusable pattern for any pipeline with a `cheap → maybe-expensive` shape.
- **Markdown-aware rewriters use CommonMark-tokenized excludes.** `link_rewriter.py` excluded fenced code, indented code (with the helper `indented_code_spans`), and inline code from the rewrite table application — but applied to wikilink and reference-style link tokens specifically. Pattern recipe for any future Markdown text-transform.
- **Dry-run preview as the cutover safety net.** `migrate-vault --dry-run` rendered a human-readable preview (sections: Entities / Wikilink rewrites / Unresolvable / Directories to remove / Idempotency marker note) that operator reviewed cold before the live cutover. The live cutover then matched the preview exactly. Pattern for any one-shot destructive operation: dry-run first, byte-identical preview.
- **Proposals land in a parallel artifact, never the authoritative one.** `domains.proposed.yaml` is consumed by `cg list-domains` as zero-effect (proven by Phase 48 isolation test). `domains.yaml` remains authored. Pattern reusable for any LLM-proposed config: proposal lives next to the authoritative file with an explicit `proposed_` prefix and a CI-grade isolation test.

### Key Lessons
- **Lock the contract in code before the consumer exists.** Phase 42 shipped `frozenset` constants + a property test before any caller. Every subsequent phase imported them. No drift, no parallel definitions, no quiet semantic changes. This is the cheapest way to prevent the "wait, what's the canonical list?" question that costs days mid-implementation.
- **Pitfall lists are only useful if each pitfall has a named test.** Pitfalls 1-10 were known going in, but the ones that mattered (1, 4, 9) were the ones that landed in plan acceptance criteria as specific tests. Pitfalls without an owning test are an aspirational TODO.
- **Atomic git commits on the destination repo are the cutover unit.** Live cutover succeeded because it was a single commit on the vault repo, reviewable cold by operator, revertible by `git revert`. The bug that almost shipped (running git ops against the source repo) was caught only because the operator looked at the dry-run preview against the wrong repo. Dry-run + correct-destination + atomic-commit is the irreducible cutover shape.
- **MILESTONES.md "Key accomplishments" extraction quality is a SUMMARY.md schema problem.** Three milestones (v1.6 and v1.8 most recently) have shipped with deviation-report one-liners or `null`s flowing into the archive. The one_liner field needs a write-time schema check — `accomplishment:` distinct from `deviation:`, both required, neither nullable.

### Cost Observations
- **Model mix:** Opus 4.7 for orchestrator + planner + research; Sonnet 4.6 for executor / verifier / code-review / pattern-mapper. New `domain-proposer` role added to `models.toml` for Phase 48 (LLM-driven domain inference fan-out); per-call cost recorded in `.graph-wiki/traces/`.
- **Sessions:** dense ~1 calendar day for the bulk of execution (2026-05-27); Phase 42 design-lock landed earlier on 2026-05-26 as a separate session. 7 phases / 20 plans / 14 days end-to-end (2026-05-13 → 2026-05-27 in the git range, but actual execution clustered in the final 2 days).
- **Notable:** the live `migrate-vault` cutover ran the `--dry-run` and the actual run with byte-identical entity count + rewrite count — meaning operator's pre-cutover review was authoritative. Zero post-cutover patches needed.
- **Trace data:** Phase 48 was the first phase to consume the new `domain-proposer` Bedrock role end-to-end; per-LLM-call cost discipline carried through.

---

## Milestone: v1.9 — Graph Refinements & Wiki Filename Slimdown

**Shipped:** 2026-05-28
**Phases:** 5 (49-53) | **Plans:** 15 | **Tasks:** 25

### What Was Built
- **`builtin` graph kind (Phase 49).** Python + Node stdlib imports admitted as first-class `Builtin` nodes (`builtin:<lang>/<module>`, `language` + `module_name` attrs, `used_by` edges only, no `requires`/`imports`), kept out of the dependency/symbol pool and excluded from wiki rendering. `cg list-builtins` / `cg describe-builtin` surfaces.
- **`package` → `app` reclassification (Phase 50).** Manifest-signal classifier (`[project.scripts]`, `package.json bin`, `next`/`expo` deps, vite+`index.html`) promotes packages to a distinct `App` graph kind with `app_kind` (cli/nextjs/expo/spa); documented precedence on multi-match, no false-positive reclassification, URI form preserved (`pkg:` → `app:`) so inbound references survive. `cg list-apps` / `cg describe-app`.
- **`package-family` ripped out (Phase 51).** Kind removed from `_VALID_KINDS`, `package_family_uri` builder deleted, template + `wiki/package-family/` gone, the v1.8 `ADMITTED_KINDS - {"package_family"}` narrow simplified to the final frozenset, CLI subcommands removed. LIB-003 `_SLUG_ONLY_RE` / `_check_no_slug_only_wikilinks` divergence rule + eval baseline retired.
- **Short entity filenames — core (Phase 52).** `short_filename(uri, collision_set, ...)` pure helper: `<kind>_<name>.md` with a deterministic hash suffix only on the collider, plus framework-aware `unit_tests_<pkg>.md` / `int_tests_<pkg>.md`. Property-tested for idempotence + collision-resistance. Left a deliberate transitional state (5 long-form call sites in `index_generator.py` + 1 in `link_rewriter.py`).
- **Filename cutover (Phase 53).** Dead `encode_slug` / `decode_slug` / `_ADMITTED_URI_PREFIXES` removed; every consumer (`link_rewriter.py`, `index_generator.py`, `commands/scan.py`) derives filenames via `short_filename` and reads URIs back via `frontmatter.uri`. Verified by a from-scratch exploratory-vault regen (UAT, short-form filenames only) and a 13/13 threat-secure audit.

### What Worked
- **Transitional-state-then-cutover across two phases.** Phase 52 landed `short_filename` and switched `write_entities` to short form while *leaving the 6 long-form call sites in place* — the suite stayed green the whole time. Phase 53 then closed those call sites and deleted the dead machinery as a clean, isolated breaking change. Introducing the new path before removing the old one kept every intermediate commit shippable.
- **Pure function + property test before consumers (again).** `short_filename(uri, collision_set)` shipped with idempotence + collision-resistance property tests before the index/rewrite/scan consumers were rewritten — same design-lock pattern that worked for v1.8's `frozenset` contracts. Reverse lookup via `frontmatter.uri` eliminated the entire bidirectional-slug round-trip surface rather than maintaining a `decode_slug`.
- **Hard dependency ordering held.** 49 (builtin) → 50 (app) → 51 (package-family removal, so `ADMITTED_KINDS` is clean) → 52 (short filenames on the clean kind set) → 53 (cutover). Each phase depended on the prior's graph-kind surface being final; sequencing prevented churn.
- **Phase 53 got the full quality gate.** UAT (3/3, manual vault regen) + security audit (13/13 threats closed) + verification (20/20 must-haves) — the cutover phase, the one with real breaking-change risk, was the most thoroughly verified.

### What Was Inefficient
- **Phase 50 shipped with no `VERIFICATION.md`.** It was executed (3 plan summaries) and its APP-01..06 requirements were marked Complete, but the verification gate never ran — the only v1.9 phase missing a verification artifact, and ironically the phase the working branch was named for. Caught only at milestone close. The per-phase verification step is not enforced; a phase can complete execution and have requirements flipped without producing the artifact.
- **MILESTONES.md one-liner extraction pulled deviation-report headings AGAIN.** `summary-extract --fields one_liner` handed `"1. [Rule 3 - Circular Import] Broke import_scan dependency..."` and `` "`BuiltinDescription` dataclass" `` straight into the v1.9 archive as "Key accomplishments" — same root cause flagged in v1.0/v1.1/v1.2/v1.6/v1.8. Hand-rewritten at close. **Sixth-plus milestone with this exact issue.** The `one_liner:` write-time schema check (`accomplishment:` distinct from `deviation:`, both required) is now badly overdue.
- **Traceability table never flipped by phase verification.** 14 of 24 requirement rows (BUILTIN, PKGFAM, CLEANUP, WIKI-FN-05/06) read `Pending` at milestone close despite their phases verifying `passed` — one SUMMARY explicitly noted "table left untouched... until phase verification flips it," and nothing ever flipped it. Same schema-gate gap as the one_liner issue, different field. Hand-corrected at close.
- **No `/gsd:audit-milestone`.** Skipped again — now the established pattern for v1.6 / v1.8 / v1.9. Either institutionalize "no formal audit for ≤8-phase milestones" or build a lighter audit shape; pretending it's a one-off is no longer honest.

### Patterns Established
- **Introduce-then-cutover for breaking refactors.** Land the new code path and switch the primary producer to it while leaving consumers on the old path (suite green); close the consumers + delete the dead code in a separate, isolated phase. Keeps every intermediate commit shippable and makes the breaking diff reviewable on its own.
- **Reverse-lookup via stored identity beats a decode function.** Reading `frontmatter.uri` off the entity page eliminated `decode_slug` and the whole bidirectional round-trip surface. When forward derivation is a pure function and the identity is persisted, you never need the inverse.
- **Reserve the heaviest quality gate for the cutover phase.** The phase that removes/breaks (53), not the phase that adds (52), is where UAT + security + verification concentrate.

### Key Lessons
- **A phase can "complete" without verifying — the gate isn't enforced.** Phase 50 reached Complete with requirements flipped and no `VERIFICATION.md`. Until `/gsd:execute-phase` (or transition) hard-requires the verification artifact before marking a phase done, milestone close is the catch-net — too late and reliant on the operator noticing.
- **Schema-field staleness (one_liner + traceability) is one problem with two faces.** Both the deviation-report one-liners and the never-flipped `Pending` rows are write-time-enforcement gaps that surface as manual cleanup at close. The fix is the same: a per-phase gate that validates/updates the field before the SUMMARY commit. Flagged for six milestones running.
- **Shipping the whole milestone as one fast-forward PR works when the branch is linear.** v1.9's entire 117-commit line lived on a single branch (`phase/50-...`) ahead of a stale `main`; the close merged it as a clean FF via PR #1. Fine here, but it means "ship a phase" and "ship the milestone" collapsed into one merge — there was no per-phase PR cadence.

### Cost Observations
- **Model mix:** Opus for orchestrator / planner / research; Sonnet for executor / verifier / code-review / security-auditor / plan-checker. No new `models.toml` roles this milestone.
- **Sessions:** execution clustered over ~2 calendar days (2026-05-27 → 2026-05-28); 5 phases / 15 plans / 25 tasks.
- **Notable:** first milestone to ship through an actual GitHub PR + merge to `main` (PR #1) rather than living on a working branch — `main` had been 121 commits / 5 phases behind. The Phase 53 vault-regen UAT was idempotent (`+0 ~0 -1`), confirming Phase 52's `write_entities` had already produced short-form on-disk entities.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~12 | 5 | Established `cores/` + `agents/` workspace pattern; SubagentPool as shared infra; eval harness with two-judge Bedrock panel |
| v1.1 | dense ~3 days | 5 | Prompt-as-Python-module with provenance comments; two-gate sweep scoring; schema-versioned trace JSONL with lenient consumer; render-once context injection; gap-closure plan pattern |
| v1.2 | dense ~3 days | 6 | Spec-only phase pattern (M3a → M3b); body-diff-then-verdict pattern for cross-codebase merge; grep-gate enforcement for brand/style rules; 2-line delegation shim across package boundaries; `TaskResult` wrapper for usage_metadata in fan-out callbacks; event-driven deferrals over calendar-driven |
| … | | | _(v1.3–v1.8 rows not back-filled — see each milestone's section above)_ |
| v1.9 | dense ~2 days | 5 | Introduce-then-cutover for breaking refactors (Phase 52 lands new path, 53 removes old); pure-function-+-property-test-before-consumers (again); reverse-lookup via stored `frontmatter.uri` instead of a decode function; first milestone shipped via real GitHub PR + FF merge to `main` (PR #1). Recurring debt re-confirmed: one_liner extraction + traceability flips still not write-time-enforced; milestone audit skipped; a phase (50) reached Complete with no VERIFICATION.md |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 359 pytest files across workspace | per-member (each member's own testpaths) | `bm25s`, `python-frontmatter`, `deepeval`, `typer`, `langchain-aws`, `mcp` |
| v1.1 | +divergence eval (37 tests), prompt snapshots (14 baselines, 26 tests), token budget (6 tests), trace renderer (~20 tests across 09-01..09-06), MCP cancel (1 stub-LLM test), DA-CLI E2E (1 subprocess test covering 6 tools) | per-member | (none — v1.1 was content-and-quality work, no new top-level deps) |
| v1.2 | +workspace-io tests (67 ported + 2 new for D-03/D-14 divergences), trace_io extraction tests, ingest/query trace coverage tests, code_reader/synthesizer DivergenceMetric rubric tests, scanner regression tests, brand-gate test (`scripts/check-brand.sh`), integration-gate convention tests | per-member; new top-level `packages/workspace-io` member | (none — v1.2 was port + rebrand + debt cleanup, all on existing deps) |

### Top Lessons (Verified Across Milestones)

1. **Schema files (REQUIREMENTS.md, traceability tables) need per-phase gate enforcement, not milestone-close cleanup.** v1.0 flagged it. v1.1 hit it. v1.2 hit it. Now classified as a tooling problem, not a discipline problem — fix must ship as GSD tooling work in v1.3, with a per-phase completion gate in `/gsd:execute-phase` that flips REQ-IDs before the SUMMARY.md commit.
2. **`one_liner:` belongs in every SUMMARY.md as a required, parseable field.** v1.0: nulls. v1.1: wrong-line matches. v1.2: 9/13 auto-extracted accomplishments unusable. Same root cause, third milestone. Schema enforcement at write-time is the only fix that scales.
3. **Phase ordering with hard constraints holds under pressure.** v1.0: `SubagentPool` before fan-out commands. v1.1: prompt port before cost-frontier sweep. v1.2: workspace-io port before rebrand before plugin contract before plugin port before wiki self-update. In every case the sequencing felt slow at the time but produced the correct foundation.
4. **Structured trace output from day 1 keeps compounding.** v1.0 shipped the JSONL format; v1.1's cost-frontier sweep + trace renderer + schema versioning sit on top of it; v1.2's TRACE-FU-01 closure (TaskResult contract) means cost rollups are now accurate, not lying by omission. Front-load observability schema decisions.
5. **Cap phase plan count at ~6 (and split when it grows).** v1.0 Phase 3 hit 9. v1.1 Phase 6 hit 16 (5 gap-closure). v1.2 mostly held the cap: largest was Phase 11 at 6 plans, with Phases 14/16 each hitting 3 plans but containing 800+ LOC of bundled work. The 3-plan-bundling-too-much pattern is a new shape worth watching.
6. **Bedrock-only single-provider focus was correct.** Three milestones validated it. v1.2 Phase 15 (wiki self-update via a one-off Claude role-override profile) was a controlled exception that validated brand on a separate model lineup; the Bedrock production defaults stayed pinned.
7. **Spec-only phases pay off when the contract surface has open questions.** v1.2 Phase 13 (M3a → M3b split) caught a foundational reframe (plugin runs on Claude Code inference, NOT a `graph-wiki-agent` wrapper) before any code moved. Same shape would have helped v1.1 Phase 6 (prompt port) had it been split into a spec-then-port pair.
8. **Grep-gates are how "must not contain X" rules survive.** v1.2 BRAND-04 shipped `scripts/check-brand.sh` + `.brand-grep-allow` as a pytest gate. Brand discipline now lives in CI. The pattern generalizes to any code-style rule that's verifiable by `grep -rE`.
9. **Event-driven deferrals beat calendar-driven deferrals.** v1.2 Phase 16 D-09 replaced "re-evaluate by date X" with "re-evaluate when langchain-aws#663 merges OR aioboto3 GA/1.0 lands". Anchored signal; no scheduled toil; the next re-evaluation will have new information.
