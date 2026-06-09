# graph-wiki:workflow — status/kind-driven superpowers dispatch

**Date:** 2026-06-09
**Status:** approved design

## Problem

The superpowers skills (brainstorming, writing-plans, systematic-debugging, subagent-driven-development, …) were forked into `plugins/graph-wiki/skills/` as unmodified copies, with five passive delegation commands. Nothing connects them to the wiki's work-item lifecycle: the user must remember which skill comes next for each item, statuses are hand-edited, and skill artifacts land in the repo (`docs/superpowers/`) instead of the workspace.

This design adds a dispatcher: given a work item, look at its status, kind, and pipeline position, launch the appropriate stage skill, and advance the item when the stage completes. Each stage runs in a fresh context window; the user clears context and re-runs the workflow command between stages.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Where pipeline state lives | New `phase` frontmatter key; `VALID_STATUSES` untouched |
| v1 kind handling | Routing table only; stock skills unmodified; variant skills (e.g. `brainstorming-spike`, lighter review for bugs) are later one-row routing changes |
| Artifact location | Workspace `raw/specs/` and `raw/plans/` (ingest-compatible; ingest support later) |
| Dispatch mechanism | CLI-backed: `gw work next` (read-only decision) + `gw work advance` (single mutation point) |
| Bug routing | systematic-debugging replaces brainstorming; effort-keyed shortcut for small bugs |
| `effort` field | T-shirt enum {xs, s, m, l, xl}; workflow prompts when missing and a routing decision needs it |

## 1. Phase model

New frontmatter key `phase`, owned by the workflow machinery. Items filed outside the workflow have no phase. The value names **the next stage to run**:

| `phase` | Meaning | Stage skill |
|---|---|---|
| *(absent)* | never entered the workflow | first dispatch sets it |
| `design` | needs brainstorming / root-cause | brainstorming or systematic-debugging |
| `plan` | spec exists, needs implementation plan | writing-plans |
| `execute` | needs implementation | subagent-driven-development (or TDD on the shortcut path) |
| `finish` | implementation done, needs integration | finishing-a-development-branch |
| `done` | pipeline complete | nothing — report and exit |

**Status semantics are unchanged.** Status = commitment/disposition (what lint, archive, and `gw work status` already understand); phase = pipeline position. The workflow advances status at the points the existing lint rules expect:

- Items stay `open` through design *and* planning. Status becomes `accepted` when the plan lands, and `advance` syncs a row into the work item's `## Plan` table at that moment — satisfying rule 4 (`accepted-without-plan`) by construction. (Setting `accepted` after brainstorming alone would make every brainstormed-not-yet-planned item a rule-4 error.)
- Dispatching execution sets `in-progress` + `owner` (rule 5).
- Completing `finish` sets `resolved` + `resolved_in` (rule 6) and `phase: done`.
- The small-bug shortcut skips `accepted` entirely (`open` → `in-progress` is a legal jump), so no plan table is required for items that never get a plan.
- Terminal statuses (`resolved`, `wontfix`, `superseded`) and `mitigated` never dispatch — the workflow reports and exits. Disposition decisions stay human; a mitigated item re-enters the pipeline only by a human flipping it to `open`.

## 2. Routing table (v1)

Lives as data in `work_io/workflow.py`: a pure function over `(kind, status, phase, effort)` returning an action. Kind variants later are one-row edits.

**First dispatch** (status `open`, no `phase`):

| Kind | Design-stage skill |
|---|---|
| `feature`, `initiative`, `spike` | brainstorming |
| `bug`, `security`, `perf` | systematic-debugging |
| `tech-debt` | brainstorming (refactors need design, not diagnosis) |
| `test-gap` | skips design → `plan`, or straight to `execute` when effort ∈ {xs, s} (the gap is identified at filing time; the effort fork applies at first dispatch since there is no design stage to advance out of) |

**Advancing out of `design`** — the effort fork:

- `effort` ∈ {xs, s} **and** kind is bug-like ({`bug`, `security`, `perf`, `tech-debt`, `test-gap`}) → jump to `execute` (small-bug shortcut).
- Everything else → `plan`. Features/initiatives/spikes always take the full pipeline in v1.
- If the decision needs `effort` and it's missing, the workflow skill prompts the user to size the item and writes it back.

**`plan`:** all kinds → writing-plans.

**`execute`:**
- Came through `plan` → subagent-driven-development (executes the written plan task-by-task with per-task review).
- Shortcut path (no plan) → test-driven-development, seeded by the systematic-debugging findings.

**`finish`:** all kinds → finishing-a-development-branch. On completion: `resolved` + `resolved_in`, `phase: done`.

Known v1 compromise: spikes going through writing-plans is heavyweight; a `brainstorming-spike` / lighter-spike variant is the first candidate follow-up.

## 3. CLI commands

Pattern: pure logic in `work-io`, async command functions in `graph_wiki_core/commands/work.py`, thin Typer wrappers in `graph-wiki-cli`. No Bedrock dependency — deterministic file I/O only, so it runs in the plugin context.

### `gw work next <slug> --json` (read-only)

1. Resolves the workspace like the other `gw work` commands (`GRAPH_WIKI_WORKSPACE` → `.graph-wiki.local.yaml` → discovery), so out-of-repo workspaces work.
2. Loads the item, validates enums, computes the action from the routing table.
3. Prints JSON:

```json
{
  "slug": "2026-06-09-fix-login-timeout",
  "status": "open", "kind": "bug", "phase": "design", "effort": null,
  "action": {"skill": "systematic-debugging", "reason": "bug at design stage"},
  "artifact": {"path": "/abs/workspace/raw/specs/2026-06-09-fix-login-timeout.md"},
  "on_complete": {"phase": "plan-or-execute", "status": "open", "requires": ["effort"]},
  "blockers": []
}
```

