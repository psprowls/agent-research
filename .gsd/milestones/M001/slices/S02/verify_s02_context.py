#!/usr/bin/env python3
"""Verify S02 context curation and archive-boundary claims.

This is a document-contract verifier for M001/S02. It asserts that the
curated M001 context preserves required legacy caveats with source references,
while rejecting common overclaims that would incorrectly promote archived or
deferred work into active M001 scope.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
CONTEXT = ROOT / ".gsd" / "milestones" / "M001" / "M001-CONTEXT.md"


def fail(message: str) -> None:
    raise AssertionError(message)


def require_contains(text: str, needle: str) -> None:
    if needle not in text:
        fail(f"missing required text: {needle!r}")


def require_regex(text: str, pattern: str, description: str) -> None:
    if not re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
        fail(f"missing required pattern for {description}: {pattern}")


def forbid_regex(text: str, pattern: str, description: str) -> None:
    if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
        fail(f"prohibited overclaim present for {description}: {pattern}")


def main() -> None:
    text = CONTEXT.read_text(encoding="utf-8")

    # Required section and source references.
    for needle in [
        "## Preserved Legacy High Notes and Caveats",
        "### Shipped Trajectory High Notes",
        "### Deferred Cost-Frontier Sweep Handoff",
        "### Stale Snapshot Caveat",
        "### Historical Process-Debt Caveats",
        "### Archive and Active-Scope Boundary Rules",
        ".planning/MILESTONES.md",
        ".planning/milestones/v1.6-ROADMAP.md",
        ".planning/milestones/v1.11-ROADMAP.md",
        ".planning/CONTINUE-sweep-harness-fixes-3.md",
        ".planning/deferred-items.md",
        ".planning/PROJECT.md",
        "agents/graph-wiki-agent/tests/unit/test_commands_graph.py::test_graph_query_output",
    ]:
        require_contains(text, needle)

    # Required caveat facts and labels.
    required_patterns = {
        "selective archive boundary": r"selective, non-exhaustive.*not a wholesale archive import",
        "archive reference only": r"\.planning/`? remains (a )?backed-up archive/reference",
        "round 3 supersedes round 2": r"supersedes `?CONTINUE-sweep-harness-fixes-2\.md`?",
        "fixes B-F verified/committed": r"Fixes B through F were committed and mechanically verified",
        "$3.46 non-authoritative run": r"\$3\.46.*not authoritative",
        "stale $7.02 sweep diagnostics": r"planning/sweep/\*\.md.*planning/sweep/INDEX\.md.*stale `?\$7\.02`? diagnostics",
        "future sweep order": r"debug answer degradation.*clean full re-run.*human.*select per-role winners",
        "snapshot dev_dependencies caveat": r"dev_dependencies: \[\].*snapshot",
        "snapshot update not M001": r"M001 records this caveat only and does not update product snapshots",
        "skipped formal audits": r"Formal milestone audits were skipped for v1\.6, v1\.8, v1\.9, and v1\.10",
        "phase 50 missing verification": r"Phase 50.*formal verification was missing",
        "security reviews skipped except phase 53": r"security reviews were skipped.*Phase 53 did produce a security audit",
        "nyquist overdue": r"Nyquist.*retro-validation decision is overdue",
        "deferred graph/wiki backlog": r"Scanner pipeline restructure.*dependency-family.*open ontology questions.*deferred",
        "no active sweep execution": r"M001 does not debug the harness, spend Bedrock budget, rerun the sweep, or choose winners",
        "future current-source verification": r"future milestone.*verify the claim against current source",
    }
    for description, pattern in required_patterns.items():
        require_regex(text, pattern, description)

    # Prohibited affirmative overclaims. These are intentionally specific so
    # that honest negated boundary language remains allowed.
    prohibited_patterns = {
        "wholesale conversion completed": r"M001 (completed|performed|finished) (a )?wholesale .*planning.*conversion",
        "exhaustive archive audit completed": r"M001 (completed|performed|finished) (an )?exhaustive archive audit",
        "authoritative sweep winner selected": r"(authoritative|final) cost-frontier (winner|winners) (selected|chosen)",
        "active phase 60 execution": r"M001 (executes|executed|runs|ran|resumes|resumed) Phase 60",
        "active sweep rerun": r"M001 (executes|executed|runs|ran|completed) .*sweep (re-)?run",
        "snapshot updated in M001": r"M001 (updates|updated|regenerates|regenerated) .*test_graph_query_output.*snapshot",
        "historical audits backfilled": r"(historical|legacy) milestone audits (were )?(backfilled|completed)",
        "security review backfill completed": r"security review backfill (completed|done)",
        "phase 50 verified now": r"Phase 50 .*formally verified in M001",
    }
    for description, pattern in prohibited_patterns.items():
        forbid_regex(text, pattern, description)

    print(f"S02 context verifier passed: {CONTEXT}")


if __name__ == "__main__":
    main()
