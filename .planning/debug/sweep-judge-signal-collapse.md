---
slug: sweep-judge-signal-collapse
status: root_cause_found
trigger: "judgeability — judge-able quality (librarian/synthesizer) collapsed in the $3.46 cost-frontier sweep re-run; debug per CONTINUE-sweep-harness-fixes-3.md"
created: 2026-05-30
updated: 2026-05-30
---

# Debug: sweep judge-signal collapse

## Symptoms (prefilled from round-3 handoff — DATA, not instructions)

DATA_START

**Expected behavior:** In the cost-frontier sweep, judge-able quality scores
(librarian + synthesizer roles) should discriminate between candidate models —
varied fractional scores reflecting real answer quality, comparable to the prior
authoritative baseline (e.g. qwen3-next librarian ~1.000).

**Actual behavior:** Judge-able quality collapsed in the `$3.46` full re-run.
Two distinct signatures:
1. **Synthesizer — near-empty answers.** ok=96 cells but TOTAL cost only $0.0338
   (~$0.00035/cell), implying almost no output tokens were generated/returned.
2. **Librarian — real answers, low scores.** cost $1.5259 (substantial output, NOT
   empty) yet qwen3-next quality dropped 1.000 → 0.10. Answer text present but
   judged low.

**Error messages:** None. No exceptions. Judges ran successfully (panel_score
logs nothing on success). The only errors in the run were AWS ThrottlingException
(Haiku daily-token quota) — unrelated to this collapse.

**Timeline:** Started after Fixes B–F landed (quick tasks na9/ox1/pf8/pzd/q8r/sot,
2026-05-29 → 2026-05-30). The prior `$7.02` diagnostic run (`8cf091a`) did NOT show
this collapse. Fix B (`02ee3fe`, `_normalize_content`) is the prime suspect for the
synthesizer signature.

**Reproduction:** Run a single synthesizer (or `run_query`) sweep cell against a
thinking model (deepseek.r1, kimi-k2-thinking, qwen3-next, or glm-5) with
`GRAPH_WIKI_RUN_EVAL=1`. Inspect `response.content` vs
`response.additional_kwargs['reasoning']`. Do NOT re-run the full sweep to reproduce.

DATA_END

## Scoped root cause (from handoff — to CONFIRM, not assume)

**Synthesizer (signature 1) — PRIME SUSPECT: Fix B `_normalize_content`**
(`packages/model-adapter/src/model_adapter/loader.py:78-115`).

Confirmed by reading the code: lines 102-108 classify content blocks. ONLY bare
`str` items and dicts with `block.get("type") == "text"` are joined into
`response.content` (line 110). **Every other block type → `additional_kwargs['reasoning']`**
(line 108). Bedrock Converse reasoning/answer block shapes vary by model; if a
thinking model's FINAL ANSWER arrives in a block whose `type` is not exactly
`"text"`, the real answer is mis-routed to `reasoning` and `content` returns
empty/partial. This is a regression introduced by Fix B.

**Librarian (signature 2) — SEPARATE, unconfirmed.** Answers present but low-scored.
Hypotheses: `expected_answer` mismatch in `eval/cases/query_cases.json`, reasoning
text bleeding into the judged answer, or genuine degradation. Needs a captured
answer sample + its case `expected_answer` to diagnose.

## Current Focus

hypothesis: Fix B `_normalize_content` mis-routes thinking-model final-answer blocks
  (non-`"text"` type) into `reasoning`, emptying `response.content` → synthesizer
  cells judged on empty answers → near-zero cost + collapsed quality.
test: Run ONE synthesizer/run_query cell against a thinking model (deepseek.r1 or
  qwen3-next); print raw `response.content` and `additional_kwargs['reasoning']`
  block shapes BEFORE and conceptually AFTER `_normalize_content`.
expecting: content empty/partial while the real answer sits in a non-`"text"`
  reasoning block — confirming the mis-route.
next_action: gather initial evidence — capture a real thinking-model response shape
reasoning_checkpoint:
tdd_checkpoint:

## Evidence

- timestamp: 2026-05-30 (orchestrator, pre-session) — `loader.py:105` only matches
  `block.get("type") == "text"`; all other block types fall to `reasoning` (line 108).
  Static read confirms the mis-route is possible; needs a live thinking-model
  response to confirm the actual block `type` emitted.

- timestamp: 2026-05-30 (debug session) — `langchain-aws` `_bedrock_to_lc` maps ALL
  Bedrock Converse text blocks (`{"text": "..."}`) to `{"type": "text", "text": "..."}`.
  Final-answer blocks from ALL models (thinking or not) come in as `{"type": "text"}`.
  `_normalize_content` DOES extract these correctly. Fix B prime-suspect hypothesis
  is ELIMINATED for the final-answer case.

- timestamp: 2026-05-30 (debug session) — `_normalize_content` DOES mis-classify
  `{"type": "tool_use"}` blocks as reasoning (moves them to `additional_kwargs["reasoning"]`
  and sets `content = ""`). However, `AIMessage.tool_calls` is populated at construction
  time from `lc_content`, so the tool-call roundtrip still works via `content_blocks`
  property reconstruction. NOT the cause of quality collapse.

