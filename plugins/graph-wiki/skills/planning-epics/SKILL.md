---
name: planning-epics
description: Use when dispatched as the `plan` stage of an epic work item — decomposes the epic into concrete child work items, runs dependency/sequence analysis, files each child via `gw work file --parent/--depends-on`, and writes the plan_doc. Sibling of writing-plans (which plans a single feature).
---

# Planning Epics

Dispatched only at the **epic `plan` stage** by the `graph-wiki:workflow` skill.
Your job is to turn the epic's design spec into real, tracked child work items
plus a dependency graph — not to write code.

**Announce at start:** "I'm using the planning-epics skill to decompose this epic."

The workspace doc-routing hook injects the resolved absolute workspace path into
your context — use it if present when you see `<workspace>` below. If `gw` is not
on PATH, run it as `uv run --package graph-wiki-cli gw …`.

## The slug/stem contract (read first)

`<epic-slug>` is the epic's **file stem** — the same value `gw work next` takes,
e.g. `2026-06-26-epic-x`. The `--parent` value MUST be that stem. Every child you
file gets its own permanent slug, derived from its title; `gw work file --json`
returns it in the `slug` field. **Note each filed child's slug from the command
output** so later `--depends-on` values name real siblings, not guesses.

## Inputs

Your dispatch brief carries the epic's `title`, `kind` (`epic`), `summary`,
`affects`, `effort`, and links to its prior artifacts. Read the work item at
`<workspace>/wiki/work/<epic-slug>.md` for current frontmatter, including its
`spec_doc` pointer (by convention `<workspace>/wiki/work/<epic-slug>/01-design-spec.md`).
Read that `spec_doc` target first — it contains one medium-detail section per
anticipated child.

## Steps

1. **Read** the epic spec and the work item.

2. **Decompose** the epic into concrete child work items — one per child
   feature/bug/etc. Choose each child's `kind`
   (`feature`, `bug`, `tech-debt`, `test-gap`, `security`, `perf`, `spike`).
   Each child should be a clean, self-contained pipeline on its own.

3. **Sequence / dependency analysis** — determine which children must precede
   others. A child is runnable only when all of its `depends_on` siblings are
   terminal, so independent children should have **no** deps (they can run
   concurrently). Capture the rationale; you write it to the plan_doc in step 5.

4. **File each child**, dependency-free / earlier children first so a later
   child can name an already-filed sibling in `--depends-on`:

   ```bash
   gw work file --json --title "<child title>" --kind <kind> \
     --summary "<one line>" --parent <epic-slug> \
     [--depends-on <sibling-slug>,<sibling-slug>]
   ```

   Read the `slug` field from each JSON result and record it before filing the
   next child. `--parent` is validated against an existing `epic`-kind item, so
   `<epic-slug>` must be the epic's file stem. If a child can only name a sibling
   filed after it (a genuine cycle of ordering, not of dependency — rare), file
   all children first, then a second pass edits the late child's `depends_on` in
   `<workspace>/wiki/work/<child-slug>.md` directly. Prefer ordering over the
   second pass.

5. **Write the plan_doc** at `<workspace>/wiki/work/<epic-slug>/02-plan-plan.md`
   (or wherever the dispatch brief's `artifact.path` points, if set): the
   decomposition rationale plus the dependency graph — which child blocks which
   and why, and which children are independent and can run in parallel. List each
   child by its filed slug and `kind`. The children **are** the executable plan,
   so there is no `## Plan` table to keep in sync and no `.tasks.json` companion —
   this doc is the human-readable record of the decomposition.

6. **STOP.** This is a single pipeline stage. Do not advance the epic, do not
   start working a child, do not invoke any execution skill. After writing the
   plan_doc, announce that the children are filed and the plan_doc is saved, and
   stop. Control returns to the `graph-wiki:workflow` skill, which advances the
   epic `plan → execute` and hands off for `/clear` + `/graph-wiki:next`.

## Notes

- **Auto-discovered.** This skill is loaded from `plugins/graph-wiki/skills/` —
  no marketplace / `plugin.json` edit is needed to register it. The
  `graph-wiki:workflow` router dispatches `skill="planning-epics"` for an epic at
  the `plan` phase.
- **Children re-run their own `design` stage.** Each child enters the pipeline at
  `phase: None` and brainstorms from scratch; the epic spec's per-child section
  seeds that brainstorm via the body pointer `gw work file` adds. The redundancy
  is intentional — it buys every child a clean, self-contained spec → plan →
  execute cycle.
