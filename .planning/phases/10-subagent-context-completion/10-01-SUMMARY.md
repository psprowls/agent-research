---
phase: 10-subagent-context-completion
plan: 01
subsystem: prompt-sources
tags: [vendoring, provenance, prompt-fragments, lattice-wiki]
requires: []
provides:
  - "cores/prompt-sources/wiki-claude-md-template.md (vendored upstream template, 159 lines)"
  - "Stable anchors: §Log format @ L124, §Style @ L153 for future fragment provenance"
affects:
  - "Unblocks Phase 10 plan 10-03 (style_rules, log_format fragments)"
tech_stack_added: []
patterns_introduced: []
key_files_created:
  - cores/prompt-sources/wiki-claude-md-template.md
key_files_modified: []
decisions:
  - "Vendored as passive data asset — no header, no provenance comment, no transformation (mirrors SKILL.md pattern in same directory)"
  - "SOURCE-COMMIT not bumped — current value ef05d99 already corresponds to the upstream commit being vendored"
metrics:
  duration: "~3 min"
  completed_date: "2026-05-17"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
  commits: 1
---

# Phase 10 Plan 01: Vendor lattice-wiki CLAUDE.md.template Summary

Vendored upstream lattice-wiki `CLAUDE.md.template` byte-identically into `cores/prompt-sources/wiki-claude-md-template.md` (159 lines) so Phase 10 prompt fragments anchored to it (`style_rules`, `log_format`) will satisfy the `test_provenance.py` invariant at every commit boundary.

## What Was Built

A single passive data asset:

| File | Purpose | Lines |
|------|---------|-------|
| `cores/prompt-sources/wiki-claude-md-template.md` | Verbatim copy of upstream `CLAUDE.md.template` from lattice-wiki, pinned at commit `ef05d99` | 159 |

The file is cited by future fragment provenance headers of the form `# Source: cores/prompt-sources/wiki-claude-md-template.md` and is verified by `agents/code-wiki-agent/tests/prompts/test_provenance.py::test_provenance_source_paths_resolve`.

Line anchors preserved exactly:
- `## Log format` at line 124 — anchor for the upcoming `log_format` fragment (`L124-L133`).
- `## Style` at line 153 — anchor for the upcoming `style_rules` fragment (`L153-L159`).

## Verification

- `diff -q cores/prompt-sources/wiki-claude-md-template.md /Users/pat/Personal/lattice/dist/lattice-wiki/skills/lattice-wiki/scripts/vendor/assets/CLAUDE.md.template` → exit 0 (byte-identical).
- `wc -l cores/prompt-sources/wiki-claude-md-template.md` → 159.
- `sed -n '124p' …` → `## Log format`.
- `sed -n '153p' …` → `## Style`.
- `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/prompts/test_provenance.py -x` → 2 passed in 0.01s.
- Scope Fence #1 (`grep -rn "^from deepagents" agents/ cores/`) → 0 hits.
- Scope Fence #6 (`git diff --stat HEAD -- 'agents/*' 'cores/subagent-runtime/*'`) → 0 lines.

## Commits

| Hash | Type | Message |
|------|------|---------|
| `350bbe5` | chore | `chore(10-01): vendor lattice-wiki CLAUDE.md.template into cores/prompt-sources/` |

## Deviations from Plan

None — plan executed exactly as written. No auto-fixes, no architectural questions, no checkpoints, no auth gates.

## Requirements Satisfied

- **CTX-01** — Vendored upstream wiki template available at the canonical `cores/prompt-sources/` location, enabling Phase 10 fragment provenance to resolve.

## Self-Check: PASSED

- `[ -f cores/prompt-sources/wiki-claude-md-template.md ]` → FOUND.
- `git log --oneline --all | grep -q 350bbe5` → FOUND.
