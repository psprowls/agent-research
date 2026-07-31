"""Worklist/results contract for the split scan pipeline (schema v2).

Plugin-internal JSON written under ``<workspace>/.graph-wiki/``. The emit phase
serializes a ``ScanWorklist``; a provider (Bedrock in-process or Claude
out-of-process) returns a ``ScanResults``; the apply phase consumes it. Every
results field is optional — a missing value is simply not injected, mirroring
the Bedrock loops that skip empty parses. Schema v2 replaces the v1
``fill_tasks``/``fills`` (FillNeeds/FillTask/FillResult) surface with the
unified diff-driven ``prose_tasks``/``prose``
(ProseRefreshTask/ProseRefreshResult) pair.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

SCHEMA_VERSION = 2


@dataclass
class PropagateEntity:
    stem: str
    narrative: str
    changed_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"stem": self.stem, "narrative": self.narrative, "changed_files": list(self.changed_files)}

    @classmethod
    def from_dict(cls, d: dict) -> PropagateEntity:
        return cls(
            stem=d["stem"],
            narrative=d.get("narrative", ""),
            changed_files=list(d.get("changed_files") or []),
        )


@dataclass
class PropagateTask:
    kind: str  # concept | adr | architecture
    target_slug: str
    title: str
    page_path: str
    entities: list[PropagateEntity] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "target_slug": self.target_slug,
            "title": self.title,
            "page_path": self.page_path,
            "entities": [e.to_dict() for e in self.entities],
        }

    @classmethod
    def from_dict(cls, d: dict) -> PropagateTask:
        return cls(
            kind=d["kind"],
            target_slug=d["target_slug"],
            title=d.get("title", d["target_slug"]),
            page_path=d["page_path"],
            entities=[PropagateEntity.from_dict(e) for e in (d.get("entities") or [])],
        )


@dataclass
class ScanWorklist:
    head_commit: str | None
    short_head: str | None
    prose_tasks: list[ProseRefreshTask] = field(default_factory=list)
    propagate_tasks: list[PropagateTask] = field(default_factory=list)
    schema: int = SCHEMA_VERSION
    # M4 stamping bookkeeping: candidate uri -> anchor (last_updated_commit at emit).
    # Apply stamps drift_propagated_commit for every processed candidate.
    propagate_anchors: dict[str, str] = field(default_factory=dict)
    # M4 stamping bookkeeping: candidate uri -> entity page_path. Parallel to
    # propagate_anchors; apply resolves the page to stamp via this map.
    propagate_pages: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not (self.prose_tasks or self.propagate_tasks)

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "head_commit": self.head_commit,
            "short_head": self.short_head,
            "prose_tasks": [t.to_dict() for t in self.prose_tasks],
            "propagate_tasks": [t.to_dict() for t in self.propagate_tasks],
            "propagate_anchors": dict(self.propagate_anchors),
            "propagate_pages": dict(self.propagate_pages),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> ScanWorklist:
        schema = d.get("schema")
        if schema != SCHEMA_VERSION:
            raise ValueError(f"unsupported worklist schema: {schema!r}")
        return cls(
            head_commit=d.get("head_commit"),
            short_head=d.get("short_head"),
            prose_tasks=[ProseRefreshTask.from_dict(t) for t in (d.get("prose_tasks") or [])],
            propagate_tasks=[PropagateTask.from_dict(t) for t in (d.get("propagate_tasks") or [])],
            schema=schema,
            propagate_anchors=dict(d.get("propagate_anchors") or {}),
            propagate_pages=dict(d.get("propagate_pages") or {}),
        )

    @classmethod
    def from_json(cls, raw: str) -> ScanWorklist:
        return cls.from_dict(json.loads(raw))


@dataclass
class ProseRefreshTask:
    """One stale entity's unified prose-refresh work order (schema v2).

    ``trigger`` is "first_fill" (placeholder/TODO page or missing anchor) or
    "diff" (scoped git diff non-empty). ``diff`` is the budgeted hunk text; it
    is None for first_fill AND for trigger="diff" when the anchor SHA is
    unknown to the owning repo (history rewrite) — the prompt builder renders
    the "history rewritten" note from that combination. ``prose_sections`` and
    result ``sections`` are keyed by FULL H2 headings ("## Narrative").
    """

    uri: str
    kind: str
    name: str
    page_path: str
    graph_path: str
    language: str
    entity_root: str
    trigger: str
    diff: str | None = None
    changed_files: list[str] = field(default_factory=list)
    page_content: str = ""
    file_map_rows: str = ""
    prose_sections: dict[str, str] = field(default_factory=dict)
    graph_context: str = ""
    owning_short_head: str | None = None

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "kind": self.kind,
            "name": self.name,
            "page_path": self.page_path,
            "graph_path": self.graph_path,
            "language": self.language,
            "entity_root": self.entity_root,
            "trigger": self.trigger,
            "diff": self.diff,
            "changed_files": list(self.changed_files),
            "page_content": self.page_content,
            "file_map_rows": self.file_map_rows,
            "prose_sections": dict(self.prose_sections),
            "graph_context": self.graph_context,
            "owning_short_head": self.owning_short_head,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProseRefreshTask:
        return cls(
            uri=d["uri"],
            kind=d["kind"],
            name=d["name"],
            page_path=d["page_path"],
            graph_path=d.get("graph_path", ""),
            language=d.get("language", "unknown"),
            entity_root=d.get("entity_root", ""),
            trigger=d["trigger"],
            diff=d.get("diff"),
            changed_files=list(d.get("changed_files") or []),
            page_content=d.get("page_content", ""),
            file_map_rows=d.get("file_map_rows", ""),
            prose_sections=dict(d.get("prose_sections") or {}),
            graph_context=d.get("graph_context", ""),
            owning_short_head=d.get("owning_short_head"),
        )


@dataclass
class ProseRefreshResult:
    """The refresh agent's parsed output for one entity (schema v2)."""

    uri: str
    sections: dict[str, str] = field(default_factory=dict)
    file_map_descriptions: dict[str, str] = field(default_factory=dict)
    dir_descriptions: dict[str, str] = field(default_factory=dict)
    overview: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "sections": dict(self.sections),
            "file_map_descriptions": dict(self.file_map_descriptions),
            "dir_descriptions": dict(self.dir_descriptions),
            "overview": self.overview,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ProseRefreshResult:
        return cls(
            uri=d["uri"],
            sections=dict(d.get("sections") or {}),
            file_map_descriptions=dict(d.get("file_map_descriptions") or {}),
            dir_descriptions=dict(d.get("dir_descriptions") or {}),
            overview=d.get("overview"),
            error=d.get("error"),
        )


