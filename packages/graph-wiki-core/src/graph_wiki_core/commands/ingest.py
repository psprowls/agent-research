"""Ingest command — route a source file or work item into the wiki vault.

Public API:
    IngestResult            — dataclass: status, page_path, slug, title, page_type,
                               source_path, cross_refs_updated
    build_ingest_source_prompt(text, source_path, source_type, vault_structure) -> str
    run_ingest_source(source_path, workspace_path) -> IngestResult
    run_ingest_work_item(frontmatter_text, body, ...) -> IngestResult

The ingestor system prompt is constructed inline via
`build_ingestor_system(project_context=...)` where `project_context` is the
rendered output of `render_project_context(wiki)` — see CTX-03.

Cross-ref update scope (CONTEXT.md deferred decision):
    Only update_index(wiki) is called after every ingest write. Deep back-ref link
    scanning across all vault pages is explicitly deferred to a future version —
    per CONTEXT.md §deferred: "ingest cross-ref deep linking — if too costly, scope
    down to index-only for v1". This is the scope-down path.
"""

from __future__ import annotations

import logging
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml
from graph_io import exit_codes, queries  # noqa: F401  — exit_codes re-exposed for CLI callers
from graph_io.store import GraphNotInitializedError, read_only_connect
from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.pool import SubagentPool, TaskResult
from subagent_runtime.trace_io import write_trace_record
from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.entity_lookup import (
    entity_filename_for_uri,
    lookup_entity_by_name,
    lookup_entity_by_path,
)
from wiki_io.ingest_source import (
    PREVIEW_CHARS,
    RAW_FOLDER_TYPE_MAP,
    SOURCE_TYPE_ENUM,
    SkillBundle,
    archive_destination,
    extract,
    gather_skill_sources,
    guess_source_type,
    resolve_skill_anchor,
    slugify,
)
from wiki_io.ingest_work_item import _parse_frontmatter, _validate, file_work_item
from wiki_io.update_index import update_index
from wiki_io.wikilinks import vault_wikilink
from work_io import doc_pointers
from workspace_io.paths import graph_dir, raw_dir

from graph_wiki_core.commands.suggest_pages import run_suggest_phase
from graph_wiki_core.graph_tools import build_graph_tools
from graph_wiki_core.prompts.ingestor import build_ingestor_system
from graph_wiki_core.prompts.project_context import render_project_context
from graph_wiki_core.prompts.skill_planner import build_skill_planner_system
from graph_wiki_core.prompts.skill_synthesizer import build_skill_synthesizer_system

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 40 / INGESTOR-02 / D-01 / D-02 — typed NOT_INITIALIZED error
# ---------------------------------------------------------------------------


class IngestorGraphNotInitializedError(RuntimeError):
    """Raised when run_ingest_source() cannot open the workspace's graph DB.

    Surface contract (Phase 40 / INGESTOR-02 / D-01 / D-02):
      - The CLI layer catches this exception and exits with code
        `graph_io.exit_codes.NOT_INITIALIZED` (=3).
      - The exception's message is the D-02 stderr text — clients can
        forward it verbatim to stderr.

    Note (Phase 40 SC#2 invariant): unlike the scanner (Phase 39 D-08), the
    ingestor does NOT gracefully fall back when the graph DB is missing —
    slug-aligning new pages with the graph is the whole point of this command.
    Operating without a graph would silently produce drift; hard-fail instead.
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        super().__init__(
            "error: graph-io not initialized for this workspace. "
            "Run 'gw graph build' (or 'cg update') to initialize, then retry."
        )


# Matches YAML list items with any indentation (2-space, 4-space, tab)
_LIST_ITEM_RE = re.compile(r"^[ \t]+- ")

# ---------------------------------------------------------------------------
# IngestResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    """Result of a run_ingest_source() or run_ingest_work_item() call.

    Fields:
        status:             Always "ok" on success.
        page_path:          Path to the written page relative to wiki root.
        slug:               URL-safe slug used for the output filename.
        title:              Human-readable page title.
        page_type:          Page category (routing class). From run_ingest_source:
                            always "source" (M3 Part A — every ingested doc lands
                            under sources/; see source_type for the closed-enum
                            classification). From run_ingest_work_item: always
                            "work" (work items file under <workspace>/work/ via
                            file_work_item).
        source_path:        Original source file path (empty for work items).
        cross_refs_updated: Number of cross-reference updates performed (index-only scope).
        entity_uri:         Phase 40 (INGESTOR-01) canonical entity URI when the graph
                            matched the source by path or by name; None when no graph
                            match was found OR when the result was produced by
                            `run_ingest_work_item` (work items bypass entity lookup).
        source_type:        Closed-enum classification on Source pages
                            (run_ingest_source). raw/<type>/ folders are
                            authoritative; otherwise LLM-classified from content,
                            defaulting to the path-guess. None for work items.
        stripped_wikilinks: Living Wiki M3: unresolved [[wikilinks]] removed from
                            the body (empty when none were stripped).
        frontmatter_parsed: Living Wiki M3: False when the ingestor frontmatter
                            failed to parse (parse miss); source_type falls back
                            to the path-guess fallback.
        suggested_pages:    Living Wiki M3: proposals upserted into the ledger
                            (wiki/proposals/) by this run (each a dict with
                            kind/slug/mode/status). Empty on a degraded run or for
                            work items.
        suggestions_parsed: Living Wiki M3: False when the extractor LLM call
                            errored or its output did not parse (zero suggestions).
        guidance_pages_written: Type-branched ingest: workspace-relative paths of
                            guidance pages written by the skill branch (empty for
                            all other source types).
        archived_to:        Workspace-relative raw/_archive/ destination the source
                            was moved to after a successful ingest; None for sources
                            outside raw/, work items, or when the move failed.
    """

    status: str
    page_path: str
    slug: str
    title: str
    page_type: str
    source_path: str
    cross_refs_updated: int
    entity_uri: str | None = None  # Phase 40: canonical entity URI; None for free-form sources
    # Living Wiki M3 Part A (ingest hardening):
    source_type: str | None = None  # closed-enum classification on Source pages; None for work items
    stripped_wikilinks: list[str] = field(default_factory=list)  # unresolved [[links]] stripped from the body
    frontmatter_parsed: bool = True  # False when the ingestor frontmatter failed to parse (parse miss)
    # Living Wiki M3 (suggestion step):
    suggested_pages: list[dict] = field(default_factory=list)  # proposals upserted by this run (empty on degraded path)
    suggestions_parsed: bool = True  # False when the extractor call errored or its output didn't parse
    proposal_reasoner_status: str = "skipped"
    proposal_extractor_status: str = "skipped"
    proposal_error: str | None = None
    # Type-branched ingest: workspace-relative paths of guidance pages created or
    # updated by the skill branch. Empty list for every other source type.
    guidance_pages_written: list[str] = field(default_factory=list)
    # Raw-source archive (design 2026-06-09): workspace-relative destination the
    # raw source was moved to (e.g. "raw/_archive/specs/x.md"). None when the
    # source was outside raw/, already archived, or the move failed.
    archived_to: str | None = None


@dataclass
class _IngestBranchResult:
    """Intermediate hand-off from a source-type branch to _run_common_tail.

    Both branches produce a source-page body and the metadata the shared tail
    needs to write + finalize it. The skill branch additionally populates
    guidance_pages_written (written before the tail runs).
    """

    page_body: str
    target_slug: str
    source_type: str
    entity_uri: str | None
    entity_stem: str | None
    frontmatter_parsed: bool
    run_suggest: bool
    allowed_kinds: frozenset[str] | None = None
    guidance_pages_written: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Route page_type -> target directory
# ---------------------------------------------------------------------------

# Slice 4: `package` is no longer an ingest target — entity pages are
# scanner-owned and live under entities/. Valid ingest page_types collapse to
# source | concept | adr (all ingest-owned, preserved dirs). The default
# fallback (page_type not in _PAGE_TYPE_DIRS -> concept) is unchanged.
_PAGE_TYPE_DIRS: dict[str, str] = {
    "concept": "concepts",
    "adr": "adrs",
    "source": "sources",
}


def _route_target_path(wiki: Path, page_type: str, slug: str) -> Path:
    """Return the absolute target path for a page given its type and slug.

    Security (T-05-05-02): slug comes from slugify() which strips non-alphanumeric
    chars; we also join under a known subdir — no path traversal is possible.
    """
    subdir = _PAGE_TYPE_DIRS.get(page_type, "concepts")
    target = wiki / subdir / f"{slug}.md"
    # Confirm path stays inside wiki (defense in depth). WR-06 (D-06): mirror
    # the `Path.is_relative_to` idiom used in commands/query.py:356 — Python
    # 3.11+ is the floor (CLAUDE.md), so no fallback needed.
    resolved = target.resolve()
    wiki_resolved = wiki.resolve()
    if not resolved.is_relative_to(wiki_resolved):
        raise ValueError(f"target path escapes wiki root: {resolved}")
    return target


# ---------------------------------------------------------------------------
# Reconcile body `target_slug:` with on-disk filename (Plan 06-13 / UAT G3)
# ---------------------------------------------------------------------------


def _rewrite_target_slug_in_body(text: str, canonical_slug: str) -> str:
    """Rewrite the `target_slug:` line in the YAML frontmatter of `text`
    so it equals `canonical_slug`. If no `target_slug:` line exists in
    the frontmatter, inject one immediately after the opening `---`.

    Operates on the raw text — does not re-emit YAML — so it preserves
    comments, ordering, and indentation of all other frontmatter fields.

    Only touches the frontmatter block (between the first two `---`
    delimiters). If text has no frontmatter, returns text unchanged.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text
    # Find the second `---` to bound the frontmatter block
    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        return text
    leading_ws = text[: len(text) - len(stripped)]
    fm_block = after_open[:close_idx]
    body_and_close = after_open[close_idx:]
    new_lines: list[str] = []
    found = False
    for line in fm_block.splitlines():
        if line.lstrip().startswith("target_slug:"):
            indent = line[: len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}target_slug: {canonical_slug}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.insert(0, f"target_slug: {canonical_slug}")
    new_fm = "\n".join(new_lines)
    return f"{leading_ws}---\n{new_fm}{body_and_close}"


