---
phase: 13-plugin-spec-m3a
plan: "03"
subsystem: plugin-spec
tags: [spec, plugin, query, log, graph-wiki]
dependency_graph:
  requires: []
  provides:
    - .planning/spec/13-plugin-contract/query.md
    - .planning/spec/13-plugin-contract/log.md
  affects:
    - Phase 14 plugin port (query shim + BM25 fallback wiring)
    - Phase 14 plugin port (log command prose rename)
tech_stack:
  added: []
  patterns:
    - SP-02 per-command spec template (all 6 mandatory H2 sections)
    - LLM-primary + BM25-fallback query shape documented per P-01
key_files:
  created:
    - .planning/spec/13-plugin-contract/query.md
    - .planning/spec/13-plugin-contract/log.md
  modified: []
decisions:
  - "query: primary path is Claude Code in-session inference (no shell-out); BM25 fallback fires only when vault insufficient — mirrors upstream librarian.md step 4 exactly"
  - "query: VP-01 prerequisite (wiki_search.py ~194 LOC port to vault_io, Phase 14 Plan 2) is blocking the fallback path; primary LLM path is unaffected until VP-01 lands"
  - "log: no script ships — parity with upstream which has no log.py; prose-only command instructs Claude Code to grep + tail wiki/log.md"
  - "log: op name rebranding (/lattice-wiki:* -> /graph-wiki:*) is the only change; log entry format (## [YYYY-MM-DD] <op> | <title>) is unchanged"
metrics:
  duration_minutes: 3
  completed_date: "2026-05-18"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 13 Plan 03: query + log Per-Command Specs Summary

**One-liner:** Per-command port specs for `/graph-wiki:query` (LLM-primary with BM25 fallback, VP-01 prerequisite locked) and `/graph-wiki:log` (prose-only, no script, upstream parity) — completing the six per-command spec files Phase 13 must produce.

## What Was Built

Two per-command spec files under `.planning/spec/13-plugin-contract/`, each conforming to the SP-02 mandatory template (all six H2 sections):

**query.md** — Documents the `/graph-wiki:query` port shape:
- Primary path is Claude Code in-session inference (librarian sub-agent); no shell-out (`uv run`) on this path per P-01.
- BM25 fallback shells out to `vault_io.wiki_search.main` via `uv run --project "$AGENT_RESEARCH_ROOT"`.
- VP-01 prerequisite called out explicitly: `wiki_search.py` (~194 LOC) must be ported from `lattice_wiki_core` to `vault_io` as Phase 14 Plan 2 before the fallback path works.
- Bedrock backend routes to `graph-wiki-agent query` subprocess (covers full flow, not just fallback).
- Librarian agent rename row: name stays (`agents/librarian.md`), internal namespace prose rebranded.
- Prose-preservation map covers all 6 upstream query.md H2 sections.

**log.md** — Documents the `/graph-wiki:log` port shape:
- No script ships — parity with upstream which has no `log.py`.
- Prose-only command: Claude Code session runs `grep + tail` against `<workspace>/wiki/log.md`.
- Op name references in the `## Valid ops` section rebranded (`/lattice-wiki:*` → `/graph-wiki:*`).
- Log entry format (`## [YYYY-MM-DD] <op> | <title>`) is unchanged verbatim.
- No sub-agent dispatch — simplest command in the plugin surface.
- Optional placeholder script noted as Phase 14 executor discretion (default: no script per CONTEXT.md §decisions).

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1: query.md | 76ec9ee | docs(13-03): add per-command spec for /graph-wiki:query |
| Task 2: log.md | bfb4971 | docs(13-03): add per-command spec for /graph-wiki:log |

## Deviations from Plan

None — plan executed exactly as written.

The only discovery worth noting: the `wiki_search.py` upstream shim (inspected per plan's `read_first`) uses an in-process `asyncio.run(QueryAgent(...).run(...))` pattern for the bedrock branch (not a subprocess), whereas the spec documents the bedrock branch as `graph-wiki-agent query <args>` subprocess. This matches the CONTEXT.md §SO-02 decision and is the correct graph-wiki pattern; the upstream shim's bedrock branch is being retargeted, not preserved verbatim.

## Known Stubs

None. These are spec-only artifacts; no code paths.

## Threat Flags

None. These are planning spec documents with no network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- `.planning/spec/13-plugin-contract/query.md` — exists, all 6 H2 sections present, VP-01 referenced, librarian rename row present, BM25/fallback appears, automated gate passes.
- `.planning/spec/13-plugin-contract/log.md` — exists, all 6 H2 sections present, "no script" explicit, `wiki/log.md` path present, automated gate passes.
- Commits 76ec9ee and bfb4971 exist in git log.
