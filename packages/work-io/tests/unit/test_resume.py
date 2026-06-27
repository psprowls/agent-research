from __future__ import annotations

from work_io.resume import (
    ResumeSuggestion,
    format_resume_suggestion,
    select_resume_suggestions,
)


def _item(slug: str, status: str = "open", updated_at: str = "", updated: str = "", title: str = "") -> dict:
    return {
        "slug": slug,
        "title": title or slug,
        "status": status,
        "updated_at": updated_at,
        "updated": updated,
    }


def _sidecar(*items: dict) -> dict:
    return {"schema_version": 1, "items": list(items)}


def test_none_sidecar_returns_none() -> None:
    assert select_resume_suggestions(None) is None


def test_empty_items_returns_none() -> None:
    assert select_resume_suggestions(_sidecar()) is None
    assert select_resume_suggestions({"schema_version": 1}) is None


def test_all_terminal_or_mitigated_returns_none() -> None:
    sidecar = _sidecar(
        _item("a", status="resolved"),
        _item("b", status="wontfix"),
        _item("c", status="superseded"),
        _item("d", status="mitigated"),
    )
    assert select_resume_suggestions(sidecar) is None


def test_orders_by_updated_at_desc() -> None:
    sidecar = _sidecar(
        _item("older", updated_at="2026-06-26T10:00:00+00:00"),
        _item("newer", updated_at="2026-06-26T18:00:00+00:00"),
    )
    result = select_resume_suggestions(sidecar)
    assert isinstance(result, ResumeSuggestion)
    assert result.primary.slug == "newer"
    assert [a.slug for a in result.alternatives] == ["older"]


def test_date_and_slug_fallback_when_updated_at_absent() -> None:
    # equal/absent updated_at -> fall back to `updated` date desc, then slug asc
    sidecar = _sidecar(
        _item("zeta", updated="2026-06-20"),
        _item("alpha", updated="2026-06-25"),
        _item("beta", updated="2026-06-25"),
    )
    result = select_resume_suggestions(sidecar)
    assert result.primary.slug == "alpha"  # newest date, slug tiebreak before beta
    assert [a.slug for a in result.alternatives] == ["beta", "zeta"]


def test_primary_plus_three_alternatives_truncates() -> None:
    sidecar = _sidecar(
        _item("i1", updated_at="2026-06-26T05:00:00+00:00"),
        _item("i2", updated_at="2026-06-26T04:00:00+00:00"),
        _item("i3", updated_at="2026-06-26T03:00:00+00:00"),
        _item("i4", updated_at="2026-06-26T02:00:00+00:00"),
        _item("i5", updated_at="2026-06-26T01:00:00+00:00"),
    )
    result = select_resume_suggestions(sidecar)
    assert result.primary.slug == "i1"
    assert [a.slug for a in result.alternatives] == ["i2", "i3", "i4"]  # i5 dropped


def test_single_actionable_item_has_no_alternatives() -> None:
    result = select_resume_suggestions(_sidecar(_item("solo")))
    assert result.primary.slug == "solo"
    assert result.alternatives == []


def test_format_contains_primary_offer() -> None:
    result = select_resume_suggestions(_sidecar(_item("my-slug", title="My Title")))
    text = format_resume_suggestion(result)
    assert "/graph-wiki:next my-slug" in text
    assert "My Title" in text


def test_format_lists_alternatives_with_explicit_slug_note() -> None:
    sidecar = _sidecar(
        _item("primary", updated_at="2026-06-26T05:00:00+00:00", title="Primary"),
        _item("alt-one", updated_at="2026-06-26T04:00:00+00:00", title="Alt One"),
    )
    text = format_resume_suggestion(select_resume_suggestions(sidecar))
    assert "alt-one" in text
    # alternatives must call out that they need an explicit slug, not a bare "yes"
    assert "slug" in text.lower()
