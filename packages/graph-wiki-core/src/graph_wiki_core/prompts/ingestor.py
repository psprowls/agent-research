"""INGESTOR_SYSTEM prompt composed from shared fragments + ingestor-local prose.

Ports plugins/graph-wiki/agents/ingestor.md per PORT-03 (Phase 6).
Adapts host-specific references (slash commands, script calls, interactive
loops) to graph-wiki-core's non-interactive tool surface per RESEARCH §Adaptation Map.
Preserves semantic rules: page-type routing, frontmatter fields, minimum-3-touches,
cite-aggressively, red flags.

Exports:
    build_ingestor_system(project_context: str = "") -> str — assembles the ingestor
        system prompt. When `project_context` is non-empty, it is inserted at
        position 1 (after the role intro, before IRON_RULES).
    INGESTOR_SYSTEM — backward-compat constant, equals build_ingestor_system().
"""

from __future__ import annotations

from graph_wiki_core.prompts._fragments.architecture_overview import ARCHITECTURE_OVERVIEW
from graph_wiki_core.prompts._fragments.citation_rules import CITATION_RULES
from graph_wiki_core.prompts._fragments.claude_md_disambiguation import CLAUDE_MD_DISAMBIGUATION
from graph_wiki_core.prompts._fragments.frontmatter_rules import FRONTMATTER_RULES
from graph_wiki_core.prompts._fragments.iron_rules import IRON_RULES
from graph_wiki_core.prompts._fragments.log_format import LOG_FORMAT
from graph_wiki_core.prompts._fragments.page_categories import PAGE_CATEGORIES
from graph_wiki_core.prompts._fragments.style_rules import STYLE_RULES

_ROLE_INTRO = (
    "You are a code wiki ingestor. Analyze a source document and produce a wiki page\n"
    "that integrates it into the vault.\n\n"
    "Output ONLY YAML frontmatter followed by a markdown body. No commentary outside\n"
    "these sections."
)

_SOURCE_LANDING = (
    "## Source landing\n\n"
    "Every ingested document becomes a **Source page** under `sources/`. You do "
    "NOT choose the destination — routing is fixed. Do NOT emit a `page_type` "
    "field; it is ignored, and this rule supersedes any `page_type` mentioned "
    "elsewhere in these instructions.\n\n"
    "Emit a `source_type` field with a value from the closed enum: "
    "`spec`, `article`, `pr`, `ticket`, `transcript`, `example`, `doc`, `note`. "
    "Classify from the content and default to `note` when unsure. It is purely "
    "descriptive and does NOT control where the page is written.\n\n"
    "Do NOT author a package page. Code entities (packages, apps, domains, "
    "dependencies, test suites) are scanner-owned and live under `entities/`. "
    "To associate this source with a code entity, reference it from the body with "
    "a `[[entities/<prefix>_<name>]]` wikilink (e.g. `[[entities/pkg_graph-io]]`) "
    "under a `## Touches` section — the scanner derives the backlink onto the "
    "entity page. Never write into `entities/` pages.\n\n"
    "`update_index()` and `append_log()` run automatically — omit those steps."
)

_INGESTOR_RULES = (
    "## Ingestor rules\n\n"
    "- `raw/` and in-repo docs are read-only.\n"
    "- Code is the source of truth; update the vault when they disagree.\n"
    "- Touch ≥3 files: new page + `index.md` + `log.md` (handled by command layer).\n"
    "- Cite aggressively — every claim links to a source page or code path.\n"
    "- Flag contradictions: vault↔vault with `> ⚠️ Contradiction:` callouts; vault↔code with path.\n"
    "- Propose ADRs for decisions.\n\n"
    "## Wikilink discipline (named anti-patterns)\n\n"
    "DO NOT emit `[[wikilink]]` targets that do not already exist in the vault. "
    "Examples of forbidden output observed in past runs:\n"
    "- `[[Person Name]]` for an author/speaker/contributor who has no vault page — "
    'use prose ("Person Name") instead.\n'
    "- `[[subdir/some-slug]]` for a path that does not exist on disk — "
    "either omit the link entirely or use the `NO_RELEVANT_CONTENT` sentinel from the citation rules.\n\n"
    "The command layer post-processes the body and STRIPS any `[[…]]` that "
    "does not resolve to an existing vault page (the wikilink is replaced by its bare "
    "label text and the strip is recorded in `log.md`). If you cite something the "
    "vault doesn't have, the link will be silently removed — don't rely on it."
)

_RED_FLAGS = (
    "## Red flags\n\n"
    "Stop if: source not under `raw/` or a recognized in-repo doc; duplicates an existing\n"
    "page; requires deleting vault pages; or >5 code contradictions."
)

_OUTPUT_FORMAT = (
    "## Output format\n\n"
    "1. YAML frontmatter (`---`) with all required fields.\n"
    "2. `## Summary` (3-5 sentences) on the source.\n"
    "3. Optional `## Key Concepts` or `## Decisions` section.\n"
    "4. `[[wikilink]]` cross-references to vault pages.\n\n"
    "Under 1500 tokens. Synthesize — do not reproduce the full source."
)

# Plan 06-12 / UAT G1: live ingestor runs occasionally wrap the YAML
# frontmatter in a markdown code fence (```yaml ... ```), which violates
# ING-001 (`text.startswith('---')`). Place this rule LAST in the
# composition so it is the most recent instruction the LLM reads before
# generating. Defense-in-depth: commands/ingest.py:_parse_ingestor_response
# also strips a leading fence as a parser-side fallback.
_NO_CODE_FENCE = (
    "## Frontmatter format (strict)\n\n"
    "Begin the response with `---` on its own line. "
    "Do NOT wrap the frontmatter in a markdown code fence "
    "(no ```yaml, no ``` of any kind around the `---` block). "
    "The first three characters of the response MUST be `---`."
)


def build_ingestor_system(project_context: str = "") -> str:
    """Assemble the ingestor system prompt.

    Args:
        project_context: Optional project-context block. When non-empty, inserted
            at position 1 (between _ROLE_INTRO and IRON_RULES).

    Returns:
        The assembled system prompt string. `_NO_CODE_FENCE` is always the
        last fragment per the UAT G1 contract documented above.
    """
    parts = [
        _ROLE_INTRO,
        IRON_RULES,
        ARCHITECTURE_OVERVIEW,
        PAGE_CATEGORIES,
        FRONTMATTER_RULES,
        CITATION_RULES,
        STYLE_RULES,
        CLAUDE_MD_DISAMBIGUATION,
        LOG_FORMAT,
        _SOURCE_LANDING,
        _INGESTOR_RULES,
        _RED_FLAGS,
        _OUTPUT_FORMAT,
        _NO_CODE_FENCE,
    ]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)


INGESTOR_SYSTEM = build_ingestor_system()
