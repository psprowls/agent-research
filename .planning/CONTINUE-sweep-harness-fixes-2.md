# CONTINUE: sweep harness fixes round 2 — verify D/E/F, then full re-run (handoff 2026-05-29)

Self-contained continuation note. Supersedes `CONTINUE-sweep-harness-fixes.md`
(that note's Fixes B + C are DONE). Working tree is clean; full suite green
(**1593 passed**, `uv run pytest -q`).

## How to resume
After `/clear`, say: **"continue the sweep harness fixes per `.planning/CONTINUE-sweep-harness-fixes-2.md`"**.
Route every code change through `/gsd-quick`. Keep the tree clean before spawning
any executor (the executor's git ops can revert uncommitted edits — commit first).

## What happened this session (all committed on `main`)
The first clean live re-run (the old note's "Step 3") was run and **cost $7.02**.
It surfaced TWO MORE harness bugs beyond B/C, plus confirmed two anomalies. All
five fixes are now landed:

- **Fix B** (quick `260529-pzd`, commit `02ee3fe`) — model-adapter `_GuardedChatBedrockConverse`
  normalizes list-shaped ("thinking"/multi-block) `response.content` → str, preserving
  reasoning blocks on `additional_kwargs["reasoning"]`. Covers `invoke` + `ainvoke`.
- **Fix C** (quick `260529-q8r`, commit `43c9dd6`) — wired per-role `DivergenceMetric` +
  `baselines_dir` into `run_full_matrix` (was hardcoded `None` → Gate 1 auto-FAIL).
- **Diagnostic run** (commit `8cf091a`) — committed the $7.02 run's docs to `.planning/sweep/`
  but labeled **NOT authoritative** (broken Gate 1 + 4 missing models). To be overwritten by
  the clean re-run.
- **Fix D** (quick `260529-sot`, commit `07c709f`) — the real reason Fix B didn't help the sweep:
  all **6 model-override branches** (query.py code_reader/librarian/synthesizer, ingest.py,
  lint.py, scan.py narrator) constructed a RAW `ChatBedrockConverse`, bypassing the guard +
  normalizer. Now all route through `make_llm(role, model_override=...)`.
- **Fix E** (quick `260529-sot`, commit `3dfeae9`) — `divergence.metric.check_regression` compared
  ABSOLUTE failure counts; baselines were recorded at runs=4 but the sweep runs at runs=12 → every
  incumbent auto-FAILed. Now compares **rates** (failures/runs). Also `two_gate.score_two_gate` now
  disqualifies zero-output candidates (gate1=None → qualified=False) instead of falsely passing them.
- **Fix F** (quick `260529-sot`, commit `e9cd8b1`) — `SweepResult.judge_scores` was never assigned,
  so the rendered `quality_mean` was a `has_citation` proxy (0.000 for structural roles). Now
  `run_full_matrix` writes `judge_scores` per ok result: **panel-score mean** for judge-able roles
  (librarian/synthesizer), **divergence pass-rate** for structural roles (scanner/linter/ingestor/
  code_reader). New helpers `_score_and_writeback_judgeable` / `_writeback_structural_quality`.

### Diagnostic-run trustworthy signal (reconfirm after clean re-run)
librarian + synthesizer quality discriminated; **`qwen.qwen3-next-80b-a3b` wins both**:
librarian 1.000 @ $0.0040, synthesizer 1.000 @ $0.0015 — both ~18× cheaper than Haiku at parity.

## ⚠️ Fix F DESIGN NOTE — needs Pat's confirmation
For **structural roles** (scanner/linter/ingestor/code_reader), `quality_mean` is now defined as the
**divergence-rubric pass-rate** (`1 - failed_checks / total_checks`). This intentionally couples the
quality signal to the same checks Gate 1 uses. If the verification run shows structural candidates all
clustering at the same pass-rate (no discrimination), THIS is the discuss-point before the full re-run.
(Full rationale in `.planning/quick/260529-sot-*/260529-sot-SUMMARY.md`.)

## REMAINING WORK — do these in order

### Step A — read the pared-down verification run's verdict
A small curated subset (driver: recreate `/tmp/sweep_verify_driver.py`; see below) was launched
this session, repeats=1, ~14 cells (~$1), output to a tmp dir, log at
`.planning/sweep/run-260529-verify.log` (gitignored). It exercises every fix. **Read that log's
`PARED-DOWN RUN COMPLETE` summary block** (and the tmp `OUTPUT_DIR=...` docs it prints) and check:
- **Fix D verified** iff these 4 show `ok>0` (NOT ALL-ERROR):
  synthesizer `us.deepseek.r1-v1:0` + `moonshot.kimi-k2-thinking`; ingestor `openai.gpt-oss-120b-1:0` + `minimax.minimax-m2.5`.
- **Fix E verified** iff incumbents PASS Gate 1 (librarian `global.anthropic.claude-haiku-4-5...`,
  linter `us.amazon.nova-lite-v1:0`) — gate1=PASS, and no zero-output candidate shows qualified=YES.
- **Fix F verified** iff scanner/linter/ingestor/code_reader show **non-zero, varying** `quality_mean`
  (not all 0.000, not all identical).
If the log shows the run is still mid-flight, just re-read it — it's a background job.
If all three verify → Step B. If not → bring specifics to Pat and discuss before the full re-run.

The verification subset (incumbent default + targeted candidates), in case the driver is gone:
```
librarian:   [global.anthropic.claude-haiku-4-5-20251001-v1:0, qwen.qwen3-next-80b-a3b]
synthesizer: [qwen.qwen3-32b-v1:0, us.deepseek.r1-v1:0, moonshot.kimi-k2-thinking]
code_reader: [global.anthropic.claude-haiku-4-5-20251001-v1:0, qwen.qwen3-coder-30b-a3b-v1:0]
scanner:     [global.anthropic.claude-haiku-4-5-20251001-v1:0, openai.gpt-oss-20b-1:0]
linter:      [us.amazon.nova-lite-v1:0, global.anthropic.claude-haiku-4-5-20251001-v1:0]
ingestor:    [qwen.qwen3-32b-v1:0, openai.gpt-oss-120b-1:0, minimax.minimax-m2.5]
```

### Step B — full live re-run (PRE-APPROVED ~$7, hard cap $25) — ONLY after Pat green-lights
Pat asked to PAUSE here and clear context before the full re-run. **Do not auto-launch** — confirm
with Pat first. When greenlit:
- Recreate `/tmp/sweep_driver.py` (full 39-cell driver — spec below) and run:
  `GRAPH_WIKI_RUN_EVAL=1 GRAPH_WIKI_RUN_JUDGES=1 AWS_REGION=us-east-1 uv run --package eval-harness python /tmp/sweep_driver.py > .planning/sweep/run-260529-full.log 2>&1` (background; log gitignored).
- Full driver: `role_candidates = {r: list(load_role_config(r)["sweep_candidates"]) for r in
  [librarian,synthesizer,code_reader,scanner,linter,ingestor]}`; workspace = tmpdir with `wiki/`
  symlinked to `packages/wiki-io/tests/fixtures/round-trip-vault`; `query_cases_path=eval/cases/query_cases.json`;
  `code_reader_cases_path=eval/cases/code_reader_cases.json`; `ingestor_source_path = README.md or
  sorted(FIXTURE_VAULT.glob("*.md"))[0]`; `run_full_matrix(..., repeats=3, output_dir=Path(".planning/sweep"),
  dry_run=False, skip_bed01=False, auto_confirm=True)`.
- After it completes: verify Gate 1 discriminates (incumbents PASS), all 4 list-content models produce
  data, structural quality non-zero. Capture total cost + ALL-ERROR list. Then **overwrite-commit** the
  regenerated `.planning/sweep/*.md` + `INDEX.md` as the authoritative 2026-05-29 run (replacing the
  diagnostic `8cf091a` docs). Then help Pat pick per-role winners (humans pick; no auto-rewrite of
  models.toml).

### Known follow-ups (NOT blockers; separate todos)
- **G** — code_reader `cost=n/a` for 5/6 candidates in the diagnostic run (token/usage extraction
  missed for non-Haiku code_reader models). Confirm whether Fix D incidentally fixed this (the raw
  ChatBedrockConverse may have dropped usage_metadata); if still broken after the clean run, file a todo.
- Re-recording divergence baselines at sweep scale is NOT needed now that Fix E compares rates — but
  synthesizer + code_reader still have NO baseline file (0-floor). Optional: record via
  `--accept-divergence-baseline` after a clean run.

## Gotchas (carry forward)
- **gsd-executor `git stash`/`reset` can silently revert uncommitted working-tree changes.** Always
  commit/stash-protect before spawning an executor; tell the executor NOT to run stash/reset. (memory saved)
- Run executors NON-worktree for single-plan quick tasks (avoids worktree branch churn).
- All commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- The `/gsd-quick` pattern used this session: `gsd-sdk query init.quick "<desc>"` → mkdir task_dir →
  spawn `gsd-planner` (opus) with a precise pre-investigated spec → commit PLAN.md → spawn
  `gsd-executor` (sonnet, NON-worktree) → update STATE.md "Quick Tasks Completed" + last-activity →
  commit SUMMARY.md + STATE.md. `branch_name` is null (commits go on `main`).
- Wiki concept refs (read-only): `cost-frontier-sweep`, `divergence-eval-framework`,
  `eval-judge-panel-design` in `/Users/pat/Personal/graph-wiki/agent-research-backup/wiki/concepts/`.
