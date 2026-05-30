---
phase: quick-260530-ehv
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/model-adapter/src/model_adapter/models.toml
  - .planning/notes/sweep-judge-independence-deferred.md
  - .planning/STATE.md
autonomous: true
requirements: [QUICK-260530-ehv]

must_haves:
  truths:
    - "No swept role (preflight + the six swept roles) references the Haiku ID claude-haiku-4-5"
    - "Every swept role's default model_id appears in its own sweep_candidates list"
    - "narrator + domain-proposer + judge_a + judge_b remain unchanged (still on prior models)"
    - "The deferred judge-independence finding is captured as a standalone note"
    - "STATE.md Next action points to the clean Haiku-free full sweep re-run"
  artifacts:
    - path: "packages/model-adapter/src/model_adapter/models.toml"
      provides: "Refreshed per-role defaults + sweep_candidates (Haiku purged from swept roles)"
      contains: "moonshotai.kimi-k2.5"
    - path: ".planning/notes/sweep-judge-independence-deferred.md"
      provides: "Deferred judge family-independence finding from 2026-05-30 /gsd-explore session"
      contains: "JUDGE_PANEL_CONFIG"
    - path: ".planning/STATE.md"
      provides: "Updated Next action pointer recording the sweep model-set refresh"
      contains: "kimi-k2.5"
  key_links:
    - from: "models.toml swept roles"
      to: "sweep_candidates invariant"
      via: "default model_id present in own candidate list"
      pattern: "model_id.*in.*sweep_candidates"
---

<objective>
Refresh the cost-frontier sweep model set in `models.toml` to remove Haiku entirely
from live sweep execution (as BOTH candidate AND held-constant default across all
swept roles), applying the per-role defaults + candidates decided in the 2026-05-30
/gsd-explore session. Then capture a deferred judge-independence finding as a planning
note and update STATE.md's Next action pointer.

Purpose: Haiku (`global.anthropic.claude-haiku-4-5-20251001-v1:0`) exhausted its
non-adjustable ~27M-tokens/day Bedrock quota, blocking the prior clean sweep re-run.
Under the single-role-swap protocol the held-constant defaults drive most token
volume, so Haiku must be purged from defaults too — not just candidate lists. All
replacement models have generous on-demand quotas.

Output: Refreshed models.toml, one deferred-finding note, surgically updated STATE.md.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

<interfaces>
<!-- Current models.toml swept-role state (read by executor; exact-string anchors). -->
<!-- Haiku ID to purge from all six swept roles + preflight: -->
<!--   global.anthropic.claude-haiku-4-5-20251001-v1:0 -->
<!-- Haiku MUST remain ONLY in [roles.narrator] and [roles.domain-proposer]. -->
<!-- Judge config of record lives in eval_harness/judge.py JUDGE_PANEL_CONFIG, -->
<!-- NOT the reference-only [roles.judge_a]/[roles.judge_b] blocks in models.toml. -->
<!-- Config-pinning tests that may assert OLD values: -->
<!--   packages/model-adapter/tests/test_loader.py -->
<!--   packages/model-adapter/tests/test_narrator_role.py -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Refresh swept-role defaults + candidates in models.toml (purge Haiku)</name>
  <files>packages/model-adapter/src/model_adapter/models.toml</files>
  <action>
Edit `models.toml` so the seven non-deferred roles match EXACTLY the spec below.
Preserve each role's existing `region`, `max_tokens`, `max_concurrency` lines unchanged.
Use the exact Bedrock model ID strings given.

[roles.preflight]
  - Set model_id = "qwen.qwen3-32b-v1:0" (was the Haiku ping; keep max_tokens=64, max_concurrency=1).
  - Update the block comment that says to pin a cheap/fast Haiku — it is now qwen3-32b (still a cheap connectivity ping).

[roles.librarian]
  - model_id = "moonshotai.kimi-k2.5"
  - sweep_candidates = [
      "qwen.qwen3-32b-v1:0",
      "qwen.qwen3-next-80b-a3b",
      "deepseek.v3.2",
      "moonshotai.kimi-k2.5",
      "zai.glm-5",
    ]

