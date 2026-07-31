"""The shared prose-refresh contract: system prompt, work order, brief, parser, sanitizer.

Base-closure safe on purpose — BOTH executors read from here. The in-process
Bedrock agent (commands/prose_refresh.py) sends PROSE_REFRESHER_SYSTEM plus
build_prose_refresh_prompt() as chat messages, then parses the model's final
text with parse_prose_refresher_output(); the out-of-process Claude subagent
receives render_prose_refresh_brief() (the same two strings plus a
tool-substitution paragraph) and its result file is read back with
parse_prose_refresh_result_dict() (commands/scan.py::load_results_dir). Neither
side transcribes the ownership contract or the response schema, so they cannot
drift.
"""

from __future__ import annotations

import json
from typing import cast

from wiki_io.entity_writer import DETERMINISTIC_SECTIONS, is_todo_like_body

from graph_wiki_core.commands.scan_contract import ProseRefreshResult, ProseRefreshTask
from graph_wiki_core.text_utils import truncate_text

MAX_WIKI_PAGE_CHARS = 40_000

PROSE_REFRESHER_SYSTEM = """You maintain the prose of one Graph Wiki entity page.

You receive the current page, a scoped git diff of the entity's source since the
prose was last updated (or a first-fill marker), the current prose sections,
File-map rows, graph context, and bounded source/wiki/graph tools.

Ownership contract:
- Deterministic sections are OFF-LIMITS: `## Referenced in wiki`, `## File map`,
  `## Commands`, `## Agents`, `## Skills`, `## Scripts`, `## Hooks`,
  `## MCP servers`. Never return them.
- The current prose is ground truth. Preserve it unless the diff contradicts
  it — make minimal edits; respect hand-written prose as valuable input.
- On a first fill (no diff), write fresh prose for placeholder/TODO sections.

Use the tools to read source files under the entity root when the diff alone is
not enough to update the prose accurately.

Output: return exactly ONE JSON object, no surrounding prose, with keys:
- "sections": list of {"heading", "replacement_markdown"} — heading must match
  one of the provided prose H2 headings INCLUDING the leading "## " (e.g.
  "## Narrative"); replacement_markdown is body markdown only (no heading
  line). Omit sections that need no change.
- "file_map_descriptions": object mapping package-root file paths (exactly as
  given in the File-map rows) to one-line descriptions, for rows still `— TODO`.
- "dir_descriptions": object mapping directory path contexts ("" for the root
  section) to one-line directory descriptions, for unfilled directory sections.
- "overview": one-line package tree overview when the overview is unfilled,
  else null.
Do not return TODO placeholder text. Cite concrete `path:line` references when
useful.
"""

BRIEF_TOOL_INSTRUCTIONS = """\
## How to do this work

You are a read-only inspection subagent. Read source files under the entity
root shown below with `Read`, `Grep`, and `Glob` only. You have no live graph
tools — the `Graph context` block below is all the graph information you get.

When you are done, write the single JSON object described above to exactly
this path — that object and nothing else, no surrounding prose or fences:

    {results_path}

That JSON object must also include a "uri" key set to this entity's URI,
exactly as given below under "Entity URI":

    "uri": "{uri}"

Use `Write` for that one file only. Make no other writes: never edit the wiki
page, and never edit anything in the repo.
"""


def build_prose_refresh_prompt(task: ProseRefreshTask) -> str:
    """The work order: what changed, what prose exists now, what may be returned."""
    if task.trigger == "first_fill":
        diff_block = "(first fill — no diff; write fresh prose for placeholder sections)"
    elif task.diff is None:
        diff_block = (
            "(history rewritten — the recorded anchor commit is unknown to this repo; "
            "re-verify all prose against current source)"
        )
    else:
        diff_block = task.diff
    sections_block = "\n\n".join(f"{heading}\n{body or '(empty)'}" for heading, body in task.prose_sections.items())
    changed = "\n".join(f"- {p}" for p in task.changed_files)
    return (
        f"Entity URI: {task.uri}\n"
        f"Kind: {task.kind}\n"
        f"Name: {task.name}\n"
        f"Graph path: {task.graph_path}\n"
        f"Language: {task.language}\n"
        f"Entity root: {task.entity_root}\n"
        f"Trigger: {task.trigger}\n\n"
        "Source diff since the prose was last updated:\n"
        f"{diff_block}\n\n"
        "Changed files:\n"
        f"{changed or '(none)'}\n\n"
        "Current prose sections (heading + body; these are the ONLY headings you may return):\n"
        f"{sections_block or '(none)'}\n\n"
        "Current File-map rows:\n"
        f"{task.file_map_rows or '(none)'}\n\n"
        "Graph context:\n"
        f"{task.graph_context or '(none)'}\n\n"
        "Current page content:\n"
        f"{truncate_text(task.page_content, MAX_WIKI_PAGE_CHARS)}"
    )


def render_prose_refresh_brief(task: ProseRefreshTask, *, results_path: str) -> str:
    """One self-contained markdown brief for an out-of-process refresh subagent.

    Same system prompt + same work order the Bedrock path sends, with the
    tool-loop tools swapped for Claude Code's and an explicit write target.
    """
    return (
        f"{PROSE_REFRESHER_SYSTEM}\n"
        f"{BRIEF_TOOL_INSTRUCTIONS.format(results_path=results_path, uri=task.uri)}\n"
        "## Work order\n\n"
        f"{build_prose_refresh_prompt(task)}\n"
    )


def normalize_heading(raw: str) -> str:
    """`Narrative` / `##Narrative` / `## Narrative` -> `## Narrative`."""
    stripped = raw.strip()
    return stripped if stripped.startswith("## ") else f"## {stripped.removeprefix('##').strip()}"