Terminal/`mitigated` items, unknown slugs, or lint-precondition failures land in `blockers` with a non-zero exit.

When a stage needs a transition *before* dispatch (the execute stage, below), the JSON also carries an `on_dispatch` object (`{"phase": ..., "status": "in-progress", "requires": ["owner"]}`) so the skill applies it mechanically rather than special-casing the stage.

### `gw work advance <slug> [--effort X] [--owner X] [--resolved-in X]` (single mutation point)

Applies the routing table's completion transition for the item's current phase: sets new `phase` (and `status` when the table says so), stamps `updated`, writes passed field flags, regenerates the sidecar, re-runs lint on the item and reports findings.

- **Effort fork at advance time:** advancing a bug-like item out of `design` requires effort (on the item or `--effort`) because the next phase depends on it; the command errors clearly otherwise. That error is the skill's prompt hook — no separate `gw work set` command.
- **Plan-table sync:** when `advance` moves an item to `accepted`, it inserts a row into the work item's `## Plan` table linking the plan artifact (via existing `plan_table.py` shapes), so rule 4 passes by construction.
- **Two-step execute transition:** subagent-driven-development needs status `in-progress` at dispatch, not completion. The routing table encodes this: the pre-dispatch `advance` sets `in-progress` + `--owner`; the post-completion `advance` moves phase to `finish`. Not special-cased in the skill.

## 4. The workflow skill & command

New skill `plugins/graph-wiki/skills/workflow/SKILL.md` + thin command `commands/workflow.md` (`/graph-wiki:workflow <slug>`). The skill is deliberately thin — decisions live in the CLI:

1. **Resolve & report.** Run `gw work next <slug> --json`. Blockers → report and stop. Otherwise announce the dispatch (item, kind, phase, skill).
2. **Dispatch.** Invoke the stage skill via the Skill tool, prepending a work-item brief (title, summary, kind, `affects`, links to prior artifacts) and: "Write your output document to `<artifact.path>` — this overrides the skill's default location." (Stock skills honor user-preference path overrides; they stay unmodified.)
3. **Verify the artifact.** After the stage completes, check the expected `raw/` path exists; if the skill wrote to the stock `docs/superpowers/` location, move the file and note it.
4. **Advance.** Run `gw work advance <slug>` with whatever flags the stage produced, prompting for `--effort` if the command demands it. Report the lint findings it returns.
5. **Hand off.** End with: "Phase advanced to `<next>`. Clear context (`/clear`) and run `/graph-wiki:workflow <slug>` to continue." At `done`, report resolution and suggest `/graph-wiki:archive` once the item ages out.

**One stage per invocation, by design.** The skill never chains stages in a session — each stage gets a fresh context window. The work item plus `raw/` artifacts are the durable state between sessions; nothing depends on conversation memory.

## 5. Artifact layout

```
<workspace>/
  raw/
    specs/<slug>.md      # brainstorming design doc, or systematic-debugging findings
    plans/<slug>.md      # writing-plans implementation plan
  wiki/
    work/<slug>.md       # the work item — links to both
```

- The spec slot is stage-agnostic: whatever the design stage produced lands at `raw/specs/<slug>.md`. Execute/finish stages produce no documents.
- `gw work advance` stamps workspace-relative frontmatter pointers as artifacts land: `spec_doc: raw/specs/<slug>.md`, `plan_doc: raw/plans/<slug>.md`. That's how fresh-context sessions and `gw work next` find prior output, and it gives lint something checkable.
- Layout is ingest-compatible: when an item resolves, a future `/graph-wiki:ingest raw/specs/<slug>.md` can distill the design into a durable `sources/`/`concepts/` page. v1 only reserves the layout; no ingest changes.

## 6. Schema & lint changes (all in `work-io`)

- `VALID_EFFORTS = frozenset({"xs", "s", "m", "l", "xl"})` and `VALID_PHASES = frozenset({"design", "plan", "execute", "finish", "done"})` join the enums in `lifecycle_lint.py`. `VALID_STATUSES` and `VALID_KINDS` untouched.
- Four new lint rules (19 → 23), each firing only when the new key is present (no migrations, per policy — existing items lint clean):
  - `effort-not-in-enum` (warn) — existing free-text efforts degrade to warnings.
  - `phase-not-in-enum` (error).
  - `phase-status-incoherent` (warn) — compatibility map: `accepted` implies phase ∈ {execute, finish, done}; `in-progress` implies {execute, finish}; `resolved` implies {done} or absent. Warn because humans may hand-edit status.
  - `artifact-doc-missing` (warn) — `spec_doc`/`plan_doc` set but file absent from the workspace (mirrors rule 10's `affects` check).

## 7. Testing

- **Routing table:** pure-function unit tests in `packages/work-io/tests/` — every `(kind, phase, effort)` cell, the small-bug shortcut, the effort-required error, terminal/mitigated refusal.
- **Commands:** `gw work next`/`advance` tests in `graph-wiki-core` alongside `test_commands_work.py`, same tmp-workspace fixtures — JSON contract, frontmatter mutation, `## Plan` table sync, sidecar regen, exit codes.
- **Lint rules:** new cases following the existing `test_lifecycle_lint.py` pattern.
- **Skill:** stays prose-thin; manual walkthrough on a real work item (the logic it wraps is covered above).

## Out of scope (v1)

- Variant skills: `brainstorming-spike`, lighter writing-plans review profiles for bugs/small work.
- Ingest support for `raw/specs/` and `raw/plans/` documents.
- Auto-advancing hooks (the `plugins/graph-wiki/hooks/examples/` patterns); the loop stays user-driven via `/clear` + re-run.
- Migrating existing work items to the new fields — all new rules are presence-gated.
