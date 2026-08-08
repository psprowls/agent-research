# Auto-Drive (Orca) — Operator Guide

Auto-drive runs a work item's full pipeline unattended via Orca-supervised
worker sessions: one command dispatches each ready stage, waits for it to
settle, advances the item, and loops until the item (or an entire epic's
dependency graph) is terminal. It replaces walking `/graph-wiki:next <slug>`
one stage at a time by hand.

This is an operator runbook and reference. It restates the coordinator
loop's mechanics in full so you never need to read skill prose to run or
debug a session — each mechanics subsection below footnotes the
`auto-drive/SKILL.md` section it mirrors. The two documents can drift; treat
the skill as the executable source of truth and this doc as due for a
refresh if a footnoted section number moves.

## How-to guides

### How to set up auto-drive

1. Install Orca and enable its **Experimental orchestration** feature — the
   `orca orchestration` and `orca worktree` command groups used below only
   exist once it's on.
2. Put `gw` on `PATH` (e.g. `uv tool install` the `graph-wiki-cli` package),
   or use the `uv run --package graph-wiki-cli gw …` fallback from this
   repo's root for every `gw` command below.
3. Set `GRAPH_WIKI_WORKSPACE` to the workspace directory (the sibling
   directory holding `wiki/`, `raw/`, and `.graph-wiki/`). It's normally
   supplied by the `env` block of the repo's `.claude/settings.local.json`;
   a bare terminal needs `export GRAPH_WIKI_WORKSPACE=<path>` or
   `--workspace <path>` on each `gw` call.
