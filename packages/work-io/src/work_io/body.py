"""Render the default body for a freshly filed work item.

Emits the scaffolding sections the work pipeline and humans fill in, instead of
the one-line ## Summary stub. The ## Plan header is shared with plan_table so
filing and ensure_plan_row keep one definition; an empty (header+separator, no
data rows) table parses as state="empty", satisfying the accepted-without-plan
lint rule.
"""

from __future__ import annotations

from work_io.lifecycle_lint import BUG_LIKE_KINDS
from work_io.plan_table import _PLAN_TABLE_HEADER


def render_default_work_body(summary: str, kind: str) -> str:
    """Build the default work-item body for the given kind.

    Always emits ## Summary, an empty ## Plan table, and ## Notes / log.
    Feature-shaped kinds also get an ## Options considered section; bug-shaped
    kinds design via debugging, not option-weighing, so it is omitted.
    """
    sections = [f"## Summary\n{summary}\n"]
    if kind not in BUG_LIKE_KINDS:
        sections.append("## Options considered\n")
    sections.append("## Plan\n\n" + "\n".join(_PLAN_TABLE_HEADER) + "\n")
    sections.append("## Notes / log\n")
    return "\n".join(sections)
