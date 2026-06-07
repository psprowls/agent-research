# Query Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agentic, evidence-strict query orchestration the default `gw query` and MCP query behavior while keeping the current fixed pipeline as an internal legacy fallback.

**Architecture:** Keep `graph_wiki_core.commands.query.run_query()` as the public entry point for CLI, MCP, and eval callers. Move query-specific orchestration into a new `graph_wiki_core.commands.query_orchestrator` module that reuses `agent_tools`, `agent_loop`, `SubagentPool`, existing graph tools, existing query retrieval helpers, and existing guardrails. Preserve the legacy query path by extracting the current `run_query()` body into `_run_legacy_query()` and routing default calls through the orchestrator after initial BM25/embedding retrieval.

**Tech Stack:** Python 3.11, uv workspace, pytest, pytest-asyncio, LangChain message/tool primitives, Bedrock Converse through `model_adapter.make_llm()`, `subagent_runtime.SubagentPool`, BM25 plus SQLite embeddings, graph-io read-only SQLite graph tools.

---

## File Structure

- Modify: `packages/model-adapter/src/model_adapter/models.toml`
  - Add `[roles.query_orchestrator]` with Kimi K2.5 defaults and max concurrency 1.
- Modify: `packages/model-adapter/tests/test_loader.py`
  - Pin the new role config and include it in role config coverage.
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/query_orchestrator.py`
  - Define the orchestrator system prompt and final JSON contract.
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`
  - Own orchestrator dataclasses, validation, staleness classification, planning tools, worker dispatch, loop control, fallback result construction, and `QueryResult` conversion helpers.
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/code_reader.py`
  - Add an orchestrated prompt branch constant without disrupting the existing fallback prompt.
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`
  - Extract current body to `_run_legacy_query()`, extract initial retrieval to a helper, invoke orchestrator by default, preserve guardrails, traces, and legacy fallback.
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py`
  - Unit-test structured output parsing and evidence rules.
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py`
  - Unit-test all v1 freshness signals.
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py`
  - Unit-test bounded wiki/search/graph planning tools.
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py`
  - Unit-test librarian/code-reader worker batch dispatch through `SubagentPool`.
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py`
  - Unit-test five-batch cap, invalid JSON degradation, and stale-claim verification behavior.
- Modify: `packages/graph-wiki-core/tests/unit/test_query_result.py`
  - Pin `QueryResult` compatibility for orchestrated output.
- Modify: `packages/graph-wiki-core/tests/test_command_overrides.py`
  - Pin role override support for `query_orchestrator`.
- Modify: `packages/graph-wiki-core/tests/test_query_graph_tools.py`
  - Adjust default query expectations from librarian-bound graph tools to orchestrator graph tool availability.
- Modify: `packages/graph-wiki-core/tests/unit/test_query_code_fallback.py`
  - Keep legacy fallback tests pointed at `_run_legacy_query()` or an explicit legacy hook.

## Implementation Notes

- Do not add repo-file read tools to the orchestrator. All source reads go through `code_reader`.
- Do not let graph rows become final answer evidence. Graph tools are planning aids only.
- Keep `QueryResult` unchanged in v1.
- Keep the existing unresolved wikilink guardrail path; orchestration output still passes through `apply_guardrails()`.
- Use `make_llm("query_orchestrator")`, `make_llm("librarian")`, and `make_llm("code_reader")`; never construct Bedrock clients directly.
- In execution, create an isolated worktree first using `superpowers:using-git-worktrees`, then run `uv sync` in that worktree before package tests.

---

### Task 1: Add Query Orchestrator Model Role

**Files:**
- Modify: `packages/model-adapter/src/model_adapter/models.toml`
- Modify: `packages/model-adapter/tests/test_loader.py`

- [ ] **Step 1: Write the failing role-config test**

Add this test near the other role-specific model tests in `packages/model-adapter/tests/test_loader.py`:

```python
def test_query_orchestrator_role_uses_kimi_k25() -> None:
    from langchain_aws import ChatBedrockConverse
    from model_adapter.loader import load_role_config, make_llm

    cfg = load_role_config("query_orchestrator")
    assert cfg["model_id"] == "moonshotai.kimi-k2.5"
    assert cfg["region"] == "us-east-1"
    assert cfg["max_tokens"] == 4096
    assert cfg["max_concurrency"] == 1
    assert cfg["sweep_candidates"] == ["moonshotai.kimi-k2.5"]

    llm = make_llm("query_orchestrator")
    assert isinstance(llm, ChatBedrockConverse)
    actual = getattr(llm, "model_id", None) or getattr(llm, "model", None)
    assert actual == "moonshotai.kimi-k2.5"
```

Also update `ALL_ROLES` in the same file:

```python
ALL_ROLES = [
    "preflight",
    "librarian",
    "scanner",
    "linter",
    "ingestor",
    "synthesizer",
    "judge_a",
    "judge_b",
    "query_orchestrator",
]
```

- [ ] **Step 2: Run the model-adapter test and verify it fails**

Run:

```bash
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py::test_query_orchestrator_role_uses_kimi_k25 -q
```

Expected: FAIL with `KeyError: 'query_orchestrator'`.

- [ ] **Step 3: Add the role config**

Insert this block in `packages/model-adapter/src/model_adapter/models.toml` after `[roles.proposal_reasoner]`:

```toml
[roles.query_orchestrator]
# Default planner/synthesizer for agentic `gw query`. One orchestrator owns
# each query session; worker parallelism is controlled by librarian/code_reader.
model_id        = "moonshotai.kimi-k2.5"
region          = "us-east-1"
max_tokens      = 4096
max_concurrency = 1
sweep_candidates = [
  "moonshotai.kimi-k2.5",
]
```

- [ ] **Step 4: Run the model-adapter tests and verify they pass**

Run:

```bash
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py::test_query_orchestrator_role_uses_kimi_k25 packages/model-adapter/tests/test_loader.py::test_load_role_config_returns_dict_for_all_seven_roles -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/model-adapter/src/model_adapter/models.toml packages/model-adapter/tests/test_loader.py
git commit -m "feat: add query orchestrator model role"
```

---

### Task 2: Add Orchestrator Prompt and Output Schema Validation

**Files:**
- Create: `packages/graph-wiki-core/src/graph_wiki_core/prompts/query_orchestrator.py`
- Create: `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py`

- [ ] **Step 1: Write failing validation tests**

Create `packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py`:

```python
from __future__ import annotations

import pytest

from graph_wiki_core.commands.query_orchestrator import (
    OrchestratorEvidence,
    OrchestratorValidationError,
    parse_orchestrator_output,
    validate_orchestrator_output,
)


def _valid_payload() -> dict:
    return {
        "answer_markdown": "Alpha is handled by [[entities/package/alpha.md]].",
        "citations": ["entities/package/alpha.md"],
        "evidence": [
            {
                "id": "E1",
                "source_type": "wiki",
                "path": "entities/package/alpha.md",
                "freshness": "fresh",
                "staleness_reason": None,
                "excerpt": "Alpha owns the query path.",
                "line_refs": [],
            }
        ],
        "answer_evidence_map": [{"claim": "Alpha owns the query path.", "evidence_ids": ["E1"]}],
        "worker_plan": [],
        "worker_results": [],
        "gaps": [],
        "confidence": "high",
    }


def test_parse_orchestrator_output_accepts_valid_json() -> None:
    result = parse_orchestrator_output(_valid_payload())

    assert result.answer_markdown.startswith("Alpha")
    assert result.confidence == "high"
    assert result.evidence == [
        OrchestratorEvidence(
            id="E1",
            source_type="wiki",
            path="entities/package/alpha.md",
            freshness="fresh",
            staleness_reason=None,
            excerpt="Alpha owns the query path.",
            line_refs=[],
        )
    ]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda p: p.__setitem__("answer_markdown", ""), "answer_markdown"),
        (lambda p: p["evidence"].append(dict(p["evidence"][0])), "unique"),
        (lambda p: p["answer_evidence_map"][0].__setitem__("evidence_ids", ["missing"]), "missing"),
        (lambda p: p["evidence"][0].__setitem__("source_type", "graph"), "source_type"),
        (lambda p: p.__setitem__("confidence", "certain"), "confidence"),
    ],
)
def test_parse_orchestrator_output_rejects_invalid_contract(mutator, message: str) -> None:
    payload = _valid_payload()
    mutator(payload)

    with pytest.raises(OrchestratorValidationError, match=message):
        parse_orchestrator_output(payload)


def test_stale_only_claim_requires_gap_or_uncertainty_note() -> None:
    payload = _valid_payload()
    payload["evidence"][0]["freshness"] = "stale"
    payload["evidence"][0]["staleness_reason"] = "last_updated_commit mismatch"

    with pytest.raises(OrchestratorValidationError, match="stale-only"):
        validate_orchestrator_output(parse_orchestrator_output(payload), require_stale_claim_gaps=True)

    payload["gaps"] = [
        {
            "question": "Whether Alpha still owns the query path.",
            "reason": "Only stale wiki evidence was available.",
        }
    ]
    validate_orchestrator_output(parse_orchestrator_output(payload), require_stale_claim_gaps=True)
```

- [ ] **Step 2: Run the validation tests and verify they fail**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'graph_wiki_core.commands.query_orchestrator'`.

- [ ] **Step 3: Add the orchestrator prompt**

Create `packages/graph-wiki-core/src/graph_wiki_core/prompts/query_orchestrator.py`:

