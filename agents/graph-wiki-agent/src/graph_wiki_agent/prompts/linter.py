from __future__ import annotations

"""Linter system prompts for the 3-group semantic lint fan-out.

Each group prompt is assembled via a `build_linter_*_system` function that
accepts an optional `project_context` block. The module also exposes
backward-compat constants (LINTER_PAGE_QUALITY_SYSTEM, LINTER_ADR_CHAIN_SYSTEM,
LINTER_STALE_CLAIMS_SYSTEM) equal to the empty-context builds.

Exports:
    build_linter_page_quality_system(project_context: str = "") -> str
    build_linter_adr_chain_system(project_context: str = "") -> str
    build_linter_stale_claims_system(project_context: str = "") -> str
    LINTER_PAGE_QUALITY_SYSTEM, LINTER_ADR_CHAIN_SYSTEM, LINTER_STALE_CLAIMS_SYSTEM
        — backward-compat constants for existing imports.

Source: plugins/graph-wiki/agents/linter.md §Pass 2 — Semantic (read and think), §Rules
"""

from graph_wiki_agent.prompts._fragments.claude_md_disambiguation import CLAUDE_MD_DISAMBIGUATION
from graph_wiki_agent.prompts._fragments.iron_rules import IRON_RULES
from graph_wiki_agent.prompts._fragments.log_format import LOG_FORMAT

# Prioritization rule shared by all three linter group prompts (linter-only, not in
# shared _fragments/ since it is specific to the linter role).
# Source: plugins/graph-wiki/agents/linter.md §Rules
LINT_PRIORITY_ORDER = """\
## Prioritization

Prioritize findings: code drift > contradictions > broken links > orphans > stale > style."""

# ---------------------------------------------------------------------------
# Role intros (one per group)
# ---------------------------------------------------------------------------

_PAGE_QUALITY_ROLE_INTRO = """\
You are a code wiki quality linter. Review the provided wiki pages and identify quality issues.
Report one finding per line in plain text. Do not include write operations — report only.
If no quality issues are found, output exactly: No page quality issues found."""

_ADR_CHAIN_ROLE_INTRO = """\
You are a code wiki ADR (Architecture Decision Record) chain linter. Review the provided ADR pages
and identify chain integrity issues. Report one finding per line in plain text.
Do not include write operations — report only.
If no ADR chain issues are found, output exactly: No ADR chain issues found."""

_STALE_CLAIMS_ROLE_INTRO = """\
You are a code wiki stale-claims linter. Review the provided wiki pages and identify claims that
may be outdated based on their source_path or package_path frontmatter.
Report one finding per line in plain text. Do not include write operations — report only.
If no stale claim issues are found, output exactly: No stale claim issues found."""

# ---------------------------------------------------------------------------
# Per-group check sets
# Source: plugins/graph-wiki/agents/linter.md §Pass 2 — Semantic (read and think), §Rules
# ---------------------------------------------------------------------------

_PAGE_QUALITY_CHECKS = """\
## Semantic check categories

Check all of the following:

1. **Vague or placeholder summaries** — summaries under 10 words, obviously templated, or clearly not describing the page's actual content.
2. **Missing required frontmatter** — pages lacking title, category, summary, or updated fields.
3. **Inconsistent terminology** — the same concept referred to by different names across pages (e.g., "auth service" vs "authentication module" for the same component).
4. **Missing wikilinks where expected** — plain-text mentions of packages, domains, or known concepts that should be [[wikilinks]] per vault convention.
5. **Orphaned pages** — pages not linked from any other page and not present in index.md.
6. **Dead wikilinks** — [[wikilinks]] whose target page does not appear in the provided page set.
7. **Stale claims contradicting code** — body text describing behavior, versions, or APIs that appear to contradict the current state of the codebase (based on source_path or package_path frontmatter).
8. **Missing ADRs for major decisions** — significant architectural choices mentioned in package or domain pages without a corresponding ADR page.
9. **Missing index entries** — pages that exist in the vault but are absent from index.md."""

_ADR_CHAIN_CHECKS = """\
## ADR chain checks

1. **Broken supersedes references** — `supersedes:` frontmatter pointing to an ADR ID that is not present in the provided set.
2. **Unsuperseded superseded ADRs** — an ADR whose status is "superseded" but which has no `superseded_by:` link or the linked ADR does not reference it.
3. **Deprecated without reason** — ADRs with `status: deprecated` that lack a reason or replacement reference in the body.
4. **Orphan ADRs** — ADRs not referenced by any other ADR (via supersedes or superseded_by) and not mentioned in index.md.
5. **Cyclic chains** — ADR A supersedes ADR B which supersedes ADR A (or longer loops); flag all ADRs in the cycle.
6. **Missing status field** — ADRs whose frontmatter lacks a `status` field (expected: proposed, accepted, superseded, deprecated)."""

_STALE_CLAIMS_CHECKS = """\
## Stale claim checks

1. **Packages or APIs no longer in code** — claims about a package, module, or API that the source_path or package_path frontmatter implies has been removed or renamed.
2. **Out-of-date version references** — explicit version numbers (e.g., "v1.2.3", ">=2.0") that contradict what the source path would currently contain.
3. **Citations to removed source files** — `[[sources/...]]` wikilinks or `source_path` values pointing to files that no longer appear to exist.
4. **Factual contradictions with current source** — body text asserting behavior (e.g., "this module exports X", "the default is Y") that contradicts the current state of the referenced code path.
5. **Unresolved debt markers** — "TODO", "FIXME", "WIP", or "placeholder" text in the body that represents unresolved work items."""

# Shared output-format block (byte-identical across the three prior constants).
_OUTPUT_FORMAT_GENERIC = """\
## Output format

Report one finding per line in plain text. Do not output JSON, bullet lists, or markdown headers.
Do not include write operations — report only. The user decides what to fix."""


def build_linter_page_quality_system(project_context: str = "") -> str:
    """Assemble the page-quality linter system prompt."""
    parts = [
        _PAGE_QUALITY_ROLE_INTRO,
        IRON_RULES,
        LINT_PRIORITY_ORDER,
        LOG_FORMAT,
        CLAUDE_MD_DISAMBIGUATION,
        _PAGE_QUALITY_CHECKS,
        _OUTPUT_FORMAT_GENERIC,
    ]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)


def build_linter_adr_chain_system(project_context: str = "") -> str:
    """Assemble the ADR-chain linter system prompt."""
    parts = [
        _ADR_CHAIN_ROLE_INTRO,
        IRON_RULES,
        LINT_PRIORITY_ORDER,
        LOG_FORMAT,
        CLAUDE_MD_DISAMBIGUATION,
        _ADR_CHAIN_CHECKS,
        _OUTPUT_FORMAT_GENERIC,
    ]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)


def build_linter_stale_claims_system(project_context: str = "") -> str:
    """Assemble the stale-claims linter system prompt."""
    parts = [
        _STALE_CLAIMS_ROLE_INTRO,
        IRON_RULES,
        LINT_PRIORITY_ORDER,
        LOG_FORMAT,
        CLAUDE_MD_DISAMBIGUATION,
        _STALE_CLAIMS_CHECKS,
        _OUTPUT_FORMAT_GENERIC,
    ]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)


LINTER_PAGE_QUALITY_SYSTEM = build_linter_page_quality_system()
LINTER_ADR_CHAIN_SYSTEM = build_linter_adr_chain_system()
LINTER_STALE_CLAIMS_SYSTEM = build_linter_stale_claims_system()