def clean_description_map(value: object) -> dict[str, str]:
    """Whitespace-collapse a description dict, dropping empty / TODO-like values."""
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for key, val in value.items():
        if not (isinstance(key, str) and isinstance(val, str)):
            continue
        cleaned = " ".join(val.split()).strip()
        if cleaned and not is_todo_like_body(cleaned):
            out[key] = cleaned
    return out


def sanitize_prose_result(result: ProseRefreshResult, *, allowed_headings: list[str]) -> ProseRefreshResult:
    """Filter one result down to what may legally be injected into a page.

    Drops headings that are deterministic, outside the task's declared prose
    surface, duplicated, empty, or still TODO-like; cleans the description
    maps and the overview. Provider-agnostic: the Bedrock parser calls it and
    so does the apply half, so an out-of-process result gets the same filter.
    ``uri`` and ``error`` pass through untouched.
    """
    allowed = {normalize_heading(h) for h in allowed_headings}
    sections: dict[str, str] = {}
    for heading, body in result.sections.items():
        normalized = normalize_heading(heading)
        cleaned = body.strip() if isinstance(body, str) else ""
        if (
            normalized not in allowed
            or normalized in DETERMINISTIC_SECTIONS
            or normalized in sections
            or not cleaned
            or is_todo_like_body(cleaned)
        ):
            continue
        sections[normalized] = cleaned

    overview = result.overview.strip() if isinstance(result.overview, str) and result.overview.strip() else None
    if overview is not None and is_todo_like_body(overview):
        overview = None

    return ProseRefreshResult(
        uri=result.uri,
        sections=sections,
        file_map_descriptions=clean_description_map(result.file_map_descriptions),
        dir_descriptions=clean_description_map(result.dir_descriptions),
        overview=overview,
        error=result.error,
    )


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


def _sections_list_to_dict(raw_sections: list) -> dict[str, str]:
    """The response schema PROSE_REFRESHER_SYSTEM documents: a list of
    {"heading", "replacement_markdown"} objects. First occurrence of a
    (normalized) heading wins; malformed entries are dropped, not fatal.
    """
    sections: dict[str, str] = {}
    for section in raw_sections:
        if not isinstance(section, dict):
            continue
        heading = section.get("heading")
        body = section.get("replacement_markdown")
        if not isinstance(heading, str) or not isinstance(body, str):
            continue
        normalized = normalize_heading(heading)
        if normalized in sections:
            continue  # first occurrence wins
        sections[normalized] = body
    return sections


def parse_prose_refresher_output(raw: str, *, allowed_headings: list[str]) -> ProseRefreshResult:
    """Parse the agent's final JSON into a ProseRefreshResult (uri filled by caller).

    Structural failures return an empty result with ``error`` set. Per-section
    filtering is delegated to ``sanitize_prose_result`` — the same filter the
    apply half runs over out-of-process results.
    """
    try:
        payload = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError as exc:
        return ProseRefreshResult(uri="", error=f"prose_refresher returned invalid JSON: {exc.msg}")
    if not isinstance(payload, dict):
        return ProseRefreshResult(uri="", error="prose_refresher output must be a JSON object")

    raw_sections = payload.get("sections")
    if raw_sections is not None and not isinstance(raw_sections, list):
        return ProseRefreshResult(uri="", error='prose_refresher "sections" must be a list')

    sections = _sections_list_to_dict(raw_sections or [])

    overview_raw = payload.get("overview")
    return sanitize_prose_result(
        ProseRefreshResult(
            uri="",
            sections=sections,
            file_map_descriptions=cast(dict[str, str], payload.get("file_map_descriptions") or {}),
            dir_descriptions=cast(dict[str, str], payload.get("dir_descriptions") or {}),
            overview=overview_raw if isinstance(overview_raw, str) else None,
        ),
        allowed_headings=allowed_headings,
    )


def parse_prose_refresh_result_dict(d: dict) -> ProseRefreshResult:
    """Parse one ``results/*.json`` payload into a ProseRefreshResult, accepting
    EITHER shape apply may see:

    - The brief-documented response shape: list-valued ``"sections"`` of
      {"heading", "replacement_markdown"} objects, exactly as
      PROSE_REFRESHER_SYSTEM instructs an out-of-process subagent to write
      (optionally with a "uri" key, per BRIEF_TOOL_INSTRUCTIONS).
    - The internal ``ProseRefreshResult.to_dict()`` shape: dict-valued
      ``"sections"`` of {heading: body}, as the combined ``results.json``
      document and hand-written fixtures use.

    ``uri`` is optional here and left "" when absent — ``load_results_dir``
    resolves a missing uri from the page-stem filename. This does NOT
    sanitize: ``apply_scan_results`` runs ``sanitize_prose_result`` over every
    result regardless of source (using the task's declared ``prose_sections``
    as the allow-list), so sanitizing again here would just be redundant.
    """
    raw_sections = d.get("sections")
    if isinstance(raw_sections, list):
        sections = _sections_list_to_dict(raw_sections)
    elif isinstance(raw_sections, dict):
        sections = dict(raw_sections)
    else:
        sections = {}
    overview = d.get("overview")
    return ProseRefreshResult(
        uri=d.get("uri") or "",
        sections=sections,
        file_map_descriptions=dict(d.get("file_map_descriptions") or {}),
        dir_descriptions=dict(d.get("dir_descriptions") or {}),
        overview=overview if isinstance(overview, str) else None,
        error=d.get("error"),
    )
