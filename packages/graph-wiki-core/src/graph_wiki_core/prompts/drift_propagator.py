"""Living Wiki M4: DRIFT_PROPAGATOR prompt + verdict parser (cross-page judge).

The propagator compares a whole CURATED page (concept / ADR) against the
CURRENT state of the changed entities that backlink it (cross-page). It is
kind-aware: concept pages (including folded `kind: architecture` pages that
live under concepts/) are stale when their described behaviour no longer
matches the entity; ADR pages are annotate-only (stale only when
Status/Consequences/Supersedes are overtaken by code reality — never a
rewrite of decision history).

Output is a small JSON verdict with one finding per triggering entity, so each
ledger origin gets precise attribution. ``parse_drift_propagator_verdict``
fails SAFE (not-stale) on any unparseable / malformed reply.
"""

from __future__ import annotations

import json
import re

_KIND_RUBRIC = {
    "concept": (
        "This is a CONCEPT page. It is stale when the behaviour or design it "
        "describes no longer matches what the entity narratives now say."
    ),
    "adr": (
        "This is an ADR (architecture decision record). Treat it as "
        "ANNOTATE-ONLY: flag it stale ONLY when the decision's Status, "
        "Consequences, or Supersedes have been overtaken by code reality (for "
        "example the decision was reversed or superseded by what the narrative "
        "now describes). Do NOT flag it merely because prose describing the "
        "original decision could be reworded, and never propose rewriting "
        "decision history."
    ),
}

DRIFT_PROPAGATOR_SYSTEM = """You judge whether a curated wiki page has gone STALE relative to the CURRENT state of the code entities it references.

You are given:
- the curated page's kind and full body, and
- for each changed entity the page references: that entity's current `## Narrative` (regenerated from the code as it exists now) and the list of files that changed since the page's claims were last checked.

Decide whether the page's claims now CONTRADICT or materially misdescribe what the narratives say. Do NOT flag a page for covering different ground, being shorter, or stylistic differences — only a genuine contradiction or material drift.

Output ONLY a single JSON object, no prose and no code fences:
{"stale": true|false,
 "findings": [{"entity_stem": "<one of the entity stems given to you>",
               "stale_claim": "<the page claim that is now wrong>",
               "rationale": "<one short line: why the narrative overtakes it>"}]}
Emit exactly one findings entry per entity that drives the staleness. When not stale, return {"stale": false, "findings": []}."""

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)
_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_drift_propagator_prompt(
    kind: str,
    page_title: str,
    page_body: str,
    entities: list[tuple[str, str, list[str]]],
) -> tuple[str, str]:
    """Return ``(system, human)`` for one curated page + its triggering entities.

    ``entities`` is a list of ``(entity_stem, narrative, changed_files)`` tuples.
    """
    rubric = _KIND_RUBRIC.get(kind, _KIND_RUBRIC["concept"])
    lines = [
        f"Page kind: {kind}",
        rubric,
        "",
        f"Curated page title: {page_title}",
        "",
        "Curated page body:",
        page_body.strip(),
        "",
        "Referenced entities that changed:",
    ]
    for stem, narrative, changed_files in entities:
        files = ", ".join(changed_files) if changed_files else "(no specific files identified)"
        lines += [
            "",
            f"### entity: {stem}",
            f"Changed files: {files}",
            "Current narrative:",
            narrative.strip(),
        ]
    lines += ["", "Is the page stale relative to these narratives? Reply with the JSON verdict."]
    return DRIFT_PROPAGATOR_SYSTEM, "\n".join(lines)


def parse_drift_propagator_verdict(text: str) -> dict:
    """Parse a ``{stale, findings[]}`` verdict. Fails SAFE to not-stale.

    Any unparseable / malformed reply yields ``{"stale": False, "findings": []}``.
    A finding survives only with a non-empty ``entity_stem`` (the origin needs
    attribution); when ``stale`` is true but no finding survives, the verdict
    collapses to not-stale.
    """
    raw = _FENCE_RE.sub("", (text or "").strip())
    match = _OBJ_RE.search(raw)
    if match is None:
        return {"stale": False, "findings": []}
    try:
        obj = json.loads(match.group(0))
    except (ValueError, TypeError):
        return {"stale": False, "findings": []}
    if not bool(obj.get("stale", False)):
        return {"stale": False, "findings": []}
    findings: list[dict] = []
    for f in obj.get("findings", []) or []:
        if not isinstance(f, dict):
            continue
        stem = str(f.get("entity_stem", "")).strip()
        if not stem:
            continue
        findings.append(
            {
                "entity_stem": stem,
                "stale_claim": str(f.get("stale_claim", "")),
                "rationale": str(f.get("rationale", "")),
            }
        )
    if not findings:
        return {"stale": False, "findings": []}
    return {"stale": True, "findings": findings}
