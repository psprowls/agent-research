"""Shared prose contract: the out-of-process brief and the result sanitizer.

The brief is the plugin path's whole reason for existing — it must carry the
SAME system prompt and the SAME work order the Bedrock agent receives, so the
two executors cannot drift.
"""

from __future__ import annotations

from graph_wiki_core.commands.scan_contract import ProseRefreshResult, ProseRefreshTask
from graph_wiki_core.prompts.prose_refresher import (
    PROSE_REFRESHER_SYSTEM,
    build_prose_refresh_prompt,
    render_prose_refresh_brief,
    sanitize_prose_result,
)


def _task(**over) -> ProseRefreshTask:
    base = dict(
        uri="pkg:org/repo/pkg-a",
        kind="package",
        name="pkg-a",
        page_path="/ws/wiki/entities/pkg_pkg-a.md",
        graph_path="packages/pkg-a",
        language="python",
        entity_root="packages/pkg-a",
        trigger="diff",
        diff="diff --git a/x b/x\n",
        changed_files=["packages/pkg-a/x.py"],
        page_content="# pkg-a\n\n## Narrative\nold prose\n",
        file_map_rows="| `x.py` | file | — TODO |",
        prose_sections={"## Narrative": "old prose", "## Purpose": "why"},
        graph_context="depends_on: dep:foo",
    )
    base.update(over)
    return ProseRefreshTask(**base)


def test_brief_embeds_system_prompt_and_work_order_verbatim():
    task = _task()
    brief = render_prose_refresh_brief(task, results_path="/ws/.graph-wiki/results/pkg_pkg-a.json")

    assert PROSE_REFRESHER_SYSTEM in brief
    assert build_prose_refresh_prompt(task) in brief


def test_brief_names_the_results_path_and_substitutes_tools():
    brief = render_prose_refresh_brief(_task(), results_path="/ws/.graph-wiki/results/pkg_pkg-a.json")

    assert "/ws/.graph-wiki/results/pkg_pkg-a.json" in brief
    # Tool substitution: Claude Code tools, not the Bedrock tool-loop names.
    for tool in ("Read", "Grep", "Glob", "Write"):
        assert tool in brief
    assert "read_repo_file" not in brief


def test_sanitizer_drops_deterministic_out_of_surface_and_todo_sections():
    result = ProseRefreshResult(
        uri="pkg:a",
        sections={
            "## File map — pkg-a": "| a | b | c |",  # not in the prose surface
            "## Referenced in wiki": "- [[x]]",  # deterministic
            "## Commands": "| cmd |",  # deterministic
            "## Invented": "made up heading",  # outside allowed
            "## Purpose": "> TODO: explain.",  # todo-like body
            "## Narrative": "   ",  # empty after strip
        },
        file_map_descriptions={"src/x.py": "  does   x  ", "src/y.py": "TODO", "src/z.py": ""},
        dir_descriptions={"": "root  dir"},
        overview="TODO — overview of this package's tree.",
    )

    out = sanitize_prose_result(result, allowed_headings=["## Narrative", "## Purpose"])

    assert out.sections == {}
    assert out.file_map_descriptions == {"src/x.py": "does x"}
    assert out.dir_descriptions == {"": "root dir"}
    assert out.overview is None
    assert out.uri == "pkg:a"


def test_sanitizer_keeps_healthy_prose_and_normalizes_headings():
    result = ProseRefreshResult(
        uri="pkg:a",
        sections={"Narrative": "Fresh prose.", "## Purpose": "Real purpose."},
        overview="A package tree.",
    )

    out = sanitize_prose_result(result, allowed_headings=["## Narrative", "## Purpose"])

    assert out.sections == {"## Narrative": "Fresh prose.", "## Purpose": "Real purpose."}
    assert out.overview == "A package tree."


def test_sanitizer_preserves_error_field():
    out = sanitize_prose_result(ProseRefreshResult(uri="pkg:a", error="boom"), allowed_headings=["## Narrative"])
    assert out.error == "boom"
