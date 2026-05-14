---
phase: 05-remaining-commands
plan: "05"
subsystem: code-wiki-agent / vault-io
tags: [ingest, command, tdd, mcp, cli, wave-3, llm-routing, work-item]
dependency_graph:
  requires:
    - phase: 05-03
      provides: vault_io.ingest_source (extract, slugify, guess_source_type), vault_io.ingest_work_item (file_work_item, _parse_frontmatter, _validate), vault_io.update_index (update_index)
    - phase: 05-04
      provides: cli.py and server.py patterns (Typer sub-app, MCP progress notifications, error handling)
  provides:
    - code_wiki_agent.commands.ingest.IngestResult
    - code_wiki_agent.commands.ingest.run_ingest_source
    - code_wiki_agent.commands.ingest.run_ingest_work_item
    - code_wiki_agent.commands.ingest.INGESTOR_SYSTEM
    - code_wiki_agent.commands.ingest.build_ingest_source_prompt
    - cli.py ingest sub-app (source + work-item subcommands)
    - code_wiki_mcp.server.wiki_ingest MCP tool with type discriminator
  affects:
    - 05-06 (lint command can follow same CLI + MCP wiring pattern)
tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN per task (4 commits total)"
    - "Single ingestor LLM call (no SubagentPool fan-out) — RESEARCH: single source does not justify fan-out overhead"
    - "Typer sub-app pattern: typer.Typer() + app.add_typer(name='ingest') + @ingest_app.command"
    - "MCP type discriminator: Literal['source','work-item'] field dispatches to separate run_* functions"
    - "MCP progress: 2 milestones (before + after run_ingest_*) — same pattern as wiki_scan"
    - "Cross-ref scope: update_index(wiki) only — index-only per CONTEXT.md deferred"
    - "Path traversal guard: _route_target_path resolves and prefix-checks target against wiki root"
key_files:
  created:
    - agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py
  modified:
    - agents/code-wiki-agent/tests/unit/test_commands_ingest.py (replaced Wave 0 stub with 6 tests)
    - agents/code-wiki-agent/src/code_wiki_agent/cli.py (ingest sub-app added)
    - agents/code-wiki-agent/src/code_wiki_mcp/server.py (wiki_ingest tool added)
    - agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py (5 wiki_ingest tests added)
decisions:
  - "D-04 resolved: ONE wiki_ingest tool with type discriminator (not two separate tools) — cleaner MCP tool surface; host sees a single ingest tool"
  - "Cross-ref update scope: index-only (update_index only) — CONTEXT.md deferred decision confirmed; deep back-ref scan deferred to future version"
  - "Single LLM call in run_ingest_source (no SubagentPool) — ingest is always a single source, fan-out overhead unjustified"
  - "slug sanitization: LLM-provided target_slug re-slugified via slugify() to prevent path traversal (T-05-05-02)"
  - "_StdoutGuard import order preserved in server.py — wiki_ingest imports placed after wiki_scan block, before def main()"
metrics:
  duration_seconds: 1680
  completed_date: "2026-05-14"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 4
---

# Phase 05 Plan 05: ingest command Summary

**`ingest` command end-to-end: single ingestor LLM call routes source file to typed vault page (package/concept/adr) + Typer `ingest source / work-item` sub-app + ONE `wiki_ingest` MCP tool with `type: Literal['source','work-item']` discriminator**

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | ingest commands failing tests | d9ca0b0 | test_commands_ingest.py |
| 1 GREEN | commands/ingest.py implementation | 9404410 | ingest.py |
| 2 RED | wiki_ingest MCP failing tests | af799b8 | test_mcp_new_tools.py |
| 2 GREEN | CLI + MCP wiki_ingest implementation | 4cf2ac0 | cli.py, server.py |

## Tests Passing

| File | Tests |
|------|-------|
| agents/code-wiki-agent/tests/unit/test_commands_ingest.py | 6 passed |
| agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py | 12 passed (7 scan + 5 ingest) |

## INGESTOR_SYSTEM Prompt (exact text for downstream plans)

```
You are a code wiki ingestor. Your job is to analyze a source document and produce
a well-structured wiki page that integrates it into an existing knowledge base.

Output ONLY YAML frontmatter followed by a markdown body. Do not add commentary
outside of these sections.

Required frontmatter fields:
  - title: <descriptive title for the page>
  - category: <one of: package, concept, adr>
  - page_type: <one of: package, concept, adr>
  - target_slug: <URL-safe slug for the output filename, e.g. "auth-design">
  - summary: <one-line description of the source's main contribution>
  - tags: []  (list of relevant tags, or empty list)

Your output must include:
1. YAML frontmatter (between --- delimiters) with all required fields above.
2. A "## Summary" section (3-5 sentences) describing the source content.
3. Optional "## Key Concepts" or "## Decisions" section where appropriate.
4. Use [[wikilink]] style cross-references to related vault pages where relevant.

Keep total output under 1500 tokens.
Do NOT reproduce the full source text — synthesize and summarize.
Do NOT speculate beyond what the provided source content shows.
```

