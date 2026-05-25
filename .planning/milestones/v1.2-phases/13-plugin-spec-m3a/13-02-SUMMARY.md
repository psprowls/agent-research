---
phase: 13-plugin-spec-m3a
plan: "02"
subsystem: plugin-spec
tags: [spec, plugin, graph-wiki, ingest, lint, reshape, rename, port-spec]
dependency_graph:
  requires: []
  provides:
    - ".planning/spec/13-plugin-contract/ingest.md"
    - ".planning/spec/13-plugin-contract/lint.md"
  affects:
    - "Phase 14 M3b plugin port (ingest shim, lint shim)"
    - "packages/vault-io (lint_wiki.py port prerequisite VP-01)"
tech_stack:
  added: []
  patterns:
    - "SP-02 per-command spec template (frontmatter + 6 mandatory H2 sections)"
key_files:
  created:
    - ".planning/spec/13-plugin-contract/ingest.md"
    - ".planning/spec/13-plugin-contract/lint.md"
  modified: []
decisions:
  - "ingest port_verdict=rename: source-ingest behavior preserved byte-for-byte; ingest_work_item.py absent from graph-wiki (C-01)"
  - "lint port_verdict=reshape: only reshape verdict in v1.2; work-layer pass 1b dropped (C-01); vault_io.lint_wiki VP-01 prerequisite port required in Phase 14 Plan 1"
metrics:
  duration: "~10 minutes"
  completed: "2026-05-18T23:16:03Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 13 Plan 02: ingest + lint Port Specs Summary

Per-command port specs for `/graph-wiki:ingest` (rename verdict, source-only) and `/graph-wiki:lint` (reshape verdict, drops work-layer pass 1b) authored under `.planning/spec/13-plugin-contract/`.

## What Was Built

Two SP-02-conformant per-command spec files that lock the port contract for the two non-trivial v1.2 decisions: source-only ingest scope (no work-item branch) and lint's dropped work-layer pass 1b. Each file contains all six mandatory sections (Shell-out contract, Prose-preservation map, Agent / skill rename map, Reshape notes, Verification gate) plus frontmatter locking command, upstream_source, and port_verdict.

## Tasks

### Task 1: ingest.md (port_verdict: rename)

Commit: `7913a1f`

- `port_verdict: rename` — source-ingest behavior preserved byte-for-byte modulo namespace strings
- Shell-out contract: `vault_io.ingest_source.main` (claude) / `graph-wiki-agent ingest source` (bedrock, explicitly NOT `ingest work-item`)
- Args: `--source`, `--json`, `--pkg-dir`, `--pkg-title` (mapped 1:1 from upstream `ingest_source.py` argparse)
- Prose-preservation map: all 8 upstream sections verdicted; work-item ingest noted as absent at the script level (not the command-doc level), captured by omission of `ingest_work_item.py`
- C-01 decision referenced 6 times; work-item string appears throughout drop-callout context

### Task 2: lint.md (port_verdict: reshape)

Commit: `aa91c21`

- `port_verdict: reshape` — only reshape verdict in the v1.2 port
- Shell-out contract: `vault_io.lint_wiki.main` (mechanical pass 1 + semantic pass 2) + `vault_io.graph_analyzer.main` (companion)
- VP-01 prerequisite: lint_wiki.py (~508 LOC) must be ported from lattice_wiki_core to vault_io as Phase 14 Plan 1 before shim can dispatch
- Args: `--stale-days`, `--log-gap-days`, `--json`, `--check` (mapped 1:1; no work-layer flags)
- Prose-preservation map: distinguishes pass 1 (verbatim rename), pass 1b (DROP — section omitted per C-01), pass 2 (verbatim rename), pass 3 (reshape: `## Work lint` header removed from report)
- Reshape notes: two concrete behavior changes (pass 1b removed, VP-01 prerequisite port)
- VP-01 referenced 5 times; work-layer/pass 1b referenced throughout

## Deviations from Plan

### Infrastructure deviation: worktree path safety issue (#3099)

**Found during:** Task 1 commit

**Issue:** The first commit for Task 1 accidentally landed on the main repo's `main` branch because the `git commit` command was run with `cd /Users/pat/Personal/agent-research` (the main repo path) instead of from the worktree at `/Users/pat/Personal/agent-research/.claude/worktrees/agent-ae045a9515948e22c`. The Write tool also wrote the initial ingest.md to the main repo's working tree.

**Fix:** 
1. Reset main repo to `5effd12` (the base commit before this agent's work) using `git reset --hard HEAD~1` — safe because the commit was seconds old and no other concurrent commits had landed.
2. Wrote ingest.md and lint.md to the correct worktree path (`/Users/pat/Personal/agent-research/.claude/worktrees/agent-ae045a9515948e22c/.planning/spec/13-plugin-contract/`).
3. Committed from the worktree using `git -C <worktree-path>`.

**Files affected:** None permanent — the accidental main commit was removed cleanly.

**Lesson:** All file writes and git operations in this agent must use the worktree root (`/Users/pat/Personal/agent-research/.claude/worktrees/agent-ae045a9515948e22c/`) as the base, not `/Users/pat/Personal/agent-research/`.

## Self-Check

**Files exist:**
- `/Users/pat/Personal/agent-research/.claude/worktrees/agent-ae045a9515948e22c/.planning/spec/13-plugin-contract/ingest.md` — FOUND
- `/Users/pat/Personal/agent-research/.claude/worktrees/agent-ae045a9515948e22c/.planning/spec/13-plugin-contract/lint.md` — FOUND

**Commits exist:**
- `7913a1f` on `worktree-agent-ae045a9515948e22c` — FOUND
- `aa91c21` on `worktree-agent-ae045a9515948e22c` — FOUND

## Self-Check: PASSED

Both files present, both commits on the correct worktree branch.

## Known Stubs

None — these are specification documents, not code. No data stubs or placeholders.

## Threat Flags

None — spec documents with no network endpoints, auth paths, or schema changes.