# ---------------------------------------------------------------------------
# Phase 40 D-05 / D-06: write `entity_uri:` frontmatter on every ingest.
# ---------------------------------------------------------------------------


def _set_entity_uri_in_body(text: str, entity_uri: str | None) -> str:
    """Insert or replace the `entity_uri:` line in the YAML frontmatter of `text`.

    Placement (CONTEXT specifics): immediately AFTER the `target_slug:` line. When
    no `target_slug:` line exists, insert as the FIRST field of the frontmatter
    block. When called repeatedly the result is idempotent (only one
    `entity_uri:` line ever appears).

    `entity_uri=None` writes the literal value `null` so downstream tooling
    (lint, link-checker, v1.8 reconciliation) can distinguish free-form pages
    from entity-backed ones (D-05).

    Operates on the raw text — does not re-emit YAML — so it preserves comments,
    ordering, and indentation of other frontmatter fields. Returns text
    unchanged when no frontmatter is present.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text
    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        return text
    leading_ws = text[: len(text) - len(stripped)]
    fm_block = after_open[:close_idx]
    body_and_close = after_open[close_idx:]

    value_str = "null" if entity_uri is None else entity_uri
    new_lines: list[str] = []
    inserted = False
    for line in fm_block.splitlines():
        stripped_line = line.lstrip()
        # Drop any existing entity_uri: line (idempotence)
        if stripped_line.startswith("entity_uri:"):
            continue
        new_lines.append(line)
        # Insert immediately after target_slug:
        if not inserted and stripped_line.startswith("target_slug:"):
            indent = line[: len(line) - len(stripped_line)]
            new_lines.append(f"{indent}entity_uri: {value_str}")
            inserted = True
    if not inserted:
        # No target_slug: line — insert at the top of the frontmatter block.
        new_lines.insert(0, f"entity_uri: {value_str}")
    new_fm = "\n".join(new_lines)
    return f"{leading_ws}---\n{new_fm}{body_and_close}"


# ---------------------------------------------------------------------------
# Source-type frontmatter + synthesize-frontmatter rule
# ---------------------------------------------------------------------------


def _set_source_type_in_body(text: str, source_type: str) -> str:
    """Insert or replace the `source_type:` line in the YAML frontmatter of `text`.

    Placement: inserted as the FIRST field of the frontmatter block. Idempotent
    — any existing `source_type:` line is dropped first, so only one ever
    appears. Operates on raw text (preserves comments/order); returns text
    unchanged when no `---` block is present.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text
    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        return text
    leading_ws = text[: len(text) - len(stripped)]
    fm_block = after_open[:close_idx]
    body_and_close = after_open[close_idx:]

    new_lines: list[str] = []
    for line in fm_block.splitlines():
        if line.lstrip().startswith("source_type:"):
            continue  # drop existing line (idempotence)
        new_lines.append(line)
    new_lines.insert(0, f"source_type: {source_type}")
    new_fm = "\n".join(new_lines)
    return f"{leading_ws}---\n{new_fm}{body_and_close}"


