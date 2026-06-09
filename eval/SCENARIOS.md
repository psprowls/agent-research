# Creating Claude Code Eval Scenarios

This guide is for contributors adding scenarios to the `claude-code-evals`
package. After reading it, you should be able to create a new scenario, run it
against one or more Claude Code configurations, and read the resulting artifacts.

The harness evaluates Claude Code behavior by running a prompt inside an
isolated checkout or fixture directory, then applying verifiers to the resulting
answer or code changes. A scenario lives under `eval/scenarios/<scenario-name>/`
and is usually made of:

- `scenario.yaml`: scenario metadata, isolation settings, budgets, and verifiers.
- `prompt.md`: the user task sent to Claude Code.
- `preflight.sh`: optional setup script run before Claude Code starts.
- `verify.sh`: optional verification script run after Claude Code finishes.
- `rubric.md`: optional LLM-judged scoring rubric.
- Optional golden patch files used by `golden` verifiers.

## When to Add a Scenario

Add a scenario when you want a repeatable behavioral test for Claude Code. Good
scenarios have a clear success condition and isolate one question:

- Does wiki context change correctness?
- Does wiki context reduce discovery cost?
- Does the graph-wiki plugin let the agent find knowledge that is not obvious
  from the source tree?
- Does a prompt or configuration change regress a known workflow?

Avoid scenarios whose outcome depends on broad subjective judgment, hidden local
state, or a moving branch tip. Prefer a pinned commit or a small fixture.

## Scenario Layout

Start by copying `eval/scenarios/TEMPLATE/`:

```bash
cp -R eval/scenarios/TEMPLATE eval/scenarios/my-scenario
```

Then edit the copied files:

- Rename `name` in `scenario.yaml` to match the directory name.
- Replace `description` with the behavior under test.
- Write `prompt.md` as the exact task Claude Code should receive.
- Make `preflight.sh` idempotently prepare the isolated repo, if needed.
- Make `verify.sh` check deterministic pass/fail conditions, if used.
- Write `rubric.md` for qualitative scoring, if used.

Keep scenario names in kebab case. The CLI resolves a scenario named
`my-scenario` from `eval/scenarios/my-scenario/scenario.yaml`.

## `scenario.yaml` Reference

The scenario schema forbids unknown fields. If a key is misspelled, loading the
scenario fails instead of silently ignoring it.

### Required Identity Fields

```yaml
name: wiki-design-tokens
description: >
  Agent must create a StatusBadge component using semantic color tokens.
```

- `name`: scenario identifier. It should match the directory name.
- `description`: human-readable summary for lists and reports.

### Isolation

The harness supports two isolation modes.

```yaml
isolation_mode: worktree
target_repo: ~/Personal/mono-repo
baseline_sha: 551f7ed8b9c0b4f51a4000302548e24284729652
```

`worktree` mode creates a detached Git worktree at `baseline_sha` from
`target_repo`. Use it for real-repo implementation tasks where you want stable
source state. Both `target_repo` and `baseline_sha` are required.

```yaml
isolation_mode: fixture
fixture_dir: fixtures/small-project
```

`fixture` mode copies `fixture_dir` into a temporary working directory. Use it
for small deterministic examples or tests that should not depend on a real Git
repo. `fixture_dir` is required.

Golden verifiers require a Git worktree and are rejected with fixture isolation.

### Config Selection

```yaml
configs: [base]
```

`configs` names default configurations from `eval/configs/*.yaml`. The pytest
fixture uses the first entry when no config is specified. The CLI defaults to
`base` unless you pass one or more `--config` flags.

### Run Mode

```yaml
mode: headless
eval_mode: implement
```

- `mode`: `headless` or `interactive`.
- `eval_mode`: `qa` or `implement`.

`eval_mode: qa` adds a system instruction that the agent should answer directly
using read-only tools and should not edit files. Use it for question-answer
tasks.

`eval_mode: implement` adds a system instruction that the agent should make the
requested changes and finish with `<DONE>`. Use it for code modification tasks.

`headless` runs Claude Code non-interactively. With no `auto_user`, the
orchestrator dispatches to a single one-shot run; with `auto_user` set, it
dispatches to a multi-turn run driven by the auto-user simulator (see below).

