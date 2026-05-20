---
phase: 10-subagent-context-completion
reviewed: 2026-05-17T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/architecture_overview.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/claude_md_disambiguation.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/log_format.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/style_rules.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/linter.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py
  - agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py
  - agents/graph-wiki-agent/tests/prompts/test_project_context.py
  - agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py
  - agents/graph-wiki-agent/tests/prompts/test_token_budget.py
  - cores/prompt-sources/wiki-claude-md-template.md
  - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_project_context.ambr
  - agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr
findings:
  critical: 0
  warning: 4
  info: 5
  total: 9
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-05-17
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 10 wires project-context awareness into four subagent prompt builders. The structural design is sound — backward-compat `*_SYSTEM` constants are preserved, the empty-context degradation path is tested, snapshots are stable, and the token-budget regression test is in place. The path-traversal defense in `ingest.py` is reasonable for the project's Unix-only target.

The dominant defect is **prompt content duplication**: when `project_context` is supplied, every linter group and the ingestor emit TWO `## Log format` sections (one from the per-vault block, one from the static `LOG_FORMAT` fragment) and the ingestor emits TWO `## Style` sections back-to-back. This is the actual product surface — the prompt the LLM reads — and the snapshots already record this duplication as "expected", so the regression gate is locked open. This is a quality defect that wastes tokens (~150-220 per affected role) and gives the LLM contradictory authority signals.

Secondary findings: a TOCTOU-adjacent unguarded second file read in `render_project_context`, a doc/impl drift in `ingestor.py`'s position docstring (now consistent but worth verifying), a misleading "no layout block detected" sentinel emitted whenever the layout block hasn't been generated yet, and several quality concerns. No security findings, no behavioral regressions in the empty-context path.

## Warnings

### WR-01: `project_context` block duplicates LOG_FORMAT (and STYLE_RULES in ingestor) producing two consecutive identical sections

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/linter.py:100-145` and `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py:107-125`
**Issue:** When `project_context` is non-empty, each linter builder produces output containing both:
1. A `## Log format (wiki/CLAUDE.md §Log format)` block sourced from the vault's CLAUDE.md
2. A `## Log format` block sourced from the static `LOG_FORMAT` fragment (`_fragments/log_format.py`)

These appear within ~15 lines of each other with substantially identical content (the canonical `## [YYYY-MM-DD] <op> | <title>` template plus the valid-ops list). The ingestor additionally emits two `## Style` sections (project-style + STYLE_RULES) within ~5 lines of each other. The current snapshot files (`test_prompt_snapshots.ambr` lines 200-310 for the ingestor, lines 614-645 for `linter_page_quality`, plus the matching adr_chain / stale_claims snapshots) record this duplication as authoritative, so a future fix will require both a code change and a snapshot regeneration.

The composition contract in `10-CONTEXT.md` calls the project_context block an "override" of static fragments — but the implementation appends both. Net wasted tokens per call: ~70 per `## Log format` duplicate × 3 linter group prompts + ingestor ≈ 280 tokens of redundant content, plus ~80 for the ingestor's duplicated `## Style`. The duplication also gives the LLM two competing authority sources for the same rule, which is precisely the failure mode the phase was meant to fix.

**Fix:** When `project_context` is non-empty AND already contains a `## Log format` / `## Style` section, omit the static `LOG_FORMAT` / `STYLE_RULES` fragments from the builder's `parts` list. Sketch:

```python
def build_linter_page_quality_system(project_context: str = "") -> str:
    parts = [_PAGE_QUALITY_ROLE_INTRO, IRON_RULES, LINT_PRIORITY_ORDER]
    if project_context:
        parts.insert(1, project_context)
        # Project-context already supplies log-format; skip the static fragment.
        if "## Log format" not in project_context:
            parts.append(LOG_FORMAT)
    else:
        parts.append(LOG_FORMAT)
    parts.extend([CLAUDE_MD_DISAMBIGUATION, _PAGE_QUALITY_CHECKS, _OUTPUT_FORMAT_GENERIC])
    return "\n\n".join(parts)
```

