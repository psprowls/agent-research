"""Select and format a resume suggestion from the work-index sidecar.

Pure functions consumed by the SessionStart hook: pick the most-recently-touched
in-flight work item (plus a few alternatives) and render the additionalContext
text that offers `/graph-wiki:next <slug>`. No IO, no hook/bash concerns.
"""

from __future__ import annotations

from dataclasses import dataclass

from work_io.archive import TERMINAL_STATUSES

# Terminal statuses are non-actionable; the workflow additionally treats
# `mitigated` as non-actionable. Reuse the shared constant — do not re-hardcode.
NON_ACTIONABLE_STATUSES = frozenset(TERMINAL_STATUSES) | {"mitigated"}

MAX_ALTERNATIVES = 3


@dataclass(frozen=True)
class ResumeItem:
    slug: str
    title: str


@dataclass(frozen=True)
class ResumeSuggestion:
    primary: ResumeItem
    alternatives: list[ResumeItem]


def _to_item(d: dict) -> ResumeItem:
    return ResumeItem(slug=str(d.get("slug") or ""), title=str(d.get("title") or ""))


def select_resume_suggestions(sidecar: dict | None) -> ResumeSuggestion | None:
    """Return the primary in-flight item + up to 3 alternatives, or None.

    None when sidecar is None, has no items, or no item is actionable.
    Actionable = status not in NON_ACTIONABLE_STATUSES. Ordering: updated_at
    desc, then updated (date) desc, then slug asc — always deterministic.
    """
    if not sidecar:
        return None
    items = sidecar.get("items") or []
    actionable = [i for i in items if str(i.get("status", "")).lower() not in NON_ACTIONABLE_STATUSES]
    if not actionable:
        return None

    # Stable two-pass sort: slug ascending first, then the descending recency
    # key on top — ties keep the slug-ascending order.
    actionable.sort(key=lambda i: str(i.get("slug") or ""))
    actionable.sort(
        key=lambda i: (str(i.get("updated_at") or ""), str(i.get("updated") or "")),
        reverse=True,
    )

    primary = _to_item(actionable[0])
    alternatives = [_to_item(i) for i in actionable[1 : 1 + MAX_ALTERNATIVES]]
    return ResumeSuggestion(primary=primary, alternatives=alternatives)


def format_resume_suggestion(suggestion: ResumeSuggestion) -> str:
    """Render the additionalContext text for a suggestion (plain text; the hook
    handles JSON escaping)."""
    p = suggestion.primary
    lines = [
        "<graph-wiki-resume>",
        "You have in-flight graph-wiki work. The most recently touched item is:",
        f"  {p.slug} — {p.title}",
        f'To resume its pipeline run `/graph-wiki:next {p.slug}`. Offer this to the user; they confirm with "yes".',
    ]
    if suggestion.alternatives:
        lines.append("")
        lines.append(
            'Other in-flight items — resume one ONLY on an explicit instruction naming its slug, NOT on a bare "yes":'
        )
        for alt in suggestion.alternatives:
            lines.append(f"  {alt.slug} — {alt.title}")
    lines.append("</graph-wiki-resume>")
    return "\n".join(lines)