`interactive` hands the isolated worktree to a human. The orchestrator dispatches
to `run_interactive()`, which prints the worktree path and polls for a
`.eval-done` sentinel file. Run `claude` yourself in that worktree, then signal
completion with `touch <worktree>/.eval-done`. The run finishes with
`final_status: completed_interactive`, or `budget_exceeded` if the wait exceeds
the interactive wait limit. Interactive mode forbids `auto_user` (a schema-level
check). Use `headless` for normal automated scenarios.

### Auto User

```yaml
auto_user: auto_user.yaml
```

`auto_user` points at an `AutoUser` YAML file. When set on a `headless` scenario,
the orchestrator runs the multi-turn path: it spawns Claude Code in multi-turn
mode and uses `AutoUserSimulator` to generate each follow-up user message until
the conversation ends. (`interactive` mode forbids `auto_user`.)

A minimal `AutoUser` file:

```yaml
model: claude-haiku-4-5-20251001
max_replies: 3
stop_on: "<DONE>"
system_prompt: "Drive the task forward. Say <DONE> when finished."
```

Fields:

- `model`: judge model used to generate LLM-driven replies.
- `max_replies`: maximum number of simulated user replies before the
  conversation ends (default 5).
- `stop_on`: when this substring appears in the assistant's text, the
  conversation ends (default `<DONE>`).
- `system_prompt`: instruction given to the reply model.
- `triggers`: optional list of rule-based replies, checked before the LLM.
- `default_reply`: reply used when an LLM call fails (default `proceed`).
- `abort_on_default_after`: after this many *consecutive* default-reply
  fallbacks, the conversation ends (default 2, must be ≥ 1).

Each `triggers` entry is a `match` plus a `reply`. A `match` sets exactly one of
`contains` (substring) or `regex` — setting both or neither fails validation:

```yaml
triggers:
  - match:
      contains: "clarify"
    reply: "Please proceed without clarification."
  - match:
      regex: "question\\?"
    reply: "Yes, go ahead."
default_reply: continue
abort_on_default_after: 3
```

The simulator resolves each turn with this priority chain:

1. `stop_on` substring present in the assistant text → end the conversation.
2. `max_replies` budget exhausted → end the conversation.
3. First matching trigger (in order) → use its `reply`; resets the consecutive
   default counter.
4. Otherwise call the LLM judge → use its reply; resets the consecutive default
   counter.
5. If the LLM call raises → fall back to `default_reply`. Once consecutive
   defaults reach `abort_on_default_after`, end the conversation instead.

Old-style `auto_user.yaml` files (without `triggers`, `default_reply`, or
`abort_on_default_after`) still load: the new fields default as listed above.

### Preflight

```yaml
preflight: preflight.sh
```

`preflight` is optional. When present, the harness runs the script from the
isolated working directory before Claude Code starts. Its stdout and stderr are
captured in `preflight.log` when non-empty.

Use preflight to remove files the agent must create, reset generated state, or
assert that expected source files exist. Make it repeatable and fast. The current
orchestrator captures preflight output but does not fail the scenario solely
because the preflight script exits non-zero, so put critical setup checks in
`verify.sh` as well.

### Verification

```yaml
verify:
  - kind: script
    path: verify.sh
  - kind: rubric
    path: rubric.md
    judge: claude-haiku-4-5-20251001
    pass_threshold: 4.0
```

Each entry has:

- `kind`: `script`, `golden`, or `rubric`.
- `path`: file path relative to the scenario directory.
- `judge`: optional model for rubric verification.
- `pass_threshold`: optional rubric threshold on the 0-5 rubric scale.

All verifier entries must pass for the scenario to pass.

`script` runs the script from the isolated working directory and passes when the
exit code is zero. Its reason is stdout, stderr, or `PASS`/`FAIL`.

`golden` applies the patch at `path`, then runs `git diff --exit-code`. It passes
when the agent's changes already match the golden patch. Use it for exact output
checks in Git worktree scenarios.

`rubric` runs a DeepEval `GEval` metric with a Claude Code judge model. The judge
sees the final assistant text, a privacy-scrubbed tool summary, and the current
Git diff. The `pass_threshold` is written as a 0-5 rubric score; internally it is
normalized to 0-1.

### Budgets

```yaml
budgets:
  max_turns: 40
  max_input_tokens: 4000000
  max_wall_seconds: 300
```

