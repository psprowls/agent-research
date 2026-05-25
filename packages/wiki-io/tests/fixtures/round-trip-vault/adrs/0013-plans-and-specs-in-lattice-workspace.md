---
title: "ADR-0013: Brainstorming specs and plans live under `<workspace>/{specs,plans}/`"
category: adr
summary: Relocate `lattice-workflows` brainstorming output and plan output from `docs/lattice-workflows/{specs,plans}/` to `<workspace>/specs/` and `<workspace>/plans/`. Filenames carry a package/plugin prefix inferred from cwd + affected paths, and missing `.lattice.yaml` hard-fails instead of silently writing.
adr_id: "0013"
status: accepted
decision_date: 2026-05-09
deciders: [Patrick Sprowls]
supersedes: []
superseded_by:
tags: [workflows, workspace, layout, paths]
updated: 2026-05-09
tokens: 1392
---

# ADR-0013: Brainstorming specs and plans live under `<workspace>/{specs,plans}/`

**Status:** accepted (2026-05-09)

## Context

Before this decision, [[wiki/plugins/lattice-workflows/lattice-workflows]]'s `brainstorming` and `writing-plans` skills wrote their output to a fixed `docs/lattice-workflows/{specs,plans}/` tree relative to the consumer repo. This was inconsistent with every other lattice ecosystem tool: `lattice-wiki`, `lattice-graph`, `lattice-work`, and `lattice-curator` all write under the [[wiki/packages/lattice-workspace/lattice-workspace|lattice workspace]] resolved by `python -m lattice_workspace.config` (typically `<repo>/lattice/`).

Two concrete problems:

1. **Scattered artifacts.** Brainstorming specs and implementation plans were physically distant from the wiki, work items, and knowledge stores they describe. A single feature could leave traces in four different roots (`docs/`, `<workspace>/wiki/`, `<workspace>/work/`, source tree).
2. **Generic filenames.** `YYYY-MM-DD-<feature>.md` carried no indication of which package or plugin the work targeted, hurting browseability inside a monorepo with 12+ packages and plugins.
3. **Silent fallback.** When a non-lattice repo invoked the brainstorming skill, output landed in a freshly created `docs/lattice-workflows/` tree without warning the user that the surrounding lattice plumbing was absent.

The `:file-work-item` slash command had already adopted workspace-resolution-via-CLI (per [[wiki/concepts/lattice-cross-plugin-contract]]). The brainstorming + writing-plans skills were the last holdouts.

## Decision

1. **Spec target:** `<workspace>/specs/YYYY-MM-DD-<prefix>-<topic>-design.md`.
2. **Plan target:** `<workspace>/plans/YYYY-MM-DD-<prefix>-<feature-name>.md` plus a co-located `<…>.md.tasks.json`.
3. **Workspace resolution:** both skills shell out to `python -m lattice_workspace.config`, falling back to `Path("lattice").resolve()`. Implemented in the shared `plugins/lattice-workflows/skills/shared/workspace-resolution.md` doc that both skills reference.
4. **Hard-fail on missing manifest.** If `<workspace>/.lattice.yaml` does not exist, surface the verbatim error pointing at `/lattice-wiki:init` or `/lattice-graph:init` and stop without writing. No silent directory creation.
5. **Prefix inference is path-based:**

   | Condition | Prefix |
   |---|---|
   | cwd or all affected paths inside `packages/<x>/` | `<x>` |
   | cwd or all affected paths inside `plugins/<x>/` | `<x>` |
   | affected paths span multiple `<x>` across packages/plugins | workspace dir name (default `lattice`) |
   | cwd at repo root or no recognisable container | workspace dir name |

   Workspace dir name = `Path(workspace).name`, so non-lattice repos with a custom `lattice-directory` override automatically pick up a sensible umbrella prefix.

## Consequences

**Positive:**
- Workflow output lives next to the wiki and work items it describes, browsable from a single `lattice/` root.
- Filename prefixes make the package/plugin scope of a spec or plan visible at a glance.
- Errors surface upfront rather than silently producing dead output in repos that haven't been initialized.
- `python -m lattice_workspace.config` becomes the canonical workspace-resolution entry point — one more adopter of the [[wiki/concepts/lattice-cross-plugin-contract]] subprocess-not-import convention.
- The brainstorming/writing-plans seam now matches `:file-work-item`'s pattern, eliminating an inconsistency.

**Negative:**
- Pre-existing `docs/lattice-workflows/{specs,plans}/` artifacts in consumer repos are not migrated automatically. Teams need to relocate them by hand or accept the dual-tree state during transition.
- Tests must seed `.lattice.yaml` and a workspace dir per fixture (a one-time uplift across ~10 test files; see the source page for the file list).
- Workflow now writes a workspace-sibling pair of directories — see the asymmetry note in [[wiki/concepts/lattice-workflows-consumption-seam]].

## Alternatives considered

- **Keep `docs/lattice-workflows/`.** Rejected: maintains the inconsistency and the silent-fallback failure mode that motivated the change.
- **Write under `<workspace>/wiki/specs/` and `<workspace>/wiki/plans/`** — fold these into the vault namespace. Rejected: specs/plans are not vault pages (no required frontmatter, not indexed, not linted as wiki content). Keeping them as workspace siblings makes ownership explicit.
- **Use a single `<workspace>/workflows/` subtree with `specs/` and `plans/` underneath.** Rejected: extra nesting buys nothing; the `specs/` and `plans/` semantics are widely understood and shorter paths read better.

## Impact

- [[wiki/plugins/lattice-workflows/lattice-workflows]] — `brainstorming` and `writing-plans` skills updated; new shared `workspace-resolution.md` doc.
- [[wiki/packages/lattice-workspace/lattice-workspace]] — `python -m lattice_workspace.config` is now also a workflow-side entry point.
- [[wiki/concepts/lattice-workflows-consumption-seam]] — adds a workspace-sibling write surface that does not violate the consumer-of-vault principle.
- [[wiki/concepts/lattice-cross-plugin-contract]] — additional adopter of the env-var-and-subprocess discovery contract.
- [[wiki/sources/2026-05-plans-specs-path-redesign]] — the originating spec.
