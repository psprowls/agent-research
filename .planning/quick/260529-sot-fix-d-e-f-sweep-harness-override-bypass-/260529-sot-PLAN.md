---
phase: quick-260529-sot
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
  - agents/graph-wiki-agent/tests/test_command_overrides.py
  - packages/eval-harness/src/eval_harness/divergence/metric.py
  - packages/eval-harness/src/eval_harness/two_gate.py
  - packages/eval-harness/src/eval_harness/sweep.py
  - packages/eval-harness/tests/test_divergence_metric.py
  - packages/eval-harness/tests/test_two_gate_scorer.py
  - packages/eval-harness/tests/test_sweep_full_matrix.py
autonomous: true
requirements: [SWEEP-FIX-D, SWEEP-FIX-E, SWEEP-FIX-F]

must_haves:
  truths:
    - "All 6 model-override branches route through make_llm(role, model_override=...) — swept candidate models get the content normalizer + AccessDenied guard"
    - "Gate 1 (check_regression) compares failure RATES, not absolute counts, so an incumbent at runs=12 matching a runs=4 baseline does NOT fail"
    - "A candidate that produced zero ok-outputs gets gate1=None, gate2=None, qualified=False (no false YES)"
    - "quality_mean reflects a real signal: panel-score mean for judge-able roles; divergence pass-rate for structural roles"
  artifacts:
    - path: "agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py"
      provides: "3 override sites collapsed to make_llm(role, model_override=...)"
      contains: "make_llm(\"librarian\", model_override="
    - path: "packages/eval-harness/src/eval_harness/divergence/metric.py"
      provides: "rate-based check_regression"
      contains: "current_rate"
    - path: "packages/eval-harness/src/eval_harness/two_gate.py"
      provides: "empty-outputs guard setting gate1=None for divergence roles"
    - path: "packages/eval-harness/src/eval_harness/sweep.py"
      provides: "r.judge_scores populated per ok result in run_full_matrix second loop"
      contains: "judge_scores ="
  key_links:
    - from: "agents/.../commands/*.py override branches"
      to: "model_adapter.make_llm"
      via: "model_override kwarg"
      pattern: "make_llm\\([^)]*model_override="
    - from: "sweep.run_full_matrix second loop"
      to: "SweepResult.judge_scores"
      via: "panel_score / metric pass-rate writeback"
      pattern: "\\.judge_scores\\s*="
---

<objective>
Fix three sweep-harness bugs found in the 2026-05-29 live run, each as an atomic commit with offline tests:

- **Fix D** — Six model-override branches construct a RAW `ChatBedrockConverse`, bypassing `_GuardedChatBedrockConverse` (so the Fix-B content normalizer and the AccessDenied guard never apply to swept candidates). Collapse each if/else to a single `make_llm(role, model_override=...)` call.
- **Fix E** — Gate 1 compares absolute failure counts at mismatched run scale (baselines recorded at runs=4, sweep runs at runs=12), so incumbents always fail; and zero-output candidates falsely "qualify". Compare RATES, and guard empty outputs.
- **Fix F** — `quality_mean` is a `has_citation` proxy (0.000 for structural roles) because `SweepResult.judge_scores` is never assigned. Populate it with a real role-appropriate quality signal.

Purpose: After these land, a pared-down verification run confirms them before the full re-run.
Output: Three commits; all offline tests green.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md

<interfaces>
<!-- Contracts extracted from the codebase. Executor: use directly — no re-investigation. -->

From packages/model-adapter/src/model_adapter/loader.py (ALREADY EXISTS — do not modify):
```python
def make_llm(role: str, *, model_override: str | None = None) -> ChatBedrockConverse:
    # Resolves region + max_tokens from the role's config (workspace override
    # → models.toml fallback). When model_override is None, returns the role
    # default — IDENTICAL to the current `else: make_llm(role)` branch.
    # When set, uses model_override as model_id, preserving region/max_tokens.
    # Returns a _GuardedChatBedrockConverse (normalizer + AccessDenied guard).
```

From packages/eval-harness/src/eval_harness/divergence/metric.py:
```python
def check_regression(role: str, current: dict, baseline: dict) -> None
    # current: {rule_id: {"runs": int, "failures": int, "accepted_failures": [...]}}
    # baseline: {"checks": {rule_id: {"failures": int, "runs": int?}, ...}, ...}
    # Raises AssertionError when a HARD-severity rule regresses.

class DivergenceMetric:
    def run_programmatic(self, outputs: list[tuple[str, AgentOutputProxy]]) -> dict[str, dict]
    # returns {rule_id: {"runs": int, "failures": int, "accepted_failures": [...]}}
```

