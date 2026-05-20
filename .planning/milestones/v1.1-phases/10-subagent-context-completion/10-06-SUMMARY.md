---
phase: 10-subagent-context-completion
plan: 06
subsystem: graph-wiki-agent/commands
tags: [ctx-03, project-context, prompt-wiring]
requires:
  - 10-04  # render_project_context() implemented
  - 10-05  # build_*_system(project_context=...) builders added to scanner/linter/ingestor prompts
provides:
  - "commands/scan.py, lint.py, ingest.py call render_project_context(wiki) once after wiki resolution and thread the result into per-role prompt builders"
affects:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
tech-stack:
  added: []
  patterns:
    - "Render-once-per-command: project_ctx = render_project_context(wiki) directly after resolve_wiki_and_repo; captured by closure or passed as kwarg to inner helpers"
key-files:
  created: []
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
decisions:
  - "Drop SCANNER_SYSTEM/INGESTOR_SYSTEM/LINTER_*_SYSTEM re-exports from commands modules — grep confirmed zero external callers import them via the commands surface; the prompts package still keeps the legacy constants for direct importers"
  - "_semantic_pass in lint.py grows a `project_context: str = ''` kwarg (default empty for back-compat) rather than reading the wiki path again; run_lint passes the rendered string in"
metrics:
  completed: 2026-05-17
  task_count: 3
  file_count: 3
requirements:
  - CTX-03
---

# Phase 10 Plan 06: Wire `render_project_context()` into commands Summary

Wired `render_project_context(wiki)` into `commands/scan.py`, `commands/lint.py`, and `commands/ingest.py` so each command renders the project-context block once at entry and threads the result into the per-role prompt builders (`build_scanner_system`, `build_linter_{page_quality,adr_chain,stale_claims}_system`, `build_ingestor_system`) at every SystemMessage construction site — completes the command-side half of CTX-03.

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Wire render_project_context into commands/scan.py | `c39e10c` | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` |
| 2 | Wire render_project_context into commands/lint.py (3-group semantic pass) | `045ea10` | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` |
| 3 | Wire render_project_context into commands/ingest.py (run_ingest_source only) | `c35f23f` | `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` |

## Wiring Pattern

All three commands now follow the same shape:

```python
wiki, ... = resolve_wiki_and_repo(vault_path)
project_ctx = render_project_context(wiki)
...
SystemMessage(content=build_<role>_system(project_context=project_ctx))
```

For `lint.py`, `_semantic_pass` accepts a new `project_context: str = ""` kwarg and calls each of the three builders inside the `semantic_groups` tuple with `project_context=project_context`. `run_lint` passes `project_ctx` into `_semantic_pass`.

For `ingest.py`, only `run_ingest_source` calls a builder — `run_ingest_work_item` is unchanged because it does not use `INGESTOR_SYSTEM` (it operates on already-formatted frontmatter/body via `file_work_item`).

For `scan.py`, `project_ctx` is captured by the existing `generate_stub` closure with no signature change.

## Deviations from Plan

None — plan executed exactly as written. The re-export-preservation branch documented in Task 1 / Task 3 was not needed: `grep -rn 'from graph_wiki_agent.commands.{scan,ingest,lint} import.*_SYSTEM'` returned zero hits across `agents/` and `cores/`, so the legacy constants were dropped from the commands' public surface cleanly.

## Verification

All command-level test suites green on vault fixtures with no `CLAUDE.md`/`AGENTS.md` — confirming that `render_project_context` returns the empty string and `build_*_system(project_context="")` equals the prior `*_SYSTEM` constants, leaving observable behavior unchanged:

- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests -k scan -x` → 22 passed
- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests -k lint -x` → 20 passed (3 syrupy snapshots stable)
- `uv run --package graph-wiki-agent pytest agents/graph-wiki-agent/tests -k ingest -x` → 24 passed (1 syrupy snapshot stable)

## Acceptance-Criteria Check

| Check | Result |
|-------|--------|
| `render_project_context` imported in all three commands | PASS (1/1/1) |
| `build_scanner_system(project_context=project_ctx)` used in scan.py | PASS |
| `build_linter_*_system(project_context=project_context)` × 3 used in lint.py | PASS (3 occurrences) |
| `build_ingestor_system(project_context=project_ctx)` used in ingest.py | PASS |
| `project_ctx = render_project_context(wiki)` exactly once per command | PASS (1/1/1) |
| `SystemMessage(content=SCANNER_SYSTEM)` removed | PASS (0) |
| `SystemMessage(INGESTOR_SYSTEM)` removed | PASS (0) |
| Legacy `LINTER_*_SYSTEM` removed from `semantic_groups` body | PASS (0) |
| `INGESTOR_SYSTEM` references in ingest.py | 0 (PASS) |
| `from deepagents` imports added (Scope Fence 1) | 0 (PASS, 3/3) |
| `pyproject.toml` modified (Scope Fence 2) | 0 (PASS) |
| `cores/subagent-runtime/pool.py` modified (Scope Fence 6) | 0 (PASS) |
| Existing scan/lint/ingest tests pass | PASS (22 + 20 + 24) |

## Self-Check: PASSED

- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` — FOUND
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` — FOUND
- `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` — FOUND
- commit `c39e10c` — FOUND
- commit `045ea10` — FOUND
- commit `c35f23f` — FOUND
