"""SKILL_PLANNER_SYSTEM — Pass-1 system prompt for the type-branched ingest skill branch.

The planner reads a full agent skill and emits a YAML list of chunk-plan entries,
one per guidance page to synthesize. It decides chunking from the content: atomic
rules become one page each; a single instructional flow becomes one page.

Exports:
    build_skill_planner_system(project_context: str = "") -> str — assembles the
        planner system prompt. When `project_context` is non-empty it is inserted
        after the role intro.
    SKILL_PLANNER_SYSTEM — backward-compat constant, equals build_skill_planner_system().
"""

from __future__ import annotations

_ROLE_INTRO = (
    "You are a guidance planner. You read a single agent **skill** (behavioral guidance\n"
    "for an AI coding agent) and decide how to break its reusable technical knowledge\n"
    "into one or more **guidance pages** for a code wiki.\n\n"
    "Output ONLY a YAML list. No commentary, no prose outside the YAML, no code fence."
)

_CHUNKING = (
    "## Chunking strategy\n\n"
    "Choose the chunking from the content:\n"
    "- **Rules / atomic directives** (a skill that is a list of independent 'do X' / "
    "'never Y' rules): emit ONE entry per rule.\n"
    "- **How-to / instructional flow** (a single coherent procedure or technique): emit "
    "ONE entry for the whole skill.\n\n"
    "Never split tightly-coupled instructions across multiple entries. When in doubt, "
    "prefer fewer, larger pages over many fragments."
)

_TOPIC = (
    "## Topic\n\n"
    "Infer `topic` from the skill's DOMAIN, not its filename (e.g. a React Native skill "
    "→ `react-native`; a brainstorming skill → `brainstorming`). `topic` is a short "
    "kebab-case slug and becomes the folder under `wiki/guidance/`."
)

_SCHEMA = (
    "## Output schema (YAML list)\n\n"
    "Each entry MUST have these keys:\n"
    "```yaml\n"
    "- title: Use a List Virtualizer for Any List   # human-readable page title\n"
    "  slug: use-list-virtualizer                    # kebab-case; filename stem\n"
    "  topic: react-native                           # domain slug → folder\n"
    "  summary: One-line summary for the wiki spine.\n"
    "  applies_when: Rendering any scrollable list in React Native.\n"
    "  impact: high                                  # critical | high | medium | low\n"
    "  triggers:                                     # all keys optional\n"
    "    globs: ['**/*.tsx']\n"
    "    keywords: [FlatList, ScrollView]\n"
    "    entities: []                                # [[entities/...]] URIs, or []\n"
    "  content: |\n"
    "    Full extracted/paraphrased body for this guidance chunk — everything the\n"
    "    synthesizer needs to write the page WITHOUT re-reading the source.\n"
    "```\n\n"
    "`impact` MUST be one of: critical, high, medium, low (lowercase). Emit `triggers` "
    "with empty lists when you have no signal — do not omit the block. `content` carries "
    "the actual technical substance; make it complete and self-contained."
)

_RULES = (
    "## Rules\n\n"
    "- Treat the source as agent behavioral guidance, not generic documentation.\n"
    "- Extract reusable TECHNICAL knowledge; drop skill-harness scaffolding "
    "(activation phrases, tool-call mechanics, meta-instructions about being a skill).\n"
    "- Begin the response with `- ` (the first YAML list item). No `---`, no code fence."
)


def build_skill_planner_system(project_context: str = "") -> str:
    """Assemble the skill-planner system prompt.

    Args:
        project_context: Optional project-context block; inserted after the role
            intro when non-empty.

    Returns:
        The assembled system prompt string.
    """
    parts = [_ROLE_INTRO, _CHUNKING, _TOPIC, _SCHEMA, _RULES]
    if project_context:
        parts.insert(1, project_context)
    return "\n\n".join(parts)


SKILL_PLANNER_SYSTEM = build_skill_planner_system()