```python
"""System prompt for the agentic query orchestrator role."""

from __future__ import annotations

QUERY_ORCHESTRATOR_SYSTEM = """You are the Graph Wiki query orchestrator.

You answer user questions by planning retrieval, requesting bounded worker
batches, inspecting evidence, and returning exactly one JSON object.

Evidence rules:
- Final answer evidence may use only source_type "wiki" or "code".
- Graph tool observations are planning context only; never emit graph evidence.
- Treat stale wiki content as a clue. Prefer code evidence or fresh linked wiki
  evidence before supporting a final claim with stale wiki evidence.
- If a claim is supported only by stale wiki evidence, label the uncertainty in
  answer_markdown and include a matching gaps entry.
- Do not invent facts, file paths, citations, or line numbers.
- If evidence is insufficient, produce a partial answer with explicit gaps.

Worker plan rules:
- Request librarian tasks for bounded wiki page reading.
- Request code_reader tasks for source verification.
- Do not ask for direct repo file reads from orchestrator tools.

Return JSON matching this contract:
{
  "answer_markdown": "Markdown final answer.",
  "citations": ["entities/package/foo.md"],
  "evidence": [
    {
      "id": "E1",
      "source_type": "wiki",
      "path": "entities/package/foo.md",
      "freshness": "fresh",
      "staleness_reason": null,
      "excerpt": "Relevant excerpt.",
      "line_refs": []
    }
  ],
  "answer_evidence_map": [
    {"claim": "A supported claim.", "evidence_ids": ["E1"]}
  ],
  "worker_plan": [],
  "worker_results": [],
  "gaps": [
    {"question": "What remains unknown?", "reason": "Why evidence is insufficient."}
  ],
  "confidence": "high"
}
"""
```

- [ ] **Step 4: Add dataclasses and validation**

Create `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py` with this initial content:

```python
"""Agentic query orchestration for graph-wiki query."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

EvidenceSourceType = Literal["wiki", "code"]
Freshness = Literal["fresh", "stale", "unknown"]
Confidence = Literal["high", "medium", "low"]

ALLOWED_SOURCE_TYPES = {"wiki", "code"}
ALLOWED_FRESHNESS = {"fresh", "stale", "unknown"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


class OrchestratorValidationError(ValueError):
    """Raised when orchestrator output violates the evidence contract."""


@dataclass(frozen=True)
class OrchestratorEvidence:
    id: str
    source_type: EvidenceSourceType
    path: str
    freshness: Freshness
    staleness_reason: str | None
    excerpt: str
    line_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnswerEvidenceMap:
    claim: str
    evidence_ids: list[str]


@dataclass(frozen=True)
class EvidenceGap:
    question: str
    reason: str


@dataclass(frozen=True)
class OrchestratorOutput:
    answer_markdown: str
    citations: list[str]
    evidence: list[OrchestratorEvidence]
    answer_evidence_map: list[AnswerEvidenceMap]
    worker_plan: list[dict[str, Any]]
    worker_results: list[dict[str, Any]]
    gaps: list[EvidenceGap]
    confidence: Confidence


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OrchestratorValidationError(f"{label} must be an object")
    return value


def _require_str(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise OrchestratorValidationError(f"{label} must be a string")
    if not allow_empty and not value.strip():
        raise OrchestratorValidationError(f"{label} must be non-empty")
    return value


def _require_str_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise OrchestratorValidationError(f"{label} must be a list of strings")
    return list(value)


def _parse_evidence(rows: Any) -> list[OrchestratorEvidence]:
    if not isinstance(rows, list):
        raise OrchestratorValidationError("evidence must be a list")
    evidence: list[OrchestratorEvidence] = []
    seen: set[str] = set()
    for index, raw_row in enumerate(rows):
        row = _require_dict(raw_row, f"evidence[{index}]")
        evidence_id = _require_str(row.get("id"), f"evidence[{index}].id")
        if evidence_id in seen:
            raise OrchestratorValidationError("evidence ids must be unique")
        seen.add(evidence_id)
        source_type = _require_str(row.get("source_type"), f"evidence[{index}].source_type")
        if source_type not in ALLOWED_SOURCE_TYPES:
            raise OrchestratorValidationError("evidence source_type must be wiki or code")
        freshness = _require_str(row.get("freshness"), f"evidence[{index}].freshness")
        if freshness not in ALLOWED_FRESHNESS:
            raise OrchestratorValidationError("evidence freshness must be fresh, stale, or unknown")
        staleness_reason = row.get("staleness_reason")
        if staleness_reason is not None and not isinstance(staleness_reason, str):
            raise OrchestratorValidationError("staleness_reason must be string or null")
        evidence.append(
            OrchestratorEvidence(
                id=evidence_id,
                source_type=source_type,  # type: ignore[arg-type]
                path=_require_str(row.get("path"), f"evidence[{index}].path"),
                freshness=freshness,  # type: ignore[arg-type]
                staleness_reason=staleness_reason,
                excerpt=_require_str(row.get("excerpt"), f"evidence[{index}].excerpt"),
                line_refs=_require_str_list(row.get("line_refs", []), f"evidence[{index}].line_refs"),
            )
        )
    return evidence


def _parse_answer_map(rows: Any) -> list[AnswerEvidenceMap]:
    if not isinstance(rows, list):
        raise OrchestratorValidationError("answer_evidence_map must be a list")
    parsed: list[AnswerEvidenceMap] = []
    for index, raw_row in enumerate(rows):
        row = _require_dict(raw_row, f"answer_evidence_map[{index}]")
        parsed.append(
            AnswerEvidenceMap(
                claim=_require_str(row.get("claim"), f"answer_evidence_map[{index}].claim"),
                evidence_ids=_require_str_list(
                    row.get("evidence_ids", []), f"answer_evidence_map[{index}].evidence_ids"
                ),
            )
        )
    return parsed


def _parse_gaps(rows: Any) -> list[EvidenceGap]:
    if not isinstance(rows, list):
        raise OrchestratorValidationError("gaps must be a list")
    gaps: list[EvidenceGap] = []
    for index, raw_row in enumerate(rows):
        row = _require_dict(raw_row, f"gaps[{index}]")
        gaps.append(
            EvidenceGap(
                question=_require_str(row.get("question"), f"gaps[{index}].question"),
                reason=_require_str(row.get("reason"), f"gaps[{index}].reason"),
            )
        )
    return gaps


def parse_orchestrator_output(raw: str | dict[str, Any]) -> OrchestratorOutput:
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OrchestratorValidationError(f"invalid JSON: {exc.msg}") from exc
    else:
        payload = raw
    payload = _require_dict(payload, "orchestrator output")
    confidence = _require_str(payload.get("confidence"), "confidence")
    if confidence not in ALLOWED_CONFIDENCE:
        raise OrchestratorValidationError("confidence must be high, medium, or low")
    output = OrchestratorOutput(
        answer_markdown=_require_str(payload.get("answer_markdown"), "answer_markdown"),
        citations=_require_str_list(payload.get("citations", []), "citations"),
        evidence=_parse_evidence(payload.get("evidence", [])),
        answer_evidence_map=_parse_answer_map(payload.get("answer_evidence_map", [])),
        worker_plan=list(payload.get("worker_plan", [])) if isinstance(payload.get("worker_plan", []), list) else [],
        worker_results=list(payload.get("worker_results", []))
        if isinstance(payload.get("worker_results", []), list)
        else [],
        gaps=_parse_gaps(payload.get("gaps", [])),
        confidence=confidence,  # type: ignore[arg-type]
    )
    validate_orchestrator_output(output, require_stale_claim_gaps=False)
    return output


def validate_orchestrator_output(
    output: OrchestratorOutput,
    *,
    require_stale_claim_gaps: bool = True,
) -> None:
    evidence_ids = {item.id for item in output.evidence}
    for mapped in output.answer_evidence_map:
        for evidence_id in mapped.evidence_ids:
            if evidence_id not in evidence_ids:
                raise OrchestratorValidationError(f"mapped evidence id is missing: {evidence_id}")
    evidence_by_id = {item.id: item for item in output.evidence}
    for mapped in output.answer_evidence_map:
        mapped_evidence = [evidence_by_id[evidence_id] for evidence_id in mapped.evidence_ids]
        if mapped_evidence and all(item.freshness == "stale" for item in mapped_evidence):
            has_gap = bool(output.gaps)
            uncertainty_words = ("stale", "uncertain", "not verified", "out of date")
            has_note = any(word in output.answer_markdown.lower() for word in uncertainty_words)
            if require_stale_claim_gaps and not has_gap and not has_note:
                raise OrchestratorValidationError("stale-only claim support requires a gap or uncertainty note")
```

- [ ] **Step 5: Run validation tests and verify they pass**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/query_orchestrator.py packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py
git commit -m "feat: validate query orchestrator output"
```

---

### Task 3: Implement Staleness-Aware Wiki Evidence Classification

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py`

- [ ] **Step 1: Write failing staleness tests**

Create `packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py`:

