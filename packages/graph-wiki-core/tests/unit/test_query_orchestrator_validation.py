"""Validation tests for query orchestrator structured output."""

from __future__ import annotations

import pytest
from graph_wiki_core.commands.query_orchestrator import (
    EvidenceGap,
    OrchestratorEvidence,
    OrchestratorValidationError,
    parse_orchestrator_output,
    validate_orchestrator_output,
)


def _valid_payload() -> dict[str, object]:
    return {
        "answer_markdown": "The scanner writes entity pages from code evidence.",
        "citations": ["wiki/entities/scanner.md"],
        "evidence": [
            {
                "id": "ev1",
                "source_type": "wiki",
                "path": "wiki/entities/scanner.md",
                "freshness": "fresh",
                "staleness_reason": None,
                "excerpt": "Scanner-owned entity pages are refreshed during scan.",
                "line_refs": ["wiki/entities/scanner.md:12"],
            }
        ],
        "answer_evidence_map": [
            {
                "claim": "The scanner writes entity pages.",
                "evidence_ids": ["ev1"],
            }
        ],
        "worker_plan": [{"worker": "librarian", "task": "Read scanner entity page."}],
        "worker_results": [{"worker": "librarian", "status": "complete"}],
        "gaps": [],
        "confidence": "medium",
    }


def test_parse_orchestrator_output_accepts_valid_payload() -> None:
    output = parse_orchestrator_output(_valid_payload())

    assert output.answer_markdown == "The scanner writes entity pages from code evidence."
    assert output.confidence == "medium"
    assert output.citations == ["wiki/entities/scanner.md"]
    assert output.evidence == [
        OrchestratorEvidence(
            id="ev1",
            source_type="wiki",
            path="wiki/entities/scanner.md",
            freshness="fresh",
            staleness_reason=None,
            excerpt="Scanner-owned entity pages are refreshed during scan.",
            line_refs=["wiki/entities/scanner.md:12"],
        ),
    ]
    assert output.gaps == []


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.update(answer_markdown=""), "answer_markdown"),
        (
            lambda payload: payload["evidence"].append(  # type: ignore[index, union-attr]
                {
                    "id": "ev1",
                    "source_type": "code",
                    "path": "packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py",
                    "freshness": "fresh",
                    "staleness_reason": None,
                    "excerpt": "Duplicate evidence id.",
                    "line_refs": ["packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py:1"],
                }
            ),
            "unique",
        ),
        (
            lambda payload: payload.update(
                answer_evidence_map=[{"claim": "Missing evidence.", "evidence_ids": ["missing"]}]
            ),
            "missing",
        ),
        (
            lambda payload: payload["evidence"][0].update(source_type="graph"),  # type: ignore[index, union-attr]
            "source_type",
        ),
        (lambda payload: payload.update(confidence="certain"), "confidence"),
    ],
)
def test_parse_orchestrator_output_rejects_invalid_payloads(mutation, message: str) -> None:
    payload = _valid_payload()
    mutation(payload)

    with pytest.raises(OrchestratorValidationError, match=message):
        parse_orchestrator_output(payload)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda row: row.pop("path"), "path"),
        (lambda row: row.pop("excerpt"), "excerpt"),
        (lambda row: row.update(line_refs="wiki/entities/scanner.md:12"), "line_refs"),
        (lambda row: row.update(staleness_reason=123), "staleness_reason"),
    ],
)
def test_parse_orchestrator_output_rejects_invalid_evidence_schema(mutation, message: str) -> None:
    payload = _valid_payload()
    mutation(payload["evidence"][0])  # type: ignore[index]

    with pytest.raises(OrchestratorValidationError, match=message):
        parse_orchestrator_output(payload)


@pytest.mark.parametrize(
    "field",
    [
        "answer_markdown",
        "citations",
        "evidence",
        "answer_evidence_map",
        "worker_plan",
        "worker_results",
        "gaps",
        "confidence",
    ],
)
def test_parse_orchestrator_output_rejects_missing_required_top_level_keys(field: str) -> None:
    payload = _valid_payload()
    del payload[field]

    with pytest.raises(OrchestratorValidationError, match=field):
        parse_orchestrator_output(payload)


def test_parse_orchestrator_output_rejects_extra_top_level_keys() -> None:
    payload = _valid_payload()
    payload["unexpected"] = "extra"

    with pytest.raises(OrchestratorValidationError, match="unexpected"):
        parse_orchestrator_output(payload)


@pytest.mark.parametrize("field", ["worker_plan", "worker_results"])
def test_parse_orchestrator_output_rejects_worker_fields_that_are_not_object_arrays(field: str) -> None:
    payload = _valid_payload()
    payload[field] = ["not an object row"]

    with pytest.raises(OrchestratorValidationError, match=field):
        parse_orchestrator_output(payload)


