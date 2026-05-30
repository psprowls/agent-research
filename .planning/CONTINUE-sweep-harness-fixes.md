# CONTINUE: sweep harness fixes + clean re-run (handoff 2026-05-29)

Self-contained continuation note so a fresh context can finish the cost-frontier
sweep work without re-deriving anything. Created at a clean checkpoint: working
tree clean, full suite green (**1580 passed, 0 failed**, `uv run pytest -q`).

## How to resume
After `/clear`, say: **"continue the sweep harness fixes per `.planning/CONTINUE-sweep-harness-fixes.md`"**.
Route every code change through `/gsd-quick` (project GSD enforcement). The working
tree is clean — keep it that way before spawning any executor (see Gotchas).

## Background / what already happened
A new cost-frontier sweep was set up and run on AWS Bedrock for the 6 in-scope
graph-wiki-agent roles. Sequence of completed quick tasks (all committed on `main`):
- **260529-na9** — refreshed `models.toml`: Haiku default `us.`→`global.` profile everywhere; six new bespoke `sweep_candidates` lists (6/8/6/7/6/6 = 39 cells); judges re-pinned (judge_a=`mistral.mistral-large-3-675b-instruct`, judge_b=`us.amazon.nova-pro-v1:0`, Sonnet dropped to remove Claude self-preference); qwen3-32b price reconciled to 0.15/0.60.
- **260529-ox1** — `EvalWorktree` now provisions an empty schema-valid graph-io DB per worktree (`graph_io.store.connect(graph_dir(wt.path)/"code.db", create=True)`), unblocking ingestor cells.
- **260529-pf8** — updated 14 stale config-pinning tests (Haiku ARN→global, qwen3 cost→$0.75, retired the D-03 tier-locked sweep tests → structural invariants). Suite green.
- `bedrock-models-considering.json` deleted (scratch input, no longer needed).

### First live run results (PRELIMINARY — do not trust/commit as-is)
Total $2.95. **librarian + synthesizer are clean → `qwen.qwen3-next-80b-a3b` wins both**
(quality 1.00 at lowest cost; qwen3-32b close behind). The other 4 roles were not
trustworthy because of the two harness bugs fixed below + structural-only scoring.
The `.planning/sweep/*.md` docs are currently the OLD 2026-05-17 baseline (the
preliminary run was not committed) — the clean re-run (step 3) regenerates them.

## REMAINING WORK — do these in order

### Fix B — content-normalizer in model-adapter  (todo: `.planning/todos/deferred/2026-05-29-model-adapter-normalize-thinking-model-content.md`)
**DECISION LOCKED: option (a) — preserve reasoning blocks, don't drop them.**
- Problem: models returning list-shaped (multi-block) `response.content` break str-assuming
  consumers. Confirmed failures: synthesizer = {`us.deepseek.r1-v1:0`, `moonshot.kimi-k2-thinking`}
  (`expected string or bytes-like object, got 'list'`); ingestor = {`openai.gpt-oss-120b-1:0`,
  `minimax.minimax-m2.5`} (`'list' object has no attribute 'strip'`). Trigger is content SHAPE,
  not model class — gpt-oss/minimax are not reasoning models.
- Fix in `packages/model-adapter/src/model_adapter/loader.py` → `_GuardedChatBedrockConverse`
  (class ~line 78; currently wraps only `invoke` ~line 92). When `response.content` is a list of
  blocks, normalize `.content` to a string by concatenating the text-type blocks
  (`block["type"]=="text"` / `block["text"]`); **preserve** the reasoning/thinking blocks on
  `response.additional_kwargs["reasoning"]` (option a). Key off content SHAPE, never model ID.
  Must cover BOTH `invoke` AND `ainvoke` (the agent/sweep use the async path) — extend the
  AccessDenied guard to `ainvoke` while in here if not already.
- Tests: feed a fake list-shaped `AIMessage.content` through the wrapper (sync + async); assert
  `.content` is the concatenated string and `additional_kwargs["reasoning"]` holds the dropped
  blocks. Offline only.
- Verify: `uv run pytest -q` stays green.

### Fix C — Gate-1 divergence wiring in sweep.py  (todo: `.planning/todos/deferred/2026-05-29-sweep-gate1-divergence-never-wired-in-run-full-matrix.md`)
- Problem: `run_full_matrix` (`packages/eval-harness/src/eval_harness/sweep.py` ~line 872) calls
  `score_two_gate(..., divergence_metric_or_none=None, baselines_dir=None)` hardcoded →
  `two_gate.py:103-105` sets `gate1_passed=False` for every divergence-eligible candidate. That's
  why the first run showed `gate1=FAIL` / `qualified=NO` for everything.