- `max_turns`: schema-supported turn budget. The current one-shot CLI path does
  not enforce this directly.
- `max_input_tokens`: schema-supported input-token budget. The current one-shot
  CLI path does not enforce this directly.
- `max_wall_seconds`: wall-clock timeout for the Claude Code process.

If the process exceeds `max_wall_seconds`, the run is marked
`budget_exceeded`.

### Discriminator

```yaml
discriminator:
  type: efficiency-gated
  metric: files_read_count
  min_improvement_pct: 40
```

The discriminator describes how to interpret a multi-arm wiki comparison. It is
used by verdict computation and report helpers, not by the basic pass/fail check
for a single `cc-eval run`.

Available types:

- `correctness-gated`: base should fail and the wiki-assisted arm should pass.
- `efficiency-gated`: both should pass, but the wiki-assisted arm should improve
  the declared metric by at least `min_improvement_pct`.
- `impossible-without-wiki`: base cannot reasonably pass because the required
  knowledge exists only in the wiki; the plugin arm should pass.

For `efficiency-gated`, set:

- `metric`: a numeric metric name, usually from `metrics.json`.
- `min_improvement_pct`: minimum percent reduction required.

Common metric names include:

- `input_tokens`
- `output_tokens`
- `turn_count`
- `files_read_count`
- `files_edited_count`
- `files_written_count`
- `tool_calls_before_first_edit`
- `distinct_paths_touched`
- `subagent_dispatches`
- `skill_invocations_count`
- `permission_prompt_count`

### Injected Wiki Pages

```yaml
inject:
  - concepts/design-tokens.md
  - entities/pkg_shared-ui.md
```

`inject` lists wiki pages relative to the workspace `wiki/` directory. The helper
for injected-context experiments prepends those pages to the prompt, separated
by `---`. Missing pages raise an error in that helper.

The standard `cc-eval run` path does not automatically inject these pages into
the prompt. Treat `inject` as scenario metadata unless you are using or extending
the injected-arm helper.

### Metrics Flags

```yaml
metrics:
  tool_shape: true
  judge_qualitative: false
```

These flags are parsed with the scenario. The current metrics collector always
computes the flat transcript and verifier metrics; these flags are available for
scenario metadata and future metric behavior.

## Config Files

Configurations live under `eval/configs/` and use this schema:

```yaml
name: plugin
plugin_dirs:
  - graph-wiki
model: claude-opus-4-8
temperature: 0.0
extra_env:
  GRAPH_WIKI_WORKSPACE: "~/Personal/graph-wiki/mono-repo-eval-551f7ed8"
extra_settings:
  permissions:
    defaultMode: acceptEdits
```

Available fields:

- `name`: config identifier, used by `--config`.
- `plugin_dirs`: plugin directories passed to `claude --plugin-dir`. Relative
  paths resolve against the current working directory.
- `model`: Claude model passed to `claude --model`.
- `temperature`: parsed config value. The current runner does not pass it to the
  Claude Code CLI.
- `extra_env`: environment variables added to the Claude Code process and written
  into the isolated settings.
- `extra_settings`: extra fields merged into the isolated Claude Code
  `settings.json`.

The runner creates an isolated Claude config directory for each run. It registers
configured plugin directories, sets `permissions.defaultMode` to `acceptEdits`,
disables Claude Code auto memory, and removes `ANTHROPIC_API_KEY` so runs use
`CLAUDE_CODE_OAUTH_TOKEN` instead of API credits.

## Runsets

A runset YAML groups scenarios and default configs:

```yaml
name: wiki-context-smoke
scenarios:
  - wiki-design-tokens
  - wiki-api-client
default_configs:
  - base
  - plugin
```

Runsets are useful when comparing multiple configs across the same scenario
set. When `cc-eval run --runset` finishes, the CLI writes a Markdown and JSON
report under `eval/reports/`.

## Writing `prompt.md`

Write the prompt as the user task only. The harness adds the eval-mode system
prompt separately.

For implementation scenarios, make the desired filesystem result explicit:

```markdown
Create a `StatusBadge` component at `apps/web-next-ts/src/components/StatusBadge.tsx`.

Requirements:
- Accept a `status` prop: `"running" | "completed" | "failed" | "pending"`
- Use semantic color tokens, not raw Tailwind palette classes
- Export `StatusBadge` as a named export
```