Then `pytest --snapshot-update tests/prompts/test_prompt_snapshots.py` once to record the new (shorter) snapshots and verify the token-budget test still passes.

### WR-02: `render_project_context` emits a misleading "(no layout block detected)" sentinel that the LLM will treat as authoritative

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py:86-87`
**Issue:** When `wiki/CLAUDE.md` exists but no `<!-- lattice-wiki:layout:start -->` block is present (the common state for any wiki that hasn't yet run a scan), `_render_layout` returns:

```
## Project layout (parsed from wiki/CLAUDE.md)

- (no layout block detected)
```

The Iron Rule "the code is the source of truth" combined with this sentinel will lead the LLM to assert authoritatively that the project has no containers. For an ingestor deciding `page_type`, this could cause it to file pages under `concepts/` rather than `packages/`. For a linter, this could cause false "missing container" findings.

**Fix:** When the layout block is missing or empty, omit the `## Project layout` section entirely rather than emitting a sentinel. Callers can still see "this vault was scanned" via the presence of CLAUDE.md itself.

```python
def _render_layout(layout: dict | None, filename: str) -> str | None:
    if not layout or not layout.get("containers"):
        return None
    header = f"## Project layout (parsed from wiki/{filename})"
    ...

# then in _render:
layout_section = _render_layout(layout, filename)
if layout_section:
    sections.append(layout_section)
```

### WR-03: Unguarded second read of schema file in `_extract_section` can raise on permission / disappearance after initial existence check

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/project_context.py:119`
**Issue:** `render_project_context` checks `schema.exists()` at line 45, then `read_layout(schema)` (which performs its own `exists()` check + read), then calls `_render(layout, schema)` which calls `_extract_section(schema_path, "Style")` and `_extract_section(schema_path, "Log format")`. Each `_extract_section` does an unguarded `schema_path.read_text(encoding="utf-8")`.

The module docstring (lines 7-10) claims this function "never raises for missing files". That contract is broken if the file becomes unreadable (permission flip, race-condition deletion) between `schema.exists()` and any of the three subsequent `read_text` calls. In practice race deletion is unlikely, but a permission-error propagation will surface as a hard crash inside the scan/ingest/lint command pipeline rather than a graceful degradation to empty project_context.

**Fix:** Read the file once at the top of `_render` and pass the text down:

```python
def render_project_context(wiki_path: Path) -> str:
    for name in _CANDIDATES:
        schema = wiki_path / name
        try:
            text = schema.read_text(encoding="utf-8")
        except OSError:
            continue
        layout = read_layout(schema)  # also reads, fine
        return _render(layout, schema, text)
    return ""

def _extract_section(text: str, heading: str) -> str:
    ...  # accept text instead of path
```

### WR-04: `repo_path` override in `commands/scan.py` renders project_context from the resolved-vault path, which can describe a different repo than the override

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:270`
**Issue:** When the eval harness or a test passes `repo_path` to override the discovered repo, the function explicitly bypasses the vault's pinned containers (lines 280-291) on the grounds that the vault layout was generated from the original repo and would not match the override. But two lines earlier (line 270), `project_ctx = render_project_context(wiki)` reads the same vault and embeds *exactly that mismatched layout description* into every subagent system prompt for the override-targeted run.

Net effect: the LLM gets a `## Project layout` block describing the source-of-truth repo (e.g. `lattice/packages/`), while the scanner is actually walking a fixture repo with a different structure. The subagent will be told that the project has containers it cannot find. This undermines the eval-harness divergence test the override exists to support.

**Fix:** When `repo_path` is supplied, suppress the project_context block to mirror the pinned-containers bypass:

```python
wiki, resolved_repo = resolve_wiki_and_repo(vault_path)
if repo_path is not None:
    project_ctx = ""  # override repo does not match vault layout
    repo = repo_path.resolve()
else:
    project_ctx = render_project_context(wiki)
    repo = resolved_repo if resolved_repo is not None else Path.cwd()
```

