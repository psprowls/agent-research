"""Unit tests for is_todo_like_body / has_todo_prose (relocated from
wiki_io.human_sections.find_todo_human_sections, now boolean-only)."""

from __future__ import annotations

from wiki_io.entity_writer import has_todo_prose, is_todo_like_body


def test_empty_body_is_todo_like() -> None:
    assert is_todo_like_body("") is True
    assert is_todo_like_body("   \n  ") is True


def test_todo_bullet_is_todo_like() -> None:
    assert is_todo_like_body("- TODO: fill this in") is True
    assert is_todo_like_body("> TODO — describe this") is True


def test_real_prose_is_not_todo_like() -> None:
    assert is_todo_like_body("This package handles async fan-out.") is False


def test_mixed_todo_and_prose_is_not_todo_like() -> None:
    # find_todo_human_sections/is_todo_like_body requires EVERY non-blank
    # line to look like a TODO; one real line disqualifies the whole body.
    assert is_todo_like_body("- TODO: fill this in\nBut here is a real sentence.") is False


def test_has_todo_prose_true_when_any_prose_section_is_todo() -> None:
    text = "# P\n\n## Narrative\nReal narrative.\n\n## Purpose\nTODO\n"
    assert has_todo_prose(text) is True


def test_has_todo_prose_false_when_all_prose_sections_filled() -> None:
    text = "# P\n\n## Narrative\nReal narrative.\n\n## Purpose\nReal purpose.\n"
    assert has_todo_prose(text) is False


def test_has_todo_prose_ignores_empty_agent_plugin_commands_table() -> None:
    """An agent_plugin page's `## Commands` table renders `_None._` when the
    plugin defines no commands. That is deterministic scanner output, not
    human-owned TODO prose, and must never count toward has_todo_prose — this
    is the case the retired `entity_kind` parameter of the old
    find_todo_human_sections used to special-case; it's now implicit because
    prose_section_bodies excludes DETERMINISTIC_SECTIONS (`## Commands`
    among them) unconditionally, for every kind."""
    text = (
        "# demo\n\n"
        "## Narrative\nA demo agent plugin.\n\n"
        "## Commands\n_None._\n\n"
        "## Purpose\nReal purpose, not a TODO.\n"
    )
    assert has_todo_prose(text) is False
