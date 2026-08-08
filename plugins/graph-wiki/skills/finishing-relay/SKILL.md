---
name: finishing-relay
description: Use when the finish stage of a work item is dispatched under auto-drive with mode relay — sends one orca orchestration ask carrying the merge/PR/hold/discard decision instead of finishing-a-development-branch's interactive menu, executes the chosen outcome, and settles the item. Dispatched by the graph-wiki:workflow skill when the `Auto-drive context:` line appears in this session's own dispatch prompt; never invoked directly by a human.
---

# Finishing a Development Branch — Relay Mode

## Overview

Relay the merge/PR/hold/discard decision to the auto-drive coordinator via
one `orca orchestration ask` instead of `finishing-a-development-branch`'s
interactive menu — this session is a dispatched worker with no human in the
terminal.

**Core principle:** Verify tests → Detect state → One ask → Execute the
choice → Settle the item and report.

**Announce at start:** "I'm using the finishing-relay skill to relay the
merge/PR/hold/discard decision for `<slug>`."

**Detection is the caller's job, not this skill's.** This skill is
dispatched only when the `graph-wiki:workflow` skill (or `/graph-wiki:next`)
already found the `Auto-drive context:` line in this session's own dispatch
prompt and routed here instead of `finishing-a-development-branch`. Nothing
in this skill re-checks that condition.

Every `orca orchestration` command below uses **this session's own**
`--from`, `--dispatch-capability`, `--task-id`, and `--dispatch-id` — the
values printed in the dispatch preamble that launched this session — never
the example values shown in this skill or in any other document.

## R1 — Verify tests

Run the project's test suite (same discovery approach as
`finishing-a-development-branch` Step 1 — `npm test` / `cargo test` /
`pytest` / `go test ./...`, whichever the repo uses).

**If tests fail:** do not stop silently and do not present options. Enter
the **Escalation path** (below) with the failure output in the escalation
body. Wait for the coordinator's instructions before doing anything else.

**If tests pass:** continue to R2.

## R2 — Detect state

Read the merge target verbatim from the `Auto-drive context:` line in this
session's dispatch prompt — never guess it via `git merge-base`:

```
Auto-drive context: relay the merge/PR/hold/discard decision via one
`orca orchestration ask`; merge target is `<branch>`.
```

Classify the current git state:

```bash
git rev-parse --abbrev-ref HEAD
git worktree list --porcelain
```

- **Detached HEAD** (`git rev-parse --abbrev-ref HEAD` prints `HEAD`): drop
  `merge` from the ask's options in R3 — the same reduction
  `finishing-a-development-branch` Step 4 makes for its 3-option menu.
- **Shared-epic-worktree case** (current branch **is** the merge target):
  the stage's commits already sit on the merge target — there is nothing to
  merge. The `merge` choice in R4 resolves to "confirm and advance" with
  `resolved_in` = current HEAD SHA (`git rev-parse HEAD`).
- **Forked-child case** (current branch differs from the merge target, not
  detached): find the worktree that has the merge target checked out by
  scanning `git worktree list --porcelain` for the block whose `branch`
  line reads `refs/heads/<merge target>`. The R4 merge executes there, not
  in this worker's own worktree.

Carry forward into R3: the merge target, the classified case, the target
worktree path (forked-child case only), commit count and one-line summary of
this stage's commits (`git log <merge-base>..HEAD --oneline` against the
merge target), and R1's test result.
