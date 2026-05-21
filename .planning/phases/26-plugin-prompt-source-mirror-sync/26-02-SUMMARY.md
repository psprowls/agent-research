---
phase: 26-plugin-prompt-source-mirror-sync
plan: 02
subsystem: prompt-anchors
tags: [re-anchor, D-03, D-05, D-06, D-07, option-a, audit-execution]
dependency_graph:
  requires: [26-AUDIT.md, 26-CONTEXT.md, 26-PATTERNS.md, 26-01-SUMMARY.md]
  provides:
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md
    - "CLAUDE.md.template §Log format and §Style sections"
  affects:
    - 26-03-PLAN.md (test_provenance.py rewrite — consumes the new 1-line shape)
    - 26-04-PLAN.md (packages/prompt-sources/ deletion — now fully un-referenced in scope dirs)
tech_stack:
  added: []
  patterns:
    - Option A 1-line provenance shape applied uniformly
    - heading slug-derivation per D-03 (em-dash → double-hyphen)
    - markdown-only asset tree under prompts/sources/ (no __init__.py)
key_files:
  created:
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md
    - .planning/phases/26-plugin-prompt-source-mirror-sync/deferred-items.md
  modified:
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/citation_rules.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/claude_md_disambiguation.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/frontmatter_rules.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/iron_rules.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/log_format.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/style_rules.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/__init__.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/linter.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/code_reader.py
    - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/synthesizer.py
    - packages/workspace-io/src/workspace_io/assets/CLAUDE.md.template
    - packages/eval-harness/src/eval_harness/divergence/scanner.py
    - packages/eval-harness/src/eval_harness/divergence/ingestor.py
    - packages/eval-harness/src/eval_harness/divergence/librarian.py
    - packages/eval-harness/src/eval_harness/divergence/linter.py
    - packages/eval-harness/src/eval_harness/divergence/synthesizer.py
    - packages/eval-harness/src/eval_harness/divergence/code_reader.py
    - packages/eval-harness/src/eval_harness/divergence/check.py
    - packages/eval-harness/src/eval_harness/divergence/rubrics/scanner.md
    - packages/eval-harness/src/eval_harness/divergence/rubrics/ingestor.md
    - packages/eval-harness/src/eval_harness/divergence/rubrics/librarian.md
    - packages/eval-harness/src/eval_harness/divergence/rubrics/linter.md
    - packages/eval-harness/src/eval_harness/divergence/rubrics/synthesizer.md
    - packages/eval-harness/src/eval_harness/divergence/rubrics/code_reader.md
decisions:
  - "Applied Option A uniformly across all 8 fragments + 4 prompt-builder sites + 2 Bedrock-only new comments + 6 rubric HTML headers — every site now carries `# Source: <path> §<section>` (or `<!-- Source: <path> §<section> -->`) and no `# Anchor:` / `# Source-commit:` lines remain in any in-scope file."
  - "RESTORE-CONTENT applied at CLAUDE.md.template: `## Log format` and `## Style` headings + bodies inserted after the existing `## Conventions for LLM agents` block; body content sourced verbatim from the LOG_FORMAT and STYLE_RULES Python constants per the plan."
  - "Created the new `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/` tree as a pure-markdown asset tree (no __init__.py). Both files are verbatim ports of `packages/prompt-sources/agents/{code_reader,synthesizer}.md` with `skills: [lattice-wiki, ...]` → `skills: [graph-wiki, ...]` rebrand applied (no other `lattice` literals found in either body)."
  - "Em-dash slug verified: linter.py L17 docstring + L55 carry `§Pass 2 — Semantic (read and think), §Rules` exactly (U+2014 em-dash). divergence/linter.py L74 uses the `#pass-3--report` double-hyphen slug from `### Pass 3 — Report`."
metrics:
  duration_minutes: ~35
  tasks_completed: 3
  files_touched: 28
  files_created: 3
  commits: 3
  audit_rows_applied: 56
completed: 2026-05-21
---