```python
from __future__ import annotations

from pathlib import Path

from graph_wiki_core.commands.query_orchestrator import classify_wiki_freshness


def test_drift_review_marks_wiki_evidence_stale(tmp_path: Path) -> None:
    page = tmp_path / "wiki" / "entities" / "package" / "alpha.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "---\n"
        "title: Alpha\n"
        "drift_review:\n"
        "  status: stale\n"
        "---\n"
        "# Alpha\n"
    )

    result = classify_wiki_freshness(page, repo_head="abc123")

    assert result.freshness == "stale"
    assert result.reason == "drift_review"


def test_last_updated_commit_mismatch_marks_source_backed_entity_stale(tmp_path: Path) -> None:
    page = tmp_path / "wiki" / "entities" / "package" / "alpha.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "---\n"
        "title: Alpha\n"
        "last_updated_commit: old456\n"
        "---\n"
        "# Alpha\n"
    )

    result = classify_wiki_freshness(page, repo_head="new789")

    assert result.freshness == "stale"
    assert result.reason == "last_updated_commit mismatch"


def test_matching_last_updated_commit_marks_source_backed_entity_fresh(tmp_path: Path) -> None:
    page = tmp_path / "wiki" / "entities" / "package" / "alpha.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "---\n"
        "title: Alpha\n"
        "last_updated_commit: abc123\n"
        "---\n"
        "# Alpha\n\n"
        "Real content.\n"
    )

    result = classify_wiki_freshness(page, repo_head="abc123")

    assert result.freshness == "fresh"
    assert result.reason is None


def test_todo_or_placeholder_marks_page_stale(tmp_path: Path) -> None:
    page = tmp_path / "wiki" / "entities" / "package" / "alpha.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\ntitle: Alpha\n---\n# Alpha\n\nPlaceholder\n")

    result = classify_wiki_freshness(page, repo_head="abc123")

    assert result.freshness == "stale"
    assert result.reason == "placeholder content"


def test_degraded_status_marks_page_stale(tmp_path: Path) -> None:
    page = tmp_path / "wiki" / "concepts" / "alpha.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\ntitle: Alpha\ningest_status: degraded\n---\n# Alpha\n\nContent.\n")

    result = classify_wiki_freshness(page, repo_head="abc123")

    assert result.freshness == "stale"
    assert result.reason == "degraded status"


def test_missing_page_is_unknown(tmp_path: Path) -> None:
    result = classify_wiki_freshness(tmp_path / "wiki" / "missing.md", repo_head="abc123")

    assert result.freshness == "unknown"
    assert result.reason == "wiki page not found"
```

- [ ] **Step 2: Run staleness tests and verify they fail**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py -q
```

Expected: FAIL with `ImportError` for `classify_wiki_freshness`.

- [ ] **Step 3: Add freshness classification code**

Append this code to `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`:

```python
from pathlib import Path

from graph_wiki_core.agent_tools import body_without_frontmatter
from wiki_io.update_index import parse_frontmatter


@dataclass(frozen=True)
class FreshnessClassification:
    freshness: Freshness
    reason: str | None


def _metadata_has_degraded_status(metadata: dict[str, Any]) -> bool:
    status_keys = ("ingest_status", "proposal_status", "status")
    degraded_values = {"degraded", "failed", "error", "blocked", "stale"}
    for key in status_keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.lower().strip() in degraded_values:
            return True
    return False


def _body_is_placeholder(body: str) -> bool:
    normalized = " ".join(body.lower().split())
    if not normalized:
        return True
    placeholder_markers = ("todo", "placeholder", "no narrative available", "needs review")
    if any(marker in normalized for marker in placeholder_markers):
        return True
    return len(normalized) < 40


def classify_wiki_freshness(page_path: Path, *, repo_head: str | None) -> FreshnessClassification:
    try:
        text = page_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return FreshnessClassification("unknown", "wiki page not found")

    metadata = parse_frontmatter(text)
    body = body_without_frontmatter(text)
    drift_review = metadata.get("drift_review")
    if drift_review:
        return FreshnessClassification("stale", "drift_review")
    last_updated = metadata.get("last_updated_commit")
    if isinstance(last_updated, str) and repo_head and last_updated.strip() and last_updated.strip() != repo_head:
        return FreshnessClassification("stale", "last_updated_commit mismatch")
    if _body_is_placeholder(body):
        return FreshnessClassification("stale", "placeholder content")
    if _metadata_has_degraded_status(metadata):
        return FreshnessClassification("stale", "degraded status")
    if isinstance(last_updated, str) and repo_head and last_updated.strip() == repo_head:
        return FreshnessClassification("fresh", None)
    return FreshnessClassification("unknown", None)
```

If imports are already present at the top of the file, move these import lines into the existing import block instead of duplicating them:

```python
from pathlib import Path

from graph_wiki_core.agent_tools import body_without_frontmatter
from wiki_io.update_index import parse_frontmatter
```

- [ ] **Step 4: Run staleness and validation tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py
git commit -m "feat: classify query evidence freshness"
```

---

### Task 4: Build Orchestrator Context and Bounded Planning Tools

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py`

- [ ] **Step 1: Write failing planning-tool tests**

Create `packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from graph_wiki_core.commands.query_orchestrator import (
    InitialCandidate,
    build_orchestrator_context,
    build_orchestrator_tools,
)


def _wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "workspace" / "wiki"
    (wiki / "entities" / "package").mkdir(parents=True)
    (wiki / "entities" / "package" / "alpha.md").write_text("---\ntitle: Alpha\n---\n# Alpha\n\nBody")
    (wiki / "concepts").mkdir()
    (wiki / "concepts" / "beta.md").write_text("---\ntitle: Beta\nsummary: Search target\n---\n# Beta\n\nBody")
    return wiki


def test_context_includes_initial_candidates_and_worker_capabilities(tmp_path: Path) -> None:
    wiki = _wiki(tmp_path)
    candidates = [
        InitialCandidate(
            path="entities/package/alpha.md",
            bm25=2.0,
            embed=0.9,
            rrf=0.03,
            excerpt="Alpha excerpt",
        )
    ]

    context = build_orchestrator_context(
        query="Who owns Alpha?",
        wiki=wiki,
        repo_root=tmp_path / "repo",
        repo_head="abc123",
        initial_candidates=candidates,
        graph_available=False,
    )

    assert context["query"] == "Who owns Alpha?"
    assert context["graph"]["available"] is False
    assert context["initial_candidates"][0]["path"] == "entities/package/alpha.md"
    assert "librarian" in context["worker_capabilities"]
    assert "code_reader" in context["worker_capabilities"]


def test_read_wiki_page_tool_is_bounded_to_wiki_root(tmp_path: Path) -> None:
    wiki = _wiki(tmp_path)
    tools = build_orchestrator_tools(wiki=wiki, graph_tools=[])
    read_tool = next(tool for tool in tools if tool.name == "read_wiki_page")

    assert "# Alpha" in read_tool.invoke({"path": "entities/package/alpha.md"})
    assert "ERROR: path is outside wiki" in read_tool.invoke({"path": "../secret.md"})


def test_search_wiki_tool_uses_catalog_and_respects_kind(tmp_path: Path) -> None:
    wiki = _wiki(tmp_path)
    tools = build_orchestrator_tools(wiki=wiki, graph_tools=[])
    search_tool = next(tool for tool in tools if tool.name == "search_wiki")

    result = search_tool.invoke({"query": "Search target", "kind": "concept", "top_k": 5})

    assert "concepts/beta.md" in result
    assert "entities/package/alpha.md" not in result


def test_graph_tools_are_filtered_to_allowed_names(tmp_path: Path) -> None:
    wiki = _wiki(tmp_path)
    cg_find = MagicMock()
    cg_find.name = "cg_find"
    cg_describe = MagicMock()
    cg_describe.name = "cg_describe"
    dangerous = MagicMock()
    dangerous.name = "read_file"

    tools = build_orchestrator_tools(wiki=wiki, graph_tools=[cg_find, cg_describe, dangerous])

    names = {tool.name for tool in tools}
    assert "cg_find" in names
    assert "cg_describe" in names
    assert "read_file" not in names
```

- [ ] **Step 2: Run planning-tool tests and verify they fail**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py -q
```

Expected: FAIL with missing `InitialCandidate` or `build_orchestrator_tools`.

- [ ] **Step 3: Add context and tool builders**

Add this code to `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`:

