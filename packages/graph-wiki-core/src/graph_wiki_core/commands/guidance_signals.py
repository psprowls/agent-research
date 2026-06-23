"""Stage-1 deterministic recall for `gw guidance suggest`.

Pure, Bedrock-free. Loads guidance pages and scores each against the task
message and an optional set of working files, firing five signals:
globs / keywords / entity / index (file-driven) and message (always on). A
top-up by coarse message overlap guarantees the orchestrator always gets a
real candidate slate.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from guidance_io.frontmatter import parse
from guidance_io.index_store import GuidanceIndex
from guidance_io.paths import guidance_dir, list_all_pages
from guidance_io.vocab import canonical_tag, load_vocab
from wiki_io.entity_lookup import entity_filename_for_uri, lookup_entity_by_path

_ENTITY_STEM_RE = re.compile(r"\[\[entities/([^\]|#\n]+?)(?:[|#][^\]\n]*)?\]\]")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Per-signal score weights.
_W_GLOB = 3.0
_W_ENTITY = 3.0
_W_KEYWORD = 2.0
_W_INDEX = 2.0
_W_MESSAGE = 1.0  # per overlapping token, capped


@dataclass
class GuidancePage:
    slug: str
    topic: str
    tags: list[str]
    keywords: list[str]
    entities: list[str]  # entity stems (no [[entities/...]] wrapper)
    globs: list[str]
    summary: str
    applies_when: str
    impact: str
    guidance_body: str
    workflow: list[str] = field(default_factory=list)


@dataclass
class PathContext:
    rel_path: str
    content: str
    package_stem: str | None
    index_topics: list[str]
    index_tags: list[str]


@dataclass
class Candidate:
    page: GuidancePage
    signals_fired: list[str] = field(default_factory=list)
    base_score: float = 0.0


def _extract_section(body: str, heading: str) -> str:
    lines = body.splitlines()
    out: list[str] = []
    capture = False
    for line in lines:
        if line.strip().lower() == f"## {heading}".lower():
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            out.append(line)
    return "\n".join(out).strip()


def load_guidance_pages(workspace: Path) -> list[GuidancePage]:
    root = guidance_dir(workspace)
    vocab = load_vocab(workspace)
    pages: list[GuidancePage] = []
    for page_path in list_all_pages(workspace):
        try:
            fm, body = parse(page_path.read_text(encoding="utf-8", errors="replace"))
        except ValueError:
            continue
        rel = page_path.relative_to(root)
        triggers = fm.get("triggers") or {}
        if not isinstance(triggers, dict):
            triggers = {}
        entities = []
        for raw in triggers.get("entities") or []:
            m = _ENTITY_STEM_RE.search(str(raw))
            entities.append(m.group(1) if m else str(raw))
        pages.append(
            GuidancePage(
                slug=f"{rel.parent.as_posix()}/{page_path.stem}",
                topic=str(fm.get("topic", "")),
                tags=[canonical_tag(str(t), vocab) or str(t) for t in (fm.get("tags") or [])],
                keywords=[str(k) for k in (triggers.get("keywords") or [])],
                entities=entities,
                globs=[str(g) for g in (triggers.get("globs") or [])],
                summary=str(fm.get("summary", "")),
                applies_when=str(fm.get("applies_when", "")),
                impact=str(fm.get("impact", "medium")),
                guidance_body=_extract_section(body, "Guidance"),
                workflow=[str(p) for p in (fm.get("workflow") or [])],
            )
        )
    return pages


def resolve_path_contexts(
    paths: list[str],
    conn: sqlite3.Connection | None,
    repo_root: Path | None,
    index: GuidanceIndex,
) -> list[PathContext]:
    contexts: list[PathContext] = []
    for raw in paths:
        rel = PurePath(raw).as_posix()
        content = ""
        if repo_root is not None:
            try:
                content = (repo_root / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""
        package_stem: str | None = None
        if conn is not None and repo_root is not None:
            hit = lookup_entity_by_path(conn, repo_root, repo_root / rel)
            if hit is not None:
                package_stem = entity_filename_for_uri(hit[0], conn)
        entry = index.files.get(rel)
        contexts.append(
            PathContext(
                rel_path=rel,
                content=content,
                package_stem=package_stem,
                index_topics=list(entry.topics) if entry else [],
                index_tags=list(entry.tags) if entry else [],
            )
        )
    return contexts


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def compute_candidates(
    pages: list[GuidancePage],
    message: str,
    path_contexts: list[PathContext],
    k: int,
) -> list[Candidate]:
    msg_tokens = _tokens(message)
    fired: list[Candidate] = []
    unfired: list[tuple[float, GuidancePage]] = []

    for page in pages:
        signals: list[str] = []
        score = 0.0

        for ctx in path_contexts:
            if page.globs and any(PurePath(ctx.rel_path).match(g) for g in page.globs):
                if "globs" not in signals:
                    signals.append("globs")
                    score += _W_GLOB
            if page.keywords and any(kw and kw in ctx.content for kw in page.keywords):
                if "keywords" not in signals:
                    signals.append("keywords")
                    score += _W_KEYWORD
            if ctx.package_stem and ctx.package_stem in page.entities:
                if "entity" not in signals:
                    signals.append("entity")
                    score += _W_ENTITY
            idx_topics = set(ctx.index_topics)
            idx_tags = set(ctx.index_tags)
            if (page.topic and page.topic in idx_topics) or (set(page.tags) & idx_tags):
                if "index" not in signals:
                    signals.append("index")
                    score += _W_INDEX

        page_vocab = _tokens(" ".join([page.topic, *page.tags, *page.keywords]))
        overlap = len(msg_tokens & page_vocab)
        if overlap:
            signals.append("message")
            score += min(overlap, 3) * _W_MESSAGE

        if signals:
            fired.append(Candidate(page=page, signals_fired=signals, base_score=score))
        else:
            coarse = len(msg_tokens & _tokens(" ".join([page.summary, page.topic, *page.tags])))
            unfired.append((float(coarse), page))

    fired.sort(key=lambda c: c.base_score, reverse=True)
    if len(fired) < k:
        unfired.sort(key=lambda t: t[0], reverse=True)
        for coarse, page in unfired:
            if len(fired) >= k:
                break
            fired.append(Candidate(page=page, signals_fired=[], base_score=coarse * 0.1))
    return fired[:k]
