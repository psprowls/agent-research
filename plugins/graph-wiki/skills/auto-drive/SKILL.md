---
name: auto-drive
description: Use when driving a work item's full pipeline unattended via Orca-supervised workers — an epic's entire dependency graph or a lone item's phase sequence — instead of walking one /graph-wiki:next stage at a time by hand. Runs a stateless plan/act/wait coordinator loop over `gw work orchestrate` and the Orca orchestration CLI — binds a Run, dispatches ready stages as supervised workers, handles the design (attend) and finish (relay) human gates, processes worker_done/question/escalation, and resumes cleanly after a crash or restart by re-deriving everything from Orca + the vault.
---

# Auto-Drive Coordinator

Drive a work item's pipeline end-to-end by dispatching each ready stage as a
supervised Orca worker and looping until the item is terminal. The CLI owns
every decision (`gw work orchestrate` computes readiness, worktree, model,
and the full worker prompt) — this skill only relays: it never picks a
worktree, a model, or a stage on its own.

**Announce at start:** "I'm using the auto-drive skill to run the coordinator
loop for `<slug>`."

This session **is** the coordinator — a human-attended session, not itself a
dispatched worker. Wherever this skill says "ask the user," that means the
native `AskUserQuestion` tool, talking to the person running this session.
`orca orchestration ask`/`reply` is a *different* channel: it carries
questions a dispatched *worker* sends up to this coordinator (see §4.3) — it
is never how this skill talks to its own human.

If `gw` is not on PATH, run it as `uv run --package graph-wiki-cli gw …`.

## 0. Preconditions

Check once at the start of the session. Any failure stops with a plain
explanation — no degraded mode, no partial loop:

1. `orca status` — must show a reachable runtime. If unreachable: stop and
   tell the user to run `orca open`, then retry.
2. `orca orchestration run-current --json` — probes that Orca's
   orchestration layer is available on this install. An "unknown command" or
   feature-disabled error means the Experimental orchestration feature isn't
   enabled; stop and say so (do not try to work around it).
3. `gw` resolvable: bare `gw --help` on PATH, else
   `uv run --package graph-wiki-cli gw --help` from the workspace's repo
   root.
4. Workspace resolves: `GRAPH_WIKI_WORKSPACE` is set, or discovery from cwd
   succeeds. `gw work status` fails loudly if not — treat that failure as a
   precondition failure, not a mid-loop error.

Resolve the repo selector once here, too — it's static for the whole
session: `orca repo list --json`, find the entry whose path matches the
resolved repo, and remember its selector for `--repo` in dispatch mechanics
(§3). This is environment lookup, not orchestration state, so caching it for
the session does not violate the "never trust session memory" rule below —
that rule is about *Run/task* state, not static repo identity.

## 1. Run bind

The Run's objective string is the stable join key for this slug:
`auto-drive:<slug>`. Nothing else maps slug → Run — this lookup **is** the
entire resume mechanism. Re-running `/graph-wiki:auto-drive <slug>` always
re-derives the Run this way; there is no separate `--resume` flag.

1. `orca orchestration run-list --json` and scan for an entry whose
   `objective` exactly equals `auto-drive:<slug>`.
2. Found → `orca orchestration run-use --id <run_id>`.
3. Not found → `orca orchestration run-create --objective "auto-drive:<slug>"`
   (this also binds this terminal to the new Run).

Every command in the rest of this skill passes `--run <run_id>` explicitly —
don't rely on implicit terminal binding once other dispatches may exist.

## 2. The cycle

Loop until Wrap-up (§5) or the user says stop. Each iteration is
self-contained — never trust anything from a previous iteration in this same
session; re-derive from Orca + the vault every time. This is what makes
crash/compaction resume the same code path as a normal cycle.

### 2.1 Derive live keys

1. `orca orchestration task-list --run <run_id> --json`. Every task's
   `--task-title` was set to a dispatch key (`<slug>#<phase>`) at creation
   (§3) — this task mirror is the dedupe ledger for the whole loop.
