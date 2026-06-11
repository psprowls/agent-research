"""DIR_DESCRIBER_SYSTEM prompt and builder for the directory-description fan-out (scan Step 10d).

Used to fill H3 section placeholders and the H2 overview in the File map section of entity pages.
Receives already-generated file descriptions grouped by directory; returns a JSON object mapping
package-root path contexts to one-line descriptions.
"""

from __future__ import annotations

import json
import re

DIR_DESCRIBER_SYSTEM = """You write one-line descriptions for the directory sections of a software package's file map. You are given the package name and the descriptions of files within each section that needs a description.

Your job: return a JSON object where each key is a directory section context string and each value is a one-line description of that directory's role.

Rules:
- Output ONLY a single JSON object. No prose, no markdown, no code fences — just the JSON.
- Keys MUST be section context strings taken verbatim from the "Sections needing a description" list. If the special key "_overview" is listed, write an overview of the entire package.
- Each value is a short description (aim for 3-10 words, at most ~12). Describe the directory's role/purpose, not its literal name. Examples: "core library source code", "pytest fixtures and test helpers", "CLI entry points and argument parsing".
- Base descriptions on the provided child file descriptions.
- Sections are listed deepest-first; write child sections before parent sections.
- The "_overview" key (if present) should describe the entire package in one short line.
- Keep descriptions free of newlines and unescaped double quotes so the JSON stays valid."""


def build_dir_describer_prompt(
    pkg: dict,
    dir_contexts: list[str],
    file_descs: dict[str, str],
    needs_overview: bool,
) -> tuple[str, str]:
    """Return (system, human) for the directory-description LLM (synthesizer role).

    Groups ``file_descs`` by parent directory context (string prefix match), lists sections
    deepest-first (most ``/`` first, then alphabetically). Appends ``_overview`` instruction
    when ``needs_overview=True``.

    Args:
        pkg:           Package metadata dict; needs ``name``.
        dir_contexts:  Package-root path contexts needing a description
                       (e.g. ``["", "src"]``).
        file_descs:    ``{package_root_path: description}`` for filled file rows.
        needs_overview: Whether to request the ``_overview`` key.
    """
    sorted_contexts = sorted(dir_contexts, key=lambda c: (-c.count("/"), c))
    sections_needed = list(sorted_contexts)
    if needs_overview:
        sections_needed.append("_overview")

    lines: list[str] = [
        f"Package name: {pkg.get('name', 'unknown')}",
        "",
        "Sections needing a description (use these exact strings as JSON keys):",
    ]
    for ctx in sections_needed:
        lines.append(f"- {ctx!r}")
    lines.append("")
    lines.append("Child file descriptions grouped by section (deepest first):")
    for ctx in sorted_contexts:
        if ctx:
            children = {k: v for k, v in file_descs.items() if k.startswith(ctx + "/")}
        else:
            children = {k: v for k, v in file_descs.items() if "/" not in k}
        lines.append(f"\nSection {ctx!r}:")
        if children:
            for path, desc in sorted(children.items()):
                lines.append(f"  - {path}: {desc}")
        else:
            lines.append("  (no child file descriptions available)")
    lines.append("")
    lines.append("Return the JSON object mapping each context string to its one-line description.")
    return DIR_DESCRIBER_SYSTEM, "\n".join(lines)


def parse_dir_describer_output(text: str) -> dict[str, str]:
    """Parse the directory-describer LLM response into a ``{context: description}`` dict.

    Tolerates leading/trailing ```` ```json ```` fences and surrounding prose.
    Returns ``{}`` on any parse failure or non-object payload. Non-string values are
    dropped; descriptions are stripped and collapsed to a single line.
    """
    if not text:
        return {}
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[-1]
        if candidate.rstrip().endswith("```"):
            candidate = candidate.rsplit("```", 1)[0]
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        obj = json.loads(candidate[start : end + 1])
    except (ValueError, TypeError):
        return {}
    if not isinstance(obj, dict):
        return {}
    result: dict[str, str] = {}
    for k, v in obj.items():
        if isinstance(k, str) and isinstance(v, str):
            cleaned = re.sub(r"\s+", " ", v).strip()
            if cleaned:
                result[k] = cleaned
    return result
