from __future__ import annotations

from graph_wiki_core.prompts.guidance_orchestrator import (
    build_guidance_orchestrator_prompt,
    parse_orchestrator_response,
)


def test_build_prompt_includes_candidates_and_message() -> None:
    system, human = build_guidance_orchestrator_prompt(
        message="add a retry to the bedrock call",
        path_summaries=["packages/x/pool.py — pkg_x [python]"],
        candidates=[
            {
                "slug": "python/retry-patterns",
                "topic": "python",
                "summary": "Add retry/backoff.",
                "applies_when": "flaky remote call",
                "signals_fired": ["index", "entity"],
            }
        ],
    )
    assert isinstance(system, str) and isinstance(human, str)
    assert "add a retry" in human
    assert "python/retry-patterns" in human
    assert "pool.py" in human


def test_parse_keeps_only_candidate_slugs() -> None:
    text = (
        "- slug: python/retry-patterns\n  relevance: high\n  reason: matches retry\n"
        "- slug: python/hallucinated\n  relevance: medium\n  reason: nope\n"
    )
    out = parse_orchestrator_response(text, {"python/retry-patterns"})
    assert len(out) == 1
    assert out[0]["slug"] == "python/retry-patterns"
    assert out[0]["relevance"] == "high"
    assert out[0]["reason"] == "matches retry"


def test_parse_normalizes_unknown_relevance() -> None:
    text = "- slug: a/b\n  relevance: super-high\n  reason: x\n"
    out = parse_orchestrator_response(text, {"a/b"})
    assert out[0]["relevance"] == "low"


def test_parse_tolerates_fence_and_malformed() -> None:
    fenced = "```yaml\n- slug: a/b\n  relevance: low\n  reason: x\n```"
    assert parse_orchestrator_response(fenced, {"a/b"})[0]["slug"] == "a/b"
    assert parse_orchestrator_response("garbage: [", {"a/b"}) == []
    assert parse_orchestrator_response("", {"a/b"}) == []
