"""Project-context renderer for subagent system prompts.

Reads `wiki/CLAUDE.md` (or `AGENTS.md` as fallback) once at command entry and
emits a compact deterministic block covering the parsed layout containers,
the project's `## Style` rules, and its `## Log format` section.

Pure: no LLM calls, no network, no mutation. Mirrors the discipline of
`wiki_io.layout_io.read_layout` — returns the empty string if neither
schema file exists, so callers can pass the result through unchanged.

Used by `commands/scan.py`, `commands/lint.py`, and `commands/ingest.py`
(wiring lands in plan 10-06; this module is the runtime half of the
spike-001 solution).
"""

from __future__ import annotations

from pathlib import Path

from wiki_io.layout_io import read_layout

# CLAUDE.md takes priority; AGENTS.md is the fallback per CONTEXT.md §Wiring.
_CANDIDATES: tuple[str, ...] = ("CLAUDE.md", "AGENTS.md")


def render_project_context(wiki_path: Path) -> str:
    """Render a compact project-context block for subagent system prompts.

    Reads `wiki_path/CLAUDE.md` if it exists, else `wiki_path/AGENTS.md`.
    On the first hit, parses the embedded layout block via `read_layout` and
    composes a deterministic rendered block (~30 lines) covering:
      - `## Project layout (parsed from wiki/<filename>)` — one bullet per
        container, sorted alphabetically by `vault_dir`.
      - `## Project style (wiki/<filename> §Style)` — body of the `## Style`
        section if present, otherwise omitted.
      - `## Log format (wiki/<filename> §Log format)` — body of the
        `## Log format` section if present, otherwise omitted.

    Returns `""` if neither schema file exists. Never raises for missing
    files; lets `read_layout` exceptions propagate (currently it does not
    raise).
    """
    for name in _CANDIDATES:
        schema = wiki_path / name
        if schema.exists():
            layout = read_layout(schema)
            return _render(layout, schema)
    return ""


def _render(layout: dict | None, schema_path: Path) -> str:
    """Compose the three-section rendered block for one schema file."""
    filename = schema_path.name
    sections: list[str] = []

    # 1. Project layout — always rendered, even if the layout block is absent
    #    or empty (we still want the heading + a marker line so the consumer
    #    knows we looked).
    sections.append(_render_layout(layout, filename))

    # 2. Project style — heading-walk extraction; omitted if no ## Style.
    style_body = _extract_section(schema_path, "Style")
    if style_body:
        sections.append(
            f"## Project style (wiki/{filename} §Style)\n\n{style_body}"
        )

    # 3. Log format — same approach.
    log_body = _extract_section(schema_path, "Log format")
    if log_body:
        sections.append(
            f"## Log format (wiki/{filename} §Log format)\n\n{log_body}"
        )

    return "\n\n".join(sections).rstrip()


def _render_layout(layout: dict | None, filename: str) -> str:
    """Render the `## Project layout` section.

    Deterministic ordering: containers are sorted alphabetically by
    `vault_dir` so syrupy snapshots remain stable regardless of YAML
    key order.
    """
    header = f"## Project layout (parsed from wiki/{filename})"
    if not layout or not layout.get("containers"):
        return f"{header}\n\n- (no layout block detected)"

    containers = sorted(
        layout["containers"], key=lambda c: c.get("vault_dir") or ""
    )
    lines = [header, ""]
    for c in containers:
        vault_dir = c.get("vault_dir", "")
        classification = c.get("classification", "")
        if "children_count" in c:
            lines.append(
                f"- {vault_dir} → {classification} "
                f"({c['children_count']} children)"
            )
        else:
            lines.append(f"- {vault_dir} → {classification}")
    return "\n".join(lines)


def _extract_section(schema_path: Path, heading: str) -> str:
    """Return the body of the first `## <heading>` section in `schema_path`.

    Walks the file line-by-line. Body starts after the matching `## <heading>`
    line and continues until the next `## ` heading (at the actual document
    level, ignoring `## ` lines inside fenced code blocks) or end-of-file.
    Leading and trailing blank lines are stripped. Returns `""` if no
    matching section is found.

    Fenced code blocks (``` or ~~~) are tracked so that, e.g., a log-format
    code sample like `## [YYYY-MM-DD] <op> | <title>` does not falsely
    terminate the section.
    """
    text = schema_path.read_text(encoding="utf-8")
    target = f"## {heading}"
    body: list[str] = []
    in_section = False
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if in_section:
            # Track fenced code blocks so headings inside them don't terminate.
            if not in_fence and (
                stripped.startswith("```") or stripped.startswith("~~~")
            ):
                in_fence = True
            elif in_fence and (
                stripped.startswith("```") or stripped.startswith("~~~")
            ):
                in_fence = False
            elif not in_fence and line.startswith("## "):
                break
            body.append(line)
        elif line.strip() == target:
            in_section = True
    # Strip leading + trailing blank lines without touching internal spacing.
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body)
