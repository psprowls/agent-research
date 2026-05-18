---
phase: 10-subagent-context-completion
plan: 03
subsystem: prompts/_fragments
tags: [prompts, fragments, provenance, style, log-format, disambiguation]
requires:
  - 10-01  # vendored cores/prompt-sources/wiki-claude-md-template.md
provides:
  - STYLE_RULES fragment (importable from code_wiki_agent.prompts._fragments.style_rules)
  - LOG_FORMAT fragment (importable from code_wiki_agent.prompts._fragments.log_format)
  - CLAUDE_MD_DISAMBIGUATION fragment (importable from code_wiki_agent.prompts._fragments.claude_md_disambiguation)
affects:
  - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/  # +3 files
tech-stack:
  added: []
  patterns:
    - "3-line provenance header (Source / Anchor / Source-commit) on every fragment file"
    - "SCREAMING_SNAKE constant matching file basename, opened with triple-quote-backslash idiom"
key-files:
  created:
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/style_rules.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/log_format.py
    - agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/claude_md_disambiguation.py
  modified: []
decisions:
  - Verbatim-copied STYLE_RULES and LOG_FORMAT from the vendored template (no rewrite needed; under budget already)
  - Verbatim-copied CLAUDE_MD_DISAMBIGUATION from SKILL.md L141 (no heading added, per plan spec — source is body text)
  - Escaped the backslash in the grep example for log_format.py (`grep "^## \\["`) so the Python raw-byte content reads `\[` like the source
metrics:
  duration_minutes: 4
  tasks_completed: 4
  tasks_total: 4
  files_created: 3
  files_modified: 0
  tokens_added: 201  # 78 + 60 + 63 (sum well under 350 combined budget)
  completed_date: 2026-05-17
---

# Phase 10 Plan 03: Style/Log/Disambiguation Fragments Summary

Added three small prompt-fragment modules (`style_rules.py`, `log_format.py`, `claude_md_disambiguation.py`) under `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/`, each carrying the mandatory 3-line provenance header anchored to files vendored by plan 10-01. Combined cost: ~201 tokens (vs. 350 budget).

## What landed

| Fragment | File | Tokens (~) | Anchor |
|---|---|---|---|
| `STYLE_RULES` | `style_rules.py` | 78 | `cores/prompt-sources/wiki-claude-md-template.md` §Style L153-L159 |
| `LOG_FORMAT` | `log_format.py` | 60 | `cores/prompt-sources/wiki-claude-md-template.md` §Log format L124-L133 |
| `CLAUDE_MD_DISAMBIGUATION` | `claude_md_disambiguation.py` | 63 | `cores/prompt-sources/SKILL.md` L141 |

Each fragment is pure data (no imports beyond optional `from __future__ import annotations`, no functions, no `__all__`) and follows the canonical shape established by `iron_rules.py` / `page_categories.py`.

## Verification

- `uv run --package code-wiki-agent pytest agents/code-wiki-agent/tests/prompts/test_provenance.py -x -v` → **2 passed, 0 skipped, 0 failed.**
  - `test_all_fragments_have_provenance_header` PASSED across all 8 fragment files.
  - `test_provenance_source_paths_resolve` PASSED — all three new Source: paths (`cores/prompt-sources/wiki-claude-md-template.md` and `cores/prompt-sources/SKILL.md`) resolve to existing files vendored by plan 10-01.
- Per-task import + substring checks all passed (see commit messages).

## Decisions Made

1. **Verbatim over paraphrase.** Both `STYLE_RULES` and `LOG_FORMAT` are byte-for-byte copies of the corresponding template ranges — they were already well under budget, and verbatim preserves the load-bearing wording (e.g. the exact 8-op list, the precise `[YYYY-MM-DD] <op> | <title>` template).
2. **No heading on `CLAUDE_MD_DISAMBIGUATION`.** The source paragraph at SKILL.md L141 is body text, not a section heading; plan spec explicitly permits omitting a heading here. Kept verbatim including the leading `**Note:**` prefix.
3. **Escaped backslash in grep example.** The source markdown has `grep "^## \[" log.md` (literal `\[`). In a Python triple-quoted string, the bare `\[` could trigger a future `SyntaxWarning` (invalid escape), so escaped to `\\[` — the rendered string still contains `\[`, identical to the source.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1/2/3 fixes required; no architectural questions raised.

## Commits

| Task | Commit | Description |
|---|---|---|
| 1 | `2bc0f4b` | `feat(10-03): add STYLE_RULES fragment anchored to wiki-claude-md-template` |
| 2 | `ef453f7` | `feat(10-03): add LOG_FORMAT fragment anchored to wiki-claude-md-template` |
| 3 | `4da4dd6` | `feat(10-03): add CLAUDE_MD_DISAMBIGUATION fragment anchored to SKILL.md` |
| 4 | (no commit — verification only, test_provenance suite passed) |

## Scope Fences Honored

- No edits to `subagent-runtime/pool.py` or any deepagents code.
- No `pyproject.toml` modifications.
- No wiring into any prompt builder (scanner/linter/ingestor/librarian) — that is plan 10-05.

## Unblocks

Plan 10-05 can now wire all three fragments into the four subagent system prompts (scanner, linter, ingestor, librarian).

## Self-Check: PASSED

- `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/style_rules.py` — FOUND
- `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/log_format.py` — FOUND
- `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/claude_md_disambiguation.py` — FOUND
- Commit `2bc0f4b` — FOUND in git log
- Commit `ef453f7` — FOUND in git log
- Commit `4da4dd6` — FOUND in git log
