from __future__ import annotations

from pathlib import Path

from wiki_io.human_sections import (
    find_todo_human_sections,
    is_todo_like_body,
    replace_todo_human_sections,
)


def _page_text(kind: str = "package") -> str:
    return (
        "---\n"
        "uri: pkg:org/repo/pkg-a\n"
        f"kind: {kind}\n"
        "---\n\n"
        "# pkg-a\n\n"
        "## Purpose\n"
        "> TODO: explain why this package exists.\n\n"
        "## Public API\n"
        "TODO list exported functions.\n\n"
        "## Narrative\n"
        "Scanner prose.\n\n"
        "## File map - pkg-a\n"
        "| Path | Kind | Description |\n"
        "|---|---|---|\n"
        "| `src/pkg_a/__init__.py` | file | - TODO |\n\n"
        "## Referenced in wiki\n"
        "- [[concepts/example]]\n\n"
        "## Real Notes\n"
        "Keep this prose.\n"
    )


def test_is_todo_like_body_accepts_existing_template_shapes() -> None:
    assert is_todo_like_body("")
    assert is_todo_like_body("> TODO: explain why this exists.")
    assert is_todo_like_body("> ToDo: explain this.")
    assert is_todo_like_body("todo later")
    assert is_todo_like_body("TODO list exported functions.")
    assert is_todo_like_body("- TODO")
    assert is_todo_like_body("* TODO")
    assert is_todo_like_body("— TODO")
    assert not is_todo_like_body("This package owns scan orchestration.")


def test_is_todo_like_body_rejects_mixed_content() -> None:
    assert not is_todo_like_body("> TODO: fill this in.\n\nReal notes")


def test_find_todo_human_sections_excludes_scanner_owned_sections() -> None:
    sections = find_todo_human_sections(_page_text(), entity_kind="package")

    assert [section.heading for section in sections] == ["Purpose", "Public API"]
    assert all(not section.body.startswith("Scanner prose") for section in sections)


def test_find_todo_human_sections_excludes_mixed_content_sections() -> None:
    text = (
        "---\n"
        "uri: pkg:org/repo/pkg-a\n"
        "kind: package\n"
        "---\n\n"
        "# pkg-a\n\n"
        "## Purpose\n"
        "> TODO: fill this in.\n\n"
        "Real notes\n\n"
        "## Public API\n"
        "TODO list exported functions.\n"
    )

    sections = find_todo_human_sections(text, entity_kind="package")

    assert [section.heading for section in sections] == ["Public API"]


def test_find_todo_human_sections_excludes_agent_plugin_scanner_data_sections() -> None:
    text = (
        "---\nuri: agent_plugin:graph-wiki\nkind: agent_plugin\n---\n\n"
        "# graph-wiki\n\n"
        "## Commands\n"
        "> TODO: scanner data table placeholder.\n\n"
        "## How it fits together\n"
        "> TODO: explain the plugin architecture.\n"
    )

    sections = find_todo_human_sections(text, entity_kind="agent_plugin")

    assert [section.heading for section in sections] == ["How it fits together"]


def test_replace_todo_human_sections_replaces_only_requested_todo_bodies(tmp_path: Path) -> None:
    page = tmp_path / "pkg-a.md"
    page.write_text(_page_text(), encoding="utf-8")

    changed = replace_todo_human_sections(
        page,
        {
            "Purpose": "Owns package-level scan orchestration.",
            "Real Notes": "This must not overwrite real prose.",
            "Unknown": "This must be ignored.",
        },
    )

    text = page.read_text(encoding="utf-8")
    assert changed == ["Purpose"]
    assert "## Purpose\nOwns package-level scan orchestration.\n\n" in text
    assert "## Public API\nTODO list exported functions." in text
    assert "## Real Notes\nKeep this prose." in text
    assert "Unknown" not in text


def test_replace_todo_human_sections_rejects_still_placeholder_replacement(tmp_path: Path) -> None:
    page = tmp_path / "pkg-a.md"
    page.write_text(_page_text(), encoding="utf-8")

    changed = replace_todo_human_sections(page, {"Purpose": "TODO later"})

    assert changed == []
    assert "## Purpose\n> TODO: explain why this package exists." in page.read_text(encoding="utf-8")


def test_replace_todo_human_sections_leaves_mixed_content_sections_untouched(tmp_path: Path) -> None:
    page = tmp_path / "pkg-a.md"
    page.write_text(
        (
            "---\n"
            "uri: pkg:org/repo/pkg-a\n"
            "kind: package\n"
            "---\n\n"
            "# pkg-a\n\n"
            "## Purpose\n"
            "> TODO: fill this in.\n\n"
            "Real notes\n"
        ),
        encoding="utf-8",
    )

    changed = replace_todo_human_sections(page, {"Purpose": "Owns package-level scan orchestration."})

    assert changed == []
    assert "> TODO: fill this in.\n\nReal notes" in page.read_text(encoding="utf-8")
