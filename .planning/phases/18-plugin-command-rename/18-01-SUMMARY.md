---
phase: 18-plugin-command-rename
plan: 01
subsystem: plugin/graph-wiki/commands
tags: [rename, slash-command, plugin, cmd-01, hard-cut]
requires: []
provides:
  - "plugins/graph-wiki/commands/bootstrap.md — slash command file installed as /graph-wiki:bootstrap"
affects:
  - "Claude Code native /init reachable again (namespace collision removed at the plugin surface)"
tech_stack_added: []
patterns_used:
  - "git mv (preserves rename history vs delete+add)"
  - "hard-cut rename, no backwards-compat stub (D-04, CLAUDE.md 'Avoid backwards-compatibility hacks')"
key_files_created:
  - plugins/graph-wiki/commands/bootstrap.md
key_files_modified: []
key_files_deleted:
  - plugins/graph-wiki/commands/init.md  # via git mv, recorded as R087 not D
decisions:
  - "Bundled Task 1 (rename + body edit) and Task 2 (test gate + commit) into a single rename commit per Task 2's instructions — the body edit and the rename land atomically via one commit."
  - "Replaced an additional occurrence of /graph-wiki:init in the prose under 'What it creates' (line 60 of original) — plan allowed semantic verbs to stay but mandated zero literal /graph-wiki:init occurrences."
metrics:
  duration_minutes: 2
  tasks_completed: 2
  files_changed: 1
  date_completed: 2026-05-19
---

# Phase 18 Plan 01: Plugin slash-command rename (init → bootstrap) Summary

One-liner: Renamed `plugins/graph-wiki/commands/init.md` → `bootstrap.md` via `git mv` and rewrote its body so the slash-command literal is `/graph-wiki:bootstrap` everywhere, restoring Claude Code's native `/init` command.

## What shipped

- File renamed via `git mv` (history preserved as `R087` — git detected an 87% similarity, well above the rename-detection threshold).
- Front-matter `name:` changed from `init` to `bootstrap`.
- Front-matter `description:` updated: `Usage /graph-wiki:bootstrap …`.
- H1 heading rewritten: `# /graph-wiki:bootstrap`.
- Usage code block: 3 lines updated to `/graph-wiki:bootstrap …`.
- Examples code block: 3 lines updated to `/graph-wiki:bootstrap …`.
- Inline prose under "What it creates" (originally line 60): `…not by /graph-wiki:bootstrap` (replaced the lone remaining `/graph-wiki:init` literal in the body).
- `init_vault.py` script reference left intact (D-02: script name out of scope).
- No backwards-compat stub at `init.md` (D-04: hard cut).

## Verification

| Check                                                       | Expected | Actual |
| ----------------------------------------------------------- | -------- | ------ |
| `test ! -e plugins/graph-wiki/commands/init.md`             | exit 0   | exit 0 |
| `test -e plugins/graph-wiki/commands/bootstrap.md`          | exit 0   | exit 0 |
| `grep -cE '^name: bootstrap$' bootstrap.md`                 | 1        | 1      |
| `grep -cE '/graph-wiki:init\b' bootstrap.md`                | 0        | 0      |
| `grep -cE '/graph-wiki:bootstrap\b' bootstrap.md`           | ≥ 3      | 9      |
| `grep -c 'init_vault\.py' bootstrap.md`                     | ≥ 1      | 2      |
| `git status --porcelain` shows `R` (renamed)                | yes      | yes (`R  init.md -> bootstrap.md`) |
| `git log -1 --name-status` rename line                      | match    | `R087	plugins/graph-wiki/commands/init.md	plugins/graph-wiki/commands/bootstrap.md` |
| `uv run --package code-wiki-agent pytest … -m "not integration"` | exit 0   | exit 0 (208 passed, 1 skipped, 5 deselected, 19 snapshots passed) |
| Commit subject contains `refactor(18)` + `init → bootstrap` | yes      | yes    |

## Exact `git log -1 --name-status` rename line

```
R087	plugins/graph-wiki/commands/init.md	plugins/graph-wiki/commands/bootstrap.md
```

## Commit

- `a9ae5af` — `refactor(18): rename plugin slash command /graph-wiki:init → /graph-wiki:bootstrap`

## Deviations from Plan

**1. [Plan refinement — body sweep beyond explicitly listed locations]** While editing the body, I encountered one `/graph-wiki:init` literal in prose under "What it creates" that the plan did not explicitly enumerate (it listed front-matter, H1, Usage block, Examples block as required hot-spots). The plan's hard rule was unambiguous: "zero occurrences of the literal `/graph-wiki:init` (with word boundary) may remain inside `plugins/graph-wiki/commands/bootstrap.md`". I updated that occurrence too, leaving the file at 0 matches for `/graph-wiki:init\b` and 9 for `/graph-wiki:bootstrap\b`.

**2. [Process — task commit granularity]** The plan defined Task 1 (rename + body edit) and Task 2 (run test gate, stage, commit) as separate tasks. Per Task 2's own instructions ("Step 3: Stage and commit only the rename…"), the rename and the body edit naturally compose into one commit. I treated Task 1 as in-working-tree work and Task 2 as the commit step — landing both tasks' work in a single `refactor(18): …` commit. The git history shows one rename commit, which is what D-06 step 1 prescribes.

No auto-fixed bugs (Rule 1), no missing-functionality additions (Rule 2), no blocking issues (Rule 3), no architectural questions (Rule 4).

## Threat Surface Check

No new threat surface introduced. T-18-01 (tampering of `bootstrap.md`) mitigated by acceptance criteria asserting exact front-matter and zero `/graph-wiki:init` literals (all passed). T-18-02 (repudiation of rename) mitigated by `git mv` producing `R087` (above git's default 50% rename-detection threshold) — `git log --follow` will trace history through the rename. T-18-03 (DoS of Claude Code native `/init`) — this rename IS the mitigation; verification of native `/init` reachability is deferred to phase verifier UAT (SC#3) as planned.

## Known Stubs

None.

## Self-Check: PASSED

- `plugins/graph-wiki/commands/bootstrap.md` — FOUND
- `plugins/graph-wiki/commands/init.md` — confirmed MISSING (expected, was renamed away)
- Commit `a9ae5af` — FOUND in `git log`
