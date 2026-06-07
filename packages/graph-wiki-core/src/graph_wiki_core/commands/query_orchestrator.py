"""Structured output parsing and validation for the query orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

ALLOWED_SOURCE_TYPES = {"wiki", "code"}
ALLOWED_FRESHNESS = {"fresh", "stale", "unknown"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
REQUIRED_TOP_LEVEL_KEYS = {
    "answer_markdown",
    "citations",
    "evidence",
    "answer_evidence_map",
    "worker_plan",
    "worker_results",
    "gaps",
    "confidence",
}
UNCERTAINTY_WORDS = ("uncertain", "uncertainty", "stale", "may", "might", "appears", "suggests", "possibly")


class OrchestratorValidationError(ValueError):
    """Raised when orchestrator output does not match the structured contract."""


@dataclass(frozen=True)
class OrchestratorEvidence:
    id: str
    source_type: str
    source: str
    summary: str
    freshness: str


@dataclass(frozen=True)
class AnswerEvidenceMap:
    claim: str
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceGap:
    detail: MappingProxyType[str, Any]


@dataclass(frozen=True)
class OrchestratorOutput:
    answer_markdown: str
    citations: tuple[str, ...]
    evidence: tuple[OrchestratorEvidence, ...]
    answer_evidence_map: tuple[AnswerEvidenceMap, ...]
    worker_plan: tuple[Mapping[str, Any], ...]
    worker_results: tuple[Mapping[str, Any], ...]
    gaps: tuple[EvidenceGap, ...]
    confidence: str


def parse_orchestrator_output(raw: str | dict[str, Any]) -> OrchestratorOutput:
    """Parse a raw model payload into an OrchestratorOutput and validate it."""

    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OrchestratorValidationError(f"Invalid JSON orchestrator output: {exc}") from exc
    else:
        payload = raw

    if not isinstance(payload, dict):
        raise OrchestratorValidationError("Orchestrator output must be a JSON object")
    _require_top_level_keys(payload)

    output = OrchestratorOutput(
        answer_markdown=_required_non_empty_str(payload, "answer_markdown"),
        citations=_str_tuple(payload["citations"], "citations"),
        evidence=tuple(_parse_evidence_rows(payload["evidence"])),
        answer_evidence_map=tuple(_parse_answer_evidence_map(payload["answer_evidence_map"])),
        worker_plan=_object_tuple(payload["worker_plan"], "worker_plan"),
        worker_results=_object_tuple(payload["worker_results"], "worker_results"),
        gaps=tuple(_parse_gaps(payload["gaps"])),
        confidence=_required_non_empty_str(payload, "confidence"),
    )
    validate_orchestrator_output(output, require_stale_claim_gaps=False)
    return output


def _require_top_level_keys(payload: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - payload.keys())
    if missing:
        raise OrchestratorValidationError(f"Missing required top-level orchestrator output keys: {missing}")


def validate_orchestrator_output(
    output: OrchestratorOutput,
    require_stale_claim_gaps: bool = True,
) -> None:
    """Validate cross-field invariants in parsed orchestrator output."""

    if not output.answer_markdown.strip():
        raise OrchestratorValidationError("answer_markdown must be non-empty")
    if output.confidence not in ALLOWED_CONFIDENCE:
        raise OrchestratorValidationError(
            f"confidence must be one of {sorted(ALLOWED_CONFIDENCE)}; got {output.confidence!r}"
        )

    evidence_ids: set[str] = set()
    evidence_by_id: dict[str, OrchestratorEvidence] = {}
    for row in output.evidence:
        if not row.id.strip():
            raise OrchestratorValidationError("evidence id must be non-empty")
        if row.id in evidence_ids:
            raise OrchestratorValidationError(f"evidence ids must be unique; duplicate {row.id!r}")
        evidence_ids.add(row.id)
        evidence_by_id[row.id] = row

        if row.source_type not in ALLOWED_SOURCE_TYPES:
            raise OrchestratorValidationError(
                f"source_type must be one of {sorted(ALLOWED_SOURCE_TYPES)}; got {row.source_type!r}"
            )
        if row.freshness not in ALLOWED_FRESHNESS:
            raise OrchestratorValidationError(
                f"freshness must be one of {sorted(ALLOWED_FRESHNESS)}; got {row.freshness!r}"
            )
        if not row.source.strip():
            raise OrchestratorValidationError("evidence source must be non-empty")
        if not row.summary.strip():
            raise OrchestratorValidationError("evidence summary must be non-empty")

    for row in output.answer_evidence_map:
        if not row.claim.strip():
            raise OrchestratorValidationError("answer_evidence_map claim must be non-empty")
        missing_ids = [evidence_id for evidence_id in row.evidence_ids if evidence_id not in evidence_by_id]
        if missing_ids:
            raise OrchestratorValidationError(f"answer_evidence_map references missing evidence ids: {missing_ids}")

        if require_stale_claim_gaps and _is_stale_only_claim(row, evidence_by_id):
            if not output.gaps and not _contains_uncertainty_note(output.answer_markdown):
                raise OrchestratorValidationError(
                    "stale-only claim support requires a gap entry or uncertainty wording in answer_markdown"
                )


def _required_non_empty_str(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise OrchestratorValidationError(f"{field} must be a non-empty string")
    return value


def _str_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError(f"{field} must be a list of strings")
    if not all(isinstance(item, str) for item in value):
        raise OrchestratorValidationError(f"{field} must be a list of strings")
    return tuple(value)


def _object_tuple(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError(f"{field} must be a list of objects")
    if not all(isinstance(item, dict) for item in value):
        raise OrchestratorValidationError(f"{field} must be a list of objects")
    return tuple(MappingProxyType(dict(item)) for item in value)


def _parse_evidence_rows(value: Any) -> list[OrchestratorEvidence]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError("evidence must be a list")
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise OrchestratorValidationError("evidence rows must be objects")
        rows.append(
            OrchestratorEvidence(
                id=_required_non_empty_str(item, "id"),
                source_type=_required_non_empty_str(item, "source_type"),
                source=_required_non_empty_str(item, "source"),
                summary=_required_non_empty_str(item, "summary"),
                freshness=_required_non_empty_str(item, "freshness"),
            )
        )
    return rows


def _parse_answer_evidence_map(value: Any) -> list[AnswerEvidenceMap]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError("answer_evidence_map must be a list")
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise OrchestratorValidationError("answer_evidence_map rows must be objects")
        if "evidence_ids" not in item:
            raise OrchestratorValidationError("answer_evidence_map rows must include evidence_ids")
        rows.append(
            AnswerEvidenceMap(
                claim=_required_non_empty_str(item, "claim"),
                evidence_ids=_str_tuple(item["evidence_ids"], "evidence_ids"),
            )
        )
    return rows


def _parse_gaps(value: Any) -> list[EvidenceGap]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError("gaps must be a list")
    gaps = []
    for item in value:
        if not isinstance(item, dict):
            raise OrchestratorValidationError("gaps rows must be objects")
        gaps.append(EvidenceGap(detail=MappingProxyType(dict(item))))
    return gaps


def _is_stale_only_claim(row: AnswerEvidenceMap, evidence_by_id: dict[str, OrchestratorEvidence]) -> bool:
    if not row.evidence_ids:
        return False
    mapped_evidence = [evidence_by_id[evidence_id] for evidence_id in row.evidence_ids]
    return all(evidence.freshness == "stale" for evidence in mapped_evidence)


def _contains_uncertainty_note(answer_markdown: str) -> bool:
    answer_lower = answer_markdown.lower()
    return any(word in answer_lower for word in UNCERTAINTY_WORDS)