- Fix: for each role in `ROLES_WITH_DIVERGENCE`, construct the divergence metric via
  `eval_harness.divergence.metric.load_baseline(...)` against `eval/baselines/divergence-{role}.json`
  and pass it (+ a real `baselines_dir`) into `score_two_gate`. Mirror how the standalone
  divergence tests build the metric (`divergence/check.py`, `divergence/metric.py`, per-role modules).
  Confirm D-08 roles (no rubric) still pass `None` → `gate1_passed=None` (not False); fix the
  distinction in `score_two_gate` if it conflates "no rubric" with "metric missing".
- Confirm the `divergence-{role}.json` baselines exist for all 6 roles; if missing, (re)record via
  the `--accept-divergence-baseline` conftest option or gate that role.
- Verify (smoke test): re-running the matrix should show the incumbent (global Haiku / current
  default) PASS Gate 1 for at least the quality-tier roles. Suite stays green.
- Related lower-priority anomalies noted in the todo (scanner/linter quality=0.000 no discrimination;
  code_reader cost=N/A for 5/6; code_reader.md frontier renders quality=0.00) — confirm/triage after
  Gate 1 works; may be separate follow-ups, not blockers for the re-run.

### Step 3 — clean full live re-run (PRE-APPROVED spend, ~$3–4, hard cap $25)
- Driver pattern (the throwaway `/tmp/sweep_driver.py` from this session may be gone after clear —
  recreate it). It must:
  - `role_candidates = {r: list(load_role_config(r)["sweep_candidates"]) for r in
    ["librarian","synthesizer","code_reader","scanner","linter","ingestor"]}`
  - workspace = a tmp dir with `wiki/` symlinked to
    `packages/wiki-io/tests/fixtures/round-trip-vault` (the fixture the eval baselines are tuned to)
  - `query_cases_path = eval/cases/query_cases.json`; `code_reader_cases_path = eval/cases/code_reader_cases.json`;
    `ingestor_source_path = FIXTURE_VAULT/README.md` or `next(FIXTURE_VAULT.glob("*.md"))`
  - `run_full_matrix(..., repeats=3, output_dir=Path(".planning/sweep"), dry_run=False,
    skip_bed01=False, auto_confirm=True)`
  - env: `GRAPH_WIKI_RUN_EVAL=1 GRAPH_WIKI_RUN_JUDGES=1 AWS_REGION=us-east-1`, run via
    `uv run --package eval-harness python <driver>`; run in background, log to `.planning/sweep/`
    (logs are gitignored).
- Pre-flight: `estimate_sweep_cost` with n_cases=6, repeats=3 (≈$3.83 before any token-volume reality).
  BED-01 ping confirms live Bedrock (AWS account 210412004691 is enabled; region us-east-1).
- After it completes: verify Gate-1 now discriminates (incumbents pass), thinking/ingestor models
  now produce data (Fix B), capture total cost + ALL-ERROR list, then **commit** the regenerated
  `.planning/sweep/*.md` + `INDEX.md` as the authoritative 2026-05-29 run. Then help Pat pick
  per-role winners and (if he wants) hand-edit `models.toml` defaults from the Pareto frontiers
  (humans pick; no auto-rewrite — see `wiki/concepts/cost-frontier-sweep`).

## Gotchas (carry forward)
- **gsd-executor `git stash` can silently revert uncommitted working-tree changes** (it lost an
  uncommitted edit + reverted regenerated docs this session). Always commit/stash-protect before
  spawning an executor; recover via `git fsck --no-reflogs --unreachable | grep commit` → `WIP on main:`.
  (Also saved as a memory.)
- Executors may not commit `uv.lock` alongside `pyproject.toml` dep changes — verify & commit it.
- `/gsd-quick` pattern used this session: `gsd-sdk query init.quick "<desc>"` → mkdir task_dir →
  spawn `gsd-planner` (opus) with a precise spec → commit PLAN.md → spawn `gsd-executor` (sonnet,
  NON-worktree for single-plan tasks) → update STATE.md "Quick Tasks Completed" + last-activity →
  commit SUMMARY.md + STATE.md. branch_name has been null (commits go on `main`).
- All commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Wiki concept refs (read-only background): `cost-frontier-sweep`, `agent-role-taxonomy`, the six
  `*-agent-anatomy` pages, `eval-judge-panel-design`, `divergence-eval-framework` (in
  `/Users/pat/Personal/graph-wiki/agent-research-backup/wiki/concepts/`).
