"""Stage-2 ranking prompt for `gw guidance suggest` + fail-safe parser.

One structured call ranks the recall candidates against the task. The parser
validates returned slugs against the candidate set (drops hallucinations) and
normalizes relevance to high|medium|low.
"""

from __future__ import annotations

import re

import yaml

GUIDANCE_ORCHESTRATOR_SYSTEM = """You rank prescriptive guidance pages by how \
relevant each is to a coding task the developer is about to do.

You are given the task message, a short summary of the files in play, and a \
slate of candidate guidance pages (each with its title/topic/summary, the \
prose trigger 'applies_when', and which deterministic signals already fired).

Rules:
- Rank ONLY the provided candidates. Never invent a slug.
- Drop candidates that are not actually relevant — a short, precise list beats a long one.
- relevance is one of: high, medium, low.

Output ONLY a YAML list, no prose and no code fences:
- slug: <candidate slug>
  relevance: high|medium|low
  reason: <one short line>"""

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")
_RELEVANCE = {"high", "medium", "low"}


def build_guidance_orchestrator_prompt(
    message: str,
    path_summaries: list[str],
    candidates: list[dict],
) -> tuple[str, str]:
    """Return ``(system, human)`` for the single ranking call."""
    lines = [f"Task: {message.strip()}", ""]
    if path_summaries:
        lines.append("Files in play:")
        lines.extend(f"  - {s}" for s in path_summaries)
        lines.append("")
    lines.append("Candidates:")
    for c in candidates:
        lines.append(f"  - slug: {c['slug']}")
        lines.append(f"    topic: {c.get('topic', '')}")
        lines.append(f"    summary: {c.get('summary', '')}")
        lines.append(f"    applies_when: {c.get('applies_when', '')}")
        lines.append(f"    signals_fired: {', '.join(c.get('signals_fired', []))}")
    lines += ["", "Rank the relevant candidates. Output the YAML list only."]
    return GUIDANCE_ORCHESTRATOR_SYSTEM, "\n".join(lines)


def parse_orchestrator_response(text: str, candidate_slugs: set[str]) -> list[dict]:
    """Parse the ranked YAML list; keep only known slugs. Fail-safe to []."""
    raw = _FENCE_RE.sub("", (text or "").strip())
    try:
        obj = yaml.safe_load(raw)
    except yaml.YAMLError:
        return []
    if not isinstance(obj, list):
        return []
    ranked: list[dict] = []
    seen: set[str] = set()
    for item in obj:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug", ""))
        if slug not in candidate_slugs or slug in seen:
            continue
        seen.add(slug)
        relevance = str(item.get("relevance", "")).strip().lower()
        if relevance not in _RELEVANCE:
            relevance = "low"
        ranked.append({"slug": slug, "relevance": relevance, "reason": str(item.get("reason", "")).strip()})
    return ranked