```python
from langchain_core.tools import BaseTool, tool

from graph_wiki_core.agent_tools import (
    build_wiki_catalog,
    filter_graph_tools,
    read_bounded_wiki_page,
    search_wiki_catalog,
    truncate_text,
)

MAX_ORCHESTRATOR_PAGE_CHARS = 40_000
MAX_INITIAL_EXCERPT_CHARS = 1_500
_ALLOWED_ORCHESTRATOR_GRAPH_TOOLS = {"cg_find", "cg_describe"}


@dataclass(frozen=True)
class InitialCandidate:
    path: str
    bm25: float
    embed: float
    rrf: float
    excerpt: str


def build_orchestrator_context(
    *,
    query: str,
    wiki: Path,
    repo_root: Path,
    repo_head: str | None,
    initial_candidates: list[InitialCandidate],
    graph_available: bool,
) -> dict[str, Any]:
    return {
        "query": query,
        "workspace_wiki": str(wiki),
        "repo_root": str(repo_root),
        "repo_head": repo_head,
        "graph": {
            "available": graph_available,
            "allowed_tools": sorted(_ALLOWED_ORCHESTRATOR_GRAPH_TOOLS) if graph_available else [],
            "evidence_rule": "Graph observations are planning context only, not final answer evidence.",
        },
        "initial_candidates": [
            {
                "path": item.path,
                "scores": {"bm25": item.bm25, "embed": item.embed, "rrf": item.rrf},
                "excerpt": truncate_text(item.excerpt, MAX_INITIAL_EXCERPT_CHARS),
            }
            for item in initial_candidates
        ],
        "worker_capabilities": {
            "librarian": {
                "task_shape": {
                    "worker": "librarian",
                    "page_path": "entities/package/foo.md",
                    "query_focus": "Specific wiki claim to extract",
                    "expected_evidence": "Relevant page-backed excerpts",
                }
            },
            "code_reader": {
                "task_shape": {
                    "worker": "code_reader",
                    "target_paths_or_hints": ["packages/foo/src"],
                    "query_focus": "Specific source behavior to verify",
                    "expected_evidence": "path:line-backed source excerpts",
                }
            },
        },
    }


def build_orchestrator_tools(*, wiki: Path, graph_tools: list[BaseTool]) -> list[BaseTool]:
    catalog = build_wiki_catalog(wiki)

    @tool
    def read_wiki_page(path: str) -> str:
        """Read one markdown page under the wiki root, bounded to a safe size."""
        return read_bounded_wiki_page(wiki, path, max_chars=MAX_ORCHESTRATOR_PAGE_CHARS)

    @tool
    def search_wiki(query: str, kind: str | None = None, top_k: int = 10) -> str:
        """Search the wiki catalog by title, summary, slug, or target slug."""
        limit = max(1, min(int(top_k or 10), 20))
        rows = search_wiki_catalog(catalog, query, kind=kind, limit=limit)
        return json.dumps(rows, indent=2, sort_keys=True)

    @tool
    def list_worker_capabilities() -> str:
        """Describe valid worker task shapes for librarian and code_reader."""
        return json.dumps(
            {
                "librarian": {
                    "required": ["worker", "page_path", "query_focus", "expected_evidence"],
                    "worker": "librarian",
                },
                "code_reader": {
                    "required": ["worker", "target_paths_or_hints", "query_focus", "expected_evidence"],
                    "worker": "code_reader",
                },
            },
            indent=2,
            sort_keys=True,
        )

    return [
        read_wiki_page,
        search_wiki,
        list_worker_capabilities,
        *filter_graph_tools(graph_tools, _ALLOWED_ORCHESTRATOR_GRAPH_TOOLS),
    ]
```

- [ ] **Step 4: Run planning-tool tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py
git commit -m "feat: add query orchestrator planning tools"
```

---

### Task 5: Add Orchestrated Worker Batch Dispatch

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/prompts/code_reader.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py`

- [ ] **Step 1: Write failing worker dispatch tests**

Create `packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from graph_wiki_core.commands.query_orchestrator import WorkerTask, run_worker_batch


@pytest.mark.asyncio
async def test_worker_batch_dispatches_librarian_and_code_reader_through_pool(tmp_path: Path) -> None:
    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    (wiki / "alpha.md").write_text("# Alpha\n\nWiki body")
    (repo / "alpha.py").write_text("def alpha():\n    return 1\n")
    pool = MagicMock()

    async def _run_all(*, items, task, role, model_id, max_concurrency):
        results = []
        for item in items:
            result = await task(item)
            results.append((item.task_id, result.value))
        return MagicMock(successes=results, errors=[])

    pool.run_all = AsyncMock(side_effect=_run_all)
    librarian_llm = MagicMock()
    librarian_llm.ainvoke = AsyncMock(return_value=AIMessage(content='{"evidence": [{"id": "L1"}]}'))
    code_llm = MagicMock()
    code_llm.bind_tools = MagicMock(return_value=code_llm)
    code_llm.ainvoke = AsyncMock(return_value=AIMessage(content='{"evidence": [{"id": "C1"}]}'))

    tasks = [
        WorkerTask(
            task_id="L1",
            worker="librarian",
            page_path="alpha.md",
            query_focus="Find Alpha wiki claim",
            expected_evidence="wiki excerpt",
            target_paths_or_hints=[],
        ),
        WorkerTask(
            task_id="C1",
            worker="code_reader",
            page_path=None,
            query_focus="Verify Alpha code",
            expected_evidence="source excerpt",
            target_paths_or_hints=["alpha.py"],
        ),
    ]

    with patch("graph_wiki_core.commands.query_orchestrator.make_llm") as mock_make_llm:
        mock_make_llm.side_effect = lambda role, **_: librarian_llm if role == "librarian" else code_llm
        results = await run_worker_batch(
            tasks=tasks,
            query="What is Alpha?",
            wiki=wiki,
            repo_root=repo,
            pool=pool,
            role_model_overrides=None,
        )

    roles = [call.kwargs["role"] for call in pool.run_all.await_args_list]
    assert roles == ["librarian", "code_reader"]
    assert results[0]["status"] == "success"
    assert results[1]["status"] == "success"
    assert results[0]["worker"] == "librarian"
    assert results[1]["worker"] == "code_reader"


@pytest.mark.asyncio
async def test_worker_batch_records_worker_failure_and_continues(tmp_path: Path) -> None:
    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    pool = MagicMock()

    async def _run_all(*, items, task, role, model_id, max_concurrency):
        return MagicMock(successes=[], errors=[("bad-task", RuntimeError("boom"))])

    pool.run_all = AsyncMock(side_effect=_run_all)
    task = WorkerTask(
        task_id="L1",
        worker="librarian",
        page_path="missing.md",
        query_focus="Find claim",
        expected_evidence="wiki excerpt",
        target_paths_or_hints=[],
    )

    results = await run_worker_batch(
        tasks=[task],
        query="q",
        wiki=wiki,
        repo_root=repo,
        pool=pool,
        role_model_overrides=None,
    )

    assert results == [
        {
            "task_id": "bad-task",
            "worker": "librarian",
            "status": "error",
            "content": "boom",
        }
    ]
```

- [ ] **Step 2: Run worker dispatch tests and verify they fail**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py -q
```

Expected: FAIL with missing `WorkerTask`.

- [ ] **Step 3: Add orchestrated code-reader prompt branch**

Append this constant to `packages/graph-wiki-core/src/graph_wiki_core/prompts/code_reader.py`:

```python
ORCHESTRATED_CODE_READER_SYSTEM = (
    CODE_READER_SYSTEM
    + "\n\nOrchestrated query mode:\n"
    "- You receive explicit target_paths_or_hints, query_focus, and expected_evidence.\n"
    "- Use read_file only for paths under the repository root.\n"
    "- Return JSON with evidence entries containing source_type='code', path, excerpt, and line_refs.\n"
    "- If the targets do not verify the requested claim, respond with exactly NO_RELEVANT_CONTENT.\n"
)
```

- [ ] **Step 4: Add worker parsing and dispatch helpers**

Add this code to `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`:

```python
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import SubagentPool, TaskResult

from graph_wiki_core.commands.query import _read_file_bounded
from graph_wiki_core.prompts.code_reader import ORCHESTRATED_CODE_READER_SYSTEM
from graph_wiki_core.prompts.librarian import LIBRARIAN_SYSTEM

NO_RELEVANT_CONTENT = "NO_RELEVANT_CONTENT"
_WORKER_MAX_ITERS = 5


@dataclass(frozen=True)
class WorkerTask:
    task_id: str
    worker: Literal["librarian", "code_reader"]
    page_path: str | None
    query_focus: str
    expected_evidence: str
    target_paths_or_hints: list[str]


def parse_worker_tasks(raw_tasks: Any) -> list[WorkerTask]:
    if not isinstance(raw_tasks, list):
        return []
    tasks: list[WorkerTask] = []
    for index, raw in enumerate(raw_tasks):
        if not isinstance(raw, dict):
            continue
        worker = raw.get("worker")
        if worker == "librarian":
            page_path = raw.get("page_path")
            if not isinstance(page_path, str) or not page_path.strip():
                continue
            tasks.append(
                WorkerTask(
                    task_id=str(raw.get("task_id") or f"librarian-{index}"),
                    worker="librarian",
                    page_path=page_path,
                    query_focus=str(raw.get("query_focus") or ""),
                    expected_evidence=str(raw.get("expected_evidence") or ""),
                    target_paths_or_hints=[],
                )
            )
        elif worker == "code_reader":
            hints = raw.get("target_paths_or_hints", [])
            if not isinstance(hints, list) or not all(isinstance(item, str) for item in hints):
                continue
            tasks.append(
                WorkerTask(
                    task_id=str(raw.get("task_id") or f"code-reader-{index}"),
                    worker="code_reader",
                    page_path=None,
                    query_focus=str(raw.get("query_focus") or ""),
                    expected_evidence=str(raw.get("expected_evidence") or ""),
                    target_paths_or_hints=list(hints),
                )
            )
    return tasks