From packages/eval-harness/src/eval_harness/two_gate.py:
```python
ROLES_WITH_DIVERGENCE = frozenset({"librarian","ingestor","linter","scanner","code_reader","synthesizer"})
def score_two_gate(role, divergence_metric_or_none, agent_outputs_by_case, baselines_dir,
                   panel_mean, default_panel_mean, threshold) -> TwoGateOutcome
# Existing semantics (KEEP): gate in {True, None} does not disqualify; False disqualifies;
# both gates None → qualified=False, note "no quality signal".
```

From packages/eval-harness/src/eval_harness/judge.py:
```python
def panel_score(query: str, actual: str, expected: str) -> dict
# returns {"judge_a","judge_b","mean","reason_a","reason_b"}
```

From packages/eval-harness/src/eval_harness/sweep.py:
```python
@dataclass SweepResult: model_id, safe_model_id, query, answer, citations, pages_drilled,
    tokens_in, tokens_out, cost_usd, wall_seconds, structural, status="ok",
    judge_scores: dict | None = None, seed=None
_QUALITY_ROLES = frozenset({"librarian", "synthesizer"})
def _panel_mean_for_candidate(role, candidate_results, cases_path) -> float | None
# Guards on os.environ["GRAPH_WIKI_RUN_JUDGES"]; loads cases via _load_and_validate_cases;
# maps case by case["query"]; uses case["expected_answer"]; skips r.status != "ok" or not r.answer.
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1 (Fix D): Route all 6 model-override branches through make_llm</name>
  <files>
    agents/graph-wiki-agent/src/graph_wiki_agent/commands/query.py,
    agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py,
    agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py,
    agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py,
    agents/graph-wiki-agent/tests/test_command_overrides.py
  </files>
  <behavior>
    - When a command is given a model override, the override-role LLM is built via `make_llm(role, model_override=<override>)` (a `_GuardedChatBedrockConverse`), NOT a raw `ChatBedrockConverse`.
    - When override is None, behavior is unchanged (`make_llm(role)`).
    - Single-role-swap still holds: overriding role X does not change role Y (Y still goes through `make_llm("Y")` with no model_override).
  </behavior>
  <action>
Collapse EACH of the 6 if/else override branches to ONE line `<llm_var> = make_llm("<role>", model_override=<override_var>)`. `make_llm` already resolves region+max_tokens from role cfg and returns the role default when override is None, so the `else` branch is redundant. Sites (file:lines → role, override var, llm var):

1. query.py:458-465 → `code_reader`, var `code_reader_override`, assign `code_llm_raw`. Leave the following `.bind_tools([read_file])` lines as-is.
2. query.py:939-946 → `librarian`, var `_lib_override`, assign `librarian_llm`.
3. query.py:1084-1091 → `synthesizer`, var `synth_override`, assign `synth_llm`. Leave the existing `resolved_synth_model_id = synth_override or synth_cfg["model_id"]` line (still used for trace records).
4. ingest.py:620-627 → `ingestor`, var `model_override`, assign `llm`. Leave the `resolved_model_id = model_override or ingestor_cfg["model_id"]` line.
5. lint.py:457-464 → `linter`, var `model_override`, assign `linter_llm`.
6. scan.py:683-690 → `narrator`, var `model_override`, assign `narrator_llm`.

KEEP every `load_role_config(...)` call (`code_cfg`, `lib_cfg`, `synth_cfg`, `ingestor_cfg`, `cfg`, `narrator_cfg`) — they are still used to compute `resolved_*` trace fields and/or other config reads. Do NOT remove them.

Orphaned-import cleanup (Karpathy: remove ONLY orphans this change creates):
- query.py — KEEP the import. `ChatBedrockConverse` is still referenced (line 44 shares `BedrockEmbeddings`; line 285 docstring/type). Do not touch line 44.
- ingest.py:31, lint.py:34, scan.py:22 — after the edit, `ChatBedrockConverse` is no longer referenced in these files. Remove the now-orphaned `from langchain_aws import ChatBedrockConverse` import in each. Verify with grep before removing (see verify).

Rewrite the EXISTING tests in test_command_overrides.py — they currently assert the OLD (now-buggy) contract (override → raw `ChatBedrockConverse`, `make_llm(role)` NOT called). Invert each to the NEW contract:
- For the override role, assert `make_llm` was called with `model_override=<candidate>` (and the role name as the positional arg) — e.g. `mock_make_llm.assert_any_call("ingestor", model_override=candidate)` or inspect `call_args_list`. For query.py sites, `make_llm` is patched once for all roles, so assert the override role appears with `model_override=candidate` AND other roles appear WITHOUT model_override (or with `model_override=None`).
- Remove the `patch(... ChatBedrockConverse ...)` context managers where they only existed to capture the raw construction; in ingest/lint/scan the symbol no longer exists in-module so patching it will fail — drop those patches.
- For `test_run_query_other_roles_unaffected`: synthesizer must still go through `make_llm("synthesizer", ...)` WITHOUT the librarian candidate. Update `_fake_make_llm` to accept `(role, *, model_override=None)` and record `(role, model_override)`; assert librarian got the candidate and synthesizer did NOT.
- Keep `test_run_query_librarian_back_compat` (legacy `librarian_model_override`) asserting the same new make_llm contract.

Match existing test style (unittest.mock patch/AsyncMock, `from __future__ import annotations`). Tests stay OFFLINE; do not gate on GRAPH_WIKI_RUN_EVAL.
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && grep -rn "ChatBedrockConverse(" agents/graph-wiki-agent/src/graph_wiki_agent/commands/ | grep -vE "query.py:285|^.*#" ; test $(grep -rln "ChatBedrockConverse" agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py | wc -l | tr -d ' ') -eq 0 && uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests/test_command_overrides.py -q</automated>
  </verify>
  <done>No raw `ChatBedrockConverse(` constructor remains in any of the 6 branches; ingest/lint/scan no longer import `ChatBedrockConverse`; query.py import untouched; test_command_overrides.py asserts the make_llm(model_override=...) contract and passes offline.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2 (Fix E): Rate-based Gate 1 + empty-output disqualification</name>
  <files>
    packages/eval-harness/src/eval_harness/divergence/metric.py,
    packages/eval-harness/src/eval_harness/two_gate.py,
    packages/eval-harness/tests/test_divergence_metric.py,
    packages/eval-harness/tests/test_two_gate_scorer.py
  </files>
  <behavior>
    - check_regression(runs=4/failures=3 baseline, current runs=12/failures=9 → rate 0.75 == baseline 0.75) does NOT raise.
    - check_regression(current runs=12/failures=12 → rate 1.0 > baseline 0.75) DOES raise.
    - check_regression skips a rule whose current runs==0 (no data — no raise).
    - Missing baseline (baseline_runs absent/0) keeps the 0.0-rate floor (any current failure on a hard rule still raises).
    - score_two_gate with empty agent_outputs_by_case for a divergence role → gate1_passed is None, divergence_failures is None, qualified is False.
  </behavior>
  <action>
**E1 — metric.py `check_regression` (lines 255-292):** Compare RATES, not counts. Keep the severity lookup, the `-JUDGE → soft` rule, and the soft-skip unchanged. Inside the per-rule loop:
- Read `current_runs = rule_data["runs"]` and `current_failures = rule_data["failures"]`.
- If `current_runs == 0`: skip this rule (no data — `continue`).
- `current_rate = current_failures / current_runs`.
- Read baseline as `baseline_entry = baseline_checks.get(rule_id, {})`, `baseline_failures = baseline_entry.get("failures", 0)`, `baseline_runs = baseline_entry.get("runs", 0)`.
- `baseline_rate = baseline_failures / baseline_runs if baseline_runs else 0.0` (the `0.0` preserves the missing-baseline 0-floor — any failure then exceeds it).
- For HARD rules, raise `AssertionError` when `current_rate > baseline_rate + 1e-9`.
- Update the message to show BOTH rates and raw counts, e.g.: `f"[{role}] {rule_id}: failure rate {current_rate:.3f} ({current_failures}/{current_runs}) > baseline {baseline_rate:.3f} ({baseline_failures}/{baseline_runs}). Run with --accept-divergence-baseline to accept."`

Note: baseline JSON entries may or may not carry a `runs` field. The `.get("runs", 0)` + `if baseline_runs else 0.0` handles the absent case as the 0-floor. Do NOT crash on missing `runs`.

**E2 — two_gate.py `score_two_gate` (lines 102-128):** Guard empty outputs BEFORE the metric branch. Inside the `if role in ROLES_WITH_DIVERGENCE:` block, add a FIRST check: when `not agent_outputs_by_case` (no ok runs), set `gate1_passed = None`, `divergence_failures = None`, log a debug note `"[%s] Gate 1: no outputs — not evaluated"`, and do NOT run the metric. Otherwise fall through to the existing `if divergence_metric_or_none is None: ... else: ...` logic UNCHANGED.

Effect: a no-output candidate gets gate1=None AND (since panel_mean is None) gate2=None → the existing `gate1_passed is None and gate2_passed is None` branch sets `qualified=False`. Do NOT alter that branch or any other None-vs-False semantics.

**Tests** (offline, not gated on GRAPH_WIKI_RUN_EVAL):
- test_divergence_metric.py: add a hard-rule case — baseline `{"checks": {RULE: {"failures": 3, "runs": 4}}}`, current `{RULE: {"runs": 12, "failures": 9}}` → does NOT raise; current `{RULE: {"runs": 12, "failures": 12}}` → raises AssertionError. Add a `current_runs == 0` case → does NOT raise. Use a real hard-severity rule_id from `ROLE_CHECKS["librarian"]` (look it up in the test, e.g. pick `next(c.id for c in ROLE_CHECKS["librarian"] if c.severity == "hard")`).
- test_two_gate_scorer.py: call `score_two_gate(role="librarian", divergence_metric_or_none=<MagicMock>, agent_outputs_by_case=[], baselines_dir=tmp, panel_mean=None, default_panel_mean=None, threshold=0.95)` → assert `outcome.gate1_passed is None`, `outcome.divergence_failures is None`, `outcome.qualified is False`. The MagicMock metric must NOT have `run_programmatic` called (assert `mock_metric.run_programmatic.assert_not_called()`).
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package eval-harness pytest packages/eval-harness/tests/test_divergence_metric.py packages/eval-harness/tests/test_two_gate_scorer.py -q -k "not eval"</automated>
  </verify>
  <done>check_regression compares rates (0.75 baseline vs 0.75 current passes, 1.0 current fails, runs==0 skipped); empty-output divergence candidate yields gate1=None/qualified=False without calling run_programmatic; soft/JUDGE handling and existing None-vs-False semantics unchanged.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3 (Fix F): Populate SweepResult.judge_scores with a real quality signal</name>
  <files>
    packages/eval-harness/src/eval_harness/sweep.py,
    packages/eval-harness/tests/test_sweep_full_matrix.py
  </files>
  <behavior>
    - After scoring, an ok result for a judge-able role (librarian/synthesizer) carries `judge_scores = {..., "mean": <panel mean>}` when GRAPH_WIKI_RUN_JUDGES is set.
    - After scoring, an ok result for a structural role (scanner/linter/ingestor/code_reader) carries `judge_scores = {"mean": <divergence pass-rate>}`.
    - When GRAPH_WIKI_RUN_JUDGES is unset, judge-able results keep judge_scores=None (structural fallback in report unchanged).
  </behavior>
  <action>
In `run_full_matrix`'s SECOND loop (the `for role, candidates in role_candidates.items():` at ~842), after the `divergence_metric` / `baselines_dir_for_role` are set up (~876-886) and the per-candidate output collection exists, write `r.judge_scores` onto each ok `SweepResult` BEFORE/while computing Gate-2 panel means. Two role classes:

**Judge-able roles (`role in _QUALITY_ROLES`):** Refactor so panel scores are computed ONCE per ok run, written back, then meaned — do NOT double-call `panel_score` (today `_panel_mean_for_candidate` calls it and discards per-run scores). Mirror the guards in `_panel_mean_for_candidate` exactly: only when `os.environ.get("GRAPH_WIKI_RUN_JUDGES")`; load cases via `_load_and_validate_cases(cases_path)` mapped by `case["query"]`; skip `r.status != "ok" or not r.answer`; skip cases with no `expected_answer`. For each scored ok run set `r.judge_scores = panel` (the full dict from `panel_score`, which contains `"mean"`). Then derive `panel_means[candidate]` as the mean of the per-run `panel["mean"]` values (None when no scores — same as today). When GRAPH_WIKI_RUN_JUDGES is unset, leave `judge_scores=None` and `panel_means[candidate]=None` (unchanged structural fallback applies). Implement this as a small helper (e.g. `_score_and_writeback(role, candidate_results, cases_path) -> float | None`) OR inline; keep `_panel_mean_for_candidate` callable for any path that still needs it but ensure the writeback path does not also re-invoke it (no double panel_score calls).

**Structural roles (`role in ROLES_WITH_DIVERGENCE and role not in _QUALITY_ROLES`** → scanner, linter, ingestor, code_reader): there is no judge. Use the divergence programmatic PASS-RATE as quality. REUSE the already-constructed `divergence_metric` (do not rebuild). For each ok `r`, build the single-output proxy the same way the Gate-2 loop does — `(r.query, type("AgentOutputProxy", (), {"answer": r.answer})())` — and call `divergence_metric.run_programmatic([proxy_pair])`. From the returned `{rule_id: {"runs", "failures"}}`, compute `total_failures = sum(d["failures"] for d in results.values())` and `total_runs = sum(d["runs"] for d in results.values())` (== number of rules, since one output). `pass_rate = 1 - total_failures / total_runs if total_runs else 0.0`. Set `r.judge_scores = {"mean": pass_rate}`.

DESIGN NOTE (record in SUMMARY, Pat confirms at the pared-down-run checkpoint): for structural roles, "quality" == divergence-rubric pass-rate. This intentionally couples quality to the same checks Gate 1 uses. If the pared-down run shows it doesn't discriminate sensibly, that is the explicit discuss-point before the full re-run.

Do NOT touch the `else` (non-divergence, non-quality) roles — leave judge_scores=None for them.

Do NOT change `render_role_doc`'s fallback logic (report.py:292-295) — it already reads `r.judge_scores["mean"]` when present and falls back to the has_citation proxy when None. (The cosmetic `divergence_failures=None` hardcode at sweep.py:917 is OPTIONAL and out of scope unless trivial — if it adds any meaningful complexity, SKIP it; not required for verification.)

**Tests** (offline — mock panel_score and DivergenceMetric.run_programmatic; do NOT call Bedrock; not gated on GRAPH_WIKI_RUN_EVAL): Prefer DIRECT unit tests of the new writeback helper(s) over a full offline `run_full_matrix` if the latter is fragile.
- Judge-able: with GRAPH_WIKI_RUN_JUDGES set and `panel_score` patched to return `{"mean": 0.8, ...}`, a librarian ok SweepResult ends with `judge_scores["mean"] == 0.8`. With GRAPH_WIKI_RUN_JUDGES unset, judge_scores stays None.
- Structural: with `DivergenceMetric.run_programmatic` patched to return `{"R1": {"runs":1,"failures":0}, "R2": {"runs":1,"failures":1}}`, a scanner ok SweepResult ends with `judge_scores["mean"] == 0.5`.
Use `monkeypatch.setenv`/`delenv` for GRAPH_WIKI_RUN_JUDGES. Build minimal SweepResult fixtures (status="ok", a query that matches the test cases file, a non-empty answer).
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package eval-harness pytest packages/eval-harness/tests/test_sweep_full_matrix.py -q -k "not eval"</automated>
  </verify>
  <done>Ok results for judge-able roles carry panel-mean judge_scores (when judges on), structural roles carry divergence pass-rate judge_scores; no double panel_score calls; GRAPH_WIKI_RUN_JUDGES-off path unchanged; DESIGN NOTE recorded in SUMMARY.</done>
</task>

</tasks>

<verification>
Run the full offline suite as the final gate (orchestrator's gate):

```
cd /Users/pat/Personal/agent-research && uv run pytest -q -k "not eval"
```

Each task is its own atomic commit. Commit messages end with:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

Suggested commit subjects:
- `fix(quick-260529-sot): route 6 model-override branches through make_llm (Fix D)`
- `fix(quick-260529-sot): rate-based Gate 1 + empty-output disqualification (Fix E)`
- `fix(quick-260529-sot): populate SweepResult.judge_scores with real quality signal (Fix F)`
</verification>

<success_criteria>
- All 6 override branches construct via `make_llm(role, model_override=...)`; no raw `ChatBedrockConverse(` constructor remains in any branch; ingest/lint/scan drop the orphaned import; query.py import untouched.
- `check_regression` compares failure RATES; runs=12/failures=9 vs baseline runs=4/failures=3 passes; runs=12/failures=12 fails; current runs==0 rule is skipped; missing-baseline 0-floor preserved.
- Empty-output divergence candidate → gate1=None, divergence_failures=None, qualified=False, run_programmatic not called.
- `SweepResult.judge_scores` populated per ok result: panel mean for judge-able roles, divergence pass-rate for structural roles; judges-off path unchanged.
- Offline test suite green: `uv run pytest -q -k "not eval"` passes.
</success_criteria>

<output>
Create `.planning/quick/260529-sot-fix-d-e-f-sweep-harness-override-bypass-/260529-sot-SUMMARY.md` when done. Record the Fix F structural-role DESIGN NOTE (quality == divergence pass-rate) for Pat to confirm at the pared-down-run checkpoint.
</output>
