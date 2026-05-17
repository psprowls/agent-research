from __future__ import annotations

"""Ingest command — route a source file or work item into the wiki vault.

Public API:
    IngestResult            — dataclass: status, page_path, slug, title, page_type,
                               source_path, cross_refs_updated
    build_ingest_source_prompt(text, source_path, source_type, vault_structure) -> str
    run_ingest_source(source_path, vault_path) -> IngestResult
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
from dataclasses import dataclass
from pathlib import Path

from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import load_role_config, make_llm
from vault_io._workspace import resolve_wiki_and_repo
from vault_io.append_log import append_log
from vault_io.ingest_source import PREVIEW_CHARS, extract, guess_source_type, slugify
from vault_io.ingest_work_item import _parse_frontmatter, _validate, file_work_item
from vault_io.update_index import update_index

from code_wiki_agent.prompts.ingestor import build_ingestor_system
from code_wiki_agent.prompts.project_context import render_project_context

logger = logging.getLogger(__name__)

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
        page_type:          Page category. From run_ingest_source: source,
                            package, concept, or adr (set by the ingestor LLM
                            and validated against _PAGE_TYPE_DIRS). From
                            run_ingest_work_item: always "work" (work items
                            bypass _route_target_path and file under
                            <workspace>/work/ via file_work_item).
        source_path:        Original source file path (empty for work items).
        cross_refs_updated: Number of cross-reference updates performed (index-only scope).
    """

    status: str
    page_path: str
    slug: str
    title: str
    page_type: str
    source_path: str
    cross_refs_updated: int


# ---------------------------------------------------------------------------
# Route page_type -> target directory
# ---------------------------------------------------------------------------

_PAGE_TYPE_DIRS: dict[str, str] = {
    "package": "packages",
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
    # Confirm path stays inside wiki (defense in depth)
    resolved = target.resolve()
    wiki_resolved = wiki.resolve()
    if not str(resolved).startswith(str(wiki_resolved) + "/"):
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
# Strip unresolved wikilinks (Plan 06-14 / UAT G4)
# ---------------------------------------------------------------------------

# Matches [[…]] wikilinks. The captured group is the target; rejects newlines
# and bracket characters inside the target so nested or malformed brackets
# don't match accidentally.
_WIKILINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")


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
    parses the YAML block with the same hand-rolled scalar/list parser
    used by ingest_work_item (no yaml.load).
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

    # Parse YAML block (simple key: value + list items)
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
        f"\nWrite a vault wiki page for this source. "
        f"Choose the most appropriate page_type (source, package, concept, or adr) "
        f"and a target_slug based on the content."
    )


# ---------------------------------------------------------------------------
# Public: run_ingest_source
# ---------------------------------------------------------------------------


async def run_ingest_source(
    source_path: Path,
    vault_path: Path | None = None,
    model_override: str | None = None,
) -> IngestResult:
    """Ingest a source file into the wiki via the ingestor LLM.

    Steps:
        1. Resolve wiki and repo paths.
        2. Extract text and title from source file.
        3. Guess source_type from path location.
        4. Build ingestor prompt (vault structure + source preview).
        5. Single LLM call to ingestor role (no fan-out needed for single source).
        6. Parse YAML frontmatter from LLM response to determine page_type + target_slug.
        7. Write LLM output to target_path based on page_type.
        8. update_index(wiki) — cross-ref update (index-only scope per CONTEXT.md deferred).
        9. append_log(wiki, "ingest", ...) — audit trail.
        10. Return IngestResult.

    Args:
        source_path:    Path to the source file to ingest.
        vault_path:     Wiki root path (None -> resolved from env var or git heuristic).
        model_override: Bedrock model ID to use for the ingestor role instead of
                        the default from models.toml. Used by the sweep runner
                        for single-role-swap evaluation (D-06).

    Returns:
        IngestResult with status="ok" on success.
    """
    # Step 1: resolve wiki and repo
    wiki, repo = resolve_wiki_and_repo(vault_path)
    project_ctx = render_project_context(wiki)
    if repo is None:
        repo = Path.cwd()

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
    if model_override is not None:
        llm = ChatBedrockConverse(
            model_id=model_override,
            region_name=ingestor_cfg["region"],
            max_tokens=ingestor_cfg["max_tokens"],
        )
    else:
        llm = make_llm("ingestor")
    resp = await llm.ainvoke([SystemMessage(build_ingestor_system(project_context=project_ctx)), HumanMessage(prompt)])
    llm_output: str = resp.content

    # Step 6: parse response to get page_type and target_slug
    fm, _body = _parse_ingestor_response(llm_output)
    page_type = str(fm.get("page_type", "concept")).lower()
    if page_type not in _PAGE_TYPE_DIRS:
        page_type = "concept"

    target_slug = str(fm.get("target_slug", "")).strip()
    # Sanitize slug: re-slugify whatever the LLM provided (T-05-05-02)
    target_slug = slugify(target_slug) if target_slug else slug

    # Step 7: write page
    target_path = _route_target_path(wiki, page_type, target_slug)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    # Reconcile target_slug in the body with the on-disk filename slug.
    # _route_target_path uses slugify(target_slug); if that differs from
    # what the LLM wrote, rewrite the body's `target_slug:` line to match.
    # Also handles the case where the LLM omitted target_slug entirely
    # (we fell back to slugify(title)) — write that fallback into the body.
    canonical_slug = target_path.stem
    llm_output = _rewrite_target_slug_in_body(llm_output, canonical_slug)
    # Write the file first so it is part of the "known pages" set when
    # resolving self-references in the body (e.g. an ADR linking to
    # itself or a sibling created earlier in the same ingest).
    target_path.write_text(llm_output, encoding="utf-8")
    # Plan 06-14 / UAT G4: strip wikilinks the LLM fabricated for pages
    # that do not exist in the vault. Two writes is acceptable — vaults
    # are local-disk and writes are <1ms.
    resolved_output, stripped_wikilinks = _resolve_wikilinks(llm_output, wiki)
    if stripped_wikilinks:
        target_path.write_text(resolved_output, encoding="utf-8")

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
        page_type=page_type,
        source_path=str(source_path),
        cross_refs_updated=1,
    )


# ---------------------------------------------------------------------------
# Public: run_ingest_work_item
# ---------------------------------------------------------------------------


async def run_ingest_work_item(
    frontmatter_text: str,
    body: str,
    slug: str | None = None,
    force: bool = False,
    pkg_dir: Path | None = None,
    pkg_title: str | None = None,
    vault_path: Path | None = None,
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
        pkg_dir:          Optional vault package directory Path for work sub-page linking.
        pkg_title:        Display title for the package sub-page template.
        vault_path:       Wiki root path (None -> env var / git heuristic).

    Returns:
        IngestResult with status="ok" on success.

    Raises:
        ValueError: If frontmatter fails schema validation (missing required fields).
        FileExistsError: If page already exists and force=False.
    """
    # Step 1: resolve wiki
    wiki, _ = resolve_wiki_and_repo(vault_path)

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
        pkg_dir=pkg_dir,
        pkg_title=pkg_title,
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