2. For each task not already marked `completed`/`failed` by a prior
   `task-update` (§4.1), run
   `orca orchestration worker-show --dispatch <dispatch_id> --json` and read
   `result.worker.state`:
   - `ready` or `running` (any non-terminal state) → **live**.
   - `failed`, `stopped`, or the dispatch is unreachable (vanished terminal,
     `worker-show` reports not-found) → **failure flow** (§4.2).
3. Build the `--live` key list for §2.2 from every task classified live.

### 2.2 Plan

`gw work orchestrate <slug> --live <key,...> --json` (workspace resolves via
`GRAPH_WIKI_WORKSPACE`; omit `--live` on the very first plan call of a fresh
Run — there's nothing live yet). The result:

- `terminal` (bool), `max_parallel` / `slots_free` (ints), `permission_mode`
  (str, default `bypassPermissions`), `live` (the echoed input list).
- `dispatches[]` — each entry: `key` (`<slug>#<phase>`), `slug`, `phase`,
  `kind`, `effort`, `skill`, `mode` (`autonomous` | `attend` | `relay`),
  `model` (`null` = inherit, omit `--model`), `reasoning_effort`,
  `worktree` (`action`: `reuse` | `fork-child` | `create-top-level`, `path`,
  `branch`, `base_branch`, `exists`), `merge_target`, `prompt`.
- `advances[]` — each: `slug`, `reason`.
- `blocked[]` — each: `slug`, `kind` (one of exactly `deps`, `capacity`,
  `affects-overlap`, `effort-required`, `human`, `worktree-pending`,
  `invalid`), `reason`.
- `warnings[]` — plain strings (e.g. a stale `--live` key matching nothing).
  Print these as notes; they are not blockers.

### 2.3 Terminal?

`terminal: true` → go to Wrap-up (§5) and stop looping. Nothing else in this
cycle runs.

### 2.4 Advances

For every entry in `advances[]`: `gw work advance <slug from entry>`. If
`advances[]` was non-empty, the plan you just read is now stale — restart
the cycle at §2.1 (skip §2.5–2.7 this iteration; don't act on a plan you
know is out of date).

### 2.5 Blockers

- **`effort-required`**: ask the user — via `AskUserQuestion`, this is the
  coordinator's own human, not a worker relay — to size the item
  (xtra-small / small / medium / large / xtra-large). Run
  `gw work advance <slug> --effort <value>`, then restart the cycle at §2.1.
- **Every other kind** (`deps`, `capacity`, `affects-overlap`, `human`,
  `worktree-pending`, `invalid`): print one line each
  (`blocked <slug> (<kind>): <reason>`) and take no action. `capacity` and
  `worktree-pending` resolve themselves next cycle as slots/worktrees free
  up; `deps`, `affects-overlap`, `human`, and `invalid` need a human decision
  outside this loop. Note: `affects-overlap` fires both on a real overlap
  *and* on an item with an empty `affects` list (declaring `affects` is what
  unlocks parallel dispatch) — don't report an empty-`affects` block to the
  user as "another dispatch is using this," the reason string already says
  which case it is.

### 2.6 Dispatch diff

Dispatch only `dispatches[]` entries whose `key` has **no existing task** in
§2.1's `task-list` output — the task mirror is the sole dedupe ledger. A key
with a task is live, settled, or an intentional skip (§4.1); in every case,
leave it alone. For each undispatched entry, run Dispatch mechanics (§3).

### 2.7 Wait

```
orca orchestration check --run <run_id> --wait \
  --types worker_done,escalation,question --timeout-ms 600000 --json
```

- **On delivery:** process **every** message in the batch (§4) before
  acking. Then acknowledge with the delivery id from the response:
  `orca orchestration check --run <run_id> --ack <delivery_id>` (a bound Run
  replays the same delivery until acked — don't ack before every message in
  the batch is handled). Restart the cycle at §2.1.
- **On timeout with nothing delivered:**
  `orca orchestration worker-show --dispatch <id> --json` for every
  still-live dispatch. All still `ready`/`running` → loop back into another
  `--wait`. Any `failed`/`stopped`/unreachable → failure flow (§4.2), then
  restart the cycle at §2.1.

## 3. Dispatch mechanics

For each planned-but-undispatched entry from §2.6:

1. ```
   orca orchestration task-create --run <run_id> \
     --spec "<dispatches[].prompt, verbatim>" \
     --task-title "<key>" --display-name "<slug> · <phase>" --json
   ```
   Capture `task_id` from the result. The `prompt` is exactly what
   `gw work orchestrate` assembled — never edit, wrap, or re-word it; it
   already contains the `Dispatch key:` line and the worker's own
   `Send worker_done` instruction.
2. `orca orchestration worker-start --task <task_id> --agent claude --run <run_id> --json` plus:
   - `model` non-null → `--model <model>`; `reasoning_effort` non-null →
     `--effort <reasoning_effort>` (only when `model` is also set —
     `--effort` requires `--model` on this CLI).
   - Worktree action `reuse` → `--worktree path:<worktree.path>` only — no
     creation flags (`--name`/`--repo`/`--base-branch`), which the CLI
     rejects for an existing worktree.
   - Worktree action `fork-child` → `--worktree new-child --name <worktree.branch> --base-branch <worktree.base_branch>`.
     **Live-validation item:** `worker-start` has no `--parent-worktree`
     flag; `new-child` is expected to infer its parent from this
     coordinator's own worktree context (which is the epic worktree per the
     shared-epic-worktree design). Confirm this on the first real dispatch.
   - Worktree action `create-top-level` → `--worktree new-top-level --name <worktree.branch> --base-branch <worktree.base_branch> --repo <repo selector resolved in §0>`.
   - **Live-validation item:** `worktree.branch` values are slash-containing
     (e.g. `epic/orca-auto-drive-pipeline`); confirm `--name` accepts that
     verbatim as the git branch name rather than treating it as a display
     name with a derived branch. Adjust this mapping if not.
   - The plan's top-level `permission_mode` (default `bypassPermissions`) is
     the intended permission mode for the launched agent — state it as
     context, not a flag; `worker-start` has no `--permission-mode` flag
     today.
   - A non-zero exit, or a result reporting `failed`/`outcome_unknown`, is a
     failed dispatch: go straight to the failure flow (§4.2) — surface the
     JSON's `stage`/`failedStage`/`recovery` hints to the user, don't
     silently retry.
