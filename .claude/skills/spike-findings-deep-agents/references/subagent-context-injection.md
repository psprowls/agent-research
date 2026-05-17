# Subagent Context Injection

## Requirements

These are non-negotiable for the build that closes this gap:

- Preserve the existing curation discipline. Every fragment under `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/` must carry the standard 3-line provenance header (`# Source:`, `# Anchor:`, `# Source-commit:`).
- Stay within the cost-optimization mindset (see [[user_cost_optimization]]). Total added context per fan-out call should justify itself; target < ~1,500 added tokens per role on top of the current baseline (~1,060 tokens of shared fragments).
- Do **not** require a deepagents migration to fix this. The subagent dispatch primitive is `cores/subagent-runtime/pool.py::SubagentPool`, not `deepagents.SubAgentMiddleware`. A virtual-filesystem solution is out of scope until that architecture decision is taken separately.
- Project-specific context (wiki `CLAUDE.md` layout block, container pins, style, log format) must reach the subagents that scan/lint/ingest. Static skill content alone is not enough — the layout differs per project and changes over a project's lifetime.

## How to Build It

The recommended approach is **Strategy C + D** from the spike report: extend the fragment library with curated extracts, then inject a small rendered project-context block at command entry. Five steps, each an atomic commit.

### Step 1 — New shared fragments

Add four files under `agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/`, each following the existing provenance pattern:

```python
# agents/code-wiki-agent/src/code_wiki_agent/prompts/_fragments/architecture_overview.py
# Source: cores/prompt-sources/SKILL.md
# Anchor: ## Architecture (L34-L69)
# Source-commit: <current commit of cores/prompt-sources/SOURCE-COMMIT>

ARCHITECTURE_OVERVIEW = """\
## Vault layout

[Compact rewrite of the vault layout tree. Drop the user-facing prose; keep
the tree, the conditional-containers note, and the "code is source of truth"
sentence. Target ~600 tokens.]
"""
```

The other three fragments:

| File | Anchor | Approx tokens | Wire into |
|---|---|---|---|
| `style_rules.py` | `lattice/wiki/CLAUDE.md §Style L153-159` | ~150 | ingestor, librarian |
| `log_format.py` | `lattice/wiki/CLAUDE.md §Log format L124-133` | ~120 | scanner, ingestor, linter |
| `claude_md_disambiguation.py` | `cores/prompt-sources/SKILL.md §Cross-tool compatibility L141` | ~80 | linter, ingestor |

### Step 2 — Project-context renderer

Add `agents/code-wiki-agent/src/code_wiki_agent/prompts/project_context.py`:

```python
from __future__ import annotations
from pathlib import Path
from vault_io.layout_io import read_layout

def render_project_context(wiki_path: Path) -> str:
    """Read wiki/CLAUDE.md once and emit a compact project-context block
    suitable for prepending to a subagent SystemMessage.

    Returns an empty string if wiki/CLAUDE.md (or AGENTS.md) is missing —
    the prompt builder treats that as 'no project pins available' and
    falls back to defaults rather than crashing.
    """
    for schema_name in ("CLAUDE.md", "AGENTS.md"):
        schema = wiki_path / schema_name
        if schema.exists():
            layout = read_layout(schema)
            return _render(layout, schema)
    return ""

def _render(layout, schema_path: Path) -> str:
    # Render: containers list + style + log format sections as ~30 lines.
    # Keep deterministic ordering so snapshot tests are stable.
    ...
```

Keep it pure — no LLM calls, no network, no mutation. Output shape (target):

```
## Project layout (parsed from wiki/CLAUDE.md)

Detected containers (vault_dir → classification):
- agents → package (1 child)
- cores → package (4 children)
- eval, lattice, scripts, test-out → skip

## Project style (wiki/CLAUDE.md §Style)
- Be concise; pages are read, not generated.
- Cite aggressively with [[wikilinks]] and `code-paths:line`.
- Update `updated:` whenever a page is touched.

## Log format
## [YYYY-MM-DD] <op> | <title>
Valid ops: scan, ingest, query, lint, create, update, delete, note.
```

### Step 3 — Wire fragments into prompts

Update `prompts/scanner.py`, `prompts/linter.py`, `prompts/ingestor.py`:

```python
# Example: prompts/scanner.py
from code_wiki_agent.prompts._fragments.architecture_overview import ARCHITECTURE_OVERVIEW
from code_wiki_agent.prompts._fragments.log_format import LOG_FORMAT

def build_scanner_system(project_context: str = "") -> str:
    parts = [
        SCANNER_ROLE,
        IRON_RULES,
        ARCHITECTURE_OVERVIEW,
        FRONTMATTER_RULES,
        LOG_FORMAT,
        SCANNER_LOCAL_RULES,
    ]
    if project_context:
        parts.insert(1, project_context)  # right after the role line
    return "\n\n".join(parts)
```