## Key Decisions

### D-04: ONE `wiki_ingest` tool with type discriminator

Per planner's discretion (D-04), implemented a single `wiki_ingest` MCP tool with `type: Literal["source", "work-item"]` field that dispatches to `run_ingest_source()` or `run_ingest_work_item()`. Alternative (two separate tools: `wiki_ingest_source` + `wiki_ingest_work_item`) was rejected as it fragments the MCP tool surface without adding clarity.

### Cross-ref update scope: index-only for v1

After every ingest write, only `update_index(wiki)` is called. Deep back-ref link scanning across all vault pages is deferred per CONTEXT.md §deferred: "ingest cross-ref deep linking — if too costly, scope down to index-only for v1". This is the scope-down path. Documented in `run_ingest_source()` docstring.

### Single LLM call (no SubagentPool)

`run_ingest_source()` uses a single direct `make_llm("ingestor").ainvoke()` call. The RESEARCH notes that single-source ingestion does not benefit from fan-out — the ingestor makes one routing decision for one source. SubagentPool overhead (tracing, semaphore, partial-failure isolation) is unjustified here.

## IngestResult Dataclass (final)

```python
@dataclass
class IngestResult:
    status: str              # Always "ok" on success
    page_path: str           # Path relative to wiki root
    slug: str                # URL-safe slug used for filename
    title: str               # Human-readable page title
    page_type: str           # "package", "concept", "adr", or "work"
    source_path: str         # Original source file path (empty for work items)
    cross_refs_updated: int  # Number of cross-ref updates (always 1 for index-only scope)
```

## MCP Progress Notifications

`wiki_ingest` emits **2 progress milestones**:
- `progress=0, total=2, message="Starting ingest"` — before invoking `run_ingest_*`
- `progress=2, total=2, message="Ingest complete: <page_path>"` — after `run_ingest_*` returns

This satisfies MCP-03 without refactoring `run_ingest_source` or `run_ingest_work_item` internals.

## Deviations from Plan

None — plan executed exactly as written. All vault_io functions from plan-05-03 were available via import. The `update_index(wiki)` callable was present (added by plan-05-03's Rule 3 fix). All acceptance criteria met without deviation.

## Known Stubs

None — both ingest paths (source + work-item) are fully wired to vault_io functions. Tests use mocks at the LLM boundary and file_work_item boundary; no placeholder data flows to UI rendering.

## Threat Flags

None — the `wiki_ingest` MCP tool follows the same trust model as `wiki_query` and `wiki_scan`. New trust surfaces introduced (source file read, YAML parse, LLM output write) are all within the plan's threat model (T-05-05-01 through T-05-05-04). Mitigations applied:
- T-05-05-01: INGESTOR_SYSTEM constrains output; `_parse_ingestor_response` handles parse failures gracefully
- T-05-05-02: `slugify()` strips non-alphanumeric chars; `_route_target_path` prefix-checks resolved path against wiki root
- T-05-05-03: `extract()` has LARGE_FILE_BYTES cap inherited from vault_io.ingest_source
- T-05-05-04: accepted (same user context, explicit invocation)

## Self-Check: PASSED

Files exist:
- agents/code-wiki-agent/src/code_wiki_agent/commands/ingest.py (created, 250+ lines)
- agents/code-wiki-agent/tests/unit/test_commands_ingest.py (6 tests, no skips)
- agents/code-wiki-agent/src/code_wiki_agent/cli.py (ingest sub-app added)
- agents/code-wiki-agent/src/code_wiki_mcp/server.py (wiki_ingest tool added)
- agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py (12 tests, no skips)

Commits exist:
- d9ca0b0 (Task 1 RED — test_commands_ingest.py stub replaced with 6 failing tests)
- 9404410 (Task 1 GREEN — ingest.py implementation)
- af799b8 (Task 2 RED — 5 wiki_ingest tests added to test_mcp_new_tools.py)
- 4cf2ac0 (Task 2 GREEN — cli.py + server.py wiki_ingest implementation)

All 18 tests passing: `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/unit/test_commands_ingest.py agents/code-wiki-agent/tests/unit/test_mcp_new_tools.py` exits 0