def _set_source_path_in_body(text: str, source_path: str) -> str:
    """Insert or replace the `source_path:` line in the YAML frontmatter of `text`.

    Placement: replaces an existing `source_path:` line in place (preserving its
    indent and position); when absent, inserts as the FIRST field of the
    frontmatter block. Idempotent. Operates on raw text (preserves comments and
    field order); returns text unchanged when no `---` block is present.
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text
    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        return text
    leading_ws = text[: len(text) - len(stripped)]
    fm_block = after_open[:close_idx]
    body_and_close = after_open[close_idx:]

    new_lines: list[str] = []
    replaced = False
    for line in fm_block.splitlines():
        stripped_line = line.lstrip()
        if stripped_line.startswith("source_path:"):
            indent = line[: len(line) - len(stripped_line)]
            new_lines.append(f"{indent}source_path: {source_path}")
            replaced = True
            continue
        new_lines.append(line)
    if not replaced:
        new_lines.insert(0, f"source_path: {source_path}")
    new_fm = "\n".join(new_lines)
    return f"{leading_ws}---\n{new_fm}{body_and_close}"


def _sanitize_proposal_error(error: object) -> str | None:
    if not error:
        return None
    text = str(error).replace("\n", " ").strip()
    return text[:160]


def _yaml_quoted_scalar(value: str) -> str:
    return yaml.safe_dump(value, default_style='"', width=1000).splitlines()[0]


def _set_proposal_status_in_body(text: str, status: dict, *, today: str | None = None) -> str:
    """Insert or replace proposal_status in Source frontmatter."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text
    after_open = stripped[3:].lstrip("\n")
    close_idx = after_open.find("\n---")
    if close_idx == -1:
        return text
    leading_ws = text[: len(text) - len(stripped)]
    fm_block = after_open[:close_idx]
    body_and_close = after_open[close_idx:]
    try:
        parsed_frontmatter = yaml.safe_load(fm_block)
    except yaml.YAMLError:
        return text
    if not isinstance(parsed_frontmatter, dict):
        return text

    updated = today or date.today().isoformat()
    proposal_lines = [
        "proposal_status:",
        f"  reasoner: {status.get('reasoner', 'skipped')}",
        f"  extractor: {status.get('extractor', 'skipped')}",
        f"  proposals: {int(status.get('proposals', 0) or 0)}",
        f"  updated: {updated}",
    ]
    error = _sanitize_proposal_error(status.get("error"))
    if error:
        proposal_lines.append(f"  error: {_yaml_quoted_scalar(error)}")

    new_lines: list[str] = []
    skipping = False
    for line in fm_block.splitlines():
        if line.startswith("proposal_status:"):
            skipping = True
            continue
        if skipping:
            if line.startswith(" ") or line.startswith("\t") or not line.strip():
                continue
            skipping = False
        new_lines.append(line)
    new_lines.extend(proposal_lines)
    return f"{leading_ws}---\n" + "\n".join(new_lines) + body_and_close


def _synthesize_frontmatter_block(body: str, source_type: str, target_slug: str, entity_uri: str | None) -> str:
    """Prepend a minimal YAML frontmatter block to a body that has none.

    The body-mutation helpers (_rewrite_target_slug_in_body /
    _set_entity_uri_in_body / _set_source_type_in_body) no-op when there is no
    `---` block. When the ingestor LLM emits a body with no frontmatter at all,
    this guarantees the Source page still lands with its metadata. The block
    carries all three fields so the downstream setters become idempotent no-ops.
    `entity_uri=None` is written as the literal `null` (mirrors
    _set_entity_uri_in_body).
    """
    uri_val = "null" if entity_uri is None else entity_uri
    return f"---\nsource_type: {source_type}\ntarget_slug: {target_slug}\nentity_uri: {uri_val}\n---\n\n{body}"


# ---------------------------------------------------------------------------
# Strip unresolved wikilinks (Plan 06-14 / UAT G4)
# ---------------------------------------------------------------------------

# Matches [[…]] wikilinks. The captured group is the target; rejects newlines
# and bracket characters inside the target so nested or malformed brackets
# don't match accidentally.
_WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")

# Slice 4: anchor for the matched entity's durable forward-link. Inserted under
# the body's `## Touches` section (created if absent). Idempotent.
_TOUCHES_HEADING_RE = re.compile(r"^## Touches[ \t]*\n", re.MULTILINE)


def _ensure_entity_touch_link(text: str, stem: str) -> str:
    """Guarantee a `[[entities/<stem>]]` wikilink is present in the body.

    This is the durable forward-anchor the scanner reads to derive the entity's
    `## Referenced in wiki` backlink, so it must survive `_resolve_wikilinks`
    stripping — call this LAST, after wikilink resolution. Idempotent: inserts
    a bullet under an existing `## Touches` heading, else appends the section.
    """
    link = vault_wikilink(f"entities/{stem}")
    if link in text:
        return text
    m = _TOUCHES_HEADING_RE.search(text)
    if m is not None:
        insert_at = m.end()
        return text[:insert_at] + f"- {link}\n" + text[insert_at:]
    sep = "" if text.endswith("\n") else "\n"
    return f"{text}{sep}\n## Touches\n- {link}\n"


