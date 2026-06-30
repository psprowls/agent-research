"""Stage-1 deterministic recall for `gw guidance suggest`.

Pure, Bedrock-free. Loads guidance pages and scores each against the task
message and an optional set of working files, firing five signals:
globs / keywords / entity / index (file-driven) and message (always on). A
top-up by coarse message overlap guarantees the orchestrator always gets a
real candidate slate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePath

from graph_io.handle import GraphReader
from guidance_io.frontmatter import normalize_language, parse
from guidance_io.index_store import GuidanceIndex
from guidance_io.paths import guidance_dir, list_all_pages
from guidance_io.vocab import canonical_tag, load_vocab
from source_parser.parsers import EXTENSIONS
from wiki_io.entity_lookup import (
    entity_filename_for_uri,
    lookup_entity_by_path,
    lookup_package_by_dir,
)

_ENTITY_STEM_RE = re.compile(r"\[\[entities/([^\]|#\n]+?)(?:[|#][^\]\n]*)?\]\]")
_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Extension (".ext") → language name, from source_parser's canonical extension map.
_EXT_TO_LANG: dict[str, str] = {ext: parser.name for ext, parser in EXTENSIONS.items()}

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
    role: list[str] = field(default_factory=list)
    language: str | None = None  # normalized lowercase; None = agnostic (wildcard)


@dataclass
class PathContext:
    rel_path: str
    content: str
    package_stem: str | None
    index_topics: list[str]
    index_tags: list[str]
    languages: set[str] = field(default_factory=set)  # file-node langs, else extension, else empty


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
        normalize_language(fm)  # Task 1 canonical helper: trim+lowercase in place, drop empty/whitespace
        page_language = fm.get("language")
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
                role=[str(p) for p in (fm.get("role") or [])],
                language=page_language,
            )
        )
    return pages


def _derive_path_languages(reader: GraphReader | None, rel: str) -> set[str]:
    """Return the language(s) for a repo-relative FILE path as a 0-or-1-element set.

    Preference order: graph file-node attrs_json.language → file extension → empty.
    (The package branch in resolve_path_contexts builds a multi-element set by
    unioning the contained files' languages.)
    """
    if reader is not None:
        # file_attrs returns the parsed attrs dict, or None for a missing row,
        # empty attrs, or unparseable JSON — the same fallback the old raw-SQL
        # path produced via its (sqlite3.Error, ValueError) guard.
        attrs = reader.file_attrs(rel)
        if attrs:
            lang = attrs.get("language")
            if lang:
                return {str(lang).strip().lower()}
    ext_lang = _EXT_TO_LANG.get(Path(rel).suffix)
    return {ext_lang} if ext_lang else set()


_SYMBOL_KINDS = ("class", "function", "method")


def _package_signal_inputs(
    reader: GraphReader, node_id: int, index: GuidanceIndex
) -> tuple[set[str], list[str], list[str], str]:
    """Build (languages, index_topics, index_tags, content) for a package node
    from its contained file nodes and their symbols. Graph-only; no disk read.

    Rows from reader.files_in_node are plain tuples (graph_io connections set no
    row_factory): col 0 = id, 1 = path, 2 = attrs_json. Access positionally.
    """
    file_rows = reader.files_in_node(node_id)
    languages: set[str] = set()
    topics: list[str] = []
    tags: list[str] = []
    name_parts: list[str] = []
    file_ids: list[int] = []
    for row in file_rows:
        file_id, path, attrs_json = row[0], row[1], row[2]
        file_ids.append(int(file_id))
        name_parts.append(Path(path).name)
        # language: file-node attrs_json.language, else extension; never the package attrs.
        lang: str | None = None
        if attrs_json:
            try:
                lang = json.loads(attrs_json).get("language")
            except ValueError:
                lang = None
        if lang:
            languages.add(str(lang).strip().lower())
        else:
            ext_lang = _EXT_TO_LANG.get(Path(path).suffix)
            if ext_lang:
                languages.add(ext_lang)
        entry = index.files.get(path)
        if entry:
            topics.extend(entry.topics)
            tags.extend(entry.tags)
    # symbol names under the package's files → keyword haystack.
    if file_ids:
        name_parts.extend(reader.symbol_names_under_files(file_ids, _SYMBOL_KINDS))
    content = " ".join(name_parts)
    # de-dupe topics/tags while preserving order
    topics = list(dict.fromkeys(topics))
    tags = list(dict.fromkeys(tags))
    return languages, topics, tags, content


def resolve_path_contexts(
    paths: list[str],
    reader: GraphReader | None,
    repo_root: Path | None,
    index: GuidanceIndex,
) -> list[PathContext]:
    contexts: list[PathContext] = []
    for raw in paths:
        rel = PurePath(raw).as_posix()
        # Baseline signals for EVERY path (pre-feature behavior): rel-level index entry
        # and the file/extension language. The package branch overrides these with
        # package-aggregated values when a directory resolves to a package.
        entry = index.files.get(rel)
        index_topics: list[str] = list(entry.topics) if entry else []
        index_tags: list[str] = list(entry.tags) if entry else []
        languages: set[str] = _derive_path_languages(reader, rel)
        package_stem: str | None = None
        content = ""

        file_hit = None
        if reader is not None and repo_root is not None:
            file_hit = lookup_entity_by_path(reader, repo_root, repo_root / rel)

        if file_hit is not None:
            # FILE branch — stem from the entity; baseline index/language already correct.
            package_stem = entity_filename_for_uri(file_hit[0], reader)
            if repo_root is not None:
                try:
                    content = (repo_root / rel).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    content = ""
        elif reader is not None and repo_root is not None:
            # PACKAGE branch — directory (or non-entity file) affects resolves to its
            # enclosing package/app; override index/language/content with package-aggregated
            # signals. No disk read for a resolved package.
            pkg = lookup_package_by_dir(reader, repo_root, repo_root / rel)
            if pkg is not None:
                uri, _name, node_id = pkg
                package_stem = entity_filename_for_uri(uri, reader)
                languages, index_topics, index_tags, content = _package_signal_inputs(reader, node_id, index)
            else:
                # Unresolved with a graph present: legacy disk read so keyword matching
                # still works on a real non-entity, non-package file. Baseline index/lang kept.
                try:
                    content = (repo_root / rel).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    content = ""
        else:
            # No graph (reader is None / no repo_root): legacy disk read; baseline index/lang
            # kept so file affects still fire index + language without a graph.
            if repo_root is not None:
                try:
                    content = (repo_root / rel).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    content = ""

        contexts.append(
            PathContext(
                rel_path=rel,
                content=content,
                package_stem=package_stem,
                index_topics=index_topics,
                index_tags=index_tags,
                languages=languages,
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

    context_languages: set[str] = set().union(*(ctx.languages for ctx in path_contexts)) if path_contexts else set()

    for page in pages:
        # Hard language pre-filter: agnostic pages (language=None) always survive;
        # language-tagged pages are kept only when their language appears in the
        # context language set; an empty context set is a no-op (nothing excluded).
        if page.language is not None and context_languages and page.language not in context_languages:
            continue
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
