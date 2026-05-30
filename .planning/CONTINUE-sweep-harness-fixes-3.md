# CONTINUE: sweep harness — round 3 (judge-signal root-cause, 2026-05-30)

Self-contained continuation. **Supersedes `CONTINUE-sweep-harness-fixes-2.md`.**
Round-2's Fixes B–F are all committed and mechanically verified. The `$3.46`
full re-run completed but is **NOT authoritative** — judge-able quality
collapsed. Root cause scoped below. Working tree is clean.

## How to resume
After `/clear`: **"continue the sweep harness work per `.planning/CONTINUE-sweep-harness-fixes-3.md`"**.
Route every code change through `/gsd-quick` (or `/gsd-debug` for the investigation).
Keep the tree clean before spawning any executor (executor git-ops revert
uncommitted edits — commit first). This is a DEBUGGING task, not a re-run.

## State as of this handoff
- **`aaa3d63`** (committed) — Fix D follow-up: routed the code-fallback
  synthesizer in `query.py:_run_code_fallback` through `make_llm("synthesizer",
  model_override=...)` (the 7th override branch Fix D missed). Covered by
  `test_run_query_synthesizer_override`. Tree now clean.
- The `$3.46` full run log: `.planning/sweep/run-260529-full.log` (gitignored).
  Per-role tallies: librarian 72 ok/$1.5259, synthesizer 96 ok/$0.0338,
  code_reader 108 ok/$1.0252, scanner 72 ok/$0.3133, linter 72 ok/$0.5340,
  ingestor 18 ok 3 err/$0.0229 (Haiku ALL-ERROR = ThrottlingException, daily
  token quota — not a harness bug). TOTAL $3.4551.
- On-disk `.planning/sweep/*.md` + `INDEX.md` are STILL the old `$7.02`
  diagnostic (`8cf091a`, "NOT authoritative"). The `$3.46` run's regenerated
  docs were written then reverted (do NOT trust them; do NOT commit as
  authoritative until the root cause below is fixed and a clean run is done).

## Verification verdict (CONTINUE-2 Step A) — fixes land, RUN is bad
- **Fix D — VERIFIED.** The 4 previously-ALL-ERROR list-content models
  (synthesizer deepseek.r1 + kimi-k2-thinking; ingestor gpt-oss-120b + minimax)
  now produce output (appear as frontier members, not in ALL-ERROR list).
- **Fix E — VERIFIED.** Candidates qualify as pareto-frontier members; only
  failures are AWS ThrottlingExceptions (quota), not Gate-1 auto-FAILs; no
  zero-output candidate falsely qualified.
- **Fix F — HALF-VERIFIED.** Structural quality (scanner 0.25 / linter 1.00 /
  ingestor 0.50 / code_reader 0.75) is populated and varies — the all-0.000 bug
  is fixed. But judge-able quality (librarian/synthesizer) collapsed (see below).

## ROOT CAUSE (scoped 2026-05-30) — answers degraded, NOT judge wiring
The judges DID run: `report.py:47-51` only falls back to has_citation (1.0/0.0)
when `judge_scores is None`; the scores were fractional (0.05/0.10/0.30/0.70) →
`judge_scores` populated → `panel_score` executed (it logs nothing on success).
The collapse is in the ANSWERS being judged. Two distinct signatures:

1. **Synthesizer — near-empty answers.** ok=96 but total cost $0.0338
   (~$0.00035/cell). PRIME SUSPECT: **Fix B `_normalize_content`**
   (`packages/model-adapter/src/model_adapter/loader.py:78-114`). It builds
   `response.content` only from `str` blocks and `{'type':'text'}` dicts;
   EVERYTHING ELSE → `additional_kwargs['reasoning']`. For thinking models
   (deepseek.r1, kimi-k2-thinking, qwen3-next, glm-5) whose FINAL ANSWER arrives
   in a block whose `type` is not exactly `"text"` (Bedrock Converse reasoning
   shapes vary), the real answer is mis-routed to `reasoning` and `content` comes
   back empty/partial. This is a **regression introduced by Fix B**. Matches the
   near-zero synthesizer cost exactly.
2. **Librarian — real answers, low scores.** cost $1.5259 (substantial output,
   NOT empty) yet qwen3-next quality 1.000→0.10. Different failure: answer text
   present but judged low. Hypotheses: expected_answer mismatch in
   `eval/cases/query_cases.json`, reasoning text bleeding into the judged answer,
   or genuine degradation. NEEDS an actual captured answer sample to confirm.

## REMAINING WORK — in order
### Step 1 — DEBUG the answer degradation (do NOT re-run the sweep first)
- Capture a real synthesizer answer for a thinking model (e.g. run ONE
  `run_query`/synthesizer cell against deepseek.r1 or qwen3-next and print
  `response.content` + `additional_kwargs['reasoning']`). Confirm whether Fix B
  empties `content` for that model's block shape.
- If yes → fix `_normalize_content`: when NO text block is found but reasoning
  blocks exist, decide the LOCKED policy (extract the answer from the reasoning
  block's text, or treat a specific reasoning sub-shape as the answer). Add a
  regression test with the real block shape. Route via `/gsd-quick`.
- Capture a real librarian answer + its case `expected_answer`; diagnose the
  separate low-score cause.
### Step 2 — only after Step 1 fixes land + tests green: clean full re-run
- Recreate `/tmp/sweep_driver.py` (full 39-cell driver, spec in CONTINUE-2
  Step B), `repeats=3`, `output_dir=.planning/sweep`, `GRAPH_WIKI_RUN_EVAL=1
  GRAPH_WIKI_RUN_JUDGES=1`. PRE-APPROVED ~$7, hard cap $25 — but CONFIRM with
  Pat before launching, and check the Bedrock daily-token quota has reset (the
  ingestor-Haiku ThrottlingException means we hit it last run).
- Verify judge-able quality now discriminates (not all ~0). Then overwrite-commit
  `.planning/sweep/*.md` + `INDEX.md` as authoritative, replacing `8cf091a`.
  Then help Pat pick per-role winners (humans pick; no auto-rewrite of models.toml).

## Known follow-ups (NOT blockers; separate todos)
- **G — cost=N/A pervasive** (most synthesizer candidates + scattered others),
  not just code_reader. Token/usage extraction misses for many non-Haiku models.
  Without cost there's no cost-frontier. File/fix alongside Step 1 if cheap.
- synthesizer + code_reader have NO divergence baseline file (0-floor); optional
  `--accept-divergence-baseline` after a clean run (Fix E compares rates so not
  blocking).

## Gotchas (carry forward)
- **gsd-executor `git stash`/`reset` silently reverts uncommitted edits.** Commit
  first; tell executors NOT to stash/reset. Run executors NON-worktree for
  single-plan quick tasks.
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Wiki concept refs (read-only): `cost-frontier-sweep`, `divergence-eval-framework`,
  `eval-judge-panel-design` in `/Users/pat/Personal/graph-wiki/agent-research-backup/wiki/concepts/`.
