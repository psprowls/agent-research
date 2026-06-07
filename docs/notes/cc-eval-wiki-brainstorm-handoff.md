# Handoff: brainstorming the `claude-code-evals` wiki-eval design

> Primer to prime a fresh brainstorming session. Written to stand alone — a cold
> session will have none of this context. It frames questions, not answers.

## Context (what this is)
We're building an eval harness, **`packages/claude-code-evals`** (CLI: `cc-eval`), that measures whether **Graph Wiki context improves Claude Code's behavior** on a real codebase. It runs **scenario × config** pairs: spins up an isolated git worktree of a target repo at a pinned SHA, runs `claude -p` headless against a task prompt, then verifies the result with a script check (file exists / shape) + an LLM-judged rubric. Eval plans live in repo-root **`eval/`** (`scenarios/`, `configs/`, `cases/`, `baselines/`).

## What's solid now (just finished, committed)
- The harness was broken (drove a dead `--config-dir` flag → every run was a phantom pass). **Fixed**: `CLAUDE_CONFIG_DIR` isolation + `CLAUDE_CODE_OAUTH_TOKEN` (subscription-billed, from `claude setup-token`) + real `is_error`-based failure detection. 80 tests green, ruff/pyright clean.
- **Two real no-wiki baselines run clean** (worktree against `~/Personal/mono-repo` @ `551f7ed8`):
  - `wiki-design-tokens / base` -> **FAIL** rubric 0.2 (agent used `text-white`, delegated to shared `Badge` instead of its own `cva` map) - a **strong discriminator**.
  - `wiki-api-client / base` -> **PASS** rubric 1.0 - agent **read 29 files / 80 turns** and *discovered* the sanctioned `TimelineApiClient` itself - a **weak discriminator**.
- The only config today is `base.yaml` (`claude-sonnet-4-6`, **no plugins** = the no-wiki control arm).

## Open threads to brainstorm

### 1. What *is* "wiki context" in the A/B? (the core design question)
We have a no-wiki control but no positive arm. Before writing a `with-wiki.yaml`, we need to decide **how the wiki actually reaches the agent**, and the options have very different implications:
- **Plugin + on-demand query** - load `plugins/graph-wiki/` so the agent can run `/graph-wiki:query` against the mono-repo's wiki. Realistic, but depends on the agent *choosing* to query. (Where does mono-repo's wiki workspace live? Is it built/current?)
- **Pre-injected context** - put relevant wiki pages in the system prompt / a file in the worktree. Cleaner signal, less realistic.
- **MCP surface** (`graph-wiki-mcp`) vs the CC plugin - which surface are we actually evaluating?
- Open question: are we evaluating *"does having the wiki help"* or *"does the agent know to use the wiki"*? Those need different setups.

### 2. What counts as "wiki helped"? (success criteria / discriminator design)
`wiki-api-client` exposes the tension: the no-wiki agent reached the **correct** answer by brute-force exploration, so a **correctness rubric can't see the wiki's value**. Threads:
- Should success include **efficiency deltas** (turns, `files_read_count`, output tokens, wall) - which the harness *already records* - not just pass/fail?
- What makes a scenario a **good discriminator**? (Convention that's *not* discoverable by reading the repo; cross-cutting knowledge; tribal/decision context that lives only in the wiki.)
- Do we want a scenario *taxonomy* (correctness-gated vs efficiency-gated vs "impossible without wiki")?

### 3. Scenario portfolio
Two scenarios is thin for "really using it." How many, what kinds, and how do we author discriminating ones cheaply? Is there a reusable pattern/template?

### 4. Operational readiness for real use
- **Token availability**: `CLAUDE_CODE_OAUTH_TOKEN` is in `~/.zshrc` (interactive shells only). For batch/cron/CI it won't be present (non-interactive shells read `~/.zshenv`). Where should it live for unattended runs?
- **Runset + reporting**: we have `cc-eval run --runset` + a markdown/JSON report. Is the current report enough to compare arms, or do we need a wiki-vs-no-wiki **diff view**?
- **Cost/time**: each run is roughly 5 min + subscription tokens. Batch sizing / parallelism?

### 5. Merge logistics
The harness fix + this handoff are on `develop` already. Decide on push / next branch when design work starts.

## Suggested brainstorm entry point
Start with **Thread 1** - until we pin down *how the wiki reaches the agent and what we're actually measuring*, the config, scenarios, and metrics (threads 2-3) can't be designed. Threads 4-5 are operational and can trail.