async def _run_librarian_task(task: WorkerTask, *, query: str, wiki: Path, librarian_llm: Any) -> TaskResult:
    assert task.page_path is not None
    try:
        page_text = (wiki / task.page_path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return TaskResult(value=f"ERROR: {exc}", response=None)
    if len(page_text) > 24_000:
        page_text = page_text[:24_000] + "\n[TRUNCATED]"
    messages = [
        SystemMessage(content=LIBRARIAN_SYSTEM),
        HumanMessage(
            content=(
                f"Query: {query}\n"
                f"Focus: {task.query_focus}\n"
                f"Expected evidence: {task.expected_evidence}\n\n"
                f"Page ({task.page_path}):\n{page_text}"
            )
        ),
    ]
    response = await librarian_llm.ainvoke(messages)
    return TaskResult(value=getattr(response, "content", "") or "", response=response)


async def _run_code_reader_task(task: WorkerTask, *, query: str, repo_root: Path, code_llm_raw: Any) -> TaskResult:
    @tool
    def read_file(path: str) -> str:
        """Read a source file by repo-relative path, bounded to the repository root."""
        try:
            return _read_file_bounded(repo_root, path)
        except (OSError, PermissionError) as exc:
            return f"ERROR: {exc}"

    code_llm = code_llm_raw.bind_tools([read_file])
    hints = "\n".join(f"- {hint}" for hint in task.target_paths_or_hints)
    messages: list[Any] = [
        SystemMessage(content=ORCHESTRATED_CODE_READER_SYSTEM),
        HumanMessage(
            content=(
                f"Query: {query}\n"
                f"Focus: {task.query_focus}\n"
                f"Expected evidence: {task.expected_evidence}\n\n"
                f"Target paths or hints:\n{hints}\n"
            )
        ),
    ]
    for _iteration in range(_WORKER_MAX_ITERS):
        response = await code_llm.ainvoke(messages)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return TaskResult(value=getattr(response, "content", "") or "", response=response)
        messages.append(response)
        for call in tool_calls:
            call_args = call.get("args", {}) if isinstance(call, dict) else {}
            call_id = call.get("id", "") if isinstance(call, dict) else ""
            requested = str(call_args.get("path", ""))
            messages.append(ToolMessage(content=read_file.invoke({"path": requested}), tool_call_id=call_id))
    return TaskResult(value=NO_RELEVANT_CONTENT, response=None)


async def run_worker_batch(
    *,
    tasks: list[WorkerTask],
    query: str,
    wiki: Path,
    repo_root: Path,
    pool: SubagentPool,
    role_model_overrides: dict[str, str] | None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    librarian_tasks = [task for task in tasks if task.worker == "librarian"]
    if librarian_tasks:
        cfg = load_role_config("librarian")
        llm = make_llm("librarian", model_override=(role_model_overrides or {}).get("librarian"))

        async def _task(item: WorkerTask) -> TaskResult:
            return await _run_librarian_task(item, query=query, wiki=wiki, librarian_llm=llm)

        fan = await pool.run_all(
            items=librarian_tasks,
            task=_task,
            role="librarian",
            model_id=cfg["model_id"],
            max_concurrency=cfg["max_concurrency"],
        )
        results.extend(
            {"task_id": task_id, "worker": "librarian", "status": "success", "content": content}
            for task_id, content in fan.successes
        )
        results.extend(
            {"task_id": task_id, "worker": "librarian", "status": "error", "content": str(error)}
            for task_id, error in fan.errors
        )

    code_tasks = [task for task in tasks if task.worker == "code_reader"]
    if code_tasks:
        cfg = load_role_config("code_reader")
        llm = make_llm("code_reader", model_override=(role_model_overrides or {}).get("code_reader"))

        async def _task(item: WorkerTask) -> TaskResult:
            return await _run_code_reader_task(item, query=query, repo_root=repo_root, code_llm_raw=llm)

        fan = await pool.run_all(
            items=code_tasks,
            task=_task,
            role="code_reader",
            model_id=cfg["model_id"],
            max_concurrency=cfg["max_concurrency"],
        )
        results.extend(
            {"task_id": task_id, "worker": "code_reader", "status": "success", "content": content}
            for task_id, content in fan.successes
        )
        results.extend(
            {"task_id": task_id, "worker": "code_reader", "status": "error", "content": str(error)}
            for task_id, error in fan.errors
        )

    return results
```

- [ ] **Step 5: Run worker dispatch tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/prompts/code_reader.py packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py
git commit -m "feat: dispatch query worker batches"
```

---

### Task 6: Implement Orchestration Loop and Safe Degradation

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`
- Create: `packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py`

- [ ] **Step 1: Write failing orchestration loop tests**

Create `packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py`:

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from graph_wiki_core.commands.query_orchestrator import InitialCandidate, run_query_orchestrator


def _valid_final_json() -> str:
    return (
        "{"
        '"answer_markdown":"Answer from [[alpha.md]].",'
        '"citations":["alpha.md"],'
        '"evidence":[{"id":"E1","source_type":"wiki","path":"alpha.md","freshness":"fresh",'
        '"staleness_reason":null,"excerpt":"Alpha evidence","line_refs":[]}],'
        '"answer_evidence_map":[{"claim":"Answer from alpha","evidence_ids":["E1"]}],'
        '"worker_plan":[],'
        '"worker_results":[],'
        '"gaps":[],'
        '"confidence":"high"'
        "}"
    )


@pytest.mark.asyncio
async def test_orchestrator_returns_valid_final_json_without_worker_batch(tmp_path: Path) -> None:
    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=_valid_final_json()))

    with patch("graph_wiki_core.commands.query_orchestrator.make_llm", return_value=llm):
        result = await run_query_orchestrator(
            query="q",
            wiki=wiki,
            repo_root=repo,
            repo_head="abc123",
            initial_candidates=[
                InitialCandidate(path="alpha.md", bm25=1.0, embed=0.5, rrf=0.03, excerpt="Alpha")
            ],
            graph_tools=[],
            pool=MagicMock(),
            role_model_overrides=None,
        )

    assert result.output.answer_markdown == "Answer from [[alpha.md]]."
    assert result.batch_iterations == 0


@pytest.mark.asyncio
async def test_orchestrator_runs_worker_batches_until_final_answer(tmp_path: Path) -> None:
    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    batch_json = (
        "{"
        '"answer_markdown":"Need workers.",'
        '"citations":[],'
        '"evidence":[],'
        '"answer_evidence_map":[],'
        '"worker_plan":[{"worker":"librarian","page_path":"alpha.md","query_focus":"Find Alpha",'
        '"expected_evidence":"wiki excerpt"}],'
        '"worker_results":[],'
        '"gaps":[],'
        '"confidence":"low"'
        "}"
    )
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[AIMessage(content=batch_json), AIMessage(content=_valid_final_json())])

    with (
        patch("graph_wiki_core.commands.query_orchestrator.make_llm", return_value=llm),
        patch(
            "graph_wiki_core.commands.query_orchestrator.run_worker_batch",
            new=AsyncMock(return_value=[{"task_id": "librarian-0", "worker": "librarian", "status": "success", "content": "Alpha evidence"}]),
        ) as mock_batch,
    ):
        result = await run_query_orchestrator(
            query="q",
            wiki=wiki,
            repo_root=repo,
            repo_head="abc123",
            initial_candidates=[],
            graph_tools=[],
            pool=MagicMock(),
            role_model_overrides=None,
        )

    assert result.batch_iterations == 1
    mock_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_invalid_json_degrades_to_insufficient_evidence(tmp_path: Path) -> None:
    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="not json"))

    with patch("graph_wiki_core.commands.query_orchestrator.make_llm", return_value=llm):
        result = await run_query_orchestrator(
            query="q",
            wiki=wiki,
            repo_root=repo,
            repo_head="abc123",
            initial_candidates=[],
            graph_tools=[],
            pool=MagicMock(),
            role_model_overrides=None,
        )

    assert result.output.confidence == "low"
    assert "insufficient evidence" in result.output.answer_markdown.lower()
    assert result.output.gaps


@pytest.mark.asyncio
async def test_orchestrator_stops_at_five_batch_cap(tmp_path: Path) -> None:
    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    batch_json = (
        "{"
        '"answer_markdown":"Need workers.",'
        '"citations":[],'
        '"evidence":[],'
        '"answer_evidence_map":[],'
        '"worker_plan":[{"worker":"librarian","page_path":"alpha.md","query_focus":"Find Alpha",'
        '"expected_evidence":"wiki excerpt"}],'
        '"worker_results":[],'
        '"gaps":[],'
        '"confidence":"low"'
        "}"
    )
    llm = MagicMock()
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content=batch_json))

    with (
        patch("graph_wiki_core.commands.query_orchestrator.make_llm", return_value=llm),
        patch("graph_wiki_core.commands.query_orchestrator.run_worker_batch", new=AsyncMock(return_value=[])),
    ):
        result = await run_query_orchestrator(
            query="q",
            wiki=wiki,
            repo_root=repo,
            repo_head="abc123",
            initial_candidates=[],
            graph_tools=[],
            pool=MagicMock(),
            role_model_overrides=None,
        )

    assert result.batch_iterations == 5
    assert result.output.confidence == "low"
    assert result.output.gaps[0].question == "What evidence is still missing?"
```

- [ ] **Step 2: Run loop tests and verify they fail**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py -q
```

Expected: FAIL with missing `run_query_orchestrator`.

- [ ] **Step 3: Add orchestration result and degraded output helpers**

Add this code to `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`:

```python
from graph_wiki_core.agent_loop import run_tool_loop
from graph_wiki_core.prompts.query_orchestrator import QUERY_ORCHESTRATOR_SYSTEM

MAX_WORKER_BATCH_ITERATIONS = 5


@dataclass(frozen=True)
class QueryOrchestratorResult:
    output: OrchestratorOutput
    batch_iterations: int
    trace_metadata: dict[str, Any]


def degraded_output(*, query: str, reason: str) -> OrchestratorOutput:
    return OrchestratorOutput(
        answer_markdown=(
            "I do not have enough verified evidence to answer this fully.\n\n"
            f"Insufficient evidence: {reason}"
        ),
        citations=[],
        evidence=[],
        answer_evidence_map=[],
        worker_plan=[],
        worker_results=[],
        gaps=[
            EvidenceGap(
                question=f"Verified answer for: {query}",
                reason=reason,
            )
        ],
        confidence="low",
    )
```

- [ ] **Step 4: Add orchestration loop**

Add this function to `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`:

```python
async def run_query_orchestrator(
    *,
    query: str,
    wiki: Path,
    repo_root: Path,
    repo_head: str | None,
    initial_candidates: list[InitialCandidate],
    graph_tools: list[BaseTool],
    pool: SubagentPool,
    role_model_overrides: dict[str, str] | None,
) -> QueryOrchestratorResult:
    tools = build_orchestrator_tools(wiki=wiki, graph_tools=graph_tools)
    context = build_orchestrator_context(
        query=query,
        wiki=wiki,
        repo_root=repo_root,
        repo_head=repo_head,
        initial_candidates=initial_candidates,
        graph_available=bool(graph_tools),
    )
    messages: list[Any] = [
        SystemMessage(content=QUERY_ORCHESTRATOR_SYSTEM),
        HumanMessage(
            content=(
                "Use the context below to answer the query. "
                "If worker evidence is needed, return JSON with worker_plan populated.\n\n"
                f"{json.dumps(context, indent=2, sort_keys=True)}"
            )
        ),
    ]
    orchestrator_llm = make_llm(
        "query_orchestrator",
        model_override=(role_model_overrides or {}).get("query_orchestrator"),
    )
    batch_iterations = 0
    worker_result_history: list[dict[str, Any]] = []
    last_output: OrchestratorOutput | None = None

    while batch_iterations <= MAX_WORKER_BATCH_ITERATIONS:
        loop_result = await run_tool_loop(
            llm=orchestrator_llm,
            tools=tools,
            messages=messages,
            max_iterations=5,
            cap_label="query_orchestrator",
        )
        if loop_result.status == "failed":
            return QueryOrchestratorResult(
                output=degraded_output(query=query, reason=loop_result.error or "orchestrator failed"),
                batch_iterations=batch_iterations,
                trace_metadata={"status": "failed", "error": loop_result.error},
            )
        try:
            parsed = parse_orchestrator_output(loop_result.final_text)
            validate_orchestrator_output(parsed, require_stale_claim_gaps=True)
        except OrchestratorValidationError as exc:
            return QueryOrchestratorResult(
                output=degraded_output(query=query, reason=str(exc)),
                batch_iterations=batch_iterations,
                trace_metadata={"status": "invalid_json", "error": str(exc)},
            )
        last_output = parsed
        tasks = parse_worker_tasks(parsed.worker_plan)
        if not tasks:
            return QueryOrchestratorResult(
                output=parsed,
                batch_iterations=batch_iterations,
                trace_metadata={"status": "ok", "worker_results": worker_result_history},
            )
        if batch_iterations >= MAX_WORKER_BATCH_ITERATIONS:
            break
        worker_results = await run_worker_batch(
            tasks=tasks,
            query=query,
            wiki=wiki,
            repo_root=repo_root,
            pool=pool,
            role_model_overrides=role_model_overrides,
        )
        worker_result_history.extend(worker_results)
        batch_iterations += 1
        messages.append(
            HumanMessage(
                content=(
                    "Worker results are below. Continue planning only if evidence is insufficient. "
                    "Return final answer JSON when possible.\n\n"
                    f"{json.dumps(worker_results, indent=2, sort_keys=True)}"
                )
            )
        )

    capped = last_output or degraded_output(query=query, reason="orchestrator reached worker batch cap")
    if not capped.gaps:
        capped = OrchestratorOutput(
            answer_markdown=capped.answer_markdown
            + "\n\nEvidence collection reached the worker batch cap; unsupported claims are omitted.",
            citations=capped.citations,
            evidence=capped.evidence,
            answer_evidence_map=capped.answer_evidence_map,
            worker_plan=[],
            worker_results=worker_result_history,
            gaps=[
                EvidenceGap(
                    question="What evidence is still missing?",
                    reason="The query orchestrator reached the five worker-batch cap.",
                )
            ],
            confidence="low",
        )
    return QueryOrchestratorResult(
        output=capped,
        batch_iterations=MAX_WORKER_BATCH_ITERATIONS,
        trace_metadata={"status": "capped", "worker_results": worker_result_history},
    )
```

- [ ] **Step 5: Run loop tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py
git commit -m "feat: run query orchestration loop"
```

---

### Task 7: Integrate Orchestrator into `run_query()` as Default Path

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_query_result.py`
- Modify: `packages/graph-wiki-core/tests/test_command_overrides.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_query_code_fallback.py`
- Modify: `packages/graph-wiki-core/tests/test_query_graph_tools.py`

- [ ] **Step 1: Write failing default-routing test**

Add this test to `packages/graph-wiki-core/tests/unit/test_query_result.py`:

```python
@pytest.mark.asyncio
async def test_run_query_routes_default_path_through_orchestrator(tmp_path: Path) -> None:
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.query import QueryResult, run_query
    from graph_wiki_core.commands.query_orchestrator import (
        EvidenceGap,
        OrchestratorEvidence,
        OrchestratorOutput,
        QueryOrchestratorResult,
    )

    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "alpha.md").write_text("# Alpha\n\nAlpha body")
    (wiki.parent / ".graph-wiki" / "bm25").mkdir(parents=True)
    (wiki.parent / ".graph-wiki" / "search.db").touch()

    orch_result = QueryOrchestratorResult(
        output=OrchestratorOutput(
            answer_markdown="Alpha answer from [[alpha.md]].",
            citations=["alpha.md"],
            evidence=[
                OrchestratorEvidence(
                    id="E1",
                    source_type="wiki",
                    path="alpha.md",
                    freshness="fresh",
                    staleness_reason=None,
                    excerpt="Alpha body",
                    line_refs=[],
                )
            ],
            answer_evidence_map=[],
            worker_plan=[],
            worker_results=[],
            gaps=[],
            confidence="high",
        ),
        batch_iterations=0,
        trace_metadata={"status": "ok"},
    )

    patches = [
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(wiki, tmp_path / "repo")),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["alpha.md"], [2.0])),
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("alpha.md", 0.9)]),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_core.commands.query.read_only_connect", side_effect=Exception("missing graph")),
        patch("graph_wiki_core.commands.query.run_query_orchestrator", new=AsyncMock(return_value=orch_result)),
    ]
    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        result = await run_query("What is Alpha?", workspace_path=wiki.parent, top_k=3)

    assert isinstance(result, QueryResult)
    assert result.answer == "Alpha answer from [[alpha.md]]."
    assert result.citations == ["alpha.md"]
    assert result.pages_drilled == 1
    assert result.search_scores["alpha.md"]["bm25"] == 2.0
