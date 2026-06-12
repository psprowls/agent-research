"""Worklist/results contract for the split scan pipeline (schema v1).

Plugin-internal JSON written under ``<workspace>/.graph-wiki/``. The emit phase
serializes a ``ScanWorklist``; a provider (Bedrock in-process or Claude
out-of-process) returns a ``ScanResults``; the apply phase consumes it. Every
results field is optional — a missing value is simply not injected, mirroring
the Bedrock loops that skip empty narration / empty parse.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

SCHEMA_VERSION = 1


@dataclass
class FillNeeds:
    narrative: bool = False
    file_todo_paths: list[str] = field(default_factory=list)
    dir_todo_contexts: list[str] = field(default_factory=list)
    overview: bool = False
    purpose: bool = False
    public_api: bool = False

    @property
    def any(self) -> bool:
        return bool(
            self.narrative
            or self.file_todo_paths
            or self.dir_todo_contexts
            or self.overview
            or self.purpose
            or self.public_api
        )

    def to_dict(self) -> dict:
        return {
            "narrative": self.narrative,
            "file_todo_paths": list(self.file_todo_paths),
            "dir_todo_contexts": list(self.dir_todo_contexts),
            "overview": self.overview,
            "purpose": self.purpose,
            "public_api": self.public_api,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FillNeeds:
        return cls(
            narrative=bool(d.get("narrative", False)),
            file_todo_paths=list(d.get("file_todo_paths") or []),
            dir_todo_contexts=list(d.get("dir_todo_contexts") or []),
            overview=bool(d.get("overview", False)),
            purpose=bool(d.get("purpose", False)),
            public_api=bool(d.get("public_api", False)),
        )


@dataclass
class FillTask:
    uri: str
    kind: str
    name: str
    page_path: str
    graph_path: str
    language: str
    needs: FillNeeds

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "kind": self.kind,
            "name": self.name,
            "page_path": self.page_path,
            "graph_path": self.graph_path,
            "language": self.language,
            "needs": self.needs.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> FillTask:
        return cls(
            uri=d["uri"],
            kind=d["kind"],
            name=d["name"],
            page_path=d["page_path"],
            graph_path=d["graph_path"],
            language=d.get("language", "unknown"),
            needs=FillNeeds.from_dict(d.get("needs") or {}),
        )


@dataclass
class DriftSectionInput:
    heading: str  # e.g. "## Purpose"
    chunk: str

    def to_dict(self) -> dict:
        return {"heading": self.heading, "chunk": self.chunk}

    @classmethod
    def from_dict(cls, d: dict) -> DriftSectionInput:
        return cls(heading=d["heading"], chunk=d.get("chunk", ""))


@dataclass
class DriftTask:
    uri: str
    page_path: str
    anchor: str
    narrative: str
    file_map: str | None
    sections: list[DriftSectionInput] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "page_path": self.page_path,
            "anchor": self.anchor,
            "narrative": self.narrative,
            "file_map": self.file_map,
            "sections": [s.to_dict() for s in self.sections],
        }

    @classmethod
    def from_dict(cls, d: dict) -> DriftTask:
        return cls(
            uri=d["uri"],
            page_path=d["page_path"],
            anchor=d["anchor"],
            narrative=d.get("narrative", ""),
            file_map=d.get("file_map"),
            sections=[DriftSectionInput.from_dict(s) for s in (d.get("sections") or [])],
        )


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
    fill_tasks: list[FillTask] = field(default_factory=list)
    drift_tasks: list[DriftTask] = field(default_factory=list)
    propagate_tasks: list[PropagateTask] = field(default_factory=list)
    schema: int = SCHEMA_VERSION
    # M4 stamping bookkeeping: candidate uri -> anchor (last_updated_commit at emit).
    # Apply stamps drift_propagated_commit for every processed candidate.
    propagate_anchors: dict[str, str] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not (self.fill_tasks or self.drift_tasks or self.propagate_tasks)

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "head_commit": self.head_commit,
            "short_head": self.short_head,
            "fill_tasks": [t.to_dict() for t in self.fill_tasks],
            "drift_tasks": [t.to_dict() for t in self.drift_tasks],
            "propagate_tasks": [t.to_dict() for t in self.propagate_tasks],
            "propagate_anchors": dict(self.propagate_anchors),
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
            fill_tasks=[FillTask.from_dict(t) for t in (d.get("fill_tasks") or [])],
            drift_tasks=[DriftTask.from_dict(t) for t in (d.get("drift_tasks") or [])],
            propagate_tasks=[PropagateTask.from_dict(t) for t in (d.get("propagate_tasks") or [])],
            schema=schema,
            propagate_anchors=dict(d.get("propagate_anchors") or {}),
        )

    @classmethod
    def from_json(cls, raw: str) -> ScanWorklist:
        return cls.from_dict(json.loads(raw))


@dataclass
class FillResult:
    uri: str
    narrative: str | None = None
    file_descriptions: dict[str, str] = field(default_factory=dict)
    dir_descriptions: dict[str, str] = field(default_factory=dict)
    overview: str | None = None
    purpose: str | None = None
    public_api: str | None = None

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "narrative": self.narrative,
            "file_descriptions": dict(self.file_descriptions),
            "dir_descriptions": dict(self.dir_descriptions),
            "overview": self.overview,
            "purpose": self.purpose,
            "public_api": self.public_api,
        }

    @classmethod
    def from_dict(cls, d: dict) -> FillResult:
        return cls(
            uri=d["uri"],
            narrative=d.get("narrative"),
            file_descriptions=dict(d.get("file_descriptions") or {}),
            dir_descriptions=dict(d.get("dir_descriptions") or {}),
            overview=d.get("overview"),
            purpose=d.get("purpose"),
            public_api=d.get("public_api"),
        )


@dataclass
class DriftVerdict:
    section: str  # heading WITHOUT the "## " prefix, e.g. "Purpose"
    stale: bool
    reason: str = ""

    def to_dict(self) -> dict:
        return {"section": self.section, "stale": self.stale, "reason": self.reason}

    @classmethod
    def from_dict(cls, d: dict) -> DriftVerdict:
        return cls(section=d["section"], stale=bool(d.get("stale", False)), reason=str(d.get("reason", "")))


@dataclass
class DriftResultItem:
    uri: str
    verdicts: list[DriftVerdict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"uri": self.uri, "verdicts": [v.to_dict() for v in self.verdicts]}

    @classmethod
    def from_dict(cls, d: dict) -> DriftResultItem:
        return cls(uri=d["uri"], verdicts=[DriftVerdict.from_dict(v) for v in (d.get("verdicts") or [])])


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
    fills: list[FillResult] = field(default_factory=list)
    drift: list[DriftResultItem] = field(default_factory=list)
    propagate: list[PropagateResultItem] = field(default_factory=list)
    schema: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "fills": [f.to_dict() for f in self.fills],
            "drift": [d.to_dict() for d in self.drift],
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
            fills=[FillResult.from_dict(f) for f in (d.get("fills") or [])],
            drift=[DriftResultItem.from_dict(x) for x in (d.get("drift") or [])],
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
    drift_flagged: int = 0
    stamped: int = 0
    propagated: int = 0
    entity_errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "narrated": self.narrated,
            "described": self.described,
            "dir_filled": self.dir_filled,
            "sections_filled": self.sections_filled,
            "drift_flagged": self.drift_flagged,
            "stamped": self.stamped,
            "propagated": self.propagated,
            "entity_errors": list(self.entity_errors),
        }
