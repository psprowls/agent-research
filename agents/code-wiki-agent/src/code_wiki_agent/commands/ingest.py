from __future__ import annotations

"""Ingest command — route a source file or work item into the wiki vault.

Public API:
    IngestResult            — dataclass: status, page_path, slug, title, page_type,
                               source_path, cross_refs_updated
    INGESTOR_SYSTEM         — system prompt for ingestor role (LLM produces YAML+body)
    build_ingest_source_prompt(text, source_path, source_type, vault_structure) -> str
    run_ingest_source(source_path, vault_path) -> IngestResult
    run_ingest_work_item(frontmatter_text, body, ...) -> IngestResult

Cross-ref update scope (CONTEXT.md deferred decision):
    Only update_index(wiki) is called after every ingest write. Deep back-ref link
    scanning across all vault pages is explicitly deferred to a future version —
    per CONTEXT.md §deferred: "ingest cross-ref deep linking — if too costly, scope
    down to index-only for v1". This is the scope-down path.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from model_adapter.loader import make_llm
from vault_io._workspace import resolve_wiki_and_repo
from vault_io.append_log import append_log
from vault_io.ingest_source import PREVIEW_CHARS, extract, guess_source_type, slugify
from vault_io.ingest_work_item import _parse_frontmatter, _validate, file_work_item
from vault_io.update_index import update_index

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt for the ingestor LLM role
# ---------------------------------------------------------------------------

INGESTOR_SYSTEM = """\
You are a code wiki ingestor. Your job is to analyze a source document and produce
a well-structured wiki page that integrates it into an existing knowledge base.

Output ONLY YAML frontmatter followed by a markdown body. Do not add commentary
outside of these sections.

Required frontmatter fields:
  - title: <descriptive title for the page>
  - category: <one of: package, concept, adr>
  - page_type: <one of: package, concept, adr>
  - target_slug: <URL-safe slug for the output filename, e.g. "auth-design">
  - summary: <one-line description of the source's main contribution>
  - tags: []  (list of relevant tags, or empty list)

Your output must include:
1. YAML frontmatter (between --- delimiters) with all required fields above.
2. A "## Summary" section (3-5 sentences) describing the source content.
3. Optional "## Key Concepts" or "## Decisions" section where appropriate.
4. Use [[wikilink]] style cross-references to related vault pages where relevant.

Keep total output under 1500 tokens.
Do NOT reproduce the full source text — synthesize and summarize.
Do NOT speculate beyond what the provided source content shows.
"""

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
        page_type:          Page category: package, concept, adr, or work.
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
# Parse ingestor LLM response
# ---------------------------------------------------------------------------


def _parse_ingestor_response(text: str) -> tuple[dict, str]:
    """Split LLM response into (frontmatter_dict, body_str).

    The LLM is instructed to produce YAML frontmatter between --- delimiters
    followed by a markdown body. We split on the closing --- and parse the YAML
    block using the same hand-rolled scalar parser as ingest_work_item (no yaml.load).

    Returns (frontmatter_dict, body_str) where frontmatter_dict may be empty
    if parsing fails (callers must handle the fallback case).
    """
    text = text.strip()

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
        if line.startswith("  - ") and cur_list is not None:
            cur_list.append(line[4:].strip())
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
        f"Choose the most appropriate page_type (package, concept, or adr) "
        f"and a target_slug based on the content."
    )


# ---------------------------------------------------------------------------
# Public: run_ingest_source
# ---------------------------------------------------------------------------


async def run_ingest_source(
    source_path: Path,
    vault_path: Path | None = None,
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
        source_path: Path to the source file to ingest.
        vault_path:  Wiki root path (None -> resolved from env var or git heuristic).

    Returns:
        IngestResult with status="ok" on success.
    """
    # Step 1: resolve wiki and repo
    wiki, repo = resolve_wiki_and_repo(vault_path)

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
    llm = make_llm("ingestor")
    resp = await llm.ainvoke([SystemMessage(INGESTOR_SYSTEM), HumanMessage(prompt)])
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
    target_path.write_text(llm_output, encoding="utf-8")

    # Step 8: update cross-refs (index-only scope — CONTEXT.md deferred)
    update_index(wiki)

    # Step 9: append log
    append_log(wiki, "ingest", title_guess, detail=f"source: {source_path}")

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