[roles.code_reader]
  - model_id = "minimax.minimax-m2.5"
  - sweep_candidates = [
      "qwen.qwen3-coder-30b-a3b-v1:0",
      "qwen.qwen3-coder-next",
      "mistral.devstral-2-123b",
      "openai.gpt-oss-120b-1:0",
      "minimax.minimax-m2.5",
    ]

[roles.scanner]
  - model_id = "openai.gpt-oss-20b-1:0"
  - sweep_candidates = [
      "openai.gpt-oss-20b-1:0",
      "zai.glm-4.7-flash",
      "mistral.ministral-3-14b-instruct",
      "qwen.qwen3-32b-v1:0",
      "qwen.qwen3-coder-30b-a3b-v1:0",
    ]

[roles.linter]
  - model_id = "us.amazon.nova-lite-v1:0" (UNCHANGED default — now ALSO added into candidates; deepseek.v3.2 dropped).
  - sweep_candidates = [
      "us.amazon.nova-lite-v1:0",
      "qwen.qwen3-32b-v1:0",
      "openai.gpt-oss-120b-1:0",
      "minimax.minimax-m2.5",
      "zai.glm-4.7-flash",
    ]
  - Update/remove the stale comment saying the incumbent nova-lite is NOT in the candidate set / needs a decision after the sweep — that decision is now made (nova-lite stays default AND is a candidate).

[roles.ingestor]
  - model_id = "zai.glm-4.7-flash" (CHANGED from qwen3-32b).
  - sweep_candidates = [
      "qwen.qwen3-32b-v1:0",
      "openai.gpt-oss-120b-1:0",
      "minimax.minimax-m2.5",
      "qwen.qwen3-next-80b-a3b",
      "zai.glm-4.7-flash",
    ]
  - (Removed haiku AND qwen.qwen3-vl-235b-a22b — vision model, overkill for text ingestion.)

[roles.synthesizer]
  - model_id = "qwen.qwen3-32b-v1:0" (UNCHANGED default — v1.0 judge-backed headline winner).
  - sweep_candidates = [
      "qwen.qwen3-32b-v1:0",
      "zai.glm-5",
      "moonshotai.kimi-k2.5",
      "deepseek.v3.2",
      "qwen.qwen3-next-80b-a3b",
      "moonshot.kimi-k2-thinking",
    ]
  - (Removed haiku AND us.deepseek.r1-v1:0 — reasoning model with a 7.9M tokens/day cap, lower than the Haiku cap being removed, plus toolCalling unsupported.)

DO NOT TOUCH (deferred / out of scope):
  - [roles.narrator] — leave on Haiku.
  - [roles.domain-proposer] — leave on Haiku.
  - [roles.judge_a] / [roles.judge_b] — leave unchanged.

Refresh stale per-role comments: replace lines like "Sweep candidates queued
2026-05-29 (sweep not yet run — no scores)" and "Previous default:
us.anthropic.claude-haiku-..." with a short note for each edited role:
"Candidate set refreshed 2026-05-30 (post-Haiku-purge, /gsd-explore session); Haiku
removed for quota exhaustion; per-role defaults chosen in that session."
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && python3 -c "
import tomllib, sys
d = tomllib.load(open('packages/model-adapter/src/model_adapter/models.toml','rb'))['roles']
swept = ['librarian','code_reader','scanner','linter','ingestor','synthesizer']
errs = []
# Haiku must not appear in any swept role or preflight
for r in swept + ['preflight']:
    blob = str(d[r])
    if 'claude-haiku-4-5' in blob:
        errs.append(f'{r}: Haiku still present')
# default must be in own candidate list
for r in swept:
    if d[r]['model_id'] not in d[r]['sweep_candidates']:
        errs.append(f'{r}: default {d[r][\"model_id\"]} not in sweep_candidates')
