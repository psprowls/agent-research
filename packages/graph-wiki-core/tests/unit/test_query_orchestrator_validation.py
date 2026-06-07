"""Validation tests for query orchestrator structured output."""

from __future__ import annotations

import pytest
from graph_wiki_core.commands.query_orchestrator import (
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
                "source": "wiki/entities/scanner.md",
                "summary": "Scanner-owned entity pages are refreshed during scan.",
                "freshness": "fresh",
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
    assert output.evidence == (
        OrchestratorEvidence(
            id="ev1",
            source_type="wiki",
            source="wiki/entities/scanner.md",
            summary="Scanner-owned entity pages are refreshed during scan.",
            freshness="fresh",
        ),
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.update(answer_markdown=""), "answer_markdown"),
        (
            lambda payload: payload["evidence"].append(  # type: ignore[index, union-attr]
                {
                    "id": "ev1",
                    "source_type": "code",
                    "source": "packages/graph-wiki-core/src/graph_wiki_core/commands/scan.py",
                    "summary": "Duplicate evidence id.",
                    "freshness": "fresh",
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


def test_stale_only_claim_support_requires_gap_or_uncertainty_note() -> None:
    payload = _valid_payload()
    payload["evidence"] = [
        {
            "id": "ev1",
            "source_type": "wiki",
            "source": "wiki/entities/scanner.md",
            "summary": "Scanner-owned entity pages are refreshed during scan.",
            "freshness": "stale",
        }
    ]
    output = parse_orchestrator_output(payload)

    with pytest.raises(OrchestratorValidationError, match="stale"):
        validate_orchestrator_output(output, require_stale_claim_gaps=True)

    output_with_gap = parse_orchestrator_output({**payload, "gaps": [{"claim": "The scanner writes entity pages."}]})
    validate_orchestrator_output(output_with_gap, require_stale_claim_gaps=True)

    output_with_uncertainty = parse_orchestrator_output(
        {**payload, "answer_markdown": "Uncertain: stale wiki evidence suggests the scanner writes entity pages."}
    )
    validate_orchestrator_output(output_with_uncertainty, require_stale_claim_gaps=True)