3. **Attend dispatches only** (`mode: attend` — the design stage), after a
   successful start:
   - `orca worktree set --worktree <same worktree selector used above> --workspace-status in-review --comment "auto-drive: <slug> design stage waiting for you — join <agent_terminal_handle>"`.
   - Print the same join instruction directly in this session — the human
     is already here, no orca call needed for that half.
   - Remember this dispatch's key as attend-pending for this Run, so its
     `worker_done` (§4.1) triggers the flip-back to `in-progress`.
4. `orca orchestration task-update --id <task_id> --status in_progress --run <run_id>`
   so the next cycle's `task-list` (§2.1) reflects it as an existing task.

## 4. Delivery processing

Handle every message in the `check --wait` batch (§2.7) — one at a time —
before acking.

### 4.1 `worker_done`

- **`outcome: succeeded`**:
  `orca orchestration task-update --id <task_id> --status completed --run <run_id>`
  → `orca orchestration worker-release --dispatch <dispatch_id> --run <run_id>`
  → if this key was attend-pending (§3), flip the card back:
  `orca worktree set --worktree <selector> --workspace-status in-progress`
  → nothing else; the next cycle's plan (§2.2) picks up the new state
  naturally.
- **`outcome: failed`**: run the **failure question**, below.

### Failure question

Used from two places: `worker_done --outcome failed` (above) and a dead
worker discovered outside any `worker_done` message (§2.1 or §2.7's
wait-timeout `worker-show`) — the design's no-auto-retry policy applies to
both identically, so it's specified once here, not duplicated.

One `AskUserQuestion` with exactly three options — *retry* / *skip this
item* / *stop the run*:

