from __future__ import annotations

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

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import load_role_config, make_llm
from subagent_runtime.trace_io import write_trace_record
from wiki_io._workspace import resolve_wiki_and_repo
from wiki_io.append_log import append_log
from wiki_io.entity_lookup import (
    entity_filename_for_uri,
    lookup_entity_by_name,
    lookup_entity_by_path,
)
from wiki_io.ingest_source import PREVIEW_CHARS, extract, guess_source_type, slugify
from wiki_io.ingest_work_item import _parse_frontmatter, _validate, file_work_item
from wiki_io.update_index import update_index

from graph_io import exit_codes, queries  # noqa: F401  — exit_codes re-exposed for CLI callers
from graph_io.store import GraphNotInitializedError, read_only_connect
from workspace_io.paths import graph_dir

from graph_wiki_core.commands.suggest_pages import read_suggested_pages, run_suggest_phase
from graph_wiki_core.prompts.ingestor import build_ingestor_system
from graph_wiki_core.prompts.project_context import render_project_context

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
                            under sources/; see source_kind for the descriptive
                            kind). From run_ingest_work_item: always "work" (work
                            items file under <workspace>/work/ via file_work_item).
        source_path:        Original source file path (empty for work items).
        cross_refs_updated: Number of cross-reference updates performed (index-only scope).
        entity_uri:         Phase 40 (INGESTOR-01) canonical entity URI when the graph
                            matched the source by path or by name; None when no graph
                            match was found OR when the result was produced by
                            `run_ingest_work_item` (work items bypass entity lookup).
        source_kind:        Living Wiki M3: descriptive kind on Source pages
                            (run_ingest_source). "unknown" on a parse miss; None
                            for work items.
        stripped_wikilinks: Living Wiki M3: unresolved [[wikilinks]] removed from
                            the body (empty when none were stripped).
        frontmatter_parsed: Living Wiki M3: False when the ingestor frontmatter
                            failed to parse and we fell through to
                            source_kind: unknown.
        suggested_pages:    Living Wiki M3: proposed concept/adr/architecture pages
                            recorded on the Source page (each a dict with
                            kind/slug/mode/status/…). Empty for work items.
        suggestions_parsed: Living Wiki M3: False when the extractor LLM call
                            errored or its output did not parse (zero suggestions).
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
    source_kind: str | None = None  # descriptive kind on Source pages; "unknown" on parse miss; None for work items
    stripped_wikilinks: list[str] = field(default_factory=list)  # unresolved [[links]] stripped from the body
    frontmatter_parsed: bool = True  # False when we fell through to source_kind: unknown via a parse miss
    # Living Wiki M3 (suggestion step):
    suggested_pages: list[dict] = field(default_factory=list)  # proposals after this run's merge
    suggestions_parsed: bool = True  # False when the extractor call errored or its output didn't parse


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
# Living Wiki M3 Part A — source_kind frontmatter + synthesize-frontmatter rule
# ---------------------------------------------------------------------------