# Phase 26 Plan 02: Re-anchor sweep (Option A) Summary

One-liner: applied all 56 AUDIT rows mechanically across three coordinated sweeps — collapsed every 3-line provenance header to the Option A 1-line shape, restored `## Log format` + `## Style` to `CLAUDE.md.template`, created the new `prompts/sources/` markdown-only tree with rebrand, and re-pointed every eval-harness `source_anchor=` literal + prose `Anchors` line + rubric HTML header to its canonical post-mirror target.

## What shipped

### Task 1 — `prompts/` tree re-anchor + CLAUDE.md.template restore + sources/ creation (commit `d41cf3d`)

- All 8 `_fragments/*.py` files: 3-line `# Source: / # Anchor: / # Source-commit:` block replaced with single-line `# Source: <path> §<section>` per AUDIT Table 1. Plugin-side fragments point at `plugins/graph-wiki/...`; the two load-bearing CLAUDE.md.template fragments (`log_format.py`, `style_rules.py`) point at the workspace-io template asset.
- 4 prompt-builder files updated per AUDIT Table 2: `scanner.py` 3-line block → 1-line shape; `linter.py` 3 sites (L17 docstring, L26, L55 — em-dash `§Pass 2 — Semantic (read and think)` preserved verbatim); `ingestor.py` L5 docstring path-prefix rebrand; `librarian.py` L7 docstring path-prefix rebrand.
- 2 Bedrock-only files gained NEW `# Source:` comments per AUDIT Table 3: `code_reader.py` and `synthesizer.py` now point at the new agent-local sources tree.
- New `prompts/sources/` directory created with `code_reader.md` and `synthesizer.md` — verbatim ports of `packages/prompt-sources/agents/{code_reader,synthesizer}.md` with `skills: [lattice-wiki, ...]` rebranded to `skills: [graph-wiki, ...]`. No `__init__.py` (markdown-only asset tree per PATTERNS recommendation).
- `CLAUDE.md.template` gained `## Log format` and `## Style` headings + body content after `## Conventions for LLM agents`. Body sourced verbatim from the `LOG_FORMAT` and `STYLE_RULES` Python constants per the plan's strict "do not rewrite from memory" instruction.
- `_fragments/__init__.py` docstring rebranded (Rule 3 inline fix to satisfy the plan's must-have `grep -rln 'packages/prompt-sources' .../prompts/ == 0` gate).

### Task 2 — eval-harness divergence Python rewrites (commit `43bd3b3`)

- All 23 `source_anchor=` literals across the 6 `divergence/*.py` modules re-pointed per AUDIT Table 4. Plugin-side anchors target `plugins/graph-wiki/...`; synthesizer + code_reader anchors target the new agent-local sources tree. Two named audit cases applied verbatim: `scanner.md#workflow-step-3` → `scanner.md#3-create-stubs-for-new-packages` (3 sites in scanner.py); `linter.md#workflow-pass-3` → `linter.md#pass-3--report` (1 site in linter.py).
- All 10 prose `Anchors ...` lines + the single `# Vault-thinness ...` comment in `divergence/{synthesizer,code_reader}.py` re-pointed per AUDIT Table 5 — path-prefix rewrite only, section anchors carry forward verbatim because the new sources are verbatim ports.
- `divergence/check.py` L60 docstring example re-pointed `packages/prompt-sources/SKILL.md#iron-rules` → `plugins/graph-wiki/skills/graph-wiki/SKILL.md#iron-rules`.

### Task 3 — rubric HTML headers + body rebrand (commit `8f10482`)

- All 6 rubric `.md` files had their 3-line `<!-- Source: --> / <!-- Anchor: --> / <!-- Source-commit: -->` HTML header collapsed to a single `<!-- Source: <path> §Rules, §Red flags -->` line per AUDIT Table 6. Plugin-side rubrics (ingestor, librarian, linter, scanner) point at `plugins/graph-wiki/agents/<role>.md`; synthesizer + code_reader rubrics point at the new agent-local sources tree.
- Body rebrand `lattice-wiki` → `graph-wiki` applied at L9 of the 4 plugin-side rubrics (synthesizer + code_reader had zero body hits per AUDIT).
- Two additional in-body path-prefix references discovered during verification (rubrics/synthesizer.md L7, rubrics/code_reader.md L7) re-pointed to the new sources tree (Rule 3 inline fix).
- Out-of-scope discoveries (test_provenance.py — Plan 03 owns; test fixtures in `tests/fixtures/post-rebrand-vault/` — Plan 04 concern) logged to `deferred-items.md`.

## Verification

| Gate | Expected | Actual |
|------|----------|--------|
| `grep -rln 'packages/prompt-sources' agents/.../prompts/` | 0 | 0 |
| `grep -rc '^# Anchor: ' .../_fragments/` total | 0 | 0 |
| `grep -rc '^# Source-commit: ' .../_fragments/` total | 0 | 0 |
| `grep -rcE '^# Source: ' .../_fragments/` total | ≥8 | 8 |
| `grep -E '^# Source: ' .../prompts/code_reader.py` | ≥1 | 1 |
| `grep -E '^# Source: ' .../prompts/synthesizer.py` | ≥1 | 1 |
| `test -f .../prompts/sources/code_reader.md` | exists | exists |
| `test -f .../prompts/sources/synthesizer.md` | exists | exists |
| `grep -i 'lattice-wiki' .../prompts/sources/*.md` | 0 | 0 |
| `grep -E 'skills:.*graph-wiki' .../code_reader.md` | ≥1 | 1 |
| `grep -E '^## Log format$' CLAUDE.md.template` | 1 | 1 |
| `grep -E '^## Style$' CLAUDE.md.template` | 1 | 1 |
| `test ! -f .../prompts/sources/__init__.py` | true | true |
| `grep -rln 'packages/prompt-sources' .../divergence/ --include='*.py'` | 0 | 0 |
| `grep -rcE 'source_anchor=' .../divergence/*.py` total | ≥20 | 23 |
| `grep -E 'scanner.md#3-create-stubs-for-new-packages' scanner.py` | 1 | 3 |
| `grep -E 'linter.md#pass-3--report' linter.py` | 1 | 1 |
| `grep -E '.../sources/synthesizer.md' divergence/synthesizer.py` | ≥9 | 9 |
| `grep -E '.../sources/code_reader.md' divergence/code_reader.py` | ≥9 | 9 |
| `grep -E 'SKILL.md#iron-rules' check.py` | 1 | 1 |
| `grep -rln 'packages/prompt-sources' .../rubrics/` | 0 | 0 |
| `grep -rln 'Source-commit' .../rubrics/` | 0 | 0 |
| `grep -rln '<!-- Anchor:' .../rubrics/` | 0 | 0 |
| `grep -rcE '^<!-- Source: ' .../rubrics/` total | ≥6 | 6 |
| `grep -rin 'lattice-wiki' .../rubrics/` | 0 | 0 |
| `uv run --package eval-harness pytest -q` | green | 165 passed, 22 skipped |
| `uv run --package graph-wiki-agent pytest -q` | green except test_provenance | 213 passed, 6 skipped, 1 failed (test_provenance.py — Plan 03) |

The single graph-wiki-agent failure (`tests/prompts/test_provenance.py::test_all_fragments_have_provenance_header`) is explicitly expected — the test's `_PROVENANCE_RE` still matches the 3-line header and Plan 03 rewrites it for Option A. Every other test in both packages is green.

## Decisions Made

1. **Em-dash literal preserved verbatim.** `linter.py` L17 docstring and L55 carry `§Pass 2 — Semantic (read and think), §Rules` with the U+2014 em-dash copied byte-for-byte from `plugins/graph-wiki/agents/linter.md`. `divergence/linter.py` L74 carries the slug `#pass-3--report` (double-hyphen from em-dash) per the AUDIT slug spot-check.
2. **CLAUDE.md.template content sourced from Python constants.** Per the plan's explicit instruction, the `## Log format` and `## Style` body content was copied verbatim from the existing `LOG_FORMAT` / `STYLE_RULES` Python constants (lines 5-15 of `log_format.py` and lines 5-12 of `style_rules.py`), not rewritten from memory. The Python constants and the new template sections are identical (modulo the closing `\` line-continuation marker in the Python heredoc, which has no markdown equivalent).
3. **No `__init__.py` in `prompts/sources/`.** Pure markdown asset tree per PATTERNS recommendation + Claude's Discretion locked in CONTEXT.
4. **Lattice rebrand sweep applied to both ported `.md` files.** Both `code_reader.md` (`skills: [lattice-wiki, source-reader]` → `skills: [graph-wiki, source-reader]`) and `synthesizer.md` (`skills: [lattice-wiki, obsidian-markdown]` → `skills: [graph-wiki, obsidian-markdown]`) rebranded at the frontmatter line; bodies scanned with `grep -i lattice` returned zero additional hits.

## Deviations from Plan

### Rule 3 — Auto-fix blocking issues (3 instances)

**1. `_fragments/__init__.py` docstring path-prefix rebrand**
- **Found during:** Task 1 verification
- **Issue:** The docstring at L4-7 referenced `packages/prompt-sources/` twice; the plan's must-have gate is `grep -rln 'packages/prompt-sources' agents/.../prompts/ | wc -l == 0` (covers the entire `prompts/` subtree including `__init__.py` files).
- **Fix:** Rewrote the docstring to reference `plugins/graph-wiki/` (and `packages/workspace-io/...` for template-sourced fragments). The file was not in any task's explicit `<files>` list but the plan's verification gate requires zero hits.
- **Files modified:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/__init__.py`
- **Commit:** `d41cf3d`

**2 & 3. Rubric body path-prefix references re-pointed (`rubrics/{synthesizer,code_reader}.md` L7)**
- **Found during:** Task 3 verification
- **Issue:** Both rubric files had a body sentence `... whether a <role> agent's answer adheres to the contract from \`packages/prompt-sources/agents/<role>.md\`. ...` at L7, separate from the HTML header. AUDIT Table 6 only audited the 3-line HTML header at L1-3; the body reference was not in the audit but was caught by Task 3's must-have gate (`grep -rln 'packages/prompt-sources' .../rubrics/ == 0`).
- **Fix:** Path-prefix rewrite `packages/prompt-sources/agents/<role>.md` → `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/<role>.md`. Consistent with where the new authoritative `.md` lives.
- **Files modified:** `rubrics/synthesizer.md`, `rubrics/code_reader.md`
- **Commit:** `8f10482`

### Out-of-scope discoveries logged, not auto-fixed

Logged to `.planning/phases/26-plugin-prompt-source-mirror-sync/deferred-items.md`:

1. **`agents/graph-wiki-agent/tests/prompts/test_provenance.py`** still references `packages/prompt-sources/` in `PROMPT_SOURCES_DIR` and the 3-line `_PROVENANCE_RE`. Plan 03 owns the rewrite (D-08).
2. **`packages/eval-harness/tests/fixtures/post-rebrand-vault/`** vault fixtures (3 files) contain wikilinks and prose referencing `packages/prompt-sources/` as a documented package. These are recorded vault state, not source-code anchors; whether to re-record at Plan 04 (deletion) time is a separate call.

## Authentication gates

None.

## Self-Check: PASSED

- Files exist:
  - `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/code_reader.md` — FOUND
  - `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/sources/synthesizer.md` — FOUND
  - `.planning/phases/26-plugin-prompt-source-mirror-sync/deferred-items.md` — FOUND
- Commits exist:
  - `d41cf3d` — FOUND (Task 1)
  - `43bd3b3` — FOUND (Task 2)
  - `8f10482` — FOUND (Task 3)
- All in-task acceptance grep gates pass (verified post-commit; see Verification table above).
- Out-of-scope hits documented and intentionally not fixed.