def _resolve_wikilinks(text: str, wiki: Path) -> tuple[str, list[str]]:
    """Strip wikilinks that do not resolve to an existing vault page.

    For each `[[target]]` in `text`:
      - If `<wiki>/<target>.md` exists OR any `<wiki>/**/<basename>.md`
        exists where `basename` is the last path segment of `target`,
        keep the wikilink verbatim.
      - Otherwise, replace `[[target]]` with the bare label (the
        target string itself, no brackets, no `.md`).

    Wikilinks inside fenced code blocks (``` … ```) are NOT modified —
    this protects example snippets in summaries from being eaten.

    Returns (rewritten_text, list_of_stripped_targets).

    Args:
      text:  the LLM body (after frontmatter has been written/rewritten).
      wiki:  vault root.
    """
    # Fast path (WR-05): if there are no wikilinks at all, skip the O(vault_size)
    # rglob. This is the common case — the ingestor LLM does not always emit
    # cross-references, and a vault walk per source page adds non-trivial
    # wallclock cost to the cost-frontier eval harness on large vaults.
    if "[[" not in text:
        return text, []

    # Build the set of known page basenames (and known relative paths).
    # rglob is O(vault_size) — acceptable: vaults are <10k files.
    known_relpaths: set[str] = set()
    known_basenames: set[str] = set()
    if wiki.exists():
        for p in wiki.rglob("*.md"):
            rel = p.relative_to(wiki).as_posix()
            # Strip the .md suffix
            known_relpaths.add(rel[:-3])
            known_basenames.add(p.stem)

    stripped: list[str] = []

    # Walk the text line-by-line so we can track fence state.
    in_fence = False
    out_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        # Toggle fence state on any line that starts with ```
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue

        def _sub(m: re.Match[str]) -> str:
            target = m.group(1).strip()
            # Try exact relpath match first
            if target in known_relpaths:
                return m.group(0)
            # Then basename match (Obsidian-style fallback: [[concepts/foo]]
            # resolves if foo.md exists anywhere)
            basename = target.rsplit("/", 1)[-1]
            if basename in known_basenames:
                return m.group(0)
            stripped.append(target)
            return target

        out_lines.append(_WIKILINK_RE.sub(_sub, line))

    return "".join(out_lines), stripped


# ---------------------------------------------------------------------------
# Parse ingestor LLM response
# ---------------------------------------------------------------------------


def _parse_ingestor_response(text: str) -> tuple[dict, str]:
    """Split LLM response into (frontmatter_dict, body_str).

    The LLM is instructed (prompts/ingestor.py:_NO_CODE_FENCE) to begin its
    response with `---`. As defense-in-depth, this parser also strips a
    leading ```yaml or ``` open-fence and the matching trailing ``` before
    looking for the `---` delimiter, so ING-001 passes even if the LLM
    wraps the YAML block in a markdown code fence.

    After fence-strip, behavior is unchanged: returns ({}, body_str) when
    the text does not start with `---` or has no closing `---`, otherwise
    parses the YAML block with yaml.safe_load (primary) and falls back to
    the hand-rolled scalar/list parser if safe_load raises YAMLError or
    returns a non-dict value (e.g. an LLM quirk like an unquoted ':' in a
    value field).
    """
    original_text = text
    text = text.strip()

    # Defense-in-depth: ingestor LLM may wrap the frontmatter in a markdown
    # code fence (```yaml ... ``` or ``` ... ```). The system prompt forbids
    # this (prompts/ingestor.py:_NO_CODE_FENCE), but we strip defensively so
    # ING-001 (startswith '---') passes even on prompt-rule violations.
    if text.startswith("```"):
        # Strip opening fence line (```yaml or just ```)
        nl = text.find("\n")
        if nl == -1:
            return {}, original_text
        text = text[nl + 1 :].lstrip("\n")
        # Strip the matching closing fence. The LLM may place ``` either at
        # the very end of the response (fence wraps only the YAML+body) or
        # immediately after the closing --- (fence wraps only the YAML
        # block, body trails below). Find the LAST line that is exactly
        # ``` and remove just that line, preserving any body that follows.
        lines = text.split("\n")
        last_fence_idx = -1
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                last_fence_idx = i
                break
        if last_fence_idx != -1:
            text = "\n".join(lines[:last_fence_idx] + lines[last_fence_idx + 1 :])
        # Re-strip leading/trailing whitespace exposed by removing the fence
        text = text.strip()
        # If post-fence-strip content has no `---`, treat as no-frontmatter
        # and return the ORIGINAL text (do not silently swallow the fence).
        if not text.startswith("---"):
            return {}, original_text

    # Strip opening ---
    if not text.startswith("---"):
        return {}, text

    rest = text[3:].lstrip("\n")

    # Find closing ---
    closing_idx = rest.find("\n---")
    if closing_idx == -1:
        return {}, text

    yaml_block = rest[:closing_idx].strip()
    body = rest[closing_idx + 4 :].lstrip("\n")

    # D3 (spec §3.3): prefer yaml.safe_load. If it raises YAMLError or returns
    # a non-dict, fall back to the hand-rolled scalar/list parser below — it
    # tolerates LLM quirks safe_load rejects (e.g. an unquoted ':' in a value).
    try:
        loaded = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        loaded = None
    if isinstance(loaded, dict):
        return loaded, body

    # Fallback: hand-rolled scalar/list parser (kept verbatim).
    fm: dict = {}
    cur_key: str | None = None
    cur_list: list | None = None

    for raw in yaml_block.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if _LIST_ITEM_RE.match(line) and cur_list is not None:
            cur_list.append(line.lstrip().removeprefix("- ").strip())
            continue
        if cur_list is not None:
            fm[cur_key] = cur_list
            cur_key, cur_list = None, None
        if ":" not in line:
            continue  # skip unparseable lines gracefully
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            cur_key, cur_list = key, []
        elif val == "[]":
            fm[key] = []
        else:
            fm[key] = val

    if cur_list is not None:
        fm[cur_key] = cur_list

    return fm, body


# ---------------------------------------------------------------------------
# Build ingestor human message
# ---------------------------------------------------------------------------


def build_ingest_source_prompt(
    text: str,
    source_path: Path,
    source_type: str,
    vault_structure: list[str],
) -> str:
    """Return the human message for the ingestor LLM.

    text is truncated to PREVIEW_CHARS (1200 chars) to stay within model budget.
    """
    preview = text[:PREVIEW_CHARS]
    if len(text) > PREVIEW_CHARS:
        preview += "\n[TRUNCATED]"

    vault_summary = "\n".join(f"  - {d}" for d in vault_structure[:20]) if vault_structure else "  (empty vault)"

    return (
        f"Source file: {source_path}\n"
        f"Source type (path-guess hint): {source_type}\n"
        f"\nVault top-level categories:\n{vault_summary}\n"
        f"\n--- Source content ---\n{preview}\n--- End source ---\n"
        f"\nWrite a Source page for this document. It will be filed under "
        f"sources/. Provide a target_slug based on the content, and a "
        f"source_type from the closed enum (spec, article, pr, ticket, "
        f"transcript, example, doc, note) — classify it from the content and "
        f"default to note when unsure. To associate this source with a code "
        f"entity, reference it with a [[entities/...]] wikilink in the body — do "
        f"not create a package page."
    )


# ---------------------------------------------------------------------------
# Skill-branch helpers (Task 11) — plan parse, source body, synthesis fan-out
# ---------------------------------------------------------------------------