For QA scenarios, ask a concrete question with enough scope boundaries to judge
the answer. Do not ask the model to choose among vague research directions unless
the rubric can score the answer deterministically.

## Writing `preflight.sh`

Use `preflight.sh` for setup. Examples:

```sh
#!/bin/sh
set -eu
rm -f apps/web-next-ts/src/components/StatusBadge.tsx
```

Keep it idempotent. If it creates files, make sure those files are expected by
the verifier or cleaned up before the run.

## Writing `verify.sh`

Use `verify.sh` for deterministic checks:

```sh
#!/bin/sh
set -eu
test -f apps/web-next-ts/src/components/StatusBadge.tsx
! grep -R "#[0-9a-fA-F]\\{6\\}" apps/web-next-ts/src/components/StatusBadge.tsx
```

Prefer simple command-line checks for existence, import paths, forbidden strings,
or focused test commands. Keep expensive full-suite runs out of normal scenarios
unless the scenario specifically evaluates test behavior.

Make scripts executable:

```bash
chmod +x eval/scenarios/my-scenario/preflight.sh eval/scenarios/my-scenario/verify.sh
```

## Writing `rubric.md`

Rubrics should use a concrete 0-5 scale. The verifier passes the final assistant
message, tool summary, and Git diff to the judge, so rubric criteria can inspect
both what the agent said and what it changed.

Recommended structure:

```markdown
Score the agent's implementation 0-5, 1 pt per criterion. Pass threshold 4.

Criteria:

1. `uses_domain_client` - Uses the sanctioned domain client.
2. `no_raw_http` - Does not call raw axios/fetch for this workflow.
3. `correct_types` - Exports the expected TypeScript types.
4. `minimal_scope` - Does not modify unrelated files.
5. `build_safe` - The implementation is syntactically valid.

Return JSON: `{"score": 0-5, "reasoning": str, "criteria_hits": [str]}`.
```

Use stable names for criteria. Avoid criteria that require knowledge not present
in the prompt, diff, transcript, or injected/plugin context.

## Running Evals

List available scenarios and configs:

```bash
uv run --package claude-code-evals cc-eval list --evals-root eval
```

Run one scenario with the default `base` config:

```bash
CLAUDE_CODE_OAUTH_TOKEN=<token> \
uv run --package claude-code-evals cc-eval run wiki-design-tokens --evals-root eval
```

Run one scenario against several configs:

```bash
CLAUDE_CODE_OAUTH_TOKEN=<token> \
uv run --package claude-code-evals cc-eval run wiki-design-tokens \
  --evals-root eval \
  --config base \
  --config plugin
```

Run without invoking Claude Code:

```bash
uv run --package claude-code-evals cc-eval run wiki-design-tokens \
  --evals-root eval \
  --config base \
  --dry-run
```

Keep the temporary isolation directory for debugging:

```bash
CLAUDE_CODE_OAUTH_TOKEN=<token> \
uv run --package claude-code-evals cc-eval run wiki-design-tokens \
  --evals-root eval \
  --keep-worktree
```

Run a runset:

```bash
CLAUDE_CODE_OAUTH_TOKEN=<token> \
uv run --package claude-code-evals cc-eval run --runset eval/runsets/wiki-context.yaml \
  --evals-root eval
```

Regenerate a report from existing run artifacts:

```bash
uv run --package claude-code-evals cc-eval report eval/runs --name wiki-context --out eval/reports/wiki-context.md
```

The CLI expects `CLAUDE_CODE_OAUTH_TOKEN`. Mint it with `claude setup-token` and
export it before real runs. The runner intentionally strips `ANTHROPIC_API_KEY`
from the child process.

## Test Commands for Scenario Authors

Validate package tests and schema parsing without running live Claude Code:

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests -m "not integration"
```

Run the scenario-file parsing tests:

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests/test_wiki_context_scenarios.py
```

Run all package tests, including integration-marked tests that may spawn
subprocesses or require a real Claude binary:

```bash
uv run --package claude-code-evals pytest packages/claude-code-evals/tests
```

## Reading Results

Each run writes artifacts under:

```text
eval/runs/<scenario>/<config>/<timestamp>/
```

The key files are:

- `meta.json`: scenario name, config name, final run status, error reason, exit
  code, and wall time.