## Info

### IN-01: Snapshot files contain the duplication of WR-01 — fixing WR-01 will require regenerating these snapshots

**File:** `agents/graph-wiki-agent/tests/prompts/__snapshots__/test_prompt_snapshots.ambr:200-310, 614-645, 717-770`
**Issue:** The recorded snapshots for `test_ingestor_system_with_project_context`, `test_linter_page_quality_system_with_project_context`, `test_linter_adr_chain_system_with_project_context`, and `test_linter_stale_claims_system_with_project_context` all contain the WR-01 duplicate-section output. Recording the bug as "expected" locks it in. If WR-01 is fixed, these snapshots must be regenerated with `pytest --snapshot-update tests/prompts/test_prompt_snapshots.py` and the diffs reviewed manually before commit.
**Fix:** Tied to WR-01.

### IN-02: `_count_tokens` rule-of-thumb is non-load-bearing and could mask real growth on a different prompt structure

**File:** `agents/graph-wiki-agent/tests/prompts/test_token_budget.py:56-58`
**Issue:** `len(s) // 4` is not a real tokenizer for any Bedrock-served model. The test correctly admits this in its docstring. On a future prompt that uses many short tokens (CJK text, dense code, frequent backticks), this approximation could understate by 40-60%. The current baselines were derived from the same approximation so the comparison is internally consistent, but a future refactor that changes the character distribution (e.g. heavy ASCII art, code samples) could pass this test while blowing real token budgets.
**Fix:** Document the limitation more aggressively in CONTEXT.md, or replace with `boto3` `bedrock-runtime.count_tokens` against a representative model. Not a v1 concern.

### IN-03: `read_layout` is invoked once via `render_project_context` and again indirectly via `_load_existing_pages` and `_module_pass` in commands — same file read 2-3× per command

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py:270, 287-291` and `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py:522, _module_pass:327`
**Issue:** Each scan/lint command call reads `wiki/CLAUDE.md` via `render_project_context` once, then again via the in-command `read_layout(wiki / schema_name)` for pinned-containers extraction (scan) or code-drift detection (lint). The file is small (~few KB) and reads are local-disk, so this is not a real cost — but threading the parsed layout through (or caching at the command boundary) would make the data flow easier to reason about and would naturally fix WR-03 by funneling all reads through one error-handling path.
**Fix:** Optional refactor; defer.

### IN-04: Doc/impl drift between `prompts/ingestor.py:14` module docstring and the actual `parts.insert(1, ...)` semantics — confusing but currently correct

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py:96-106`
**Issue:** The module-level docstring (line 13-14) says `project_context` is "inserted at position 1 (after the role intro, before IRON_RULES)". The function docstring at line 100-104 says the same. The implementation at line 124 does `parts.insert(1, project_context)`. Because `parts[0]` is `_ROLE_INTRO` and `parts[1]` is `IRON_RULES`, inserting at index 1 places `project_context` between them — correct, matches the docstring. The wording is just slightly awkward; "position 1" can be read as either "the second slot" or "before slot 1". A future reader chasing a snapshot diff may mis-read this.
**Fix:** Re-word docstring to "inserted between the role intro (position 0) and IRON_RULES, becoming the new position 1".

### IN-05: `commands/lint.py:72-77` performs imports after the module body has begun (after `LINTED_TOPS` constant) — PEP 8 mild style nit

**File:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py:72-77`
**Issue:** `from graph_wiki_agent.prompts.linter import (...)` and `from graph_wiki_agent.prompts.project_context import render_project_context` are placed mid-module after several other top-level statements. PEP 8 prefers all imports at the top; this is a quality nit, not a correctness issue. The other command files (`scan.py`, `ingest.py`) correctly group these at the top.
**Fix:** Move the two import blocks at lines 72-77 up to join the rest of the imports at line 38.

---

_Reviewed: 2026-05-17_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
