# Phase 10: Subagent Context Completion - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 13 (6 new, 7 modified)
**Analogs found:** 13 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `cores/prompt-sources/wiki-claude-md-template.md` | vendored-source | — | `cores/prompt-sources/SKILL.md` | exact |
| `prompts/_fragments/architecture_overview.py` | prompt-fragment | transform | `prompts/_fragments/iron_rules.py` | exact |
| `prompts/_fragments/style_rules.py` | prompt-fragment | transform | `prompts/_fragments/iron_rules.py` | exact |
| `prompts/_fragments/log_format.py` | prompt-fragment | transform | `prompts/_fragments/iron_rules.py` | exact |
| `prompts/_fragments/claude_md_disambiguation.py` | prompt-fragment | transform | `prompts/_fragments/page_categories.py` | exact |
| `prompts/project_context.py` | utility | file-I/O | `cores/vault-io/src/vault_io/layout_io.py` | role-match |
| `prompts/scanner.py` | prompt-builder | transform | `prompts/scanner.py` (self) | exact (wiring change only) |
| `prompts/linter.py` | prompt-builder | transform | `prompts/linter.py` (self) | exact (wiring change only) |
| `prompts/ingestor.py` | prompt-builder | transform | `prompts/ingestor.py` (self) | exact (wiring change only) |
| `prompts/librarian.py` | prompt-builder | transform | `prompts/librarian.py` (self) | exact (wiring change only) |
| `commands/scan.py` | command | request-response | `commands/scan.py` (self) | exact (wiring change only) |
| `commands/lint.py` | command | request-response | `commands/lint.py` (self) | exact (wiring change only) |
| `commands/ingest.py` | command | request-response | `commands/ingest.py` (self) | exact (wiring change only) |
| `tests/prompts/test_prompt_snapshots.py` | test | — | `tests/prompts/test_prompt_snapshots.py` (self) | exact (additive) |
| `tests/prompts/test_project_context.py` | test | — | `tests/prompts/test_prompt_snapshots.py` | role-match |

---

## Pattern Assignments

### `cores/prompt-sources/wiki-claude-md-template.md` (vendored-source — new file, lands as commit #0)

**Analog:** `cores/prompt-sources/SKILL.md` (also vendored from upstream lattice-wiki)

**Pattern:** verbatim copy of the upstream template file into the vendored-sources tree. No header, no transformation — the file IS the source of truth that fragment provenance headers cite.

**Source path** (upstream):
```
/Users/pat/Personal/lattice/dist/lattice-wiki/skills/lattice-wiki/scripts/vendor/assets/CLAUDE.md.template
```

**Vendored destination:**
```
/Users/pat/Personal/agent-research/packages/prompt-sources/wiki-claude-md-template.md
```

Notes:
- Verbatim copy (159 lines). Do not edit — the test_provenance assertion `resolved.exists()` on the cited file path is the contract; line numbers in fragment anchors must match this file's line numbers exactly.
- Lands as commit #0 of Phase 10, **before** any fragment that cites it. This preserves the `test_provenance.py` invariant at every commit boundary (style_rules and log_format would otherwise fail their provenance test the moment they land).
- The source-commit value (`ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030`) tracks the upstream commit of the vendored content, matching the existing `cores/prompt-sources/SOURCE-COMMIT` value. No bump to SOURCE-COMMIT is required.
- This is a passive data file — no imports, no provenance header. The provenance discipline is for the Python fragments under `prompts/_fragments/`; vendored source assets are tracked by `cores/prompt-sources/SOURCE-COMMIT` instead.

---

### `prompts/_fragments/architecture_overview.py` (prompt-fragment, transform)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/iron_rules.py`

**Module shape** (iron_rules.py lines 1-15 — copy exactly, change header values and constant name):
```python
# Source: cores/prompt-sources/SKILL.md
# Anchor: ## Architecture (L34-L69)
# Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030

ARCHITECTURE_OVERVIEW = """\
## Vault layout

[compact rewrite — vault tree + conditional-containers note + "code is source of truth"]
"""
```

