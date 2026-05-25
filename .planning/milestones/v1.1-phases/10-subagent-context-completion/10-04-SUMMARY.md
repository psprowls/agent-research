---
phase: 10-subagent-context-completion
plan: 04
subsystem: prompts
tags: [project-context, render, layout-io, syrupy, snapshot, pure-function]

# Dependency graph
requires:
  - phase: 01-infrastructure-wiki-io-and-mcp-skeleton
    provides: wiki_io.layout_io.read_layout — parser for the <!-- lattice-wiki:layout:start --> block
provides:
  - render_project_context(wiki_path: Path) -> str — pure renderer for the project-context block delivered to scanner / linter / ingestor subagents at command entry
  - Fence-aware heading-walk helper that safely extracts `## Style` and `## Log format` section bodies even when they contain `## ` lines inside fenced code blocks
affects: [10-06 wiring, 10-05 fragment extraction, future subagent prompt builders]

# Tech tracking
tech-stack:
  added: []  # no new pyproject deps — Scope Fence #2
  patterns:
    - "Pure-function renderers under prompts/ (not _fragments/): callable modules sit beside string constants, mirror layout_io's pure-read discipline"
    - "Heading-walk markdown section extraction with fenced-code-block awareness — stdlib only"
    - "Deterministic ordering invariant (sort containers by vault_dir) so syrupy snapshots stay stable across YAML key-order changes"

key-files:
  created:
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py
    - agents/graph-wiki-agent/tests/prompts/test_project_context.py
    - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_project_context.ambr
  modified: []

key-decisions:
  - "Single tuple ('CLAUDE.md', 'AGENTS.md') for candidate iteration: matches CONTEXT.md ordering (CLAUDE.md primary, AGENTS.md fallback) without a separate priority constant."
  - "Render layout heading always (with '(no layout block detected)' marker) even when read_layout returns None — keeps the section anchor stable across vaults that have not yet been initialized."
  - "Heading-walk extractor tracks fenced code blocks (``` and ~~~) so a log-format sample like '## [YYYY-MM-DD] <op> | <title>' inside a code block does not falsely terminate the section. This was discovered after the first snapshot recording cut the Log format body short at the opening fence."

patterns-established:
  - "Provenance for callable prompt modules: project_context.py lives in prompts/ (not _fragments/) because it is a function, not a string constant. Tests cover behavior; provenance lives in the module docstring."
  - "Snapshot-recording cadence: when a heading-walk bug is discovered after first snapshot capture, fix the implementation, re-record (--snapshot-update), then re-run without --snapshot-update to confirm determinism. Two snapshot runs gate every behavior change."

requirements-completed:
  - CTX-02

# Metrics
duration: 4min
completed: 2026-05-17
---

# Phase 10 Plan 04: Project-Context Renderer Summary

**Pure-function `render_project_context(wiki_path)` that reads `wiki/CLAUDE.md` (or `AGENTS.md`), parses the layout block via `wiki_io.layout_io.read_layout`, and emits a deterministic ~30-line block covering project layout + style + log format for downstream subagent prompts.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-17T19:56:55Z
- **Completed:** 2026-05-17T20:00:31Z
- **Tasks:** 2 (TDD pair — RED then GREEN+REFACTOR-in-GREEN)
- **Files created:** 3 (1 src module + 1 test module + 1 recorded snapshot)
- **Files modified:** 0

## Accomplishments

- `render_project_context(wiki_path: Path) -> str` shipped in `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py`.
- Four unit tests cover the LOCKED behavioral contract: missing-file → `""`, CLAUDE.md present with syrupy snapshot, AGENTS.md fallback, byte-identical determinism on repeated calls.
- Snapshot baseline recorded at `tests/prompts/__snapshots__/test_project_context.ambr`; second run confirms it is stable.
- Fence-aware heading walk so log-format code samples (`## [YYYY-MM-DD] <op> | <title>` inside a triple-backtick fence) no longer falsely terminate the `## Log format` section. This was a real bug — the first snapshot recording cut the Log format body short at line 17 (`\`\`\``) before being fixed.
- All scope fences honored: zero `deepagents` imports, zero `pyproject.toml` changes, zero `cores/subagent-runtime/` modifications. The only new external import in the module is `from wiki_io.layout_io import read_layout`.