`librarian.py` gets `STYLE_RULES`; `linter.py`'s three group prompts get `CLAUDE_MD_DISAMBIGUATION` and `LOG_FORMAT`. Keep each prompt's existing structure; only add the new fragments.

### Step 4 — Wire into command entries

Update `commands/scan.py`, `commands/lint.py`, `commands/ingest.py` to compute the project context once per invocation:

```python
# commands/scan.py (near the top of the invocation path)
from code_wiki_agent.prompts.project_context import render_project_context
from code_wiki_agent.prompts.scanner import build_scanner_system

project_ctx = render_project_context(wiki)
system_prompt = build_scanner_system(project_context=project_ctx)
...
SystemMessage(content=system_prompt)
```

`commands/query.py` (librarian path) doesn't need the layout block — librarian's context comes from the pages it reads — but it does benefit from `STYLE_RULES`. Wire only `STYLE_RULES` into `build_librarian_system()`.

### Step 5 — Tests

Use `syrupy` (already in the stack) for snapshot tests on assembled system-prompt strings:

```python
# tests/test_prompt_assembly.py
def test_scanner_system_with_project_context(snapshot, tmp_path):
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "CLAUDE.md").write_text(FIXTURE_CLAUDE_MD)
    ctx = render_project_context(wiki)
    prompt = build_scanner_system(project_context=ctx)
    assert prompt == snapshot

def test_scanner_system_degrades_without_claude_md(tmp_path):
    # No wiki/CLAUDE.md present; renderer must return empty string and
    # build_scanner_system must succeed.
    ctx = render_project_context(tmp_path / "missing")
    assert ctx == ""
    prompt = build_scanner_system(project_context=ctx)
    assert "SCANNER_ROLE" not in prompt  # sanity — prompt is the assembled text
    assert prompt  # non-empty
```

Optionally add an eval check using `cores/eval-harness` that compares a recorded linter/librarian output before and after the change, to confirm the added context didn't regress baseline behavior.

## What to Avoid

- **Do not** dump full `SKILL.md` into the system prompt. Roughly half is user-facing or meta (When to use, Quick start, Slash commands, Related skills, Templates, Why this works) and adding it dilutes the load-bearing rules without improving outcomes.
- **Do not** migrate to `deepagents.SubAgentMiddleware` as part of this fix. The current `SubagentPool` works; switching to deepagents-managed subagents is a separate architectural decision worth its own discussion. Conflating the two will blow the scope of a small, well-bounded fix.
- **Do not** add a `read_skill_doc(section)` tool. The current dispatch is single-turn `llm.ainvoke([SystemMessage, HumanMessage])` — no tool loop, no ReAct. Adding a tool means adding a tool loop around every subagent, which is a substantial architecture change for marginal benefit over (C+D).
- **Do not** crash when `wiki/CLAUDE.md` is missing or when `AGENTS.md` is used instead. `render_project_context()` must degrade gracefully to an empty string; prompt builders must accept an empty `project_context` argument and continue.
- **Do not** drop the provenance headers on new fragments. They are the only mechanism keeping the curated fragments aligned with `cores/prompt-sources/SOURCE-COMMIT`. Re-anchor when that file advances.

## Constraints

- **Architecture is fixed (for this fix).** `cores/subagent-runtime/pool.py::SubagentPool` is the dispatch primitive. No deepagents virtual FS available.
- **Token budget per role:** soft ceiling of ~1,500 added tokens above the current ~1,060-token baseline. Combined C+D lands in the 800–1,200 range.
- **Bedrock pricing:** added input cost is marginal at fan-out tier (Qwen3-32B). One lint pass adds ~$0.003; one ingest with 10 page updates adds ~$0.013. Cost is not the constraint — signal-to-noise is.
- **Frontmatter source split:** `frontmatter_rules.py` currently anchors to `cores/prompt-sources/agents/ingestor.md`; the project-side required-fields list lives in `lattice/wiki/CLAUDE.md` (lines 56-67). When extracting style/log fragments, decide whether `frontmatter_rules.py` should also re-anchor to the wiki-side list or stay as the ingestor-specific variant. Leaning toward keeping the ingestor anchor and treating wiki/CLAUDE.md's frontmatter list as the project-pinned override delivered via `render_project_context()`.
- **Source-of-truth file:** `cores/prompt-sources/SOURCE-COMMIT` tracks the upstream lattice-wiki commit our fragments are anchored to. Any new fragment must record the same commit and be re-checked when that file is bumped.

## Origin

Synthesized from spikes: 001
Source files available in: `sources/001-subagent-context-audit/`