def _set_source_kind_in_body(text: str, source_kind: str) -> str:
    """Insert or replace the `source_kind:` line in the YAML frontmatter of `text`.

    Placement: inserted as the FIRST field of the frontmatter block. Idempotent
    — any existing `source_kind:` line is dropped first, so only one ever
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
        if line.lstrip().startswith("source_kind:"):
            continue  # drop existing line (idempotence)
        new_lines.append(line)
    new_lines.insert(0, f"source_kind: {source_kind}")
    new_fm = "\n".join(new_lines)
    return f"{leading_ws}---\n{new_fm}{body_and_close}"


def _synthesize_frontmatter_block(
    body: str, source_kind: str, target_slug: str, entity_uri: str | None
) -> str:
    """Prepend a minimal YAML frontmatter block to a body that has none.

    D3 synthesize-frontmatter rule (spec §3.3): the body-mutation helpers
    (_rewrite_target_slug_in_body / _set_entity_uri_in_body /
    _set_source_kind_in_body) no-op when there is no `---` block. When the
    ingestor LLM emits a body with no frontmatter at all, this guarantees the
    unknown-kind Source page still lands with its metadata. The block carries
    all three fields so the downstream setters become idempotent no-ops.
    `entity_uri=None` is written as the literal `null` (mirrors
    _set_entity_uri_in_body).
    """
    uri_val = "null" if entity_uri is None else entity_uri
    return (
        "---\n"
        f"source_kind: {source_kind}\n"
        f"target_slug: {target_slug}\n"
        f"entity_uri: {uri_val}\n"
        "---\n\n"
        f"{body}"
    )


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
    link = f"[[entities/{stem}]]"
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
    body = rest[closing_idx + 4:].lstrip("\n")

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
        f"Source type: {source_type}\n"
        f"\nVault top-level categories:\n{vault_summary}\n"
        f"\n--- Source content ---\n{preview}\n--- End source ---\n"
        f"\nWrite a Source page for this document. It will be filed under "
        f"sources/. Provide a target_slug based on the content, and optionally a "
        f"descriptive source_kind. To associate this source with a code entity, "
        f"reference it with a [[entities/...]] wikilink in the body — do not "
        f"create a package page."
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

    Steps:
        1. Resolve wiki and repo paths.
        2. Extract text and title from source file.
        3. Guess source_type from path location.
        4. Build ingestor prompt (vault structure + source preview).
        5. Single LLM call to ingestor role (no fan-out needed for single source).
        6. Parse YAML frontmatter from LLM response to read source_kind + target_slug.
        7. Write LLM output to sources/<target_slug>.md (routing is fixed — M3 Part A).
        8. update_index(wiki) — cross-ref update (index-only scope per CONTEXT.md deferred).
        9. append_log(wiki, "ingest", ...) — audit trail.
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
        # Step 2: extract text and title
        text, title = extract(source_path)
        title_guess = title or source_path.stem.replace("-", " ").title()
        slug = slugify(title_guess)

        # Step 3: guess source type
        rel_to_wiki: Path | None = None
        rel_to_repo: Path | None = None
        try:
            rel_to_wiki = source_path.relative_to(wiki)
        except ValueError:
            pass
        try:
            rel_to_repo = source_path.relative_to(repo)
        except ValueError:
            pass
        source_type = guess_source_type(rel_to_wiki, rel_to_repo)

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
        canonical: tuple[str, str] | None = lookup_entity_by_path(
            conn, repo, source_path
        )
        if canonical is None:
            canonical = lookup_entity_by_name(conn, title_guess)
        canonical_uri: str | None = canonical[0] if canonical else None
        # Slice 4: the matched entity drives a [[entities/<stem>]] forward-link
        # whose target equals the scanner's on-disk filename. None when the
        # match has no entity page (cls:/fn:/method:) — no link is written.
        entity_stem: str | None = (
            entity_filename_for_uri(canonical_uri, conn) if canonical_uri else None
        )

        # Step 4: vault structure for context
        vault_structure: list[str] = []
        try:
            vault_structure = sorted(
                d.name for d in wiki.iterdir() if d.is_dir() and not d.name.startswith(".")
            )
        except OSError:
            pass

        prompt = build_ingest_source_prompt(text, source_path, source_type, vault_structure)

        # Step 5: single ingestor LLM call
        ingestor_cfg = load_role_config("ingestor")
        llm = make_llm("ingestor", model_override=model_override)
        resolved_model_id = model_override or ingestor_cfg["model_id"]
        # TRACE-FU-01 (D-03): write per-call trace record so usage_metadata flows
        # to disk for every production ingest invocation, not just pool-driven calls.
        trace_dir = graph_dir(wiki.parent) / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_file = trace_dir / f"ingest_{int(time.time())}_{uuid.uuid4().hex[:8]}.jsonl"
        t0 = time.monotonic()
        try:
            resp = await llm.ainvoke([SystemMessage(build_ingestor_system(project_context=project_ctx)), HumanMessage(prompt)])
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
        llm_output: str = resp.content

        # Step 6: parse response to get source_kind and target_slug.
        # M3 Part A: classification is DECOUPLED from routing. Every ingested
        # doc becomes a Source page; `source_kind` is descriptive only and
        # defaults to "unknown" on a parse miss (empty fm).
        fm, _body = _parse_ingestor_response(llm_output)
        frontmatter_parsed = bool(fm)  # False ⟺ parse miss (spec §3.5)
        source_kind = str(fm.get("source_kind", "")).strip().lower() or "unknown"

        target_slug = str(fm.get("target_slug", "")).strip()
        # Sanitize slug: re-slugify whatever the LLM provided (T-05-05-02)
        target_slug = slugify(target_slug) if target_slug else slug

        # Step 7: write page. D1 — always route to sources/ (page_type fixed to
        # "source"; _route_target_path keeps the path-traversal safety check).
        target_path = _route_target_path(wiki, "source", target_slug)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_slug = target_path.stem

        # D3 synthesize-frontmatter rule: when the LLM emitted NO frontmatter at
        # all, the body-mutation helpers below would no-op — prepend a minimal
        # block so the unknown-kind Source page lands with its metadata.
        if not frontmatter_parsed and not llm_output.lstrip().startswith("---"):
            llm_output = _synthesize_frontmatter_block(
                llm_output, source_kind, canonical_slug, canonical_uri
            )

        # Reconcile target_slug in the body with the on-disk filename slug, write
        # entity_uri (null when no graph match), and stamp source_kind. All three
        # helpers are idempotent and preserve comments/order.
        llm_output = _rewrite_target_slug_in_body(llm_output, canonical_slug)
        llm_output = _set_entity_uri_in_body(llm_output, canonical_uri)
        llm_output = _set_source_kind_in_body(llm_output, source_kind)
        # Living Wiki M3: capture the page's prior suggested_pages (human
        # decisions) BEFORE the ingestor output overwrites the page, so the
        # suggest phase can preserve approved/rejected across re-ingest (§3.4).
        prior_suggested = (
            read_suggested_pages(target_path.read_text(encoding="utf-8"))
            if target_path.exists()
            else []
        )
        # Write the file first so it is part of the "known pages" set when
        # resolving self-references in the body (e.g. an ADR linking to
        # itself or a sibling created earlier in the same ingest).
        target_path.write_text(llm_output, encoding="utf-8")
        # Plan 06-14 / UAT G4: strip wikilinks the LLM fabricated for pages
        # that do not exist in the vault. Two writes is acceptable — vaults
        # are local-disk and writes are <1ms.
        resolved_output, stripped_wikilinks = _resolve_wikilinks(llm_output, wiki)
        current_output = resolved_output if stripped_wikilinks else llm_output
        if stripped_wikilinks:
            target_path.write_text(resolved_output, encoding="utf-8")
        # Slice 4: ensure the matched entity's forward-link is present. Runs
        # AFTER _resolve_wikilinks so it is never stripped (the entity page may
        # not exist on disk yet at ingest time — the scanner backfills it).
        if entity_stem:
            linked_output = _ensure_entity_touch_link(current_output, entity_stem)
            if linked_output != current_output:
                target_path.write_text(linked_output, encoding="utf-8")

        # Step 7.5 (Living Wiki M3): inline suggest phase — propose derived
        # concept/adr/architecture pages from the just-written Source page.
        # Best-effort: a failure here never fails the ingest (spec §3.1).
        try:
            suggested_pages, suggestions_parsed = await run_suggest_phase(
                wiki=wiki, page_path=target_path, prior_entries=prior_suggested
            )
        except Exception:
            logger.warning("suggest phase failed; continuing without suggestions", exc_info=True)
            suggested_pages, suggestions_parsed = [], False

        # Step 8: update cross-refs (index-only scope — CONTEXT.md deferred)
        update_index(wiki)

        # Step 9: append log (record stripped-wikilink count for hallucination audit)
        detail = f"source: {source_path}"
        if stripped_wikilinks:
            detail += (
                f"; stripped {len(stripped_wikilinks)} unresolved wikilink(s): "
                f"{stripped_wikilinks[:5]}"
            )
        append_log(wiki, "ingest", title_guess, detail=detail, silent=True, raise_exception=True)

        # Step 10: return result
        page_path_rel = str(target_path.relative_to(wiki))
        return IngestResult(
            status="ok",
            page_path=page_path_rel,
            slug=target_slug,
            title=title_guess,
            page_type="source",  # D1: run_ingest_source always files under sources/
            source_path=str(source_path),
            cross_refs_updated=1,
            entity_uri=canonical_uri,
            source_kind=source_kind,
            stripped_wikilinks=stripped_wikilinks,
            frontmatter_parsed=frontmatter_parsed,
            suggested_pages=suggested_pages,
            suggestions_parsed=suggestions_parsed,
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