@dataclass
class PropagateFinding:
    entity_stem: str
    claim: str
    reason: str = ""

    def to_dict(self) -> dict:
        return {"entity_stem": self.entity_stem, "claim": self.claim, "reason": self.reason}

    @classmethod
    def from_dict(cls, d: dict) -> PropagateFinding:
        return cls(entity_stem=d["entity_stem"], claim=d.get("claim", ""), reason=str(d.get("reason", "")))


@dataclass
class PropagateResultItem:
    kind: str
    target_slug: str
    stale: bool
    findings: list[PropagateFinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "target_slug": self.target_slug,
            "stale": self.stale,
            "findings": [f.to_dict() for f in self.findings],
        }

    @classmethod
    def from_dict(cls, d: dict) -> PropagateResultItem:
        return cls(
            kind=d["kind"],
            target_slug=d["target_slug"],
            stale=bool(d.get("stale", False)),
            findings=[PropagateFinding.from_dict(f) for f in (d.get("findings") or [])],
        )


@dataclass
class ScanResults:
    prose: list[ProseRefreshResult] = field(default_factory=list)
    propagate: list[PropagateResultItem] = field(default_factory=list)
    schema: int = SCHEMA_VERSION
    # Runtime-only (NOT serialized): provider-side errors (e.g. prose_refresher
    # failures on the in-process Bedrock surface) that run_scan merges into its
    # ScanResult for partial-success reporting. Out-of-process surfaces leave this
    # empty; per-entity errors DO cross the boundary via ProseRefreshResult.error
    # (serialized), which the apply-half stamp gate consults.
    provider_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "prose": [p.to_dict() for p in self.prose],
            "propagate": [p.to_dict() for p in self.propagate],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> ScanResults:
        schema = d.get("schema", SCHEMA_VERSION)
        if schema != SCHEMA_VERSION:
            raise ValueError(f"unsupported results schema: {schema!r}")
        return cls(
            prose=[ProseRefreshResult.from_dict(p) for p in (d.get("prose") or [])],
            propagate=[PropagateResultItem.from_dict(p) for p in (d.get("propagate") or [])],
            schema=schema,
        )

    @classmethod
    def from_json(cls, raw: str) -> ScanResults:
        return cls.from_dict(json.loads(raw))


@dataclass
class ApplyResult:
    """Counts returned by apply_scan_results / apply_scan_worklist."""

    narrated: int = 0
    described: int = 0
    dir_filled: int = 0
    sections_filled: int = 0
    stamped: int = 0
    propagated: int = 0
    entity_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "narrated": self.narrated,
            "described": self.described,
            "dir_filled": self.dir_filled,
            "sections_filled": self.sections_filled,
            "stamped": self.stamped,
            "propagated": self.propagated,
            "entity_errors": list(self.entity_errors),
        }
