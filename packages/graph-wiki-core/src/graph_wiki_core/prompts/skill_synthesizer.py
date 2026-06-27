"""SKILL_SYNTHESIZER_SYSTEM — Pass-2 system prompt for the type-branched ingest skill branch.

Given ONE chunk-plan entry (from the planner), the synthesizer emits ONE complete
guidance page: frontmatter per the guidance-io schema plus a focused `## Guidance`
body and an optional `## Applies to` section.

Exports:
    build_skill_synthesizer_system(project_context: str = "") -> str
    SKILL_SYNTHESIZER_SYSTEM — backward-compat constant.
"""

from __future__ import annotations

_ROLE_INTRO = (
    "You are a guidance-page synthesizer. You receive ONE chunk-plan entry describing a\n"
    "single piece of reusable technical guidance, and you emit ONE complete guidance\n"
    "page for a code wiki.\n\n"
    "Output ONLY the page: YAML frontmatter followed by a markdown body. No commentary."
)

_FRONTMATTER = (
    "## Frontmatter (strict)\n\n"
    "Emit exactly these keys, taking values from the chunk-plan entry:\n"
    "```yaml\n"
    "title: <entry.title>\n"
    "category: guidance          # FIXED — always this literal value\n"
    "language: <entry.language if the chunk-plan entry carries one; omit otherwise>\n"
    "summary: <entry.summary>\n"
    "topic: <entry.topic>\n"
    "applies_when: <entry.applies_when>\n"
    "triggers:                   # copy entry.triggers verbatim (globs/keywords/entities)\n"
    "  globs: []\n"
    "  keywords: []\n"
    "  entities: []\n"
    "tags: []                    # optional coarse tags\n"
    "impact: <entry.impact>      # critical | high | medium | low (lowercase)\n"
    "updated: <today's date, YYYY-MM-DD>\n"
    "tokens: 0\n"
    "```\n\n"
    "`category` MUST be the literal `guidance`. `impact` MUST be lowercase and one of "
    "critical/high/medium/low. Keep `topic` and `title` exactly as given so the page "
    "lands at the planned path. "
    "Copy `language` verbatim from the chunk-plan entry when present; omit it for "
    "agnostic entries (do NOT invent one). (The writer also stamps this deterministically.)"
)

_BODY = (
    "## Body\n\n"
    "1. `# <title>`\n"
    "2. `## Guidance` — the prescriptive content: how to do it correctly and why. "
    "Synthesize from `entry.content`. No padding, no restating the title.\n"
    "3. Optional `## Incorrect` / `## Correct` code examples when they sharpen the point.\n"
    "4. `## Applies to` — ONLY when `entry.triggers.entities` is non-empty: one "
    "`- [[entities/...]]` bullet per entity. Omit the section entirely when there are "
    "no entities.\n"
)

_FORMAT = (
    "## Output format (strict)\n\n"
    "Begin the response with `---` on its own line. Do NOT wrap the page in a markdown "
    "code fence of any kind. The first three characters MUST be `---`."
)


def build_skill_synthesizer_system(project_context: str = "") -> str:
    """Assemble the skill-synthesizer system prompt.

    Args:
        project_context: Optional project-context block; inserted after the role
            intro when non-empty.

    Returns:
        The assembled system prompt string.
    """
    parts = [_ROLE_INTRO, _FRONTMATTER, _BODY, _FORMAT]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)


SKILL_SYNTHESIZER_SYSTEM = build_skill_synthesizer_system()