Notes:
- The 3-line provenance header is mandatory and tested by `tests/prompts/test_provenance.py`. `Source:` must begin with `cores/prompt-sources/` and the file must exist at that path.
- Source-commit value = `ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030` (current value of `cores/prompt-sources/SOURCE-COMMIT`, per CONTEXT.md §Canonical References).
- Constant name is `ARCHITECTURE_OVERVIEW` (screaming snake case, matching `IRON_RULES`, `PAGE_CATEGORIES` etc.).
- No imports; the file is a pure string-constant module.
- Target content: compact rewrite of `cores/prompt-sources/SKILL.md §Architecture L34-L69` — keep vault directory tree, conditional-containers note, "code is source of truth" sentence; drop all user-facing prose (~600 tokens target).

---

### `prompts/_fragments/style_rules.py` (prompt-fragment, transform)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/iron_rules.py`

**Module shape**:
```python
# Source: cores/prompt-sources/wiki-claude-md-template.md
# Anchor: ## Style (L153-L159)
# Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030

STYLE_RULES = """\
## Style

[verbatim or compact rewrite of wiki-claude-md-template.md §Style L153-159]
"""
```

Notes:
- Provenance points to the vendored upstream template at `cores/prompt-sources/wiki-claude-md-template.md` (vendored in commit #0 of this phase). The live project-pinned `lattice/wiki/CLAUDE.md` is **not** the provenance anchor — it is read at runtime by `render_project_context()` but never cited in a `# Source:` header.
- The vendored file must exist before this fragment lands. Order: commit #0 (vendor template) → commit #2 (this fragment).
- ~150 tokens. Wire into: ingestor, librarian.

---

### `prompts/_fragments/log_format.py` (prompt-fragment, transform)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/iron_rules.py`

**Module shape**:
```python
# Source: cores/prompt-sources/wiki-claude-md-template.md
# Anchor: ## Log format (L124-L133)
# Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030

LOG_FORMAT = """\
## Log format

[verbatim or compact rewrite of wiki-claude-md-template.md §Log format L124-133]
"""
```

Notes:
- Provenance points to the vendored upstream template at `cores/prompt-sources/wiki-claude-md-template.md` (vendored in commit #0 of this phase). The live project-pinned `lattice/wiki/CLAUDE.md` is **not** the provenance anchor.
- The vendored file must exist before this fragment lands. Order: commit #0 (vendor template) → commit #2 (this fragment).
- ~120 tokens. Wire into: scanner, ingestor, linter (all three groups).

---

### `prompts/_fragments/claude_md_disambiguation.py` (prompt-fragment, transform)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/page_categories.py`

**Module shape** (page_categories.py lines 1-4):
```python
# Source: cores/prompt-sources/SKILL.md
# Anchor: ## Cross-tool compatibility (L141)
# Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030

CLAUDE_MD_DISAMBIGUATION = """\
[compact rewrite of cross-tool note: root CLAUDE.md ≠ wiki CLAUDE.md]
"""
```

Notes:
- This anchors to `cores/prompt-sources/SKILL.md` line 141, which IS under `cores/prompt-sources/` — no provenance test issue.
- ~80 tokens. Wire into: linter, ingestor.

---

### `prompts/project_context.py` (utility, file-I/O)

**Analog:** `cores/vault-io/src/vault_io/layout_io.py` (the read_layout function pattern)

**Imports + function signature pattern** (layout_io.py lines 25-49):
```python
from __future__ import annotations

from pathlib import Path
from typing import Optional

def read_layout(schema_path: Path) -> Optional[dict]:
    """Return parsed layout dict, or None if no block is present."""
    if not schema_path.exists():
        return None
    text = schema_path.read_text(encoding="utf-8")
    ...
```

**New module shape to replicate** (from spike-findings blueprint):
```python
from __future__ import annotations

from pathlib import Path
from vault_io.layout_io import read_layout

def render_project_context(wiki_path: Path) -> str:
    """Read wiki/CLAUDE.md once and emit a compact project-context block.

    Returns "" if neither CLAUDE.md nor AGENTS.md exists — callers
    pass the empty string through unchanged.
    """
    for schema_name in ("CLAUDE.md", "AGENTS.md"):
        schema = wiki_path / schema_name
        if schema.exists():
            layout = read_layout(schema)
            return _render(layout, schema)
    return ""

def _render(layout, schema_path: Path) -> str:
    # Render containers list + style + log-format sections as ~30 lines.
    # Keep deterministic ordering so syrupy snapshots are stable.
    ...
```

Notes:
- Pure function — no LLM calls, no network, no mutation. Mirrors layout_io.py's pure-read discipline.
- Use `read_layout()` from `vault_io.layout_io` for the layout block; do not write a bespoke YAML parser.
- Style and log-format sections are grabbed by a simple heading-based walk of the raw markdown text (no frontmatter library needed — sections are plain markdown headings, not frontmatter).
- Returns `""` on missing file; callers MUST accept empty string without crashing.
- Output ordering must be deterministic (sort containers by `vault_dir` or preserve YAML order) so syrupy snapshots are stable.
- No `__all__` needed; single exported function.
- File lives in the `prompts/` package, not `_fragments/`, because it is a callable module not a string constant.

---

### `prompts/scanner.py` (prompt-builder, transform — wiring change)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py` (self)

**Current composition pattern** (scanner.py lines 61-69):
```python
SCANNER_SYSTEM = "\n\n".join([
    _ROLE_INTRO,
    IRON_RULES,
    FRONTMATTER_RULES,
    _STUB_SCHEMA,
    _SCANNER_RULES,
    _RED_FLAGS,
    _TOKEN_BUDGET,
])
```

**Target pattern** (from blueprint, scanner.py §Step 3):
```python
from graph_wiki_agent.prompts._fragments.architecture_overview import ARCHITECTURE_OVERVIEW
from graph_wiki_agent.prompts._fragments.log_format import LOG_FORMAT

def build_scanner_system(project_context: str = "") -> str:
    parts = [
        _ROLE_INTRO,
        IRON_RULES,
        ARCHITECTURE_OVERVIEW,
        FRONTMATTER_RULES,
        LOG_FORMAT,
        _STUB_SCHEMA,
        _SCANNER_RULES,
        _RED_FLAGS,
        _TOKEN_BUDGET,
    ]
    if project_context:
        parts.insert(1, project_context)  # after role line, before IRON_RULES
    return "\n\n".join(parts)

# Backward-compat constant for imports that currently use SCANNER_SYSTEM directly
SCANNER_SYSTEM = build_scanner_system()
```

Notes:
- The existing `SCANNER_SYSTEM` constant is imported by `commands/scan.py` (line 34) and re-exported. After this change `SCANNER_SYSTEM` stays as a module-level attribute (composed with empty context) for backward compat. `commands/scan.py` will switch to calling `build_scanner_system(project_context=...)` instead.
- Fragment insertion order: role → project_context (if present) → IRON_RULES → ARCHITECTURE_OVERVIEW → FRONTMATTER_RULES → LOG_FORMAT → local rules.

---

### `prompts/linter.py` (prompt-builder, transform — wiring change)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/linter.py` (self)

**Current composition pattern** (linter.py lines 33-63, excerpt):
```python
LINTER_PAGE_QUALITY_SYSTEM = "\n\n".join([
    """\nYou are a code wiki quality linter...""",
    IRON_RULES,
    LINT_PRIORITY_ORDER,
    """## Semantic check categories\n...""",
    """## Output format\n...""",
])
```

**Target pattern:**
```python
from graph_wiki_agent.prompts._fragments.claude_md_disambiguation import CLAUDE_MD_DISAMBIGUATION
from graph_wiki_agent.prompts._fragments.log_format import LOG_FORMAT

def build_linter_page_quality_system(project_context: str = "") -> str:
    parts = [role_intro, IRON_RULES, LINT_PRIORITY_ORDER, LOG_FORMAT,
             CLAUDE_MD_DISAMBIGUATION, semantic_checks_section, output_format_section]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)

# ADR and stale-claims groups get LOG_FORMAT + CLAUDE_MD_DISAMBIGUATION too
```

Notes:
- All three group prompts (page_quality, adr_chain, stale_claims) get `LOG_FORMAT` and `CLAUDE_MD_DISAMBIGUATION`.
- The three module-level constants (`LINTER_PAGE_QUALITY_SYSTEM`, `LINTER_ADR_CHAIN_SYSTEM`, `LINTER_STALE_CLAIMS_SYSTEM`) stay as backward-compat attributes (built with empty context).
- `commands/lint.py` line 423 passes the system prompt string directly; it will switch to calling the builder.

---

### `prompts/ingestor.py` (prompt-builder, transform — wiring change)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/ingestor.py` (self)

**Current composition pattern** (ingestor.py lines 85-96):
```python
INGESTOR_SYSTEM = "\n\n".join([
    _ROLE_INTRO,
    IRON_RULES,
    PAGE_CATEGORIES,
    FRONTMATTER_RULES,
    CITATION_RULES,
    _PAGE_TYPE_ROUTING,
    _INGESTOR_RULES,
    _RED_FLAGS,
    _OUTPUT_FORMAT,
    _NO_CODE_FENCE,
])
```

**Target pattern:**
```python
from graph_wiki_agent.prompts._fragments.architecture_overview import ARCHITECTURE_OVERVIEW
from graph_wiki_agent.prompts._fragments.claude_md_disambiguation import CLAUDE_MD_DISAMBIGUATION
from graph_wiki_agent.prompts._fragments.log_format import LOG_FORMAT
from graph_wiki_agent.prompts._fragments.style_rules import STYLE_RULES

def build_ingestor_system(project_context: str = "") -> str:
    parts = [
        _ROLE_INTRO, IRON_RULES, ARCHITECTURE_OVERVIEW, PAGE_CATEGORIES,
        FRONTMATTER_RULES, CITATION_RULES, STYLE_RULES, CLAUDE_MD_DISAMBIGUATION,
        LOG_FORMAT, _PAGE_TYPE_ROUTING, _INGESTOR_RULES, _RED_FLAGS,
        _OUTPUT_FORMAT, _NO_CODE_FENCE,
    ]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)

INGESTOR_SYSTEM = build_ingestor_system()
```

Notes:
- `_NO_CODE_FENCE` must stay last (existing comment at lines 71-76 explains why — it is the most recent instruction the LLM reads).
- `commands/ingest.py` line 422 uses `INGESTOR_SYSTEM` directly as a positional arg: `SystemMessage(INGESTOR_SYSTEM)` — this will switch to `SystemMessage(build_ingestor_system(project_context=ctx))`.

---

### `prompts/librarian.py` (prompt-builder, transform — wiring change)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/librarian.py` (self)

**Current composition pattern** (librarian.py lines 54-62):
```python
LIBRARIAN_SYSTEM = "\n\n".join([
    _ROLE_INTRO,
    IRON_RULES,
    PAGE_CATEGORIES,
    CITATION_RULES,
    _WORKFLOW,
    _RED_FLAGS,
    _OUTPUT_FORMAT,
])
```

**Target pattern:**
```python
from graph_wiki_agent.prompts._fragments.style_rules import STYLE_RULES

def build_librarian_system() -> str:
    return "\n\n".join([
        _ROLE_INTRO, IRON_RULES, PAGE_CATEGORIES, CITATION_RULES,
        STYLE_RULES, _WORKFLOW, _RED_FLAGS, _OUTPUT_FORMAT,
    ])

LIBRARIAN_SYSTEM = build_librarian_system()
```

Notes:
- Librarian does NOT receive `project_context` (per CONTEXT.md §Wiring: "Librarian gets STYLE_RULES only; it does not receive the project-context block").
- No `project_context` kwarg on this builder — keep the signature simple.
- `LIBRARIAN_SYSTEM` stays as a module-level constant for backward compat (no callers need to switch).

---

### `commands/scan.py` (command, request-response — wiring change)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` (self)

**Current SystemMessage assembly** (scan.py lines 34, 341-346):
```python
from graph_wiki_agent.prompts.scanner import SCANNER_SYSTEM  # noqa: F401
...
msgs = [
    SystemMessage(content=SCANNER_SYSTEM),
    HumanMessage(content=prompt),
]
```

**Target wiring pattern** (from blueprint §Step 4):
```python
from graph_wiki_agent.prompts.project_context import render_project_context
from graph_wiki_agent.prompts.scanner import build_scanner_system

# Near top of the invocation path, after wiki is resolved (scan.py line 265):
project_ctx = render_project_context(wiki)
# Inside generate_stub():
msgs = [
    SystemMessage(content=build_scanner_system(project_context=project_ctx)),
    HumanMessage(content=prompt),
]
```

Notes:
- `wiki` is already resolved at line 265 (`wiki, resolved_repo = resolve_wiki_and_repo(vault_path)`). Call `render_project_context(wiki)` once after that line.
- The `generate_stub` closure captures `project_ctx` from the outer scope — no need to pass it as an argument.
- The existing `from graph_wiki_agent.prompts.scanner import SCANNER_SYSTEM` re-export on line 34 stays until `SCANNER_SYSTEM` backward compat is confirmed as unused by other callers (check `__init__.py`).

---

### `commands/lint.py` (command, request-response — wiring change)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/lint.py` (self)

**Current semantic pass assembly** (lint.py lines 422-444, excerpt):
```python
semantic_groups = [
    ("page_quality", LINTER_PAGE_QUALITY_SYSTEM, pages_sample),
    ("adr_chain", LINTER_ADR_CHAIN_SYSTEM, adr_pages),
    ("stale_claims", LINTER_STALE_CLAIMS_SYSTEM, pages_with_source),
]

async def run_linter_group(group_tuple: tuple) -> list[str]:
    name, system_prompt, pages_input = group_tuple
    ...
    msgs = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=_build_linter_input(pages_input)),
    ]
```

**Target wiring:**
```python
from graph_wiki_agent.prompts.project_context import render_project_context
from graph_wiki_agent.prompts.linter import (
    build_linter_page_quality_system,
    build_linter_adr_chain_system,
    build_linter_stale_claims_system,
)

# After wiki resolved (lint.py line 505):
project_ctx = render_project_context(wiki)

semantic_groups = [
    ("page_quality", build_linter_page_quality_system(project_ctx), pages_sample),
    ("adr_chain", build_linter_adr_chain_system(project_ctx), adr_pages),
    ("stale_claims", build_linter_stale_claims_system(project_ctx), pages_with_source),
]
```

Notes:
- `wiki` is resolved at line 505: `wiki, repo = resolve_wiki_and_repo(vault_path)`. Call `render_project_context(wiki)` once after that.
- The three group prompts are built once at `semantic_groups` construction time, not inside the async closure.

---

### `commands/ingest.py` (command, request-response — wiring change)

**Analog:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/ingest.py` (self)

**Current LLM invocation** (ingest.py line 422):
```python
resp = await llm.ainvoke([SystemMessage(INGESTOR_SYSTEM), HumanMessage(prompt)])
```

**Target wiring:**
```python
from graph_wiki_agent.prompts.project_context import render_project_context
from graph_wiki_agent.prompts.ingestor import build_ingestor_system

# After wiki resolved (ingest.py line 379):
project_ctx = render_project_context(wiki)
# At LLM invocation (line 422):
resp = await llm.ainvoke([
    SystemMessage(build_ingestor_system(project_context=project_ctx)),
    HumanMessage(prompt),
])
```

Notes:
- `wiki` is resolved at line 379: `wiki, repo = resolve_wiki_and_repo(vault_path)`. Call `render_project_context(wiki)` once immediately after.

---

### `tests/prompts/test_prompt_snapshots.py` (test — additive change)

**Analog:** `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py` (self)

**Existing test pattern** (test_prompt_snapshots.py lines 19-25):
```python
def test_librarian_system_snapshot(snapshot: SnapshotAssertion) -> None:
    """LIBRARIAN_SYSTEM matches recorded snapshot."""
    try:
        from graph_wiki_agent.prompts.librarian import LIBRARIAN_SYSTEM
    except ImportError:
        pytest.skip("prompts module not yet implemented")
    assert LIBRARIAN_SYSTEM == snapshot
```

**New tests to add** — same pattern, different constants:
- `test_scanner_system_with_project_context` — passes a fixture CLAUDE.md and compares assembled prompt to snapshot.
- `test_scanner_system_without_project_context` — calls `build_scanner_system()` with no args; existing `SCANNER_SYSTEM` snapshot should still pass.
- Same two variants for linter (page_quality, adr_chain, stale_claims groups) and ingestor.

Notes:
- The existing 8 snapshot tests (for `SCANNER_SYSTEM`, `INGESTOR_SYSTEM`, etc.) should continue to pass after wiring because the backward-compat module-level constants are built with empty `project_context`.
- New tests require a `FIXTURE_CLAUDE_MD` fixture string with a valid `<!-- lattice-wiki:layout:start -->` block for `render_project_context` to parse.

---

### `tests/prompts/test_project_context.py` (test — new file)

**Analog:** `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py`

**Pattern to replicate** (blueprint §Step 5):
```python
# tests/prompts/test_project_context.py
import pytest
from syrupy.assertion import SnapshotAssertion

def test_render_project_context_with_claude_md(snapshot: SnapshotAssertion, tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(FIXTURE_CLAUDE_MD)
    from graph_wiki_agent.prompts.project_context import render_project_context
    ctx = render_project_context(wiki)
    assert ctx == snapshot

def test_render_project_context_missing_file(tmp_path):
    from graph_wiki_agent.prompts.project_context import render_project_context
    ctx = render_project_context(tmp_path / "missing")
    assert ctx == ""

def test_scanner_system_degrades_without_claude_md(tmp_path):
    from graph_wiki_agent.prompts.project_context import render_project_context
    from graph_wiki_agent.prompts.scanner import build_scanner_system
    ctx = render_project_context(tmp_path / "missing")
    assert ctx == ""
    prompt = build_scanner_system(project_context=ctx)
    assert prompt  # non-empty string; no crash
```

Notes:
- Test file placement: `tests/prompts/test_project_context.py` alongside the existing `test_prompt_snapshots.py` and `test_provenance.py`.
- `FIXTURE_CLAUDE_MD` should be a module-level string constant containing a minimal but valid `<!-- lattice-wiki:layout:start -->` block (see layout_io.py lines 9-20 for the expected YAML shape) plus stub `## Style` and `## Log format` sections.
- Syrupy snapshot file for this test will be auto-created in `tests/prompts/__snapshots__/test_project_context/` on first `--snapshot-update` run.

---

### `tests/unit/test_token_budget.py` (test — new file)

**Analog:** `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py`

**Pattern:**
```python
# tests/unit/test_token_budget.py
PRE_PHASE_10_BASELINE = {
    "scanner": 1500,   # approximate current token count
    "linter_page_quality": 1200,
    "linter_adr_chain": 1200,
    "linter_stale_claims": 1200,
    "ingestor": 1800,
}
TOKEN_CEILING_DELTA = 1500

def test_scanner_token_budget():
    from graph_wiki_agent.prompts.scanner import build_scanner_system
    prompt = build_scanner_system(project_context="")
    tokens = len(prompt) / 4
    assert tokens <= PRE_PHASE_10_BASELINE["scanner"] + TOKEN_CEILING_DELTA
```

Notes:
- Uses `len(prompt) / 4` as the rule-of-thumb tokenizer per spike-001 §Token cost estimate.
- Test file placed under `tests/unit/` (parallel to existing unit tests like `test_commands_scan.py`).

---

## Shared Patterns

### Provenance header (mandatory on all new fragments)

**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/_fragments/iron_rules.py` lines 1-3
**Apply to:** All 4 new `_fragments/*.py` files
**Enforced by:** `tests/prompts/test_provenance.py` — will FAIL without this header

```python
# Source: cores/prompt-sources/<path>
# Anchor: ## <Section heading> (L<start>-L<end>)
# Source-commit: ef05d991a9ab1ea12b1bc7ebc1fb20ba70074030
```

Constraint: `Source:` path must start with `cores/prompt-sources/` AND the file must exist on disk at that path. The wiki-side fragments (`style_rules`, `log_format`) anchor to the vendored `cores/prompt-sources/wiki-claude-md-template.md` (vendored in commit #0 of this phase, before any fragment that cites it). The SKILL.md-side fragments (`architecture_overview`, `claude_md_disambiguation`) anchor to the existing `cores/prompt-sources/SKILL.md`.

### Prompt-builder function + backward-compat constant pattern

**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/prompts/scanner.py` lines 61-69 (current), plus blueprint §Step 3
**Apply to:** `prompts/scanner.py`, `prompts/linter.py`, `prompts/ingestor.py`

Pattern: add a `build_X_system(project_context: str = "") -> str` function that composes parts and inserts `project_context` at position 1 if non-empty. Retain the module-level constant (`SCANNER_SYSTEM = build_scanner_system()`) for backward compat.

### `render_project_context` call at command entry

**Source:** `agents/graph-wiki-agent/src/graph_wiki_agent/commands/scan.py` line 265 (wiki resolution)
**Apply to:** `commands/scan.py`, `commands/lint.py`, `commands/ingest.py`

Pattern: call `render_project_context(wiki)` once, immediately after `wiki` is resolved by `resolve_wiki_and_repo(...)`. Capture result in `project_ctx`. Pass into prompt builder at the point of `SystemMessage` construction.

### Syrupy snapshot test pattern

**Source:** `agents/graph-wiki-agent/tests/prompts/test_prompt_snapshots.py` lines 19-25
**Apply to:** All new prompt snapshot tests

Pattern: `try/except ImportError` guard → `pytest.skip()` on missing module. `assert X == snapshot`. No assertions on snapshot content directly — let syrupy handle the comparison.

---

## Commit Ordering Constraint

The `test_provenance.py` invariant (every `_fragments/*.py` cites a `Source:` path that exists on disk under `cores/prompt-sources/`) must hold at every commit boundary. This pins the commit order:

1. **Commit #0** — vendor `cores/prompt-sources/wiki-claude-md-template.md` from upstream lattice. No fragment changes; provenance test still passes (no new fragments yet).
2. **Commit #1** — add `architecture_overview.py` (anchors to existing SKILL.md, no dependency on commit #0).
3. **Commit #2** — add `style_rules.py`, `log_format.py`, `claude_md_disambiguation.py`. Provenance test now exercises the wiki-claude-md-template.md anchor; commit #0 must already have landed.
4. **Commit #3** — add `prompts/project_context.py` + unit tests.
5. **Commit #4** — wire fragments into `prompts/scanner.py`, `linter.py`, `ingestor.py`, `librarian.py`.
6. **Commit #5** — wire `render_project_context()` into `commands/scan.py`, `lint.py`, `ingest.py`.
7. **Commit #6** — snapshot tests + divergence-eval re-run.

Reversing commits #0 and #2 would fail `test_provenance.py` on the intermediate commit.

---

## No Analog Found

All files have analogs. No new capability areas without prior art.

---

## Metadata

**Analog search scope:** `agents/graph-wiki-agent/src/`, `cores/vault-io/src/`, `cores/prompt-sources/`, `agents/graph-wiki-agent/tests/`
**Files scanned:** 15 source files, 4 test files
**Pattern extraction date:** 2026-05-17
