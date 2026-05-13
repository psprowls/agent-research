---
title: "Plans & Specs Path Redesign"
category: source
summary: Relocate lattice-workflows brainstorming + writing-plans output from `docs/lattice-workflows/{plans,specs}/` to `<workspace>/{specs,plans}/`, prefix filenames by affected package/plugin, hard-fail when no `.lattice.yaml` is present.
source_path: lattice/specs/2026-05-09-lattice-workflows-plans-specs-redesign.md
source_type: spec
source_date: 2026-05-09
authors: []
status: approved
ingested: 2026-05-09
updated: 2026-05-09
tokens: 1730
---

# Plans & Specs Path Redesign

## TL;DR
`lattice-workflows` previously wrote brainstorming specs and implementation plans into a generic `docs/lattice-workflows/{specs,plans}/` tree, scattering workflow artifacts away from the workspace where every other ecosystem tool writes. This spec relocates them to `<workspace>/specs/` and `<workspace>/plans/`, prefixes filenames by the affected package/plugin (or the workspace dir name when work spans multiple), and surfaces a clear error rather than silently writing to the wrong place when no lattice workspace exists.

## Key claims

1. **Workspace resolution shared with `file-work-item`.** Both writing skills (`brainstorming`, `writing-plans`) resolve the workspace by shelling out to `python -m lattice_workspace.config`, falling back to `Path("lattice").resolve()`. They then assert `<workspace>/.lattice.yaml` exists; missing manifest → `SystemExit` with a message pointing at `/lattice-wiki:init` or `/lattice-graph:init`. This matches the pattern already used by [[wiki/plugins/lattice-workflows/lattice-workflows|lattice-workflows]]'s `:file-work-item`.
2. **File targets land beside the wiki, not under `docs/`.**

   | Artifact | Path |
   |---|---|
   | Spec | `<workspace>/specs/YYYY-MM-DD-<prefix>-<topic>-design.md` |
   | Plan | `<workspace>/plans/YYYY-MM-DD-<prefix>-<feature-name>.md` |
   | Plan tasks JSON | `<workspace>/plans/YYYY-MM-DD-<prefix>-<feature-name>.md.tasks.json` |

3. **Prefix inference is path-based.** Computed from cwd plus the set of affected paths surfaced during brainstorming/planning:

   | Condition | Prefix |
   |---|---|
   | cwd or all affected paths inside `packages/<x>/` | `<x>` |
   | cwd or all affected paths inside `plugins/<x>/` | `<x>` |
   | affected paths span multiple `<x>` across packages/plugins | workspace dir name (default `lattice`) |
   | cwd at repo root or no recognisable container | workspace dir name |

   Workspace dir name = `Path(workspace).name`, so non-lattice repos with a custom `lattice-directory` override automatically get the right umbrella prefix.
4. **Hard-fail on missing workspace.** No `.lattice.yaml` → emit the verbatim error and stop without writing any file. Message: ==No lattice workspace found at `<workspace>`. Run any lattice plugin init command (e.g. `/lattice-wiki:init` or `/lattice-graph:init`) to create the workspace, then retry.==
5. **Out of scope.** Ephemeral `.lattice-workflows/brainstorm/` session dirs (hidden state, not docs — unchanged) and `dist/lattice-workflows/` (rebuilt by `scripts/build.sh`, not edited by hand).

## Proposed changes

### Production skills — path-writing

- `plugins/lattice-workflows/skills/brainstorming/SKILL.md` — step 6 + Documentation section
- `plugins/lattice-workflows/skills/brainstorming/spec-document-reviewer-prompt.md` — "Dispatch after" line
- `plugins/lattice-workflows/skills/writing-plans/SKILL.md` — "Save plans to", inline examples, co-location note

### Production skills — example paths only

- `plugins/lattice-workflows/skills/executing-plans/SKILL.md`
- `plugins/lattice-workflows/skills/subagent-driven-development/SKILL.md`
- `plugins/lattice-workflows/skills/requesting-code-review/SKILL.md`

### Tests

For each test that creates plan/spec fixtures: `mkdir -p "$PROJECT_DIR/lattice/{plans,specs}"`, write a minimal `.lattice.yaml`, export `LATTICE_WORKSPACE="$PROJECT_DIR/lattice"`, update fixture paths from `docs/lattice-workflows/{plans,specs}/...` to `lattice/{plans,specs}/YYYY-MM-DD-lattice-<name>.md`, update prompts that reference plan file paths.

Affected test files: `tests/claude-code/test-document-review-system.sh`, `tests/claude-code/test-helpers.sh`, `tests/claude-code/test-subagent-driven-development-integration.sh`, `tests/explicit-skill-requests/run-test.sh`, `tests/explicit-skill-requests/run-multiturn-test.sh`, `tests/explicit-skill-requests/run-claude-describes-sdd.sh`, `tests/explicit-skill-requests/run-haiku-test.sh`, `tests/explicit-skill-requests/run-extended-multiturn-test.sh`, `tests/explicit-skill-requests/prompts/*.txt`, `tests/skill-triggering/prompts/executing-plans.txt`.

## Evidence / rationale

- Verified landed in code at ingest time:
  - `plugins/lattice-workflows/skills/brainstorming/SKILL.md` step 6 references `<workspace>/specs/YYYY-MM-DD-<prefix>-<topic>-design.md` and the workspace-resolution shared doc.
  - `plugins/lattice-workflows/skills/writing-plans/SKILL.md` "Save plans to:" line points at `<workspace>/plans/YYYY-MM-DD-<prefix>-<feature-name>.md`.
  - `plugins/lattice-workflows/skills/shared/workspace-resolution.md` exists as the canonical resolution doc.
  - This very spec lives at `lattice/specs/2026-05-09-lattice-workflows-plans-specs-redesign.md` and its sibling plan at `lattice/plans/2026-05-09-lattice-workflows-plans-specs-redesign.md` — the redesign is dogfooded.
- Why this matters: every other ecosystem tool (wiki, graph, work-tracker, knowledge) writes under the lattice workspace; workflow's brainstorming/planning artifacts are now the same kind of citizen rather than an out-of-band `docs/` tree.

## Surprises / contradictions

> [!warning] Workflow is a consumer, but now also a writer of workspace siblings
> [[wiki/concepts/lattice-workflows-consumption-seam]] frames workflow as ==consumer, not writer==. That principle was specifically about the *wiki vault* — new vault pages still go through `ingest_work_item.py`, not direct edits. This spec adds a different write surface: `<workspace>/specs/` and `<workspace>/plans/`, which are workspace siblings of `wiki/`, not vault interior. Consumer-of-vault still holds; new lattice-workflow-owned-siblings now exist.

No code↔vault contradictions: the spec is fully landed and verified against `plugins/lattice-workflows/skills/{brainstorming,writing-plans}/SKILL.md` and `skills/shared/workspace-resolution.md`.

## Touches

- [[wiki/plugins/lattice-workflows/lattice-workflows]]
- [[wiki/packages/lattice-workspace/lattice-workspace]]
- [[wiki/concepts/lattice-workflows-consumption-seam]]
- [[wiki/concepts/lattice-cross-plugin-contract]]

## Decisions triggered

- [[wiki/adrs/0013-plans-and-specs-in-lattice-workspace]]

## Where it's cited in this wiki

- [[wiki/plugins/lattice-workflows/context]]
- [[wiki/plugins/lattice-workflows/patterns]]
- [[wiki/packages/lattice-workspace/context]]
- [[wiki/concepts/lattice-workflows-consumption-seam]]
- [[wiki/concepts/lattice-cross-plugin-contract]]