# Required keys a planner chunk-plan entry must carry to be usable.
_SKILL_PLAN_REQUIRED = ("title", "topic", "content")


def _parse_skill_plan(text: str) -> list[dict] | None:
    """Parse the planner response (a YAML list of chunk entries).

    Strips a leading ```yaml / ``` code fence defensively (same failure mode as
    the ingestor). Returns None when the text is empty, not valid YAML, not a
    list, or contains no usable entry (each usable entry has title/topic/content).
    """
    if not text or not text.strip():
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        nl = stripped.find("\n")
        if nl == -1:
            return None
        stripped = stripped[nl + 1 :]
        fence = stripped.rfind("```")
        if fence != -1:
            stripped = stripped[:fence]
        stripped = stripped.strip()
    try:
        loaded = yaml.safe_load(stripped)
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, list):
        return None
    entries = [e for e in loaded if isinstance(e, dict) and all(e.get(k) for k in _SKILL_PLAN_REQUIRED)]
    return entries or None


def _guidance_wikilink_target(rel_path: str) -> str:
    """Turn a workspace-relative guidance path into a wikilink target.

    `wiki/guidance/<topic>/<slug>.md` -> `guidance/<topic>/<slug>`.
    """
    t = rel_path
    if t.startswith("wiki/"):
        t = t[len("wiki/") :]
    if t.endswith(".md"):
        t = t[: -len(".md")]
    return t


def _compose_skill_source_body(
    title: str, written_rel_paths: list[str], excluded_files: list[str] | None = None
) -> str:
    """Build the Source page body for a skill ingest.

    Minimal frontmatter (title only — source_type/target_slug/entity_uri are
    stamped by the common tail) plus a `## Generates` section linking every
    guidance page the skill produced. Provenance: skill → guidance. When the
    skill directory had non-markdown files, an additive `## Excluded` section
    records them (directory-aware skill ingest, 2026-06-09).
    """
    lines = [f"- [[{_guidance_wikilink_target(p)}]]" for p in written_rel_paths]
    generates = "\n".join(lines) if lines else "_No guidance pages were generated._"
    body = (
        f"---\ntitle: {title}\n---\n\n"
        f"# {title}\n\n"
        f"## Summary\n"
        f"Agent skill ingested. Reusable guidance was synthesized into "
        f"{len(written_rel_paths)} guidance page(s) under `wiki/guidance/`.\n\n"
        f"## Generates\n{generates}\n"
    )
    if excluded_files:
        excl_lines = "\n".join(f"- `{p}`" for p in excluded_files)
        body += f"\n## Excluded\n{len(excluded_files)} non-markdown file(s) were not ingested:\n{excl_lines}\n"
    return body


def _build_skill_synth_human(entry: dict) -> str:
    """Human message for one synthesizer call: the chunk-plan entry as YAML."""
    return "Chunk plan entry:\n```yaml\n" + yaml.safe_dump(entry, sort_keys=False, allow_unicode=True) + "```\n"


async def _synthesize_guidance_pages(
    plan: list[dict],
    *,
    workspace_root: Path,
    project_ctx: str,
    model_override: str | None,
    today: str | None = None,
) -> list[str]:
    """Pass 2: synthesize + write one guidance page per plan entry.

    Fans out one skill_synthesizer call per entry via SubagentPool. Each result
    is parsed + validated against the guidance-io schema; valid pages are written
    to wiki/guidance/<topic>/<slug>.md (overwriting on re-ingest). Invalid or
    failed chunks are logged and skipped (best-effort — a bad chunk never fails
    the ingest). The on-disk path is derived from the planner entry's topic/slug
    (NOT the synthesizer's frontmatter), so the path is deterministic.

    The `updated:` frontmatter is post-stamped with `today` (default: real
    today) rather than trusted from the model, which otherwise hallucinates it.

    Returns workspace-relative paths of the pages written, in plan order.
    """
    stamp = today or date.today().isoformat()
    synth_cfg = load_role_config("skill_synthesizer")
    system = build_skill_synthesizer_system(project_context=project_ctx)

    async def synth_one(entry: dict) -> TaskResult:
        llm = make_llm("skill_synthesizer", model_override=model_override)
        resp = await llm.ainvoke([SystemMessage(system), HumanMessage(_build_skill_synth_human(entry))])
        content = resp.content if isinstance(resp.content, str) else ""
        return TaskResult(value=content, response=resp)

    pool = SubagentPool(trace_dir=graph_dir(workspace_root) / "traces")
    fan = await pool.run_all(
        items=list(plan),
        task=synth_one,
        role="skill_synthesizer",
        model_id=synth_cfg["model_id"],
        max_concurrency=int(synth_cfg.get("max_concurrency", 5)),
    )

    # Map entries to their synthesized text (only successes).
    by_id = {id(entry): page_text for entry, page_text in fan.successes}

    from guidance_io.writer import write_page as _write_guidance_page

    written: list[str] = []
    for entry in plan:  # preserve plan order, not fan-out completion order
        page_text = by_id.get(id(entry))
        if not page_text:
            continue
        res = _write_guidance_page(
            workspace_root,
            topic_raw=str(entry["topic"]),
            slug_raw=str(entry.get("slug") or entry["title"]),
            page_text=page_text,
            stamp=stamp,
        )
        if res.written_rel is None:
            logger.warning("skipping guidance page for %r: %s", entry.get("title"), res.skip_reason)
            continue
        written.append(res.written_rel)
    return written


def _build_skill_planner_human(text: str, source_path: Path) -> str:
    """Human message for the planner: the full skill text + its path."""
    return f"Skill file: {source_path}\n\n--- Skill content ---\n{text}\n--- End skill ---\n"