```

- [ ] **Step 2: Run the routing test and verify it fails**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_result.py::test_run_query_routes_default_path_through_orchestrator -q
```

Expected: FAIL because `run_query_orchestrator` is not imported or not called.

- [ ] **Step 3: Extract legacy query body**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`, rename the current public function:

```python
async def _run_legacy_query(
    query: str,
    workspace_path: Path | None = None,
    top_k: int = 5,
    librarian_model_override: str | None = None,
    role_model_overrides: dict[str, str] | None = None,
) -> QueryResult:
    """Legacy fixed query pipeline: hybrid search -> librarian fan-out -> synthesis/code fallback."""
```

Keep the current function body under `_run_legacy_query()` unchanged except for the docstring name.

- [ ] **Step 4: Add initial retrieval helper**

Add this dataclass and helper above `run_query()` in `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`:

```python
@dataclass(frozen=True)
class PreparedQueryRetrieval:
    wiki: Path
    repo_root: Path | None
    bm25_score_map: dict[str, float]
    embed_score_map: dict[str, float]
    fused: dict[str, float]
    top_pages: list[str]
    search_scores: dict[str, dict[str, float]]


def _read_candidate_excerpt(wiki: Path, page_path: str, *, max_chars: int = 1500) -> str:
    try:
        text = (wiki / page_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n[TRUNCATED]"


def _prepare_query_retrieval(query: str, workspace_path: Path | None, top_k: int) -> PreparedQueryRetrieval:
    wiki, repo_root = resolve_wiki_and_repo(workspace_path)
    bm25_dir = graph_dir(wiki.parent) / _BM25_SUBDIR
    db_path = graph_dir(wiki.parent) / _SEARCH_DB_NAME
    if not bm25_dir.exists() or not db_path.exists():
        logger.warning("First-time index build — may take a moment.")
        build_index(wiki)
    bm25_paths, bm25_raw = bm25_query(query, wiki, top_k * 3)
    bm25_rank_map = {p: i + 1 for i, p in enumerate(bm25_paths)}
    bm25_score_map = {p: s for p, s in zip(bm25_paths, bm25_raw)}
    embeddings = BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0",
        region_name="us-east-1",
        normalize=True,
    )
    query_vec = embeddings.embed_query(query)
    embed_hits = _cosine_search_sqlite(wiki, query_vec, top_k * 3)
    embed_rank_map = {path: i + 1 for i, (path, _) in enumerate(embed_hits)}
    embed_score_map = {path: score for path, score in embed_hits}
    fused = _rrf_fuse(bm25_rank_map, embed_rank_map)
    top_pages = sorted(fused, key=fused.get, reverse=True)[:top_k]  # type: ignore[arg-type]
    search_scores = {
        p: {
            "bm25": bm25_score_map.get(p, 0.0),
            "embed": embed_score_map.get(p, 0.0),
            "rrf": fused.get(p, 0.0),
        }
        for p in top_pages
    }
    return PreparedQueryRetrieval(
        wiki=wiki,
        repo_root=repo_root,
        bm25_score_map=bm25_score_map,
        embed_score_map=embed_score_map,
        fused=fused,
        top_pages=top_pages,
        search_scores=search_scores,
    )
