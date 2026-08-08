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

## R3 — One ask

Send exactly one `orca orchestration ask`, using this session's own
`--from` / `--dispatch-capability` from its dispatch preamble:

```
orca orchestration ask --from <this session's --from> \
  --dispatch-capability <this session's --dispatch-capability> \
  --question "Finish stage for <slug> on branch <current branch> ready to settle. <N> commit(s): <one-line summary>. Tests: <pass/fail summary>. Merge target: <merge target>. How should this be handled?" \
  --options "<merge,pr,hold,discard — or pr,hold,discard on detached HEAD>" \
  --timeout-ms 600000
```

`ask` blocks until the coordinator replies and prints the reply body — there
is no separate poll/fetch step. **Live-validation item:** if the call times
out or disconnects, the resume mechanism is not a documented flag in this
session's own preamble (see CLI Reference); check
`orca orchestration ask --help` for the real resume syntax before sending a
second, duplicate question.

The reply body is one of the option labels (`merge`, `pr`, `hold`,
`discard`). Any other reply text: treat it as `hold` and note the verbatim
reply in the R5 report — don't guess at unrecognized intent.

## R4 — Execute the choice

### `merge`

- **Shared-epic-worktree case:** no-op merge — the commits are already on
  the merge target. Skip straight to R5 with `resolved_in` = the HEAD SHA
  captured in R2.
- **Forked-child case:**
  ```bash
  git -C <target worktree path from R2> merge <this worker's branch>
  ```
  **Conflicts:** never auto-resolve (parent-epic policy). Enter the
  **Escalation path** with the conflict file list in the body; wait for
  instructions.
  **On a clean merge:** re-run the test suite (R1's command) in the target
  worktree, on the merged result. **Failing tests post-merge:** enter the
  Escalation path — the merge already happened, so the escalation body must
  say so explicitly (don't let the coordinator think it's still pending).
  Continue to R5 with `resolved_in` = the merge commit SHA
  (`git -C <target worktree path> rev-parse HEAD`).

### `pr`

```bash
git push -u origin <this worker's branch>
gh pr create --title "<slug title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] <verification steps>
EOF
)"
```

Reuses `finishing-a-development-branch`'s Option 2 body template verbatim.
Continue to R5 with the PR URL.

### `hold`

Nothing to execute. Continue to R5.

### `discard`

Send a second, option-less `ask` asking for exact confirmation:

```
orca orchestration ask --from <this session's --from> \
  --dispatch-capability <this session's --dispatch-capability> \
  --question "Confirm discard of <slug> branch <branch> (<N> commits: <list>). Reply exactly 'discard' to confirm, anything else cancels." \
  --timeout-ms 600000
```

- Reply is exactly `discard` → confirmed. **Discard is recorded, not
  executed**: delete nothing. Continue to R5 with the branch name and commit
  list for the report — the human removes the branch/worktree later, after
  Orca releases it (see Worktree & branch ownership, below).
- Any other reply → downgrade to `hold`; say so explicitly in the R5 report
  (state the reply that caused the downgrade).