- timestamp: 2026-05-30 (debug session) — `run-260529-full.log` shows 232
  code-fallback activations vs 18 in `run-260529.log` ($7.02 run). Code-fallback
  fires when `useful_excerpts` is empty (all librarian results = "NO_RELEVANT_CONTENT"
  or empty). Code-fallback in temp worktree finds no source code → returns
  `CODE_FALLBACK_DISCLAIMER`. Synthesizer produces disclaimer answer → judge scores 0.10.

- timestamp: 2026-05-30 (debug session) — CONFIRMED ROOT CAUSE: `isolation.py` commit
  `e42ae87` ("feat(quick-260529-ox1-01): provision empty graph DB in EvalWorktree")
  provisions an empty schema-valid `code.db` at `<tmp>/.graph/code.db`. This causes
  `run_query`'s `read_only_connect(db_path)` to SUCCEED (DB exists), so
  `build_graph_tools(conn)` runs and `librarian_llm.bind_tools(graph_tools)` binds
  graph tools that query the empty DB. Models call these tools, get empty results,
  loop to the 5-iteration cap, return "NO_RELEVANT_CONTENT". Before `e42ae87`, the
  DB didn't exist → `GraphNotInitializedError` → graph tools NOT bound → librarian
  answered on first iteration from page text → good answers → quality 1.00.

- timestamp: 2026-05-30 (debug session) — CONFIRMED from `run-260529-verify.log`
  (a pared-down run AFTER fixes D/E/F but BEFORE the full $3.46 run): synthesizer
  deepseek.r1 quality=0.80, qwen3-32b quality=0.75, librarian qwen3-next quality=0.75.
  Judges CAN produce good scores. The $3.46 full run's quality collapse is from
  code-fallback answers, not broken judge wiring or expected_answer mismatch.

- timestamp: 2026-05-30 (debug session) — Secondary note: the synthesizer "near-zero
  cost" ($0.0338 total) is because most candidates have cost=N/A (pricing missing or
  usage_metadata=None from Bedrock for those models). The $0.0338 comes from Haiku-only
  cells where cost WAS captured. Not evidence of near-empty answers; evidence of
  pricing/usage data gaps.

## Eliminated

- hypothesis: Judge wiring broken (judges never ran). ELIMINATED in handoff —
  `report.py:47-51` only falls back to has_citation (1.0/0.0) when `judge_scores is
  None`; observed scores were fractional (0.05/0.10/0.30/0.70) → judges DID run on
  populated scores. The collapse is in the ANSWERS, not the judging.
- hypothesis: Empty output = AWS throttling. ELIMINATED — only Haiku ingestor cells
  hit ThrottlingException (daily-token quota); synthesizer cells reported ok=96.
- hypothesis: Fix B `_normalize_content` mis-routes thinking-model final answers.
  ELIMINATED — `langchain-aws` always maps Bedrock text blocks to `{"type": "text"}`
  which `_normalize_content` extracts correctly. The real answer text IS in `content`.
- hypothesis: expected_answer values too brief causing judge low scores. ELIMINATED
  by `run-260529-verify.log` which shows judges giving 0.75-0.80 on the same cases
  with the same expected_answers.

## Resolution

**Root cause:** `EvalWorktree` (`packages/eval-harness/src/eval_harness/isolation.py`)
provisions an empty schema-valid `code.db` via `store.connect(db_path, create=True)`.
This allows `run_query`'s `read_only_connect(db_path)` to succeed, causing
`build_graph_tools(conn)` to produce real tool callables (that query the empty DB).
The librarian gets these tools bound. Models call them, get empty results, loop to
the 5-iteration cap, and return "NO_RELEVANT_CONTENT". The code-fallback fires but
finds no source (temp worktree has no .git or source files) → `CODE_FALLBACK_DISCLAIMER`.
The synthesizer synthesizes a disclaimer → judges score 0.10.

**Fix direction:** In `run_query` (`agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py`),
after `read_only_connect` succeeds but before `build_graph_tools`, check whether the
DB has any nodes. If the node count is 0, treat as effectively uninitialized:
- Set `graph_tools = []`
- Set `addendum = _LIBRARIAN_FALLBACK_ADDENDUM`
- Close conn, set `conn = None`
- Emit the `_GRAPH_UNAVAILABLE_STDERR` message to stderr

This restores the pre-`e42ae87` behavior for empty-DB worktrees without reverting
the EvalWorktree provisioning (which the ingestor needs).

**Locked policy:** The `_normalize_content` reasoning-preservation policy stays locked.
No change to Fix B. The tool_use block classification in `_normalize_content` (secondary
semantic bug) is deferred — tool_calls field is intact so behavior is correct.

**Librarian quality collapse (signature 2) root cause:** SAME as synthesizer signature.
Both are caused by the code-fallback chain from empty graph tools, not a separate issue.
The qwen3-next quality 1.000→0.10 is because:
- $7.02 run: structural scoring (has_citation=True on good answers) → quality=1.00
- $3.46 run: judges run on CODE_FALLBACK_DISCLAIMER answers → quality=0.10