def test_parse_orchestrator_output_rejects_answer_map_missing_evidence_ids() -> None:
    payload = _valid_payload()
    payload["answer_evidence_map"] = [{"claim": "The scanner writes entity pages."}]

    with pytest.raises(OrchestratorValidationError, match="evidence_ids"):
        parse_orchestrator_output(payload)


def test_parse_orchestrator_output_rejects_answer_map_empty_evidence_ids() -> None:
    payload = _valid_payload()
    payload["answer_evidence_map"] = [{"claim": "The scanner writes entity pages.", "evidence_ids": []}]

    with pytest.raises(OrchestratorValidationError, match="evidence_ids"):
        parse_orchestrator_output(payload)


@pytest.mark.parametrize(
    ("gap", "message"),
    [
        ({"reason": "Needs fresh code verification."}, "question"),
        ({"question": "Is this still true?"}, "reason"),
        ({"question": "", "reason": "Needs fresh code verification."}, "question"),
        ({"question": "Is this still true?", "reason": ""}, "reason"),
    ],
)
def test_parse_orchestrator_output_rejects_invalid_gaps(gap: dict[str, str], message: str) -> None:
    payload = _valid_payload()
    payload["gaps"] = [gap]

    with pytest.raises(OrchestratorValidationError, match=message):
        parse_orchestrator_output(payload)


def test_parse_orchestrator_output_returns_immutable_worker_rows() -> None:
    output = parse_orchestrator_output(_valid_payload())

    with pytest.raises(TypeError):
        output.worker_plan[0]["worker"] = "code_reader"


def test_parse_orchestrator_output_returns_recursively_immutable_worker_rows() -> None:
    payload = _valid_payload()
    payload["worker_plan"] = [{"worker": "librarian", "args": {"pages": ["wiki/entities/scanner.md"]}}]

    output = parse_orchestrator_output(payload)

    with pytest.raises(TypeError):
        output.worker_plan[0]["args"]["pages"][0] = "changed"


def test_parse_orchestrator_output_copies_worker_rows() -> None:
    payload = _valid_payload()
    payload["worker_plan"] = [{"worker": "librarian", "args": {"pages": ["wiki/entities/scanner.md"]}}]

    output = parse_orchestrator_output(payload)
    payload["worker_plan"][0]["args"]["pages"][0] = "changed"  # type: ignore[index]

    assert output.worker_plan[0]["args"]["pages"][0] == "wiki/entities/scanner.md"


def test_parse_orchestrator_output_rejects_invalid_json_string() -> None:
    with pytest.raises(OrchestratorValidationError, match="Invalid JSON"):
        parse_orchestrator_output("{not-json")


def test_stale_only_claim_support_requires_gap_or_uncertainty_note() -> None:
    payload = _valid_payload()
    payload["evidence"] = [
        {
            "id": "ev1",
            "source_type": "wiki",
            "path": "wiki/entities/scanner.md",
            "freshness": "stale",
            "staleness_reason": "Wiki page predates current HEAD.",
            "excerpt": "Scanner-owned entity pages are refreshed during scan.",
            "line_refs": ["wiki/entities/scanner.md:12"],
        }
    ]
    output = parse_orchestrator_output(payload)

    with pytest.raises(OrchestratorValidationError, match="stale"):
        validate_orchestrator_output(output, require_stale_claim_gaps=True)

    output_with_gap = parse_orchestrator_output(
        {
            **payload,
            "gaps": [
                {
                    "question": "Does fresh code confirm the scanner still writes entity pages?",
                    "reason": "Only stale wiki evidence supports this claim.",
                }
            ],
        }
    )
    assert output_with_gap.gaps == [
        EvidenceGap(
            question="Does fresh code confirm the scanner still writes entity pages?",
            reason="Only stale wiki evidence supports this claim.",
        )
    ]
    validate_orchestrator_output(output_with_gap, require_stale_claim_gaps=True)


def test_stale_only_claim_support_allows_uncertainty_wording_without_gap() -> None:
    payload = _valid_payload()
    payload["evidence"] = [
        {
            "id": "ev1",
            "source_type": "wiki",
            "path": "wiki/entities/scanner.md",
            "freshness": "stale",
            "staleness_reason": "Wiki page predates current HEAD.",
            "excerpt": "Scanner-owned entity pages are refreshed during scan.",
            "line_refs": ["wiki/entities/scanner.md:12"],
        }
    ]
    output_with_uncertainty = parse_orchestrator_output(
        {**payload, "answer_markdown": "Uncertain: stale wiki evidence suggests the scanner writes entity pages."}
    )
    validate_orchestrator_output(output_with_uncertainty, require_stale_claim_gaps=True)