- **Retry**: `orca orchestration worker-start --task <task_id> --retry-of <dispatch_id> --run <run_id> --json`,
  repeating the *same* agent/model/effort/worktree placement as the original
  dispatch — `--retry-of` links the replacement attempt but does not
  inherit placement; you must repeat it explicitly.
- **Skip**: do nothing. The task stays in the Run at its current status, so
  §2.6's dispatch diff never re-proposes that key this run — the task
  mirror itself is the skip record, no session memory involved.
- **Stop the run**: exit the loop. Report run state (what's done, what's
  live, what's blocked). For each still-live dispatch, ask (plain text) if
  the user wants `orca orchestration worker-stop --dispatch <id> --run <run_id>`,
  then stop.

### 4.2 Failure flow (dead worker found outside a `worker_done` message)

Identical to the `outcome: failed` branch above — run the failure question.
Triggered from §2.1's live-derivation or §2.7's wait-timeout `worker-show`.

### 4.3 `question` (finish-stage relay)

A worker in `relay` mode (the finish stage) sends this via its own
`orca orchestration ask` when it needs the merge/PR/hold/discard decision —
this coordinator only relays it, it does not interpret the question
(deciding what the options mean is child 5's / the worker's job).

1. Mirror the message's question text and options to the user as one
   `AskUserQuestion` in this session.
2. `orca orchestration reply --id <message_id> --body "<the user's answer>" --run <run_id>`.
3. A typed-`discard` confirmation some finish flows require is just a
   second question/reply round-trip initiated by the worker — handle it the
   same way, no special-casing here.

### 4.4 `escalation`

Surface the message body to the user and ask, free-form (not a forced
multiple-choice `AskUserQuestion`), how to proceed. If the user wants to
send something back to the worker:
`orca orchestration reply --id <message_id> --body "<reply>" --run <run_id>`.
Otherwise just note it and continue — an escalation doesn't have to block
the loop unless the user says so.

Worker heartbeats are never in `--types` (§2.7), so they're never delivered
here; liveness between deliveries is checked only via `worker-show` on
wait-timeout.

## 5. Resume & wrap-up

**Resume** is just re-running `/graph-wiki:auto-drive <slug>` (§1 re-binds
the same Run by objective). Cycle 1's live-derivation (§2.1) classifies
every existing task — live, settled, or dead — before anything else
happens; dead dispatches enter the failure flow immediately. Nothing is
reconstructed from conversation memory: a fresh session with zero context
resumes identically to one that's been running for hours.

**Wrap-up** (§2.3 reported `terminal: true`):

1. `orca orchestration worker-release --dispatch <id> --run <run_id>` for
   any dispatch still holding a terminal that settled successfully but
   wasn't released yet.
2. Print a run summary: items resolved, branches merged back (from each
   settled dispatch's `merge_target`), anything skipped (§4.1's skip
   choices this run), anything left in `blocked[]`.
3. Stop. Merging the epic branch to `develop` is **not** this coordinator's
   job — it happens inside the root item's finish-relay stage (child 5's
   scope), not here.

**User stop** (mid-run, on explicit instruction): exit the loop between
cycles — never mid-dispatch. Live workers keep running independently; offer
`orca orchestration worker-stop --dispatch <id> --run <run_id>` for each one
before exiting — same mechanics as the failure question's Stop branch
(§4.1).

## Out of scope

- Any dispatch-decision logic — readiness, worktree choice, model, prompt
  assembly, parallelism caps, `affects` serialization — all owned by
  `gw work orchestrate`. A wrong-looking plan (bad worktree action, a
  missing blocker kind, a bad prompt) gets filed against the decision-engine
  work item; never patched around in this skill's prose.
- Finish-stage relay behavior *inside* the worker — deciding what the
  merge/PR/hold/discard options mean and sending the `ask` — child 5's
  scope. This skill only mirrors the `question` it receives (§4.3).
- A vault-wide watcher or scheduled sweep mode. Orca automations may invoke
  this skill later; today it drives exactly one slug per invocation.
- Auto-retry of failed stages, and automatic merge-conflict resolution for
  parallel forks — both explicit policy (see the failure question and the
  `affects`-disjoint rule), not gaps.