```

- [ ] **Step 5: Add graph-tool availability helper**

Add this helper next to the retrieval helper:

```python
def _load_query_graph_tools(workspace: Path) -> tuple[sqlite3.Connection | None, list]:
    db_path = graph_dir(workspace) / "code.db"
    try:
        conn = read_only_connect(db_path)
        node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        if node_count == 0:
            conn.close()
            sys.stderr.write(_GRAPH_UNAVAILABLE_STDERR + "\n")
            return None, []
        return conn, build_graph_tools(conn)
    except GraphNotInitializedError:
        sys.stderr.write(_GRAPH_UNAVAILABLE_STDERR + "\n")
        return None, []
```

- [ ] **Step 6: Add new public `run_query()` wrapper**

Add the new public function below `_run_legacy_query()`:

```python
async def run_query(
    query: str,
    workspace_path: Path | None = None,
    top_k: int = 5,
    librarian_model_override: str | None = None,
    role_model_overrides: dict[str, str] | None = None,
    *,
    use_legacy: bool = False,
) -> QueryResult:
    """End-to-end query entry point. Defaults to agentic query orchestration."""
    if use_legacy:
        return await _run_legacy_query(
            query,
            workspace_path=workspace_path,
            top_k=top_k,
            librarian_model_override=librarian_model_override,
            role_model_overrides=role_model_overrides,
        )
    if not (3 <= top_k <= 10):
        raise RuntimeError(f"top_k must be between 3 and 10 (got {top_k})")

    from graph_wiki_core.commands.query_orchestrator import InitialCandidate, run_query_orchestrator

    prepared = _prepare_query_retrieval(query, workspace_path, top_k)
    repo_root = prepared.repo_root or _resolve_repo_root(prepared.wiki)
    graph_conn, graph_tools = _load_query_graph_tools(prepared.wiki.parent)
    try:
        pool = SubagentPool(trace_dir=graph_dir(prepared.wiki.parent) / "traces")
        orchestrated = await run_query_orchestrator(
            query=query,
            wiki=prepared.wiki,
            repo_root=repo_root,
            repo_head=None,
            initial_candidates=[
                InitialCandidate(
                    path=page,
                    bm25=prepared.search_scores[page]["bm25"],
                    embed=prepared.search_scores[page]["embed"],
                    rrf=prepared.search_scores[page]["rrf"],
                    excerpt=_read_candidate_excerpt(prepared.wiki, page),
                )
                for page in prepared.top_pages
            ],
            graph_tools=graph_tools,
            pool=pool,
            role_model_overrides={
                **(role_model_overrides or {}),
                **({"librarian": librarian_model_override} if librarian_model_override else {}),
            },
        )
    except Exception as exc:
        logger.warning("query orchestrator failed; falling back to legacy query: %s", exc)
        return await _run_legacy_query(
            query,
            workspace_path=workspace_path,
            top_k=top_k,
            librarian_model_override=librarian_model_override,
            role_model_overrides=role_model_overrides,
        )
    finally:
        if graph_conn is not None:
            graph_conn.close()

    useful_evidence_count = sum(1 for evidence in orchestrated.output.evidence if evidence.excerpt.strip())
    query_result = QueryResult(
        answer=orchestrated.output.answer_markdown,
        citations=list(dict.fromkeys([*_extract_wikilinks(orchestrated.output.answer_markdown), *orchestrated.output.citations])),
        pages_drilled=useful_evidence_count,
        search_scores=prepared.search_scores,
    )
    fan_result = FanOutResult(successes=[(item.id, item.excerpt) for item in orchestrated.output.evidence], errors=[])
    return apply_guardrails(query_result, prepared.wiki, fan_result, skip_g4=False)
```

- [ ] **Step 7: Update legacy tests to use `_run_legacy_query()` or `use_legacy=True`**

In `packages/graph-wiki-core/tests/unit/test_query_code_fallback.py`, tests that specifically assert fixed pipeline code fallback should import `_run_legacy_query`:

```python
from graph_wiki_core.commands.query import _run_legacy_query
```

Then replace calls like:

```python
await run_query("q", workspace_path=vault, top_k=3)
```

with:

```python
await _run_legacy_query("q", workspace_path=vault, top_k=3)
```

For CLI/MCP-level tests, do not change the public `run_query` import; those should continue testing default behavior.

- [ ] **Step 8: Add query-orchestrator override test**

Add this to `packages/graph-wiki-core/tests/test_command_overrides.py`:

```python
@pytest.mark.asyncio
async def test_run_query_passes_query_orchestrator_role_override(tmp_path: Path) -> None:
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, MagicMock, patch

    from graph_wiki_core.commands.query import run_query
    from graph_wiki_core.commands.query_orchestrator import OrchestratorOutput, QueryOrchestratorResult

    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "alpha.md").write_text("# Alpha")
    (wiki.parent / ".graph-wiki" / "bm25").mkdir(parents=True)
    (wiki.parent / ".graph-wiki" / "search.db").touch()
    captured = {}

    async def _fake_orchestrator(**kwargs):
        captured.update(kwargs["role_model_overrides"])
        return QueryOrchestratorResult(
            output=OrchestratorOutput(
                answer_markdown="No evidence.",
                citations=[],
                evidence=[],
                answer_evidence_map=[],
                worker_plan=[],
                worker_results=[],
                gaps=[],
                confidence="low",
            ),
            batch_iterations=0,
            trace_metadata={},
        )

    patches = [
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(wiki, tmp_path / "repo")),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["alpha.md"], [1.0])),
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("alpha.md", 0.5)]),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_core.commands.query.read_only_connect", side_effect=Exception("missing graph")),
        patch("graph_wiki_core.commands.query.run_query_orchestrator", new=AsyncMock(side_effect=_fake_orchestrator)),
    ]
    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        await run_query(
            "q",
            workspace_path=wiki.parent,
            top_k=3,
            role_model_overrides={"query_orchestrator": "override-model"},
        )

    assert captured["query_orchestrator"] == "override-model"
```

- [ ] **Step 9: Run integration-focused unit tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_query_result.py packages/graph-wiki-core/tests/unit/test_query_code_fallback.py packages/graph-wiki-core/tests/test_command_overrides.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/query.py packages/graph-wiki-core/tests/unit/test_query_result.py packages/graph-wiki-core/tests/test_command_overrides.py packages/graph-wiki-core/tests/unit/test_query_code_fallback.py packages/graph-wiki-core/tests/test_query_graph_tools.py
git commit -m "feat: route query through orchestrator"
```

---

### Task 8: Add Orchestrator Trace Summary and Guardrail Coverage

**Files:**
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py`
- Modify: `packages/graph-wiki-core/tests/test_query_trace_unit.py`
- Modify: `packages/graph-wiki-core/tests/unit/test_query_summary_schema_version.py`

- [ ] **Step 1: Write failing trace test**

Add this test to `packages/graph-wiki-core/tests/test_query_trace_unit.py`:

```python
@pytest.mark.asyncio
async def test_orchestrated_query_summary_records_batch_iterations(tmp_path: Path) -> None:
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, patch

    from graph_wiki_core.commands.query import run_query
    from graph_wiki_core.commands.query_orchestrator import OrchestratorOutput, QueryOrchestratorResult

    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "alpha.md").write_text("# Alpha")
    (wiki.parent / ".graph-wiki" / "bm25").mkdir(parents=True)
    (wiki.parent / ".graph-wiki" / "search.db").touch()
    orch = QueryOrchestratorResult(
        output=OrchestratorOutput(
            answer_markdown="Alpha.",
            citations=[],
            evidence=[],
            answer_evidence_map=[],
            worker_plan=[],
            worker_results=[],
            gaps=[],
            confidence="low",
        ),
        batch_iterations=2,
        trace_metadata={"status": "ok"},
    )
    patches = [
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(wiki, tmp_path / "repo")),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["alpha.md"], [1.0])),
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("alpha.md", 0.5)]),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_core.commands.query.read_only_connect", side_effect=Exception("missing graph")),
        patch("graph_wiki_core.commands.query.run_query_orchestrator", new=AsyncMock(return_value=orch)),
    ]
    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        await run_query("q", workspace_path=wiki.parent, top_k=3)

    trace_files = sorted((wiki.parent / ".graph-wiki" / "traces").glob("query_*.jsonl"))
    assert trace_files
    record = json.loads(trace_files[-1].read_text().splitlines()[0])
    assert record["kind"] == "query_summary"
    assert record["schema_version"] == 1
    assert record["orchestrated"] is True
    assert record["orchestrator_batch_iterations"] == 2
    assert record["orchestrator_status"] == "ok"
```

- [ ] **Step 2: Run trace test and verify it fails**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/test_query_trace_unit.py::test_orchestrated_query_summary_records_batch_iterations -q
```

Expected: FAIL because no orchestrator trace summary fields are written.

- [ ] **Step 3: Add orchestrated summary writer**

Add this helper to `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`:

