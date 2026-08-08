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
