"""Render the default body for a freshly filed work item.

The body comes from a per-kind markdown template under assets/bodies/. Each
template is a body fragment (no frontmatter, no H1) with two placeholders:
{summary} (the item's summary text) and {plan_table} (the canonical empty Plan
table). An unknown/missing kind falls back to bodies/default.md.

The ## Plan header + empty table is shared with plan_table via the single
_PLAN_TABLE_HEADER definition, kept as a {plan_table} placeholder so the table
is never copied into the template files (9 copies could drift and break the
accepted-without-plan lint rule, which needs an empty table to parse as
state="empty").
"""

from __future__ import annotations

from work_io.plan_table import _PLAN_TABLE_HEADER
from work_io.templates import templates_dir


def render_default_work_body(summary: str, kind: str) -> str:
    """Build the default work-item body for the given kind.

    Resolves bodies/<kind>.md, falling back to bodies/default.md for an unknown
    kind, then substitutes the {summary} and {plan_table} placeholders. Uses
    str.replace (not str.format) so stray { } in template prose cannot raise.
    """
    bodies_dir = templates_dir() / "bodies"
    template_path = bodies_dir / f"{kind}.md"
    if not template_path.exists():
        template_path = bodies_dir / "default.md"

    text = template_path.read_text(encoding="utf-8")
    text = text.replace("{plan_table}", "\n".join(_PLAN_TABLE_HEADER))
    text = text.replace("{summary}", summary)
    return text
