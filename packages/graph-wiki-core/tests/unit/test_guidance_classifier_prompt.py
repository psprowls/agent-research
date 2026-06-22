from __future__ import annotations

from graph_wiki_core.prompts.guidance_classifier import (
    build_guidance_classifier_prompt,
    parse_classifier_response,
)
from guidance_io.vocab import Vocab


def _vocab() -> Vocab:
    return Vocab(
        topics=frozenset({"python", "langchain"}),
        tags=frozenset({"retry", "resilience"}),
        aliases={"retries": "retry"},
        vocab_hash="h",
    )


def test_build_prompt_includes_vocab_and_path() -> None:
    system, human = build_guidance_classifier_prompt(
        "packages/foo/bar.py",
        head="def f(): ...",
        symbols=["f", "Bar"],
        topics=["python", "langchain"],
        tags=["retry", "resilience"],
    )
    assert isinstance(system, str) and isinstance(human, str)
    assert "packages/foo/bar.py" in human
    assert "python" in human and "langchain" in human
    assert "retry" in human and "resilience" in human


def test_parse_keeps_only_in_vocab() -> None:
    text = "topics: [python, ruby]\ntags: [Retries, made-up]\n"
    out = parse_classifier_response(text, _vocab())
    assert out == {"topics": ["python"], "tags": ["retry"]}


def test_parse_tolerates_code_fence() -> None:
    text = "```yaml\ntopics: [langchain]\ntags: [resilience]\n```"
    out = parse_classifier_response(text, _vocab())
    assert out == {"topics": ["langchain"], "tags": ["resilience"]}


def test_parse_malformed_returns_empty() -> None:
    assert parse_classifier_response("not yaml: [", _vocab()) == {"topics": [], "tags": []}
    assert parse_classifier_response("", _vocab()) == {"topics": [], "tags": []}
    assert parse_classifier_response("- a\n- b\n", _vocab()) == {"topics": [], "tags": []}
