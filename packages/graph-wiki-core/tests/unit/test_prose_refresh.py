"""Unit tests for the unified prose-refresh agent's parser and prompt builder."""

from __future__ import annotations

import json

from graph_wiki_core.commands.prose_refresh import (
    build_prose_refresh_prompt,
    parse_prose_refresher_output,
)
from graph_wiki_core.commands.scan_contract import ProseRefreshTask

ALLOWED = ["## Narrative", "## Purpose"]


def _payload(**over):
    base = {
        "sections": [{"heading": "## Narrative", "replacement_markdown": "New prose."}],
        "file_map_descriptions": {"src/x.py": "does x"},
        "dir_descriptions": {"src": "sources"},
        "overview": "pkg overview",
    }
    base.update(over)
    return json.dumps(base)


def test_parse_happy_path():
    r = parse_prose_refresher_output(_payload(), allowed_headings=ALLOWED)
    assert r.error is None
    assert r.sections == {"## Narrative": "New prose."}
    assert r.file_map_descriptions == {"src/x.py": "does x"}
    assert r.dir_descriptions == {"src": "sources"}
    assert r.overview == "pkg overview"


def test_parse_normalizes_bare_heading_and_tolerates_fence():
    raw = "```json\n" + _payload(sections=[{"heading": "Narrative", "replacement_markdown": "Prose."}]) + "\n```"
    r = parse_prose_refresher_output(raw, allowed_headings=ALLOWED)
    assert r.sections == {"## Narrative": "Prose."}


def test_parse_drops_deterministic_unknown_and_todo_bodies():
    raw = _payload(
        sections=[
            {"heading": "## Referenced in wiki", "replacement_markdown": "hax"},
            {"heading": "## Unknown", "replacement_markdown": "x"},
            {"heading": "## Purpose", "replacement_markdown": "TODO"},
            {"heading": "## Narrative", "replacement_markdown": "   "},
        ]
    )
    r = parse_prose_refresher_output(raw, allowed_headings=ALLOWED)
    assert r.sections == {} and r.error is None


def test_parse_invalid_json_returns_error():
    r = parse_prose_refresher_output("not json", allowed_headings=ALLOWED)
    assert r.sections == {} and r.error is not None


def test_parse_non_object_returns_error():
    r = parse_prose_refresher_output("[1,2]", allowed_headings=ALLOWED)
    assert r.error is not None


def _task(**over):
    base = dict(
        uri="pkg:demo",
        kind="package",
        name="demo",
        page_path="/w/entities/pkg_demo.md",
        graph_path="packages/demo",
        language="python",
        entity_root="packages/demo",
        trigger="diff",
        diff="diff --git a/x b/x\n@@ -1 +1 @@\n+x\n",
        changed_files=["x"],
        page_content="# demo page",
        file_map_rows="| `x.py` | file | — TODO |",
        prose_sections={"## Narrative": "old"},
        graph_context="Language: python",
        owning_short_head=None,
    )
    base.update(over)
    return ProseRefreshTask(**base)


def test_prompt_diff_first():
    prompt = build_prose_refresh_prompt(_task())
    assert prompt.index("@@ -1 +1 @@") < prompt.index("## Narrative")
    assert "Language: python" in prompt and "# demo page" in prompt


def test_prompt_first_fill_variant():
    prompt = build_prose_refresh_prompt(_task(trigger="first_fill", diff=None))
    assert "first fill — no diff" in prompt


def test_prompt_history_rewritten_variant():
    prompt = build_prose_refresh_prompt(_task(trigger="diff", diff=None))
    assert "history rewritten" in prompt
