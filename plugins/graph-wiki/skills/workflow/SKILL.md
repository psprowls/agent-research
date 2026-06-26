---
name: workflow
description: Use when driving a work item through its development pipeline — runs `gw work next` to compute the stage, dispatches the stage skill (brainstorming, systematic-debugging, writing-plans, subagent-driven-development, test-driven-development, finishing-a-development-branch), verifies the artifact, and advances the item with `gw work advance`. One stage per invocation; clear context between stages.
---

# Work Item Workflow

Dispatch one pipeline stage for a work item, then advance it. The CLI owns every
decision (routing, transitions, validation); this skill only relays.

**One stage per invocation, by design.** Never chain stages in a session — each
stage gets a fresh context window. The work item plus `raw/` artifacts are the
durable state between sessions; nothing depends on conversation memory.

The workspace doc-routing hook injects the resolved absolute workspace path into your context — use it if present when you see `<workspace>` mentioned in a command or instruction.

If `gw` is not on PATH, run it as
`uv run --package graph-wiki-cli gw …`.

## Steps

### 1. Resolve & report

Run `gw next <slug> --json --file <workspace>/raw/guidance/<slug>.md`.

`gw next` wraps the read-only `gw work next` and adds two keys to the JSON:
`guidance` (ranked phase-relevant pages) and `guidance_warnings`. It also writes
the assembled guidance bodies to the `--file` path when any matched. The
`--file` parent dir is created on demand. All the blocker / terminal / dispatch
fields the steps below read are unchanged from `gw work next`.

- If `blockers` is non-empty:
  - If a blocker reports a **terminal status** (`resolved`, `wontfix`, or
    `superseded`) or **`phase=done`**, run **Terminal handling** (below): the
    pipeline is finished and the remaining work is ingest + archive.
  - Otherwise report each blocker and **stop** (the effort-required blocker is
    handled by the next bullet). Do not improvise around `mitigated` items,
    invalid enums, or unknown slugs — these are human decisions.
- If the only blocker says **effort required**: ask the user to size the item
  (xtra-small / small / medium / large / xtra-large — xtra-small/small means a bug-like item skips the planning stage),
  then run `gw work advance <slug> --effort <value>` and re-run `gw work next`.
- Otherwise announce the dispatch: item title, kind, phase, and the stage skill
  from `action.skill`.

### 2. Apply the dispatch transition (when present)

If the JSON carries a non-null `on_dispatch`, apply it mechanically **before**
dispatching: run `gw work advance <slug>`, supplying any flag named in
`on_dispatch.requires` (e.g. `--owner <handle>` when dispatching execution —
ask the user if no owner is known). Do not special-case stages; the CLI encodes
which transitions happen at dispatch time.

### 3. Dispatch the stage skill

Invoke the stage skill named by `action.skill` via the Skill tool (namespaced
`graph-wiki:<skill>`), prepending a work-item brief:

- title, kind, summary, `affects`, and effort from the item's frontmatter
- links to prior artifacts (`spec_doc`, `plan_doc`) so the stage starts from
  the durable state, not from memory
- when `artifact.path` is set: "Write your output document to
  `<artifact.path>` — this overrides the skill's default location."
- when the `gw next` output's `guidance` list is non-empty, add a
  `## Relevant guidance` block to the brief pointing the stage skill at the
  assembled bundle:

  ```
  ## Relevant guidance
  Phase-relevant guidance assembled at: raw/guidance/<slug>.md
  Read it before starting this stage.
  ```

  Omit this block entirely when `guidance` is empty (guidance skipped or no
  matches). Surface any `guidance_warnings` to the user as plain notes.
- when the dispatched `action.skill` is a chained-handoff skill, add the
  matching STOP line so its pipeline-stage guard fires (without it the skill
  self-chains into the next stage, collapsing two stages into one session):
  - dispatching `brainstorming` → add: *"STOP after writing the spec — do not
    invoke writing-plans. This is a single pipeline stage; the workflow skill
    advances the item."*
  - dispatching `writing-plans` → add: *"STOP after writing the plan — do not
    run the Execution Handoff. This is a single pipeline stage; the workflow
    skill advances the item."*
  - `systematic-debugging`, `test-driven-development`,
    `subagent-driven-development`, and `finishing-a-development-branch` need no
    STOP line — they do not self-chain into the next stage.

The stock skills honor user-preference path overrides; they stay unmodified.

### 4. Verify the artifact

When `artifact.path` is set, check the file exists after the stage completes.
If the skill wrote to its stock location (`<workspace>/raw/specs/` or
`<workspace>/raw/plans/` in the workspace), move the file (and any `.tasks.json`
companion) to `artifact.path` and say so.

### 5. Advance

Run `gw work advance <slug>` with whatever flags the stage produced
(`--effort` if the command demands it, `--resolved-in <ref>` when completing
the finish stage). Report the lint findings it returns — they are the item's
health check, not noise. If the command errors with *effort required*, ask the
user to size the item as in step 1 — never pick an effort yourself — then retry.

If the advance lands the item at `phase: done` and `status: resolved`, run
**Terminal handling** (below) instead of the step 6 hand-off.

### 6. Hand off

End with: "Phase advanced to `<phase>`. Clear context (`/clear`) and run
`/graph-wiki:next <slug>` to continue."

(Items that have reached a terminal state are handled by **Terminal handling**
below, not this hand-off.)

### Terminal handling

Run this when an item has reached a terminal state — either `gw work advance`
just landed it at `phase: done` / `status: resolved` (step 5), or `gw work next`
reported a terminal-status / `phase=done` blocker (step 1). This is post-pipeline
cleanup, not a pipeline stage — run it inline (it does not get its own fresh
context window).

1. **Ingest the spec (resolved only).** If `status` is `resolved` (from the
   `gw work next` / `gw work advance` JSON result), read the item's `spec_doc`
   from its frontmatter (`<workspace>/wiki/work/<slug>.md` — the finish→done
   transition does not re-stamp it). If `spec_doc` is set and the
   file exists at `<workspace>/<spec_doc>`, dispatch the ingest skill
   (`graph-wiki:ingest`) on that path inline; the ingestor runs its own
   confirmation dialog and, on success, archives the source and repoints the
   pointer. Skip the ingest (announce "no spec to ingest") when the status is
   `wontfix`/`superseded`, when `spec_doc` is unset (e.g. a small `test-gap`
   item that skipped design), or when the `spec_doc` file is already gone
   (already ingested). `plan_doc` ingest is a deferred future extension —
   ingest does not yet accept plan-type sources.

2. **Offer to archive (any terminal status).** Ask the user "Archive `<slug>`
   now?" If yes, run `/graph-wiki:archive <slug>`. If no, report that the item
   stays in `work/` and can be archived later with `/graph-wiki:archive`.