```python
def _write_orchestrated_query_summary(
    *,
    wiki: Path,
    query_id: str,
    query: str,
    top_k: int,
    pages_retrieved: int,
    pages_drilled: int,
    started_at: str,
    orchestrator_result,
) -> None:
    ended_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    trace_dir = graph_dir(wiki.parent) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    summary_file = trace_dir / f"query_{query_id}.jsonl"
    record = {
        "schema_version": 1,
        "kind": "query_summary",
        "query_id": query_id,
        "query": query,
        "top_k": top_k,
        "pages_retrieved": pages_retrieved,
        "pages_drilled": pages_drilled,
        "code_fallback": False,
        "orchestrated": True,
        "orchestrator_batch_iterations": orchestrator_result.batch_iterations,
        "orchestrator_status": orchestrator_result.trace_metadata.get("status"),
        "started_at": started_at,
        "ended_at": ended_at,
        "tokens_in": None,
        "tokens_out": None,
    }
    try:
        summary_file.write_text(json.dumps(record) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write orchestrated query summary trace: %s", exc)
```

Call it from the new public `run_query()` immediately before returning guarded output:

```python
query_id = uuid.uuid4().hex[:12]
started_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
```

Then after `query_result = apply_guardrails(...)`:

```python
_write_orchestrated_query_summary(
    wiki=prepared.wiki,
    query_id=query_id,
    query=query,
    top_k=top_k,
    pages_retrieved=len(prepared.top_pages),
    pages_drilled=query_result.pages_drilled,
    started_at=started_at,
    orchestrator_result=orchestrated,
)
return query_result
```

- [ ] **Step 4: Add unresolved wikilink guardrail regression**

Add this test to `packages/graph-wiki-core/tests/unit/test_query_result.py`:

```python
@pytest.mark.asyncio
async def test_orchestrated_query_still_applies_unresolved_wikilink_guardrail(tmp_path: Path) -> None:
    from contextlib import ExitStack
    from unittest.mock import AsyncMock, patch

    from graph_wiki_core.commands.query import run_query
    from graph_wiki_core.commands.query_orchestrator import OrchestratorOutput, QueryOrchestratorResult

    wiki = tmp_path / "workspace" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "alpha.md").write_text("# Alpha")
    (wiki.parent / ".graph-wiki" / "bm25").mkdir(parents=True)
    (wiki.parent / ".graph-wiki" / "search.db").touch()
    orch = QueryOrchestratorResult(
        output=OrchestratorOutput(
            answer_markdown="See [[missing]].",
            citations=["missing"],
            evidence=[],
            answer_evidence_map=[],
            worker_plan=[],
            worker_results=[],
            gaps=[],
            confidence="low",
        ),
        batch_iterations=0,
        trace_metadata={"status": "ok"},
    )
    patches = [
        patch("graph_wiki_core.commands.query.resolve_wiki_and_repo", return_value=(wiki, tmp_path / "repo")),
        patch("graph_wiki_core.commands.query.bm25_query", return_value=(["alpha.md"], [1.0])),
        patch("graph_wiki_core.commands.query._cosine_search_sqlite", return_value=[("alpha.md", 0.5)]),
        patch("graph_wiki_core.commands.query.BedrockEmbeddings"),
        patch("graph_wiki_core.commands.query.read_only_connect", side_effect=Exception("missing graph")),
        patch("graph_wiki_core.commands.query.run_query_orchestrator", new=AsyncMock(return_value=orch)),
    ]
    with ExitStack() as stack:
        for item in patches:
            stack.enter_context(item)
        result = await run_query("q", workspace_path=wiki.parent, top_k=3)

    assert "[warning: 1 citation(s) did not resolve" in result.answer
```

- [ ] **Step 5: Run trace and guardrail tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/test_query_trace_unit.py packages/graph-wiki-core/tests/unit/test_query_result.py packages/graph-wiki-core/tests/unit/test_query_summary_schema_version.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/graph-wiki-core/src/graph_wiki_core/commands/query.py packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py packages/graph-wiki-core/tests/test_query_trace_unit.py packages/graph-wiki-core/tests/unit/test_query_result.py packages/graph-wiki-core/tests/unit/test_query_summary_schema_version.py
git commit -m "feat: trace orchestrated query results"
```

---

### Task 9: Run Focused Verification and Clean Up Public Surface Docs

**Files:**
- Modify: `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`
- Modify: `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`
- Modify: `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`
- Modify: `docs/superpowers/specs/2026-06-07-query-orchestrator-design.md`

- [ ] **Step 1: Update CLI help text**

In `packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py`, change the query command docstring from the fixed pipeline wording to:

```python
"""Query the wiki with agentic retrieval orchestration over wiki and code evidence."""
```

- [ ] **Step 2: Update MCP tool description**

In `packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py`, update the `wiki_query` description string from librarian fan-out wording to:

```python
"Query the code wiki using hybrid retrieval plus agentic evidence orchestration over wiki pages and source-reading workers."
```

- [ ] **Step 3: Update `run_query()` docstring**

In `packages/graph-wiki-core/src/graph_wiki_core/commands/query.py`, update the public `run_query()` docstring to:

```python
"""End-to-end query entry point.

Default path:
    1. Resolve workspace and wiki.
    2. Ensure BM25 and embedding indexes exist.
    3. Run initial hybrid retrieval and RRF.
    4. Run query_orchestrator over bounded planning tools and worker batches.
    5. Convert validated orchestrator output to QueryResult.
    6. Apply existing citation guardrails and write query trace summary.

Pass use_legacy=True for the previous fixed pipeline test seam.
"""
```

- [ ] **Step 4: Mark spec implemented**

At the top of `docs/superpowers/specs/2026-06-07-query-orchestrator-design.md`, change:

```markdown
Status: approved for spec review
```

to:

```markdown
Status: implemented
```

- [ ] **Step 5: Run focused package tests**

Run:

```bash
uv run --package graph-wiki-core pytest packages/graph-wiki-core/tests/unit/test_agent_tools.py packages/graph-wiki-core/tests/unit/test_agent_loop.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py packages/graph-wiki-core/tests/test_query_graph_tools.py packages/graph-wiki-core/tests/unit/test_query_code_fallback.py packages/graph-wiki-core/tests/test_command_overrides.py packages/graph-wiki-core/tests/test_query_trace_unit.py
uv run --package model-adapter pytest packages/model-adapter/tests/test_loader.py
uv run --package graph-wiki-cli pytest packages/graph-wiki-cli/tests/unit/test_cli_query.py
uv run --package graph-wiki-mcp pytest packages/graph-wiki-mcp/tests/unit/test_mcp_query_schema.py
```

Expected: PASS.

- [ ] **Step 6: Run scoped lint**

Run:

```bash
uv run ruff check packages/model-adapter/src/model_adapter/models.toml packages/model-adapter/tests/test_loader.py packages/graph-wiki-core/src/graph_wiki_core/prompts/query_orchestrator.py packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py packages/graph-wiki-core/src/graph_wiki_core/prompts/code_reader.py packages/graph-wiki-core/src/graph_wiki_core/commands/query.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
```

Expected: PASS, or fail only because `models.toml` is not a Python file. If Ruff rejects the TOML path, rerun without it:

```bash
uv run ruff check packages/model-adapter/tests/test_loader.py packages/graph-wiki-core/src/graph_wiki_core/prompts/query_orchestrator.py packages/graph-wiki-core/src/graph_wiki_core/commands/query_orchestrator.py packages/graph-wiki-core/src/graph_wiki_core/prompts/code_reader.py packages/graph-wiki-core/src/graph_wiki_core/commands/query.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_validation.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_staleness.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_tools.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_workers.py packages/graph-wiki-core/tests/unit/test_query_orchestrator_loop.py packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/graph-wiki-cli/src/graph_wiki_cli/wiki_cli/main.py packages/graph-wiki-mcp/src/graph_wiki_mcp/server.py packages/graph-wiki-core/src/graph_wiki_core/commands/query.py docs/superpowers/specs/2026-06-07-query-orchestrator-design.md
git commit -m "docs: describe orchestrated query path"
```

---

## Self-Review

Spec coverage:
- Default `run_query()` routes through the orchestrator: Task 7.
- Legacy/fallback helper remains reachable: Task 7 via `_run_legacy_query()` and `use_legacy=True`.
- `query_orchestrator` model role: Task 1.
- Initial BM25/embedding and RRF are preserved: Task 7 `_prepare_query_retrieval()`.
- Bounded direct planning tools and graph omission behavior: Task 4 and Task 7.
- Worker batches through `SubagentPool`: Task 5.
- Five-batch cap: Task 6.
- Structured output validation and safe invalid-output degradation: Task 2 and Task 6.
- Staleness signals and stale-only claim gaps: Task 3 and Task 2.
- Existing guardrails and trace records: Task 8.
- CLI and MCP default behavior update through shared `run_query()`: Task 9.

Placeholder scan:
- No forbidden placeholder markers or vague task descriptions remain.
- Every code-changing step includes concrete code or exact replacement text.
- Every verification step includes exact command and expected result.

Type consistency:
- `InitialCandidate`, `WorkerTask`, `OrchestratorOutput`, `QueryOrchestratorResult`, and `EvidenceGap` are introduced before use in integration tasks.
- `run_query_orchestrator()` returns `QueryOrchestratorResult`; `run_query()` converts that to existing `QueryResult`.
- `role_model_overrides` consistently includes `"query_orchestrator"`, `"librarian"`, `"code_reader"`, and legacy `"synthesizer"` support where relevant.