## Task Commits

1. **Task 1: Failing tests** — `4f50b5a` (test) — RED phase: four collected tests, all skipping cleanly because the implementation module does not yet exist.
2. **Task 2: Renderer implementation** — `713c382` (feat) — GREEN phase: module + recorded snapshot land together. Includes the fence-aware heading-walk fix discovered during snapshot review.

## Files Created/Modified

- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py` — exports `render_project_context(wiki_path) -> str`; uses `wiki_io.layout_io.read_layout` for the layout block; private `_render`, `_render_layout`, `_extract_section` helpers.
- `agents/graph-wiki-agent/tests/prompts/test_project_context.py` — four tests covering missing-file, CLAUDE.md-with-snapshot, AGENTS.md-fallback, deterministic-output. `FIXTURE_CLAUDE_MD` constant carries a valid layout block (apps + cores containers), `## Style` section, and `## Log format` section.
- `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_project_context.ambr` — single syrupy snapshot for `test_render_project_context_with_claude_md`.

## Decisions Made

- Per CONTEXT.md §Project-context renderer (LOCKED): use `wiki_io.layout_io.read_layout` for the layout YAML; never roll a bespoke YAML parser. Done — the module imports `read_layout` and lets it handle the YAML shape.
- Per CONTEXT.md §Project-context renderer (LOCKED): deterministic container ordering. Implemented by sorting `layout["containers"]` by `vault_dir` (the YAML parser preserves insertion order, but sort-by-key is the stronger guarantee).
- Render the `## Project layout` heading always (with a `(no layout block detected)` marker when `read_layout` returns `None` or the containers list is empty) so consumers can reason about a stable section structure even on freshly-cloned vaults.
- Style and log-format sections are *omitted entirely* when absent (not rendered with an empty marker) — these are optional schema content; rendering empty headings would inject useless tokens into the subagent prompt and would be visible in the snapshot.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Heading-walk terminated early when section body contained a fenced code block with a `## ` line**
- **Found during:** Task 2 (snapshot review after first `--snapshot-update`)
- **Issue:** The initial `_extract_section` broke on any line matching `line.startswith("## ")`. The `## Log format` body in `FIXTURE_CLAUDE_MD` contains a fenced code sample `## [YYYY-MM-DD] <op> | <title>` inside a triple-backtick block. The walker treated that as the next heading and terminated the section at the opening fence, so the recorded snapshot for `## Log format` was just `\`\`\`` (one line) instead of the full code block + trailing prose.
- **Fix:** Added fence tracking (``` or ~~~) inside `_extract_section`. While inside a fence, `## ` lines are appended to the body instead of terminating the section.
- **Files modified:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py`
- **Verification:** Re-recorded snapshot now contains the full Log format body (code block + `Valid ops:` line); re-run without `--snapshot-update` confirms determinism; all 14 tests in `tests/prompts/` pass with no regression.
- **Committed in:** `713c382` (rolled into the same GREEN commit as the initial implementation)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug was caught at snapshot-review time and fixed before commit, so the recorded snapshot reflects the correct behavior. No scope creep — fix stayed inside the same `_extract_section` helper.

## Issues Encountered

- One: see the deviation above. Resolution was inline (Rule 1 auto-fix).

## User Setup Required

None — pure module addition with no external service configuration.

## Next Phase Readiness

- `render_project_context` is ready to be imported by `commands/scan.py`, `commands/lint.py`, and `commands/ingest.py` in plan 10-06. The signature is exactly what the plan-10 wiring plans expect: `(wiki_path: Path) -> str` with `""` for missing inputs.
- Plan 10-05 (fragment extraction) is independent of this plan and was the second plan in this wave; both are completing in parallel.
- No blockers for plan 10-06.

## Self-Check

**Files claimed:**
- `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py` — FOUND
- `agents/graph-wiki-agent/tests/prompts/test_project_context.py` — FOUND
- `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_project_context.ambr` — FOUND

**Commits claimed:**
- `4f50b5a` (test) — FOUND
- `713c382` (feat) — FOUND

## Self-Check: PASSED

---
*Phase: 10-subagent-context-completion*
*Completed: 2026-05-17*