- `metrics.json`: token counts, tool counts, touched-file counts, and
  `verify_passed`.
- `verify.json`: verifier pass/fail details, scores, and reasons.
- `transcript.json`: raw Claude Code stream JSON plus parsed token totals.
- `preflight.log`: preflight output when present.

Start with `meta.json`:

- `final_status: success`: Claude Code emitted a successful result event.
- `final_status: completed_interactive`: an `interactive`-mode run finished when
  the `.eval-done` sentinel file appeared.
- `final_status: budget_exceeded`: `max_wall_seconds` expired (or, for
  interactive runs, the interactive wait limit expired).
- `final_status: dry_run`: `--dry-run` skipped the Claude Code invocation.
- `final_status: error_no_result`: the CLI crashed or produced no result event.
- Other `error*` statuses come from Claude Code result events.

Then inspect `verify.json`:

```json
{
  "success": false,
  "verifiers": [
    {
      "kind": "ScriptVerifier",
      "score": 0.0,
      "passed": false,
      "reason": "missing StatusBadge.tsx"
    }
  ]
}
```

`success` is true only when every verifier passes. For rubric verifiers, `score`
is normalized to 0-1 even though `pass_threshold` is specified on the 0-5 rubric
scale. A threshold of `4.0` appears as an internal threshold of `0.8`.

Use `metrics.json` to understand behavior and efficiency:

- `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`
- `turn_count`
- `tool_call_counts`
- `files_read_count`, `files_edited_count`, `files_written_count`
- `tool_calls_before_first_edit`
- `distinct_paths_touched`
- `subagent_dispatches`
- `skill_invocations_count`
- `permission_prompt_count`
- `verify_passed`

Use `transcript.json` when you need to debug why the agent behaved a certain
way. The `jsonl` field is the raw Claude Code event stream. The parsed block
contains the aggregate turn and token counts used by metrics.

## Reading Reports

`cc-eval report` and runset execution collect the latest timestamped run for
each `(scenario, config)` pair. The Markdown report summarizes:

- total pass/fail counts,
- each scenario/config pair,
- final status and error reason,
- wall seconds,
- input and output tokens,
- run directory.

The adjacent JSON report contains the same records in machine-readable form.
If a scenario has multiple timestamps for the same config, only the newest one
is included.

## Interpreting Wiki-Context Verdicts

For three-arm wiki experiments, think of the arms as:

- `base`: no wiki help.
- `injected`: relevant wiki pages are placed directly in context, representing
  the ceiling if the right knowledge is available.
- `plugin`: the graph-wiki plugin is available, so the agent must discover the
  right knowledge.

Verdict computation can return:

- `WIKI_HELPED`: wiki context changed correctness or exceeded the efficiency
  threshold.
- `NO_WIKI_VALUE`: base was sufficient, wiki did not improve enough, or even
  injected/plugin failed.
- `PLUGIN_MISS`: the wiki could help, but the plugin arm failed to retrieve or
  use it.
- `INCOMPLETE`: required scores or metrics were missing.

For `correctness-gated`, expect base to fail and injected to pass. For
`efficiency-gated`, expect plugin to reduce the declared metric by at least the
threshold. For `impossible-without-wiki`, expect base to fail and plugin to pass.

## Troubleshooting

If the run fails before verification, check `meta.json` first. Auth errors,
unknown CLI flags, missing Claude binary, and plugin-load failures usually show
up as `error_no_result` or another `error*` status with `error_reason`.

If verification fails but `final_status` is `success`, check `verify.json`. The
first failing verifier reason is usually the fastest path to the problem.

If the agent edited the wrong checkout, confirm `target_repo` and `baseline_sha`.
Worktree isolation always checks out a detached worktree from the target repo.

If a plugin scenario cannot find graph-wiki data, confirm the config's
`plugin_dirs` and `GRAPH_WIKI_WORKSPACE`. Relative plugin directories resolve
from the current working directory.

If a rubric result seems surprising, inspect `transcript.json` and the Git diff
in the kept worktree. Rubric judges see a scrubbed tool summary and truncated
assistant/diff text, not unlimited context.

If results are stale in a report, remember reports use only the latest timestamp
per scenario/config pair. Re-run the scenario or remove old run directories when
you need a clean comparison.