async def _run_skill_branch(
    *,
    text: str,
    title_guess: str,
    slug: str,
    source_path: Path,
    workspace_root: Path,
    wiki: Path,
    project_ctx: str,
    canonical_uri: str | None,
    entity_stem: str | None,
    model_override: str | None,
    bundle: SkillBundle | None = None,
) -> _IngestBranchResult | None:
    """Two-pass skill ingest. Returns None to signal fall-back to the default branch.

    Pass 1 (planner): one skill_planner call → a YAML chunk plan.
    Pass 2 (synthesizer): SubagentPool fan-out → written guidance pages.
    The Source page body lists the generated pages under `## Generates`.
    On planner failure / unparseable plan, returns None (caller falls back).
    """
    planner_cfg = load_role_config("skill_planner")
    llm = make_llm("skill_planner", model_override=model_override)
    resolved_model_id = model_override or planner_cfg["model_id"]
    trace_dir = graph_dir(wiki.parent) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"ingest_skill_{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"
    t0 = time.monotonic()
    try:
        resp = await llm.ainvoke(
            [
                SystemMessage(build_skill_planner_system(project_context=project_ctx)),
                HumanMessage(_build_skill_planner_human(text, source_path)),
            ]
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        write_trace_record(
            trace_file,
            role="skill_planner",
            model_id=resolved_model_id,
            item=str(source_path),
            status="error",
            latency_ms=latency_ms,
            response=None,
            error=str(exc),
        )
        logger.warning("skill planner call failed; falling back to default ingest branch", exc_info=True)
        return None
    latency_ms = int((time.monotonic() - t0) * 1000)
    write_trace_record(
        trace_file,
        role="skill_planner",
        model_id=resolved_model_id,
        item=str(source_path),
        status="success",
        latency_ms=latency_ms,
        response=resp,
    )

    plan_text = resp.content if isinstance(resp.content, str) else ""
    plan = _parse_skill_plan(plan_text)
    if plan is None:
        logger.warning("skill planner produced no usable chunk plan; falling back to default ingest branch")
        return None

    written = await _synthesize_guidance_pages(
        plan, workspace_root=workspace_root, project_ctx=project_ctx, model_override=model_override
    )

    excluded_files = bundle.excluded_files if bundle is not None else []
    if excluded_files:
        logger.warning(
            "skill ingest excluded %d non-markdown file(s): %s",
            len(excluded_files),
            excluded_files,
        )
    if bundle is not None and bundle.scripts_dominant:
        logger.warning(
            "skill directory %s looks like a workflow skill (scripts/non-markdown dominant); "
            "guidance ingestion may be a poor fit — proceeding anyway",
            bundle.skill_dir,
        )

    page_body = _compose_skill_source_body(title_guess, written, excluded_files=excluded_files)
    return _IngestBranchResult(
        page_body=page_body,
        target_slug=slug,
        source_type="skill",
        entity_uri=canonical_uri,
        entity_stem=entity_stem,
        frontmatter_parsed=True,
        run_suggest=False,  # guidance written directly — nothing to propose
        guidance_pages_written=written,
    )


async def _run_common_tail(
    branch: _IngestBranchResult,
    *,
    wiki: Path,
    conn,
    source_path: Path,
    source_text: str,
    title_guess: str,
    archive_unit: Path | None = None,
) -> IngestResult:
    """Shared finalize path for every ingest branch.

    Writes the source page (stamping source_type/target_slug/entity_uri),
    resolves wikilinks, ensures the entity forward-link, optionally runs the
    suggest phase (gated by branch.run_suggest), updates the index, and logs.
    """
    # Route + write the source page (D1: always under sources/).
    target_path = _route_target_path(wiki, "source", branch.target_slug)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_slug = target_path.stem

    body = branch.page_body
    # D3 synthesize-frontmatter rule (only when the branch produced no frontmatter).
    if not branch.frontmatter_parsed and not body.lstrip().startswith("---"):
        body = _synthesize_frontmatter_block(body, branch.source_type, canonical_slug, branch.entity_uri)

    body = _rewrite_target_slug_in_body(body, canonical_slug)
    body = _set_entity_uri_in_body(body, branch.entity_uri)
    body = _set_source_type_in_body(body, branch.source_type)
    target_path.write_text(body, encoding="utf-8")

    resolved_output, stripped_wikilinks = _resolve_wikilinks(body, wiki)
    current_output = resolved_output if stripped_wikilinks else body
    if stripped_wikilinks:
        target_path.write_text(resolved_output, encoding="utf-8")

    if branch.entity_stem:
        linked_output = _ensure_entity_touch_link(current_output, branch.entity_stem)
        if linked_output != current_output:
            target_path.write_text(linked_output, encoding="utf-8")

    # Suggest phase (gated). Best-effort: a failure never fails the ingest.
    if branch.run_suggest:
        try:
            graph_tools = build_graph_tools(conn)
            suggested_pages, proposal_status = await run_suggest_phase(
                wiki=wiki,
                page_path=target_path,
                source_path=source_path,
                source_text=source_text,
                entity_uri=branch.entity_uri,
                entity_stem=branch.entity_stem,
                graph_tools=graph_tools,
                allowed_kinds=branch.allowed_kinds,
            )
        except Exception:
            logger.warning("suggest phase failed; continuing without suggestions", exc_info=True)
            suggested_pages = []
            proposal_status = {
                "reasoner": "failed",
                "extractor": "skipped",
                "proposals": 0,
                "error": "suggest phase failed",
            }
        suggestions_parsed = proposal_status["extractor"] == "ok"
        current_text = target_path.read_text(encoding="utf-8")
        stamped_text = _set_proposal_status_in_body(current_text, proposal_status)
        if stamped_text != current_text:
            target_path.write_text(stamped_text, encoding="utf-8")
    else:
        suggested_pages = []
        suggestions_parsed = True
        proposal_status = {"reasoner": "skipped", "extractor": "skipped", "proposals": 0, "error": None}

    update_index(wiki)

    # Archive the raw source (raw-source-archive design 2026-06-09). The raw
    # dir is derived from the workspace root (wiki.parent — matching
    # workspace_io.paths.raw_dir); sources outside raw/ map to None and are
    # never touched. A failed move logs a warning and leaves archived_to=None
    # — housekeeping never poisons a completed ingest.
    archived_to: str | None = None
    if archive_unit is not None:
        workspace_root = wiki.parent
        dest = archive_destination(raw_dir(workspace_root), archive_unit)
        if dest is not None:
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.is_dir():
                    shutil.rmtree(dest)
                elif dest.exists():
                    dest.unlink()
                shutil.move(str(archive_unit), str(dest))
                archived_to = dest.relative_to(workspace_root).as_posix()
            except Exception:
                logger.warning("failed to archive ingested source %s; leaving it in place", archive_unit, exc_info=True)
                archived_to = None

    # Stamp the archive location into the page frontmatter so the source page
    # records where the source now lives (raw-source-archive 2026-06-14). Only on
    # a successful move — a no-op move (outside raw/) or a failed move leaves the
    # page's source_path as written.
    if archived_to:
        current_page = target_path.read_text(encoding="utf-8")
        stamped_page = _set_source_path_in_body(current_page, archived_to)
        if stamped_page != current_page:
            target_path.write_text(stamped_page, encoding="utf-8")
        # Repoint any work item whose spec_doc/plan_doc pointed at the just-moved
        # source. Best-effort: housekeeping never poisons a completed ingest.
        try:
            doc_pointers.sweep(wiki.parent, dry_run=False)
        except Exception:
            logger.warning("failed to repoint work doc pointers after archive", exc_info=True)

    detail = f"source: {source_path}"
    if archived_to:
        detail += f"; archived: {archived_to}"
    if stripped_wikilinks:
        detail += f"; stripped {len(stripped_wikilinks)} unresolved wikilink(s): {stripped_wikilinks[:5]}"
    append_log(wiki, "ingest", title_guess, detail=detail, silent=True, raise_exception=True)

    page_path_rel = str(target_path.relative_to(wiki))
    return IngestResult(
        status="ok",
        page_path=page_path_rel,
        slug=branch.target_slug,
        title=title_guess,
        page_type="source",
        source_path=str(source_path),
        cross_refs_updated=1,
        entity_uri=branch.entity_uri,
        source_type=branch.source_type,
        stripped_wikilinks=stripped_wikilinks,
        frontmatter_parsed=branch.frontmatter_parsed,
        suggested_pages=suggested_pages,
        suggestions_parsed=suggestions_parsed,
        proposal_reasoner_status=str(proposal_status.get("reasoner", "skipped")),
        proposal_extractor_status=str(proposal_status.get("extractor", "skipped")),
        proposal_error=proposal_status.get("error"),
        guidance_pages_written=branch.guidance_pages_written,
        archived_to=archived_to,
    )


async def _run_default_branch(
    *,
    text: str,
    title_guess: str,
    slug: str,
    source_path: Path,
    path_guess: str,
    wiki: Path,
    project_ctx: str,
    canonical_uri: str | None,
    entity_stem: str | None,
    model_override: str | None,
) -> _IngestBranchResult:
    """The default ingest path: one ingestor LLM call → a Source page body."""
    vault_structure: list[str] = []
    try:
        vault_structure = sorted(d.name for d in wiki.iterdir() if d.is_dir() and not d.name.startswith("."))
    except OSError:
        pass

    prompt = build_ingest_source_prompt(text, source_path, path_guess, vault_structure)

    ingestor_cfg = load_role_config("ingestor")
    llm = make_llm("ingestor", model_override=model_override)
    resolved_model_id = model_override or ingestor_cfg["model_id"]
    trace_dir = graph_dir(wiki.parent) / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / f"ingest_{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"
    t0 = time.monotonic()
    try:
        resp = await llm.ainvoke(
            [SystemMessage(build_ingestor_system(project_context=project_ctx)), HumanMessage(prompt)]
        )
    except Exception as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        write_trace_record(
            trace_file,
            role="ingestor",
            model_id=resolved_model_id,
            item=str(source_path),
            status="error",
            latency_ms=latency_ms,
            response=None,
            error=str(exc),
        )
        raise
    latency_ms = int((time.monotonic() - t0) * 1000)
    write_trace_record(
        trace_file,
        role="ingestor",
        model_id=resolved_model_id,
        item=str(source_path),
        status="success",
        latency_ms=latency_ms,
        response=resp,
    )
    if not isinstance(resp.content, str):
        raise RuntimeError("ingestor returned non-text content")
    llm_output = resp.content

    fm, _body = _parse_ingestor_response(llm_output)
    frontmatter_parsed = bool(fm)
    if path_guess in RAW_FOLDER_TYPE_MAP.values():
        source_type = path_guess
    else:
        llm_value = str(fm.get("source_type", "")).strip().lower()
        source_type = llm_value if llm_value in SOURCE_TYPE_ENUM else path_guess

    target_slug = str(fm.get("target_slug", "")).strip()
    target_slug = slugify(target_slug) if target_slug else slug

    return _IngestBranchResult(
        page_body=llm_output,
        target_slug=target_slug,
        source_type=source_type,
        entity_uri=canonical_uri,
        entity_stem=entity_stem,
        frontmatter_parsed=frontmatter_parsed,
        run_suggest=True,
        allowed_kinds=None,
    )


# ---------------------------------------------------------------------------
# Public: run_ingest_source
# ---------------------------------------------------------------------------


async def run_ingest_source(
    source_path: Path,
    workspace_path: Path | None = None,
    model_override: str | None = None,
) -> IngestResult:
    """Ingest a source file into the wiki via the ingestor LLM.

    Shared setup resolves wiki/repo, extracts text, path-guesses source_type, and
    looks up the matching entity (Steps 1–3 below). It then DISPATCHES on the
    path-guess: a `raw/skill/` file runs `_run_skill_branch` (a two-pass
    planner→synthesizer flow that writes `wiki/guidance/<topic>/<slug>.md` pages
    directly and falls back to the default branch on planner failure); every other
    type runs `_run_default_branch`. Both produce an `_IngestBranchResult` that
    `_run_common_tail` finalizes (Steps 4–10).

    Steps:
        1. Resolve wiki and repo paths.
        2. Extract text and title from source file.
        3. Guess source_type from path location; look up the matching entity.
        4. Branch: default → single ingestor LLM call → Source body; skill →
           two-pass guidance synthesis. Both yield an _IngestBranchResult.
        5. Parse/stamp source_type + target_slug onto the page body.
        6. Write the body to sources/<target_slug>.md (routing is fixed — M3 Part A).
        7. Resolve wikilinks + ensure the entity forward-link.
        8. Suggest phase (default branch only; skill branch skips it).
        9. update_index(wiki) + append_log(wiki, "ingest", ...) — cross-ref + audit.
        10. Return IngestResult.

    Args:
        source_path:    Path to the source file to ingest.
        workspace_path: Wiki workspace root path (None -> resolved from env var or git heuristic).
        model_override: Bedrock model ID to use for the ingestor role instead of
                        the default from models.toml. Used by the sweep runner
                        for single-role-swap evaluation (D-06).

    Returns:
        IngestResult with status="ok" on success.
    """
    # Step 1: resolve wiki and repo
    wiki, repo = resolve_wiki_and_repo(workspace_path)
    project_ctx = render_project_context(wiki)
    if repo is None:
        repo = Path.cwd()

    # Phase 40 D-01: open read-only graph conn at command entry.
    # `wiki = <workspace>/wiki` per wiki_io._workspace.resolve_wiki_and_repo;
    # the workspace root is `workspace_path` when supplied, else `wiki.parent`.
    workspace_root = workspace_path if workspace_path is not None else wiki.parent
    db_path = graph_dir(workspace_root) / "code.db"
    try:
        conn = read_only_connect(db_path)
    except GraphNotInitializedError as exc:
        raise IngestorGraphNotInitializedError(workspace_root) from exc

    try:
        # Step 2: resolve a skill anchor (a directory containing SKILL.md, or a
        # SKILL.md file). When found, gather SKILL.md + all transitively-linked
        # companion markdown into one combined text and force the skill branch.
        # Otherwise fall through to today's single-file extract.
        anchor = resolve_skill_anchor(source_path)
        bundle: SkillBundle | None = None
        if anchor is not None:
            bundle = gather_skill_sources(anchor)
            text = bundle.combined_text
            title = bundle.title
        else:
            text, title = extract(source_path)
        title_guess = title or source_path.stem.replace("-", " ").title()
        slug = slugify(title_guess)

        # Step 3: path-guess the source_type. A resolved skill anchor forces
        # "skill" regardless of where the directory lives (works for skills
        # outside raw/skill/). Otherwise guess from the path: raw/<type>/
        # folders are authoritative (measured workspace-relative — raw/ is a
        # sibling of wiki/), in-repo docs fall to `doc`, loose files to `note`.
        if anchor is not None:
            path_guess = "skill"
        else:
            rel_to_workspace: Path | None = None
            rel_to_repo: Path | None = None
            try:
                rel_to_workspace = source_path.relative_to(workspace_root)
            except ValueError:
                pass
            try:
                rel_to_repo = source_path.relative_to(repo)
            except ValueError:
                pass
            path_guess = guess_source_type(rel_to_workspace, rel_to_repo)

        # Archive move-unit (raw-source-archive design 2026-06-09): a skill
        # anchor moves its directory wholesale — unless the anchor sits
        # directly in a kind folder (e.g. raw/skill/SKILL.md, parent path has
        # fewer than 2 parts relative to raw/), where moving the parent would
        # archive the entire kind folder; move just the file there. Every
        # other source moves itself. Units outside raw/ no-op downstream
        # (archive_destination returns None).
        archive_unit: Path = source_path
        if anchor is not None:
            archive_unit = anchor.parent
            try:
                rel = anchor.parent.relative_to(raw_dir(wiki.parent))
                if len(rel.parts) < 2:
                    archive_unit = anchor
            except ValueError:
                pass

        # URI-drift limitation (INGESTOR-03 / Phase 40):
        #
        # When a package is renamed in the source repo, the `entity_uri` recorded
        # in existing ingested pages becomes orphaned — it still points at the
        # old URI even though the graph now uses the new one. Phase 40 does NOT
        # automatically migrate orphaned URIs; this is tracked as a v1.8
        # reconciliation item.
        #
        # Surfaces: grep -r "entity_uri: pkg:" wiki/ will find all entity-backed
        # pages; a v1.8 tool may parse + reconcile against the live graph.
        canonical: tuple[str, str] | None = lookup_entity_by_path(conn, repo, source_path)
        if canonical is None:
            canonical = lookup_entity_by_name(conn, title_guess)
        canonical_uri: str | None = canonical[0] if canonical else None
        # Slice 4: the matched entity drives a [[entities/<stem>]] forward-link
        # whose target equals the scanner's on-disk filename. None when the
        # match has no entity page (cls:/fn:/method:) — no link is written.
        entity_stem: str | None = entity_filename_for_uri(canonical_uri, conn) if canonical_uri else None

        # Dispatch on the path-guessed source_type. raw/skill/ → the skill branch
        # (writes guidance pages directly); everything else → the default branch.
        branch: _IngestBranchResult | None = None
        if path_guess == "skill":
            branch = await _run_skill_branch(
                text=text,
                title_guess=title_guess,
                slug=slug,
                source_path=source_path,
                workspace_root=workspace_root,
                wiki=wiki,
                project_ctx=project_ctx,
                canonical_uri=canonical_uri,
                entity_stem=entity_stem,
                model_override=model_override,
                bundle=bundle,
            )
        if branch is None:
            branch = await _run_default_branch(
                text=text,
                title_guess=title_guess,
                slug=slug,
                source_path=source_path,
                path_guess=path_guess,
                wiki=wiki,
                project_ctx=project_ctx,
                canonical_uri=canonical_uri,
                entity_stem=entity_stem,
                model_override=model_override,
            )
        return await _run_common_tail(
            branch,
            wiki=wiki,
            conn=conn,
            source_path=source_path,
            source_text=text,
            title_guess=title_guess,
            archive_unit=archive_unit,
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass  # closing a read-only conn should not raise; defensive


# ---------------------------------------------------------------------------
# Public: run_ingest_work_item
# ---------------------------------------------------------------------------


async def run_ingest_work_item(
    frontmatter_text: str,
    body: str,
    slug: str | None = None,
    force: bool = False,
    workspace_path: Path | None = None,
) -> IngestResult:
    """File a structured work item into the wiki workspace.

    Steps:
        1. Resolve wiki path.
        2. Parse frontmatter YAML.
        3. Validate required fields — raise ValueError on failure.
        4. file_work_item() — writes page, calls update_index + append_log internally.
        5. Return IngestResult.

    Note: update_index and append_log are called by file_work_item() per plan-05-03.
    Cross-ref update is index-only (same scope as run_ingest_source).

    Args:
        frontmatter_text: YAML string with work item frontmatter.
        body:             Markdown body text.
        slug:             Optional page slug; derived from fm['title'] if omitted.
        force:            Overwrite existing page if True.
        workspace_path:   Wiki workspace root path (None -> env var / git heuristic).

    Returns:
        IngestResult with status="ok" on success.

    Raises:
        ValueError: If frontmatter fails schema validation (missing required fields).
        FileExistsError: If page already exists and force=False.
    """
    # Step 1: resolve wiki
    wiki, _ = resolve_wiki_and_repo(workspace_path)

    # Step 2: parse frontmatter
    fm = _parse_frontmatter(frontmatter_text)

    # Step 3: validate
    issues = _validate(fm)
    if issues:
        raise ValueError("schema validation failed: " + "; ".join(issues))

    # Step 4: file the work item (update_index + append_log called internally)
    result_dict = file_work_item(
        wiki,
        fm,
        body,
        slug=slug,
        force=force,
    )

    # Step 5: return IngestResult
    return IngestResult(
        status="ok",
        page_path=result_dict["page_path"],
        slug=result_dict["slug"],
        title=str(fm["title"]),
        page_type="work",
        source_path="",
        cross_refs_updated=1,
    )
