"""Structured output parsing and validation for the query orchestrator."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from wiki_io.update_index import parse_frontmatter

from graph_wiki_core.agent_tools import body_without_frontmatter

ALLOWED_SOURCE_TYPES = {"wiki", "code"}
ALLOWED_FRESHNESS = {"fresh", "stale", "unknown"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}
DEGRADED_STATUS_VALUES = {"degraded", "failed", "error", "blocked", "stale"}
DEGRADED_STATUS_KEYS = ("ingest_status", "proposal_status", "status")
PLACEHOLDER_MARKERS = ("todo", "placeholder", "no narrative available", "needs review")
MIN_MEANINGFUL_BODY_CHARS = 40
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
UNCERTAINTY_WORDS = ("uncertain", "uncertainty", "may", "might", "appears", "suggests", "possibly")
FrozenValue = Mapping[str, Any] | tuple[Any, ...] | str | int | float | bool | None


class OrchestratorValidationError(ValueError):
    """Raised when orchestrator output does not match the structured contract."""


@dataclass(frozen=True)
class OrchestratorEvidence:
    id: str
    source_type: str
    path: str
    freshness: str
    staleness_reason: str | None
    excerpt: str
    line_refs: list[str]


@dataclass(frozen=True)
class AnswerEvidenceMap:
    claim: str
    evidence_ids: list[str]


@dataclass(frozen=True)
class EvidenceGap:
    question: str
    reason: str


@dataclass(frozen=True)
class FreshnessClassification:
    freshness: str
    reason: str | None


@dataclass(frozen=True)
class OrchestratorOutput:
    answer_markdown: str
    citations: list[str]
    evidence: list[OrchestratorEvidence]
    answer_evidence_map: list[AnswerEvidenceMap]
    worker_plan: tuple[Mapping[str, Any], ...]
    worker_results: tuple[Mapping[str, Any], ...]
    gaps: list[EvidenceGap]
    confidence: str


def classify_wiki_freshness(page_path: Path, *, repo_head: str | None) -> FreshnessClassification:
    """Classify whether wiki evidence is fresh enough to use as current evidence."""

    try:
        text = page_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return FreshnessClassification(freshness="unknown", reason="wiki page not found")

    metadata = parse_frontmatter(text)
    body = body_without_frontmatter(text)

    if _has_drift_review(metadata.get("drift_review")):
        return FreshnessClassification(freshness="stale", reason="drift_review")

    last_updated_commit = metadata.get("last_updated_commit")
    if repo_head and last_updated_commit and str(last_updated_commit) != repo_head:
        return FreshnessClassification(freshness="stale", reason="last_updated_commit mismatch")

    if _has_placeholder_content(body):
        return FreshnessClassification(freshness="stale", reason="placeholder content")

    if _has_degraded_status(metadata):
        return FreshnessClassification(freshness="stale", reason="degraded status")

    if repo_head and last_updated_commit and str(last_updated_commit) == repo_head:
        return FreshnessClassification(freshness="fresh", reason=None)

    return FreshnessClassification(freshness="unknown", reason=None)


def parse_orchestrator_output(
    raw: str | dict[str, Any],
    *,
    require_stale_claim_gaps: bool = False,
) -> OrchestratorOutput:
    """Parse raw orchestrator output and validate its structured contract.

    Parsing always performs structural and cross-reference validation. Pass
    require_stale_claim_gaps=True to also require stale-only claim support to
    include an explicit gap or uncertainty wording.
    """

    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OrchestratorValidationError(f"Invalid JSON orchestrator output: {exc}") from exc
    else:
        payload = raw

    if not isinstance(payload, dict):
        raise OrchestratorValidationError("Orchestrator output must be a JSON object")
    _validate_top_level_keys(payload)

    output = OrchestratorOutput(
        answer_markdown=_required_non_empty_str(payload, "answer_markdown"),
        citations=_str_list(payload["citations"], "citations"),
        evidence=_parse_evidence_rows(payload["evidence"]),
        answer_evidence_map=_parse_answer_evidence_map(payload["answer_evidence_map"]),
        worker_plan=_object_tuple(payload["worker_plan"], "worker_plan"),
        worker_results=_object_tuple(payload["worker_results"], "worker_results"),
        gaps=_parse_gaps(payload["gaps"]),
        confidence=_required_non_empty_str(payload, "confidence"),
    )
    validate_orchestrator_output(output, require_stale_claim_gaps=require_stale_claim_gaps)
    return output


def _has_drift_review(value: Any) -> bool:
    if not value:
        return False
    if isinstance(value, dict):
        status = value.get("status")
        if status is not None:
            return _status_value_is_stale(status)
        return bool(value)
    if isinstance(value, list | tuple | set):
        return any(_has_drift_review(item) for item in value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "false", "none", "null", "[]", "{}"}:
            return False
        if "status:" in normalized or "status=" in normalized:
            return "status: stale" in normalized or "status=stale" in normalized
        return True
    return True


def _has_placeholder_content(body: str) -> bool:
    normalized = " ".join(body.split()).lower()
    if len(normalized) < MIN_MEANINGFUL_BODY_CHARS:
        return True
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _has_degraded_status(metadata: Mapping[str, Any]) -> bool:
    return any(_status_value_is_stale(metadata.get(key)) for key in DEGRADED_STATUS_KEYS)


def _status_value_is_stale(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_status_value_is_stale(item) for item in value.values())
    if isinstance(value, list | tuple | set):
        return any(_status_value_is_stale(item) for item in value)
    if value is None:
        return False
    return str(value).strip().lower() in DEGRADED_STATUS_VALUES


def _validate_top_level_keys(payload: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - payload.keys())
    if missing:
        raise OrchestratorValidationError(f"Missing required top-level orchestrator output keys: {missing}")
    extra = sorted(payload.keys() - REQUIRED_TOP_LEVEL_KEYS)
    if extra:
        raise OrchestratorValidationError(f"Unexpected top-level orchestrator output keys: {extra}")


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
        if not row.path.strip():
            raise OrchestratorValidationError("evidence path must be non-empty")
        if row.staleness_reason is not None and not row.staleness_reason.strip():
            raise OrchestratorValidationError("evidence staleness_reason must be non-empty when present")
        if not row.excerpt.strip():
            raise OrchestratorValidationError("evidence excerpt must be non-empty")

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


def _str_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError(f"{field} must be a list of strings")
    if not all(isinstance(item, str) for item in value):
        raise OrchestratorValidationError(f"{field} must be a list of strings")
    return list(value)


def _object_tuple(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError(f"{field} must be a list of objects")
    if not all(isinstance(item, dict) for item in value):
        raise OrchestratorValidationError(f"{field} must be a list of objects")
    return tuple(_freeze_mapping(item) for item in value)


def _freeze_mapping(value: dict[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: Any) -> FrozenValue:
    if isinstance(value, dict):
        return _freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


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
                path=_required_non_empty_str(item, "path"),
                freshness=_required_non_empty_str(item, "freshness"),
                staleness_reason=_optional_non_empty_str(item, "staleness_reason"),
                excerpt=_required_non_empty_str(item, "excerpt"),
                line_refs=_str_list(item.get("line_refs"), "line_refs"),
            )
        )
    return rows


def _optional_non_empty_str(payload: dict[str, Any], field: str) -> str | None:
    if field not in payload:
        raise OrchestratorValidationError(f"{field} must be present")
    value = payload[field]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise OrchestratorValidationError(f"{field} must be a string or null")
    return value


def _parse_answer_evidence_map(value: Any) -> list[AnswerEvidenceMap]:
    if not isinstance(value, list | tuple):
        raise OrchestratorValidationError("answer_evidence_map must be a list")
    rows = []
    for item in value:
        if not isinstance(item, dict):
            raise OrchestratorValidationError("answer_evidence_map rows must be objects")
        if "evidence_ids" not in item:
            raise OrchestratorValidationError("answer_evidence_map rows must include evidence_ids")
        evidence_ids = _str_list(item["evidence_ids"], "evidence_ids")
        if not evidence_ids:
            raise OrchestratorValidationError("answer_evidence_map evidence_ids must be non-empty")
        rows.append(
            AnswerEvidenceMap(
                claim=_required_non_empty_str(item, "claim"),
                evidence_ids=evidence_ids,
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
        gaps.append(
            EvidenceGap(
                question=_required_non_empty_str(item, "question"),
                reason=_required_non_empty_str(item, "reason"),
            )
        )
    return gaps


def _is_stale_only_claim(row: AnswerEvidenceMap, evidence_by_id: dict[str, OrchestratorEvidence]) -> bool:
    if not row.evidence_ids:
        return False
    mapped_evidence = [evidence_by_id[evidence_id] for evidence_id in row.evidence_ids]
    return all(evidence.freshness == "stale" for evidence in mapped_evidence)


def _contains_uncertainty_note(answer_markdown: str) -> bool:
    answer_lower = answer_markdown.lower()
    return any(_contains_uncertainty_word(answer_lower, word) for word in UNCERTAINTY_WORDS)


def _contains_uncertainty_word(answer_lower: str, word: str) -> bool:
    if word == "may":
        return re.search(r"\bmay\b(?!\s+\d{4}\b)", answer_lower) is not None
    return re.search(rf"\b{re.escape(word)}\b", answer_lower) is not None
