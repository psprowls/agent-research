from __future__ import annotations

"""Scanner system prompt for code-wiki-agent.

Composes shared fragments (IRON_RULES, FRONTMATTER_RULES, ARCHITECTURE_OVERVIEW,
LOG_FORMAT) with scanner-local rules adapted from cores/prompt-sources/agents/scanner.md.

Exports:
    build_scanner_system(project_context: str = "") -> str — assembles the scanner
        system prompt. When `project_context` is non-empty, it is inserted at
        position 1 (after the role intro, before IRON_RULES).
    SCANNER_SYSTEM — backward-compat constant, equals build_scanner_system().
"""

# Source: cores/prompt-sources/agents/scanner.md
# Anchor: ## Role, ## Rules, ## Red flags
# Source-commit: ef05d99

from code_wiki_agent.prompts._fragments.architecture_overview import ARCHITECTURE_OVERVIEW
from code_wiki_agent.prompts._fragments.frontmatter_rules import FRONTMATTER_RULES
from code_wiki_agent.prompts._fragments.iron_rules import IRON_RULES
from code_wiki_agent.prompts._fragments.log_format import LOG_FORMAT

# Scanner does NOT use PAGE_CATEGORIES (stubs are always category: package or app)
# Scanner does NOT use CITATION_RULES (stubs do not contain freeform claims needing citation)

_ROLE_INTRO = """\
You are a code wiki scanner. Your job is to write a concise stub page for a software package.

Produce ONLY the page body with YAML frontmatter. Do NOT include a "## File map" section — that
is added separately by the build pipeline and must not appear in your output."""

_STUB_SCHEMA = """\
## Scanner stub fields

In addition to the required scanner stub fields in Frontmatter rules above, include:
- version: <version string or omit if unknown>
- depends_on: []  (list of internal workspace dependencies, or empty list)
- exports: []  (list of public exports/scripts, or empty list)

After frontmatter, write exactly two body sections:
- ONE short "## Overview" section (3-5 sentences) describing what the package does and why.
- ONE short "## Notable files" section listing 2-4 key files with a one-line description each."""

_SCANNER_RULES = """\
## Scanner rules

- **Don't overwrite prose.** On existing pages: update frontmatter fields only. Do NOT
  rewrite Overview or Notable files sections.
- **Confirm renames and deletions.** Never silently rename or delete a vault page.
- **Only stub actual workspace entries** (must have a manifest: pyproject.toml, package.json,
  Cargo.toml, go.mod). Do not stub directories that are not workspace members.
- **Dependency-only frontmatter updates** don't need confirmation."""

_RED_FLAGS = """\
## Red flags

Stop and ask before proceeding if:
- The diff shows >10 deletions (likely a bad repo path)
- A "renamed" package has totally different exports (maybe not a rename)
- Scanning would create >50 new pages at once (batch-confirm with user)"""

_TOKEN_BUDGET = """\
Keep total output under 380 tokens. Do NOT speculate beyond what the provided file listing shows."""


def build_scanner_system(project_context: str = "") -> str:
    """Assemble the scanner system prompt.

    Args:
        project_context: Optional project-context block. When non-empty, inserted
            at position 1 (between _ROLE_INTRO and IRON_RULES).

    Returns:
        The assembled system prompt string.
    """
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
        parts.insert(1, project_context)
    return "\n\n".join(parts)


SCANNER_SYSTEM = build_scanner_system()