# preflight default is qwen3-32b
if d['preflight']['model_id'] != 'qwen.qwen3-32b-v1:0':
    errs.append('preflight default not qwen3-32b')
# Haiku MUST still be in narrator + domain-proposer
for r in ['narrator','domain-proposer']:
    if 'claude-haiku-4-5' not in d[r]['model_id']:
        errs.append(f'{r}: Haiku unexpectedly removed (should be deferred)')
if errs:
    print('FAIL:'); [print(' -',e) for e in errs]; sys.exit(1)
print('OK: Haiku purged from swept roles; invariant holds; deferred roles intact')
"</automated>
  </verify>
  <done>The verify script prints OK: every swept role's default is in its own
  candidate list, no `claude-haiku-4-5` remains in the six swept roles or preflight,
  preflight default is qwen3-32b, and narrator + domain-proposer still on Haiku.</done>
</task>

<task type="auto">
  <name>Task 2: Sync config-pinning tests + run model-adapter suite</name>
  <files>packages/model-adapter/tests/test_loader.py, packages/model-adapter/tests/test_narrator_role.py</files>
  <action>
Run the model-adapter test suite. Existing config-pinning tests (from quick task
260529-pf8) assert specific model IDs / candidate lists; the Task 1 edits will likely
turn some red.

Run: `uv run --package model-adapter pytest` (fall back to `cd packages/model-adapter
&& uv run pytest` if the workspace flag is unavailable).

For each failing assertion that pins an OLD Haiku default or OLD candidate list,
update the expected value to the NEW value set in Task 1. Do NOT relax or delete
assertions — update them to the new pinned values. Do NOT touch tests unrelated to
the swept-role model set (e.g. narrator-on-Haiku assertions stay green and unchanged,
since narrator is intentionally deferred).
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && uv run --package model-adapter pytest -q</automated>
  </verify>
  <done>Model-adapter test suite passes green. Any config-pinning test that asserted
  OLD Haiku defaults/candidates is updated to the new values; narrator-on-Haiku
  assertions remain unchanged and green.</done>
</task>

<task type="auto">
  <name>Task 3: Write deferred judge-independence note + update STATE.md pointer</name>
  <files>.planning/notes/sweep-judge-independence-deferred.md, .planning/STATE.md</files>
  <action>
CREATE `.planning/notes/sweep-judge-independence-deferred.md` with frontmatter:
  title: "Sweep judge family-independence — deferred finding"
  date: 2026-05-30
  context: "v1.11 Phase 60 cost-frontier sweep / /gsd-explore"

Body (prose + bullets, faithful to these points):
  - D-07 rule: a judge must NOT belong to a model family that is also a sweep
    candidate (originally why Sonnet was dropped as a judge — Haiku was a candidate in
    every role, so a Claude judge would self-prefer the Claude candidate).
  - After the 2026-05-30 Haiku purge, candidate families shifted. judge_a = Mistral
    Large 3 (`mistral.mistral-large-3-675b-instruct`) now VIOLATES the rule: Mistral
    is now a candidate family via `mistral.devstral-2-123b` in code_reader, and
    code_reader IS a judge-scored (query-style) role — so judge_a can self-prefer the
    devstral candidate.
  - judge_b = Nova Pro (`us.amazon.nova-pro-v1:0`, Amazon) is clean for judged roles
    TODAY (nova-lite only appears in linter/ingestor, which are not judge-scored), but
    becomes a collision the moment judging is extended to linter (where nova-lite is
    now default + candidate).
  - Reversal: with Haiku removed from all candidate lists, NO Claude model is a
    candidate anymore — so Claude/Sonnet (incl. extended-thinking) is now the only
    major family fully absent from candidates, making it the natural clean independent
    judge again, AND a viable reasoning judge.
  - Reasoning-model-as-judge analysis: judging fits reasoning (multi-step EVAL_STEPS
    rubric, hallucination detection; a judge stronger than the candidates is
    desirable). Caveats: (1) determinism — the panel pins temperature=0; many
    reasoning models won't honor temp=0 and variable-length traces hurt
    reproducibility; (2) cost/latency — judges fire on every judged cell × repeats × 2
    judges, so token-heavy reasoners blow up judge spend far more than a single
    candidate cell (same reason deepseek.r1 was cut as a candidate); (3) deepeval
    score-extraction may trip on thinking-block output (cf. Fix B / quick task pzd
    content normalization). Most Bedrock reasoning models belong to candidate families
    (DeepSeek, Moonshot, Qwen, OpenAI gpt-oss) → only Claude extended-thinking is
    family-clean.
  - DECISION: judges left UNCHANGED this pass (Pat: "fine for now with what we have").
  - TRIGGER to revisit: before trusting code_reader judge scores from the next sweep
    (Mistral judge ↔ devstral candidate collision), and before extending the judge
    panel to non-query roles (linter/ingestor/scanner) where Nova/Amazon would collide
    with nova-lite. NOTE the binding config lives in
    `packages/eval-harness/src/eval_harness/judge.py` (`JUDGE_PANEL_CONFIG`), NOT the
    reference-only `[roles.judge_a]`/`[roles.judge_b]` blocks in models.toml.

