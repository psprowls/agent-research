#!/usr/bin/env python3
"""Verify M001/S04 initialized GSD readiness.

This is the final assembly verifier for M001 initialization. It composes the
S02/S03 document-contract verifiers and checks only S04 readiness concerns:
required artifacts, roadmap dependency order, requirement bucket ownership,
decision concepts, sampled source-path existence, and negation-aware rejection
of affirmative overclaims.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[5]
GSD = ROOT / ".gsd"
MILESTONE = GSD / "milestones" / "M001"
SLICES = MILESTONE / "slices"

PROJECT = GSD / "PROJECT.md"
REQUIREMENTS = GSD / "REQUIREMENTS.md"
DECISIONS = GSD / "DECISIONS.md"
CONTEXT = MILESTONE / "M001-CONTEXT.md"
ROADMAP = MILESTONE / "M001-ROADMAP.md"
S02_VERIFIER = SLICES / "S02" / "verify_s02_context.py"
S03_VERIFIER = SLICES / "S03" / "verify_s03_requirements.py"

REQUIRED_ARTIFACTS = [PROJECT, REQUIREMENTS, DECISIONS, CONTEXT, ROADMAP]
REQUIRED_SUMMARIES = [
    SLICES / "S01" / "S01-SUMMARY.md",
    SLICES / "S02" / "S02-SUMMARY.md",
    SLICES / "S03" / "S03-SUMMARY.md",
]
SAMPLED_SOURCE_PATHS = [
    ROOT / ".planning" / "PROJECT.md",
    ROOT / ".planning" / "ROADMAP.md",
    ROOT / ".planning" / "MILESTONES.md",
    ROOT / ".planning" / "milestones" / "v1.11-ROADMAP.md",
    ROOT / ".planning" / "CONTINUE-sweep-harness-fixes-3.md",
    ROOT / ".planning" / "deferred-items.md",
    ROOT / "pyproject.toml",
    ROOT / "agents" / "graph-wiki-agent" / "pyproject.toml",
]


@dataclass(frozen=True)
class Requirement:
    id: str
    section: str
    body: str

    def field(self, label: str) -> str:
        match = re.search(rf"^- {re.escape(label)}: (.*)$", self.body, flags=re.MULTILINE)
        return match.group(1).strip() if match else ""


def fail(message: str) -> None:
    raise AssertionError(message)


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_non_empty(path: Path) -> str:
    if not path.exists():
        fail(f"required artifact is missing: {display_path(path)}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        fail(f"required artifact is empty: {display_path(path)}")
    return text


def require_contains(text: str, needle: str) -> None:
    if needle not in text:
        fail(f"missing required text: {needle!r}")


def require_regex(text: str, pattern: str, description: str) -> None:
    if not re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
        fail(f"missing required pattern for {description}: {pattern}")


def forbid_regex(text: str, pattern: str, description: str) -> None:
    if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL):
        fail(f"prohibited affirmative overclaim present for {description}: {pattern}")


def verify_required_artifacts(paths: Iterable[Path] = REQUIRED_ARTIFACTS) -> None:
    for path in paths:
        read_non_empty(path)
    for path in REQUIRED_SUMMARIES:
        read_non_empty(path)


def run_dependency_verifiers(verifiers: Sequence[Path] = (S02_VERIFIER, S03_VERIFIER)) -> None:
    for verifier in verifiers:
        if not verifier.exists():
            fail(f"dependency verifier is missing: {verifier.relative_to(ROOT)}")
        result = subprocess.run(
            [sys.executable, str(verifier)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
            fail(
                "dependency verifier failed: "
                f"{display_path(verifier)} exited {result.returncode}"
                + (f"\n{output}" if output else "")
            )


def parse_requirements(text: str) -> dict[str, Requirement]:
    current_section = ""
    requirements: dict[str, Requirement] = {}
    current_id: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_body
        if current_id is None:
            return
        requirements[current_id] = Requirement(current_id, current_section, "\n".join(current_body).strip())
        current_id = None
        current_body = []

    for line in text.splitlines():
        section_match = re.match(r"^## (Active|Validated|Deferred|Out of Scope)$", line)
        if section_match:
            flush()
            current_section = section_match.group(1)
            continue

        req_match = re.match(r"^### (R\d{3}) — ", line)
        if req_match:
            flush()
            current_id = req_match.group(1)
            current_body = [line]
            continue

        if current_id is not None:
            current_body.append(line)

    flush()
    return requirements


def require_requirement(requirements: dict[str, Requirement], req_id: str) -> Requirement:
    req = requirements.get(req_id)
    if req is None:
        fail(f"missing requirement {req_id}")
    return req


def assert_owner(req: Requirement, primary: str) -> None:
    actual = req.field("Primary owning slice")
    if actual != primary:
        fail(f"{req.id} primary owner mismatch: expected {primary!r}, found {actual!r}")


def assert_no_active_owner(req: Requirement) -> None:
    primary = req.field("Primary owning slice").lower()
    supporting = req.field("Supporting slices").lower()
    if primary not in {"", "none"}:
        fail(f"{req.id} should not have an active M001 primary owner, found {primary!r}")
    if supporting not in {"", "none"}:
        fail(f"{req.id} should not have active supporting slices, found {supporting!r}")


def verify_requirements_readiness(text: str) -> None:
    requirements = parse_requirements(text)

    for req_id in ["R001", "R002", "R003", "R004"]:
        req = require_requirement(requirements, req_id)
        if req.section != "Validated" or req.field("Status") != "validated":
            fail(f"{req_id} must be validated before S04 readiness closeout")

    r005 = require_requirement(requirements, "R005")
    if r005.section not in {"Active", "Validated"} or r005.field("Status") not in {"active", "validated"}:
        fail("R005 must be active or validated and owned by M001/S04")
    assert_owner(r005, "M001/S04")

    for req_id in ["R006", "R007"]:
        req = require_requirement(requirements, req_id)
        if req.section != "Deferred" or req.field("Status") != "deferred":
            fail(f"{req_id} must remain deferred")
        assert_no_active_owner(req)

    for req_id in ["R008", "R009", "R010", "R011"]:
        req = require_requirement(requirements, req_id)
        if req.section != "Out of Scope" or req.field("Status") != "out-of-scope":
            fail(f"{req_id} must remain out of scope")
        assert_no_active_owner(req)


def verify_roadmap(text: str) -> None:
    slice_patterns = {
        "S01": r"- \[x\] \*\*S01: .*depends:\[\]",
        "S02": r"- \[x\] \*\*S02: .*depends:\[S01\]",
        "S03": r"- \[x\] \*\*S03: .*depends:\[S01,S02\]",
        "S04": r"- \[[ x]\] \*\*S04: .*depends:\[S01,S02,S03\]",
    }
    positions: dict[str, int] = {}
    for slice_id, pattern in slice_patterns.items():
        match = re.search(pattern, text)
        if not match:
            fail(f"roadmap missing dependency mapping for {slice_id}: {pattern}")
        positions[slice_id] = match.start()

    if [positions[key] for key in ["S01", "S02", "S03", "S04"]] != sorted(positions.values()):
        fail("roadmap slices are not listed in dependency order S01 -> S02 -> S03 -> S04")

    require_contains(text, "### S04 → Future milestones")
    require_regex(text, r"S04 → Future milestones.*Verified initialized GSD state", "S04 to future milestones boundary")
    require_contains(text, "Consumes:")
    require_regex(text, r"Consumes:\s*- PROJECT, REQUIREMENTS, M001-CONTEXT, ROADMAP, and DECISIONS artifacts", "S04 consumed artifacts")


def verify_decisions(text: str) -> None:
    for decision_id in ["D001", "D002", "D003"]:
        require_contains(text, decision_id)
    required_concepts = {
        "lean current truth": r"lean current-truth|current truth.*not.*full.*planning|not.*full.*planning.*conversion",
        "manual curation": r"manual curation.*migration tooling|manual curation.*migration script|manual curation",
        "preserve caveats deferred": r"preserve.*caveats.*deferred|deferred work.*active M001|without promoting.*active",
    }
    for description, pattern in required_concepts.items():
        require_regex(text, pattern, description)


def verify_sampled_sources() -> None:
    for path in SAMPLED_SOURCE_PATHS:
        if not path.exists():
            fail(f"sampled source path is missing: {display_path(path)}")
        if path.is_file() and not path.read_text(encoding="utf-8").strip():
            fail(f"sampled source path is empty: {display_path(path)}")


def verify_no_affirmative_overclaims(text: str) -> None:
    """Reject affirmative claims while allowing negated exclusions.

    Patterns intentionally require an affirmative subject/verb shape such as
    "M001 completed ..." so boundary phrases like "not wholesale conversion"
    and "does not run the sweep" remain valid.
    """

    prohibited_patterns = {
        "wholesale conversion completed": r"\bM001\s+(completed|performed|finished|does|did)\s+(a\s+)?wholesale\s+[^\n.]*\.planning[^\n.]*conversion",
        "exhaustive archive audit completed": r"\bM001\s+(completed|performed|finished|does|did)\s+(an\s+)?exhaustive\s+archive\s+audit",
        "active sweep rerun": r"\bM001\s+(ran|runs|executed|executes|completed|performs|performed)\s+[^\n.]*\bsweep\s+(rerun|re-run|run)\b",
        "authoritative winners selected": r"\bauthoritative\s+cost-frontier\s+winners?\s+(selected|chosen)\b",
        "legacy audit backfill completed": r"\blegacy\s+audit(?:/verification)?\s+backfill\s+(completed|done)\b",
        "historical audits backfilled": r"\b(historical|legacy)\s+milestone\s+audits\s+(were\s+)?backfilled\b",
        "phase 50 verified now": r"\bPhase\s+50\b[^\n.]*\bformally\s+verified\s+in\s+M001\b",
        "snapshot updated in M001": r"\bM001\s+(updated|updates|regenerated|regenerates)\s+[^\n.]*test_graph_query_output[^\n.]*snapshot",
    }
    for description, pattern in prohibited_patterns.items():
        forbid_regex(text, pattern, description)


def verify_readiness_texts(requirements_text: str, roadmap_text: str, decisions_text: str, assembled_text: str) -> None:
    verify_requirements_readiness(requirements_text)
    verify_roadmap(roadmap_text)
    verify_decisions(decisions_text)
    verify_no_affirmative_overclaims(assembled_text)


def expect_failure(action, expected_message_part: str) -> None:
    try:
        action()
    except AssertionError as exc:
        if expected_message_part not in str(exc):
            fail(
                "negative self-check failed for unexpected reason: "
                f"wanted {expected_message_part!r}, got {str(exc)!r}"
            )
        return
    fail(f"negative self-check unexpectedly passed: {expected_message_part}")


def run_negative_self_checks(requirements_text: str, roadmap_text: str, decisions_text: str, assembled_text: str) -> None:
    expect_failure(
        lambda: verify_required_artifacts([PROJECT, ROOT / ".gsd" / "MISSING-ARTIFACT.md"]),
        "required artifact is missing",
    )

    with tempfile.TemporaryDirectory() as tmp:
        failing = Path(tmp) / "failing_verifier.py"
        failing.write_text("import sys\nsys.stderr.write('synthetic dependency failure\\n')\nsys.exit(7)\n", encoding="utf-8")
        expect_failure(lambda: run_dependency_verifiers([failing]), "dependency verifier failed")

    expect_failure(
        lambda: verify_decisions(decisions_text.replace("Manual curation", "Hand-written notes").replace("manual curation", "hand-written notes")),
        "manual curation",
    )
    expect_failure(
        lambda: verify_roadmap(roadmap_text.replace("depends:[S01,S02,S03]", "depends:[S01,S02]", 1)),
        "roadmap missing dependency mapping for S04",
    )
    expect_failure(
        lambda: verify_no_affirmative_overclaims(assembled_text + "\nM001 completed a wholesale .planning conversion.\n"),
        "wholesale conversion completed",
    )


def main() -> None:
    verify_required_artifacts()
    verify_sampled_sources()
    run_dependency_verifiers()

    project_text = read_non_empty(PROJECT)
    requirements_text = read_non_empty(REQUIREMENTS)
    context_text = read_non_empty(CONTEXT)
    roadmap_text = read_non_empty(ROADMAP)
    decisions_text = read_non_empty(DECISIONS)
    assembled_text = "\n\n".join([project_text, requirements_text, context_text, roadmap_text, decisions_text])

    verify_readiness_texts(requirements_text, roadmap_text, decisions_text, assembled_text)
    run_negative_self_checks(requirements_text, roadmap_text, decisions_text, assembled_text)

    print("S04 readiness verifier passed: initialized GSD artifacts are coherent and traceable")


if __name__ == "__main__":
    main()
