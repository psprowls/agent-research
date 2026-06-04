"""Living Wiki M2e: DRIFT_JUDGE prompt + verdict parser.

The drift judge receives one human-owned section of an entity page plus the
page's freshly-regenerated `## Narrative` (the scanner's current, code-derived
understanding) and decides whether the section's curated prose has gone stale
relative to that narrative. It judges against the narrative ONLY — it never
re-reads source (code-diff grounding is deferred to M4). Output is a tiny JSON
verdict; `parse_drift_verdict` fails safe (not-stale) on any unparseable reply,
so a flaky model can never inject a false flag.
"""

from __future__ import annotations

import json
import re

DRIFT_JUDGE_SYSTEM = """You judge whether a curated, human-written section of a wiki page has gone STALE relative to that page's machine-generated narrative.

You are given:
- the section's heading and body (human-authored prose), and
- the page's current `## Narrative` (regenerated from the code as it exists now),
- and sometimes a `## File map` listing for extra context.

The narrative reflects what the code does NOW. Decide whether the section's prose now CONTRADICTS or materially misdescribes what the narrative says. Examples of stale: the section claims synchronous processing but the narrative describes async fan-out; the section names a responsibility the narrative says moved elsewhere.

Do NOT flag a section merely because it covers different ground (e.g. a `## Public API` listing endpoints the narrative does not mention is fine), is shorter, or is stylistically different. Only flag a genuine contradiction or material drift.

Output ONLY a single JSON object, no prose and no code fences:
{"stale": true|false, "reason": "<one short line; empty string when not stale>"}"""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_drift_judge_prompt(
    heading: str,
    section_body: str,
    narrative: str,
    file_map: str | None,
) -> tuple[str, str]:
    """Return ``(system, human)`` messages for one (section, narrative) judgement."""
    lines = [
        f"Section heading: {heading.strip()}",
        "",
        "Section body (human-authored prose):",
        section_body.strip(),
        "",
        "Current narrative (regenerated from the code as it exists now):",
        narrative.strip(),
    ]
    if file_map:
        lines += ["", "File map (for context):", file_map.strip()[:1500]]
    lines += ["", "Is the section body stale relative to the narrative? Reply with the JSON verdict."]
    return DRIFT_JUDGE_SYSTEM, "\n".join(lines)


def parse_drift_verdict(text: str) -> dict:
    """Parse a `{stale, reason}` verdict from the model reply. Fails SAFE: any
    unparseable / malformed reply yields ``{"stale": False, ...}`` so noise never
    becomes a false flag."""
    raw = _FENCE_RE.sub("", (text or "").strip())
    match = _OBJ_RE.search(raw)
    if match is None:
        return {"stale": False, "reason": "unparseable judge response"}
    try:
        obj = json.loads(match.group(0))
    except (ValueError, TypeError):
        return {"stale": False, "reason": "unparseable judge response"}
    stale = bool(obj.get("stale", False))
    reason = str(obj.get("reason", "")) if stale else ""
    return {"stale": stale, "reason": reason}
