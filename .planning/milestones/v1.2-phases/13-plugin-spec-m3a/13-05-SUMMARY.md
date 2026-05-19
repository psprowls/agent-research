---
phase: 13-plugin-spec-m3a
plan: 05
subsystem: planning
tags: [plugin-spec, graph-wiki, project-md, requirements-md, contract-lock]

# Dependency graph
requires:
  - phase: 13-plugin-spec-m3a/13-04-PLAN
    provides: .planning/spec/13-plugin-contract/CONTRACT-INDEX.md (the file PROJECT.md links to)
  - phase: 13-plugin-spec-m3a/13-CONTEXT.md
    provides: SP-05 lock requirement, VP-01 prerequisite framing, P-01 inference reframe
provides:
  - .planning/PROJECT.md — Key Decisions entry locking the Phase 13 plugin contract surface (SP-05)
  - .planning/REQUIREMENTS.md — VP-01 prerequisite note attached to PLUGIN-01 bullet
affects:
  - 14-plugin-port (reads PROJECT.md Key Decisions as load_prior_context; reads REQUIREMENTS.md PLUGIN-01 to know Phase 14 Plan 1 and Plan 2 are prerequisite ports)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PROJECT.md Key Decisions: one new table row locking spec surface, linking to CONTRACT-INDEX.md and SHELL-OUT-PATTERN.md"
    - "REQUIREMENTS.md: prerequisite note appended inline to PLUGIN-01 bullet (single-line bullet style)"

key-files:
  created: []
  modified:
    - .planning/PROJECT.md
    - .planning/REQUIREMENTS.md

# Key decisions
decisions:
  - "Appended Phase 14 prerequisite note inline on the PLUGIN-01 bullet (not a sub-bullet) to match the file's single-line bullet style"
  - "PROJECT.md Key Decisions entry references both CONTRACT-INDEX.md and SHELL-OUT-PATTERN.md as source-of-truth spec files"

# Metrics
metrics:
  duration: "~3 minutes"
  completed: 2026-05-18
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
---

# Phase 13 Plan 05: Planning Artifact Lock Summary

**One-liner:** PROJECT.md Key Decisions row + REQUIREMENTS.md PLUGIN-01 note locking the graph-wiki plugin contract surface and flagging VP-01 prerequisite ports for Phase 14.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Append Key Decisions entry to PROJECT.md locking the plugin contract surface | c16955b | `.planning/PROJECT.md` |
| 2 | Add VP-01 prerequisite note to REQUIREMENTS.md PLUGIN-01 entry | f0bf955 | `.planning/REQUIREMENTS.md` |

## What Was Done

### Task 1 — PROJECT.md Key Decisions entry (SP-05)

Added one new row to the Key Decisions table in `.planning/PROJECT.md` covering:

- **P-01 reframe:** the ported graph-wiki plugin runs on Claude Code inference, NOT as a wrapper around `code-wiki-agent`. The two surfaces coexist as parallel paths over the same `vault-io` / `workspace-io` helpers.
- **Verdict summary:** 6 commands rename or reshape (`init`, `scan`, `ingest`, `lint`, `query`, `log`) + 3 dropped (`archive`, `regen-index`, `status`) per C-01.
- **Shell-out shape:** `uv run --project "$DEEP_AGENTS_ROOT" python3 ...` (SO-01); `[plugin]` backend-selector block in `.graph-wiki.yaml` (SO-03); `claude` default everywhere, `bedrock` as documented per-command opt-in (P-02).
- **VP-01 prerequisite:** `lint_wiki.py` and `wiki_search.py` must land in `vault-io` as Phase 14 Plans 1 and 2.
- **Links** to `.planning/spec/13-plugin-contract/CONTRACT-INDEX.md` and `SHELL-OUT-PATTERN.md`.

This satisfies Phase 13 SC#3 ("contract surface locked in PROJECT.md Key Decisions").

### Task 2 — REQUIREMENTS.md PLUGIN-01 prerequisite note (VP-01)

Appended the VP-01 prerequisite note inline on the existing PLUGIN-01 bullet, naming:
- `vault_io.lint_wiki` (port from `lattice_wiki_core/lint_wiki.py`, ~508 LOC) — Phase 14 Plan 1
- `vault_io.wiki_search` (port from `lattice_wiki_core/wiki_search.py`, ~194 LOC) — Phase 14 Plan 2

Both required before `/graph-wiki:lint` and `/graph-wiki:query` shims can shell out. Link to `CONTRACT-INDEX.md §Phase 14 prerequisite ports` included. PLUGIN-01 checkbox left unchecked — orchestrator handles at phase close.

## Verification

All automated grep gates passed:

**PROJECT.md gates:**
- `grep -q '13-plugin-contract'` — PASS
- `grep -q 'CONTRACT-INDEX'` — PASS
- `grep -iq 'phase 13\|m3a\|plugin contract'` — PASS
- `grep -iq 'claude code inference\|p-01\|claude.*inference'` — PASS

**REQUIREMENTS.md gates:**
- `grep -q 'lint_wiki'` — PASS
- `grep -q 'wiki_search'` — PASS
- `grep -q 'PLUGIN-01'` — PASS
- `grep -B1 -A3 'PLUGIN-01' | grep -iq 'phase 14\|prerequisite\|prereq'` — PASS

Git diffs confirmed both changes are surgical — exactly one addition per file, no other content touched.

## Deviations from Plan

None — plan executed exactly as written. The prerequisite note was appended inline on the PLUGIN-01 bullet (not as a sub-bullet) to match the file's single-line bullet style, which the plan explicitly specified as the correct approach when nested bullets are absent.

## Known Stubs

None. Both files contain only durable planning content — no placeholder text, empty values, or stubs.

## Threat Flags

None. These are pure markdown planning artifact edits with no new code, endpoints, or security-relevant surface.

## Self-Check: PASSED

- [x] `.planning/PROJECT.md` modified: verified (line 191, new Key Decisions row)
- [x] `.planning/REQUIREMENTS.md` modified: verified (line 36, PLUGIN-01 note appended)
- [x] Commit `c16955b` exists: confirmed (`git log` shows it on `worktree-agent-a0d92a531d452cb7c`)
- [x] Commit `f0bf955` exists: confirmed (`git log` shows it on `worktree-agent-a0d92a531d452cb7c`)
- [x] All grep gates passed
- [x] Phase 13 SC#3 satisfied
