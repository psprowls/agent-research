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
    parse_prose_refresh_result_dict,
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


def test_brief_tells_the_subagent_to_include_uri():
    """Task 3's fix: PROSE_REFRESHER_SYSTEM never mentions "uri" (it's an LLM
    response schema written for the Bedrock tool loop, which fills uri
    out-of-band). The out-of-process brief must add that field explicitly, in
    the executor-specific adapter half, without editing the shared system
    prompt (that would change the Bedrock path too).
    """
    task = _task(uri="pkg:org/repo/pkg-a")
    brief = render_prose_refresh_brief(task, results_path="/ws/.graph-wiki/results/pkg_pkg-a.json")

    assert '"uri"' not in PROSE_REFRESHER_SYSTEM
    assert '"uri": "pkg:org/repo/pkg-a"' in brief


def test_documented_response_schema_round_trips_through_the_loader():
    """Structural pin: build a payload using exactly the key names
    PROSE_REFRESHER_SYSTEM documents ("sections", "heading",
    "replacement_markdown") and confirm parse_prose_refresh_result_dict
    recognizes them. If a future edit renames what the doc tells the model to
    write without updating the parser (or vice versa), one of these two
    assertions catches it: first that the doc still promises these exact key
    names, second that the parser still keys on them.
    """
    for key in ('"sections"', '"heading"', '"replacement_markdown"'):
        assert key in PROSE_REFRESHER_SYSTEM, f"{key} no longer documented in PROSE_REFRESHER_SYSTEM"

    payload = {
        "uri": "pkg:org/repo/pkg-a",
        "sections": [{"heading": "## Narrative", "replacement_markdown": "Fresh prose."}],
    }
    result = parse_prose_refresh_result_dict(payload)

    assert result.uri == "pkg:org/repo/pkg-a"
    assert result.sections == {"## Narrative": "Fresh prose."}

    # A payload using the WRONG key names must not be silently reinterpreted
    # (this is exactly how the original defect went undetected: dict(list of
    # dicts) reinterprets the dicts' own keys as data instead of raising).
    wrong_keys = {"uri": "pkg:org/repo/pkg-a", "sections": [{"section": "## Narrative", "body": "Fresh prose."}]}
    assert parse_prose_refresh_result_dict(wrong_keys).sections == {}


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
