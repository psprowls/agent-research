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

If `gw` is not on PATH, run it as
`uv run --package graph-wiki-cli gw …`.

## Steps

### 1. Resolve & report

Run `gw work next <slug> --json`.

- If `blockers` is non-empty: report each blocker and **stop**. Do not improvise
  around a blocker — terminal/mitigated items, invalid enums, and unknown slugs
  are all human decisions.
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

The stock skills honor user-preference path overrides; they stay unmodified.

### 4. Verify the artifact

When `artifact.path` is set, check the file exists after the stage completes.
If the skill wrote to its stock location (`docs/superpowers/specs/` or
`docs/superpowers/plans/` in the repo), move the file (and any `.tasks.json`
companion) to `artifact.path` and say so.

### 5. Advance

Run `gw work advance <slug>` with whatever flags the stage produced
(`--effort` if the command demands it, `--resolved-in <ref>` when completing
the finish stage). Report the lint findings it returns — they are the item's
health check, not noise. If the command errors with *effort required*, ask the
user to size the item as in step 1 — never pick an effort yourself — then retry.

### 6. Hand off

End with: "Phase advanced to `<phase>`. Clear context (`/clear`) and run
`/graph-wiki:next <slug>` to continue."

When the item reaches `phase: done`, report the resolution (`resolved_in`) and
suggest `/graph-wiki:archive` once the item ages out.