4. Configure auto-drive, if you want anything other than the defaults:
   ```bash
   gw config set workflow.auto_drive.max_parallel 2
   gw config set workflow.auto_drive.permission_mode bypassPermissions
   gw config set workflow.auto_drive.models.execute sonnet
   ```
   See the [config reference](#workflowauto_drive-config-reference) below
   for every key.
5. Verify the install:
   ```bash
   orca status                              # must show a reachable runtime
   orca orchestration run-current --json    # probes the orchestration layer
   ```
   `orca status` unreachable → run `orca open`, then retry. `run-current`
   reporting an unknown command or a feature-disabled error → the
   Experimental orchestration feature isn't enabled; turn it on and retry.
6. If you previously installed the retired `gw-dispatch` background-session
   dispatcher, remove its `Notification` hook entry from your **user**
   settings (`~/.claude/settings.json`) by hand — it pointed at
   `scripts/gw-dispatch-notify.sh`, which no longer exists in this repo, and
   the repo cannot remove a user-level settings entry for you.

### How to start a run

```
/graph-wiki:auto-drive <slug>
```

A healthy start looks like: the coordinator announces it's using the
auto-drive skill, binds (or creates) a Run for `auto-drive:<slug>`, and
prints its first dispatch(es) — one line per stage it just started, naming
the slug and phase. If instead you see a precondition failure (unreachable
Orca, workspace not resolving), fix that per the setup guide above and
re-run the same command.

### How to attend a design gate

The design stage is human-attended by policy — auto-drive dispatches it like
any other stage, then stops and waits for you before the item can advance.

1. Recognize the signal: the worktree card for that dispatch flips to
   `in-review`, and the coordinator prints a join instruction (the same
   instruction is also posted as a comment on the worktree) naming the
   worker's agent terminal handle.
2. Join that worker terminal and work the design conversation normally
   (this is an ordinary `brainstorming`-driven session under the hood).
3. Once you approve the spec and the worker sends its `worker_done`, the
   coordinator flips the worktree card back to `in-progress` automatically
   and the loop continues — nothing further to do on your side.

### How to answer a finish relay

The finish stage runs in `relay` mode under auto-drive: instead of
`finishing-a-development-branch`'s interactive menu, the worker sends one
question up to your coordinator session, mirrored as a native
`AskUserQuestion`.

1. Answer with one of the offered options: `merge`, `pr`, `hold`, `discard`
   (`merge` is omitted on a detached-HEAD worker — only `pr`/`hold`/`discard`
   apply). The question text states the branch, commit count and summary,
   test result, and merge target so you can decide without leaving the
   coordinator session.
2. If you chose `discard`, a second round-trip asks for an exact `discard`
   confirmation — anything else downgrades to `hold`, and the worker's
   report says so explicitly.
3. Your answer is relayed back to the worker, which executes it (merges,
   opens a PR, does nothing, or records-not-executes the discard) and
   settles the item. Only `merge` advances the item's phase automatically;
   `pr`/`hold`/`discard` leave it at `phase: finish` for a later attended
   pass.

### How to recover a failed worker

When a dispatched worker reports `worker_done --outcome failed`, or the
coordinator finds one dead (crashed terminal, no `worker_done` ever sent),
you get one `AskUserQuestion` with exactly three options:

- **Retry** — starts a replacement worker with the same agent, model,
  effort, and worktree placement as the original dispatch.
- **Skip this item** — takes no action; the task stays in the Run at its
  current status, so this key is never re-proposed for the rest of the run.
  Nothing to clean up.
- **Stop the run** — exits the coordinator loop. For each dispatch still
  live, you're asked whether to stop its worker too.

**Manual cleanup after a coordinator crash** (the coordinator session itself
died, not a worker):

- Stop a still-running worker directly:
  `orca orchestration worker-stop --dispatch <dispatch_id>`.
- If a design-stage worktree is stuck showing `in-review` because the
  coordinator crashed before processing that worker's `worker_done`, flip it
  back by hand: `orca worktree set --worktree <selector> --workspace-status in-progress`.
- Otherwise, just re-run `/graph-wiki:auto-drive <slug>` — see *How to stop
  and resume* below; the coordinator re-derives all state from Orca and the
  vault, so a crash needs no special recovery beyond the two items above.

### How to stop and resume

**Stopping between cycles:** tell the coordinator to stop, or just end the
session. It only exits between cycles, never mid-dispatch. Any workers still
running keep running independently — you're offered
`orca orchestration worker-stop --dispatch <id>` for each live dispatch
before the session ends, but declining leaves them live and unsupervised
until you attend to them separately.

**Resuming:** re-run the exact same command, `/graph-wiki:auto-drive <slug>`.
There is no `--resume` flag — the Run re-binds by its `auto-drive:<slug>`
objective string, which is the sole slug → Run mapping. The first cycle of
the resumed session re-derives every task's live/settled/dead state from
Orca before doing anything else, so a fresh session with zero conversation
history resumes identically to one that had been running for hours.

## Reference

### The coordinator loop

One iteration, in order — re-run from the top on every `advances[]`
non-empty result, on every processed message batch, and on every wait
timeout that finds a dead worker. Nothing is trusted across iterations
within a session; everything is re-derived from Orca and the vault each
time.[^cycle]

1. **Derive live keys.** List the Run's tasks
   (`orca orchestration task-list --run <run_id> --json`) — every task's
   title is a dispatch key `<slug>#<phase>`, and this task list is the
   loop's sole dedupe ledger. For each task not already settled, query
   `orca orchestration worker-show --dispatch <dispatch_id> --json`:
   `ready`/`running` → live; `failed`/`stopped`/unreachable → failure
   flow.[^live]
2. **Plan.** `gw work orchestrate <slug> --live <key,...> --json` (omit
   `--live` on the very first plan call — nothing is live yet). Returns:
   - `terminal` (bool), `max_parallel` / `slots_free` (ints),
     `permission_mode` (str), `live` (echoed input).
   - `dispatches[]` — one entry per stage ready to run: `key`, `slug`,
     `phase`, `kind`, `effort`, `skill`, `mode`
     (`autonomous` | `attend` | `relay`), `model` (`null` = inherit),
     `reasoning_effort`, `worktree` (`action`, `path`, `branch`,
     `base_branch`, `exists`), `merge_target`, `prompt`.
   - `advances[]` — `slug` + `reason`, items whose phase should move without
     a dispatch.
   - `blocked[]` — `slug`, `kind`, `reason`. `kind` is always one of exactly
     seven values: `deps`, `capacity`, `affects-overlap`,
     `effort-required`, `human`, `worktree-pending`, `invalid`.
   - `warnings[]` — plain strings (e.g. a stale `--live` key). Informational
     only, never a blocker.[^plan]
3. **Terminal check.** `terminal: true` → wrap-up (below), stop looping —
   nothing else in the cycle runs.[^terminal]
4. **Advances.** `gw work advance <slug>` for every `advances[]` entry. If
   any ran, the plan just read is stale — restart the cycle at step 1
   without acting on the rest of it.[^advances]
5. **Blockers.** `effort-required` → ask the operator to size the item
   (`AskUserQuestion`, native — this is the coordinator's own human, not a
   worker relay), then `gw work advance <slug> --effort <value>` and restart
   at step 1. Every other kind: print `blocked <slug> (<kind>): <reason>`
   and take no action — `capacity`/`worktree-pending` resolve themselves
   next cycle; `deps`/`affects-overlap`/`human`/`invalid` need a human
   decision outside the loop.[^blockers]
6. **Dispatch diff.** Dispatch only `dispatches[]` entries whose key has no
   existing task in step 1's list — a key with a task is live, settled, or
   an intentional skip; leave it alone either way.[^diff]
7. **Wait.**
   ```
   orca orchestration check --run <run_id> --wait \
     --types worker_done,escalation,question --timeout-ms 600000 --json
   ```
   On delivery: process every message in the batch (see *Message types*
   below) before acking with the delivery id, then restart at step 1. On
   timeout with nothing delivered: `worker-show` every still-live dispatch —
   all still `ready`/`running` → wait again; any dead → failure flow, then
   restart at step 1.[^wait]

**Dispatch mechanics**[^dispatch] — for each undispatched `dispatches[]`
entry: create a task with the plan's `prompt` verbatim
(`orca orchestration task-create --run <run_id> --spec "<prompt>" --task-title "<key>" --json`),
start a worker
(`orca orchestration worker-start --task <task_id> --agent claude --run <run_id> --json`,
plus `--model`/`--effort` when the plan set them, plus the worktree flags for
the plan's `worktree.action` — `reuse` passes `--worktree path:<path>` only;
`fork-child` passes `--worktree new-child --name <branch> --base-branch <base_branch>`;
`create-top-level` adds `--repo <selector>`), and — for `attend`-mode
dispatches only — flip the worktree card to `in-review` with a join comment
(`orca worktree set --worktree <selector> --workspace-status in-review --comment "..."`).
Finally mark the task `in_progress`
(`orca orchestration task-update --id <task_id> --status in_progress --run <run_id>`)
so the next cycle's task-list reflects it.

### Message types

| Type | Sent by | Coordinator handling |
| --- | --- | --- |
| `worker_done` (`succeeded`) | any worker on completion | Mark the task `completed`, release the dispatch's terminal, flip an attend-pending worktree card back to `in-progress`. Nothing else — the next plan call picks up the new state. |
| `worker_done` (`failed`) | any worker on completion | Run the failure question (retry / skip / stop) — see *How to recover a failed worker*. |
| `question` | a `relay`-mode (finish-stage) worker | Mirror the question text and options to the operator as one native `AskUserQuestion`, then relay the reply back with `orca orchestration reply --id <message_id> --body "<answer>" --run <run_id>`. A typed-`discard` confirmation is just a second question/reply round-trip, handled the same way. |
| `escalation` | any worker | Surface the message body to the operator and ask, free-form, how to proceed. Doesn't have to block the loop unless the operator says so; a reply is relayed with `orca orchestration reply`. |
| heartbeat | any worker | **Never delivered here** — heartbeats aren't in the `check --wait --types` list. Liveness between message deliveries is checked only via `worker-show` on wait timeout. |

### Worktree & branch lifecycle

Every dispatch's `worktree.action` is one of three values, decided entirely
by `gw work orchestrate` (the coordinator never picks one itself):

- **`reuse`** — an existing worktree already checked out at the right
  branch; started with `--worktree path:<path>` and no creation flags (the
  CLI rejects creation flags for an existing worktree).
- **`fork-child`** — a new worktree forked as a child of the coordinator's
  own worktree, inheriting its parent implicitly; started with
  `--worktree new-child --name <branch> --base-branch <base_branch>`.
- **`create-top-level`** — a brand-new top-level worktree on the resolved
  repo; started with `--worktree new-top-level --name <branch> --base-branch <base_branch> --repo <selector>`.

**Merge-backs:** only the root work item's finish stage merges to
`develop` — child/epic branches merge back into their parent epic's branch,
never directly to `develop`. Each settled dispatch's `merge_target` in the
plan output names where its finish stage will merge.

**The `affects`-disjoint parallelism rule:** two dispatches can run in
parallel only when their `affects` lists don't overlap. An item with an
**empty** `affects` list is treated as blocking, not as automatically safe
to parallelize — declaring `affects` is what unlocks parallel dispatch for
an item, and the `affects-overlap` blocked-kind reason string distinguishes
the empty-list case from a real overlap.

**Frontmatter stamps:** `gw work advance` writes the `worktree` and
`branch` fields on the item's frontmatter page as part of applying a
dispatch or advance — these are the durable record of where a stage's work
happened, read back by later cycles and by this doc's own worktree-action
descriptions above.

### `workflow.auto_drive` config reference

Read with `gw config get workflow.auto_drive.<key>`; write with
`gw config set workflow.auto_drive.<key> <value>` (except `overrides`,
manifest-only — see below). Every key lives under
`<workspace>/.graph-wiki.yaml`.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `max_parallel` | int | `2` | Concurrent auto-drive worker sessions across a Run. Example: `gw config set workflow.auto_drive.max_parallel 4`. |
| `permission_mode` | str | `bypassPermissions` | Permission mode for auto-drive worker sessions; anything stricter turns every write into a permission block. Example: `gw config set workflow.auto_drive.permission_mode bypassPermissions`. |
| `models.design` | str | unset (inherit coordinator session model) | Model override for design-stage workers. Example: `gw config set workflow.auto_drive.models.design opus`. |
| `models.plan` | str | unset (inherit coordinator session model) | Model override for plan-stage workers. Example: `gw config set workflow.auto_drive.models.plan sonnet`. |
| `models.execute` | str | unset (inherit coordinator session model) | Model override for execute-stage workers. Example: `gw config set workflow.auto_drive.models.execute sonnet`. |
| `models.finish` | str | unset (inherit coordinator session model) | Model override for finish-stage workers. Example: `gw config set workflow.auto_drive.models.finish sonnet`. |
| `overrides` | list | unset | First-match-wins model override rules keyed by phase/kind/effort — manifest-only, hand-edit `workflow.auto_drive.overrides` in `<workspace>/.graph-wiki.yaml`; not settable via `gw config set`. Rules may also set `reasoning_effort`. |

[^cycle]: `auto-drive/SKILL.md` §2 ("The cycle").
[^live]: `auto-drive/SKILL.md` §2.1 ("Derive live keys").
[^plan]: `auto-drive/SKILL.md` §2.2 ("Plan").
[^terminal]: `auto-drive/SKILL.md` §2.3 ("Terminal?").
[^advances]: `auto-drive/SKILL.md` §2.4 ("Advances").
[^blockers]: `auto-drive/SKILL.md` §2.5 ("Blockers").
[^diff]: `auto-drive/SKILL.md` §2.6 ("Dispatch diff").
[^wait]: `auto-drive/SKILL.md` §2.7 ("Wait").
[^dispatch]: `auto-drive/SKILL.md` §3 ("Dispatch mechanics").