UPDATE `.planning/STATE.md` — surgically rewrite the "Next action" pointer (and the
Current Position "Next activity" line if it still points at the quota-blocked re-run)
to record:
  Sweep candidate set refreshed 2026-05-30 (Haiku purged from all 6 swept roles +
  preflight; per-role defaults/candidates set via /gsd-explore — librarian→kimi-k2.5,
  code_reader→minimax-m2.5, scanner→gpt-oss-20b, linter→nova-lite [now also a
  candidate], ingestor→glm-4.7-flash, synthesizer→qwen3-32b, preflight→qwen3-32b);
  judges intentionally held (see
  `.planning/notes/sweep-judge-independence-deferred.md`); next step = clean full sweep
  re-run with the new Haiku-free set (the daily-token quota throttle that blocked the
  prior re-run no longer applies since Haiku is gone). narrator + domain-proposer still
  on Haiku, deferred.

Keep this edit surgical — do NOT rewrite unrelated STATE.md sections (Performance
Metrics, Quick Tasks table, Deferred Items, archive footer). DO NOT TOUCH the sweep
result docs (.planning/sweep/STORY.md, INDEX.md, per-role *.md).
  </action>
  <verify>
    <automated>cd /Users/pat/Personal/agent-research && test -f .planning/notes/sweep-judge-independence-deferred.md && grep -q "JUDGE_PANEL_CONFIG" .planning/notes/sweep-judge-independence-deferred.md && grep -q "kimi-k2.5" .planning/STATE.md && grep -q "sweep-judge-independence-deferred" .planning/STATE.md && echo OK</automated>
  </verify>
  <done>Note file exists and references JUDGE_PANEL_CONFIG; STATE.md Next action
  references the new defaults (kimi-k2.5) and the deferred-judge note path; sweep
  result docs untouched.</done>
</task>

</tasks>

<verification>
- `models.toml` parses as valid TOML.
- Haiku ID `claude-haiku-4-5` absent from all six swept roles + preflight; present
  ONLY in narrator + domain-proposer.
- Every swept role's default model_id is a member of its own sweep_candidates.
- `uv run --package model-adapter pytest` is green (pinning tests updated to new values).
- Deferred-judge note created; STATE.md pointer updated surgically.
</verification>

<success_criteria>
- Haiku fully purged from live sweep execution (defaults + candidates) across all
  swept roles and preflight; deferred roles (narrator, domain-proposer, judges) intact.
- Default-in-own-candidates invariant holds for all six swept roles.
- Config-pinning test suite green.
- Judge-independence finding captured; STATE.md Next action points to the clean
  Haiku-free full sweep re-run.
</success_criteria>

<output>
Create `.planning/quick/260530-ehv-refresh-sweep-model-set-in-models-toml-r/260530-ehv-SUMMARY.md` when done.
</output>
